import { createHash, timingSafeEqual } from "node:crypto";
import type { NextRequest } from "next/server";

import { demoLaunchContextHeader } from "../../../../../src/experience/demo-launch-context.ts";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const stageflowApiSecretHeader = "x-stageflow-api-secret";

const commandPaths = new Set([
  "sessions/start",
  "sessions/end-presentation",
  "sessions/process-transcription",
  "sessions/package-ready",
  "sessions/approve-package",
  "moments/mark",
]);
const programRefreshPaths = new Set(["program/refresh"]);
const workspacePath = /^sessions\/[0-9a-f-]{36}\/workspace$/i;
const maximumCommandBytes = 32 * 1024;
const maximumResponseBytes = 12 * 1024 * 1024;
const maximumAttributionValueLength = 128;
const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function backendBase(): URL {
  const configured =
    process.env.STAGEFLOW_DEMO_API_BASE_URL ??
    "http://127.0.0.1:8000/api/v1/demo";
  const url = new URL(configured.endsWith("/") ? configured : `${configured}/`);
  const loopback =
    url.hostname === "127.0.0.1" ||
    url.hostname === "localhost" ||
    url.hostname === "[::1]";
  if (url.protocol !== "http:" || !loopback || url.username || url.password) {
    throw new Error("demo_backend_must_be_loopback_http");
  }
  return url;
}

function noStoreHeaders(contentType = "application/json"): Headers {
  return new Headers({
    "Cache-Control": "no-store, max-age=0",
    "Content-Type": contentType,
    "X-Content-Type-Options": "nosniff",
    Pragma: "no-cache",
  });
}

function isSameOriginCommand(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  const fetchSite = request.headers.get("sec-fetch-site");
  return (
    (origin === null || origin === request.nextUrl.origin) &&
    fetchSite !== "cross-site"
  );
}

function currentApiSecret(): string | undefined {
  const value = process.env.STAGEFLOW_API_SHARED_SECRET;
  return value && value.length >= 32 ? value : undefined;
}


function currentLaunchContext(): string | undefined {
  const value = process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT;
  return value && value.length >= 32 ? value : undefined;
}

function launchContextFingerprint(value: string | undefined): string {
  return value
    ? createHash("sha256").update(value, "utf8").digest("hex").slice(0, 16)
    : "unavailable";
}

function launchContextMatches(presented: string | null): boolean {
  const current = currentLaunchContext();
  if (!current || !presented) return false;
  const expectedBytes = Buffer.from(current, "utf8");
  const presentedBytes = Buffer.from(presented, "utf8");
  return (
    expectedBytes.byteLength === presentedBytes.byteLength &&
    timingSafeEqual(expectedBytes, presentedBytes)
  );
}

function boundedClientAddress(request: NextRequest): string {
  const forwarded = request.headers.get("x-forwarded-for")?.split(",", 1)[0]?.trim();
  const value = forwarded || request.headers.get("x-real-ip")?.trim() || "unavailable";
  return value.slice(0, maximumAttributionValueLength);
}

function requestIdentity(body: string | undefined): {
  correlation_id: string | null;
  operation_id: string | null;
} {
  if (!body) return { correlation_id: null, operation_id: null };
  try {
    const payload = JSON.parse(body) as unknown;
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      return { correlation_id: null, operation_id: null };
    }
    const values = payload as Record<string, unknown>;
    const operationId = values.operation_id;
    const correlationId = values.correlation_id;
    return {
      operation_id:
        typeof operationId === "string" && uuidPattern.test(operationId)
          ? operationId
          : null,
      correlation_id:
        typeof correlationId === "string" && uuidPattern.test(correlationId)
          ? correlationId
          : null,
    };
  } catch {
    return { correlation_id: null, operation_id: null };
  }
}

function recordAuthorityRequest(
  request: NextRequest,
  path: string,
  body: string | undefined,
  launchContextValid: boolean,
): void {
  const identity = requestIdentity(body);
  console.info(
    "stageflow_demo_authority_request=" +
      JSON.stringify({
        timestamp: new Date().toISOString(),
        command: path,
        path: "/api/stageflow/demo/" + path,
        launch_context_fingerprint: launchContextFingerprint(currentLaunchContext()),
        operation_id: identity.operation_id,
        correlation_id: identity.correlation_id,
        producer_proxy_client_address: boundedClientAddress(request),
        launch_context_valid: launchContextValid,
      }),
  );
}

function recordProgramRefreshRequest(
  request: NextRequest,
  path: string,
  launchContextValid: boolean,
): void {
  console.info(
    "stageflow_demo_program_refresh_request=" +
      JSON.stringify({
        timestamp: new Date().toISOString(),
        path: "/api/stageflow/demo/" + path,
        launch_context_fingerprint: launchContextFingerprint(currentLaunchContext()),
        producer_proxy_client_address: boundedClientAddress(request),
        launch_context_valid: launchContextValid,
      }),
  );
}

function recordProtectedRequest(
  request: NextRequest,
  path: string,
  body: string | undefined,
  launchContextValid: boolean,
  authorityCommand: boolean,
): void {
  if (authorityCommand) {
    recordAuthorityRequest(request, path, body, launchContextValid);
  } else {
    recordProgramRefreshRequest(request, path, launchContextValid);
  }
}

async function proxy(
  request: NextRequest,
  segments: string[],
  method: "GET" | "POST",
): Promise<Response> {
  const path = segments.join("/");
  const authorityCommand = method === "POST" && commandPaths.has(path);
  const programRefresh = method === "POST" && programRefreshPaths.has(path);
  if (
    (method === "GET" && !workspacePath.test(path)) ||
    (method === "POST" && !authorityCommand && !programRefresh)
  ) {
    return Response.json(
      { detail: "demo_proxy_path_not_allowed" },
      { status: 404, headers: noStoreHeaders() },
    );
  }
  if (method === "POST" && !isSameOriginCommand(request)) {
    recordProtectedRequest(request, path, undefined, false, authorityCommand);
    return Response.json(
      { detail: "demo_command_origin_not_allowed" },
      { status: 403, headers: noStoreHeaders() },
    );
  }

  let body: string | undefined;
  if (method === "POST") {
    const declaredLength = Number(request.headers.get("content-length") ?? "0");
    if (declaredLength > maximumCommandBytes) {
      recordProtectedRequest(request, path, undefined, false, authorityCommand);
      return Response.json(
        { detail: "demo_command_too_large" },
        { status: 413, headers: noStoreHeaders() },
      );
    }
    body = await request.text();
    if (new TextEncoder().encode(body).byteLength > maximumCommandBytes) {
      recordProtectedRequest(request, path, undefined, false, authorityCommand);
      return Response.json(
        { detail: "demo_command_too_large" },
        { status: 413, headers: noStoreHeaders() },
      );
    }
    const launchContextValid = launchContextMatches(
      request.headers.get(demoLaunchContextHeader),
    );
    recordProtectedRequest(request, path, body, launchContextValid, authorityCommand);
    if (!launchContextValid) {
      return Response.json(
        { detail: "demo_launch_context_invalid" },
        { status: 403, headers: noStoreHeaders() },
      );
    }
  }

  const apiSecret = currentApiSecret();
  if (!apiSecret) {
    return Response.json(
      { detail: "demo_api_authentication_unavailable" },
      { status: 503, headers: noStoreHeaders() },
    );
  }

  try {
    const upstream = await fetch(new URL(path, backendBase()), {
      method,
      body,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(10_000),
      headers: {
        Accept: "application/json",
        [stageflowApiSecretHeader]: apiSecret,
        ...(method === "POST" ? { "Content-Type": "application/json" } : {}),
      },
    });
    const payload = await upstream.arrayBuffer();
    if (payload.byteLength > maximumResponseBytes) {
      return Response.json(
        { detail: "demo_response_exceeds_bound" },
        { status: 502, headers: noStoreHeaders() },
      );
    }
    return new Response(payload, {
      status: upstream.status,
      headers: noStoreHeaders(
        upstream.headers.get("content-type") ?? "application/json",
      ),
    });
  } catch {
    return Response.json(
      { detail: "demo_backend_unavailable" },
      { status: 503, headers: noStoreHeaders() },
    );
  }
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  return proxy(request, (await context.params).path, "GET");
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  return proxy(request, (await context.params).path, "POST");
}
