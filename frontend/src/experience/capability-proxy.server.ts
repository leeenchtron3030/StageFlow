import "server-only";
import { createHash, randomUUID, timingSafeEqual } from "node:crypto";
import { isIP } from "node:net";
import type { NextRequest } from "next/server";

import { demoLaunchContextHeader } from "./demo-launch-context.ts";

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
export const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function backendBase(capability: Capability): URL {
  const configured =
    process.env[`STAGEFLOW_${capability.toUpperCase().replaceAll("-", "_")}_API_BASE_URL`] ??
    `http://127.0.0.1:8000/api/v1/${capability}`;
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

export async function proxy(
  request: NextRequest,
  segments: string[],
  method: string,
  capability: Capability = "demo",
): Promise<Response> {
  if (capability === "demo" || method !== "POST") return proxyTransport(request, segments, method, capability);
  const audit = capabilityAudit(request, segments, method, capability);
  const response = await proxyTransport(request, segments, method, capability, audit);
  await audit.finish(response);
  return response;
}

async function proxyTransport(
  request: NextRequest, segments: string[], method: string, capability: Capability,
  audit?: ReturnType<typeof capabilityAudit>,
): Promise<Response> {
  const record = capability === "demo" ? recordProtectedRequest : () => undefined;
  const path = segments.join("/");
  const authorityCommand = method === "POST" && commandPaths.has(path);
  const programRefresh = method === "POST" && programRefreshPaths.has(path);
  if (capability === "demo" ? (
    (method === "GET" && !workspacePath.test(path)) ||
    (method === "POST" && !authorityCommand && !programRefresh)
  ) : !allowedRoute(capability, method, path)) {
    return Response.json(
      { detail: `${capability.replaceAll("-", "_")}_proxy_path_not_allowed` },
      { status: 404, headers: noStoreHeaders() },
    );
  }
  if ((method === "POST" || capability !== "demo") && !isSameOriginCommand(request)) {
    record(request, path, undefined, false, authorityCommand);
    return Response.json(
      { detail: `${capability.replaceAll("-", "_")}_command_origin_not_allowed` },
      { status: 403, headers: noStoreHeaders() },
    );
  }

  let body: string | undefined;
  if (method === "POST") {
    const declaredLength = Number(request.headers.get("content-length") ?? "0");
    if (declaredLength > maximumCommandBytes) {
      record(request, path, undefined, false, authorityCommand);
      return Response.json(
        { detail: `${capability.replaceAll("-", "_")}_command_too_large` },
        { status: 413, headers: noStoreHeaders() },
      );
    }
    try {
      body = capability === "demo" ? await request.text() : new TextDecoder().decode(await boundedBody(request, maximumCommandBytes));
    } catch (error) {
      if (capability === "demo") throw error;
      record(request, path, undefined, false, authorityCommand);
      return Response.json({ detail: `${capability.replaceAll("-", "_")}_command_too_large` }, { status: 413, headers: noStoreHeaders() });
    }
    if (new TextEncoder().encode(body).byteLength > maximumCommandBytes) {
      record(request, path, undefined, false, authorityCommand);
      return Response.json(
        { detail: `${capability.replaceAll("-", "_")}_command_too_large` },
        { status: 413, headers: noStoreHeaders() },
      );
    }
    audit?.body(body);
    const launchContextValid = launchContextMatches(
      request.headers.get(demoLaunchContextHeader),
    );
    record(request, path, body, launchContextValid, authorityCommand);
    if (!launchContextValid) {
      return Response.json(
        { detail: `${capability.replaceAll("-", "_")}_launch_context_invalid` },
        { status: 403, headers: noStoreHeaders() },
      );
    }
  }

  if (method === "POST" && capability !== "demo") {
    const actor = process.env.STAGEFLOW_DEMO_OPERATOR_ID;
    if (!actor || !uuidPattern.test(actor)) {
      return Response.json({ detail: "operator_identity_unavailable" }, { status: 503, headers: noStoreHeaders() });
    }
    try {
      const command: unknown = JSON.parse(body!);
      if (!command || typeof command !== "object" || Array.isArray(command)) throw new Error();
      body = JSON.stringify({ ...command, actor_id: actor });
      if (new TextEncoder().encode(body).byteLength > maximumCommandBytes) {
        return Response.json({ detail: `${capability.replaceAll("-", "_")}_command_too_large` }, { status: 413, headers: noStoreHeaders() });
      }
    } catch {
      return Response.json({ detail: "command_json_invalid" }, { status: 422, headers: noStoreHeaders() });
    }
  }

  const apiSecret = currentApiSecret();
  if (!apiSecret) {
    return Response.json(
      { detail: `${capability.replaceAll("-", "_")}_api_authentication_unavailable` },
      { status: 503, headers: noStoreHeaders() },
    );
  }

  try {
    audit?.received("accepted");
    const upstream = await fetch(upstreamUrl(capability, path, request.nextUrl.search), {
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
    if (audit) audit.backendStatus = upstream.status;
    let payload: ArrayBuffer;
    try {
      payload = capability === "demo" ? await upstream.arrayBuffer() : await boundedBody(upstream, maximumResponseBytes);
    } catch (error) {
      if (capability === "demo") throw error;
      return Response.json({ detail: `${capability.replaceAll("-", "_")}_response_exceeds_bound` }, { status: 502, headers: noStoreHeaders() });
    }
    if (payload.byteLength > maximumResponseBytes) {
      return Response.json(
        { detail: `${capability.replaceAll("-", "_")}_response_exceeds_bound` },
        { status: 502, headers: noStoreHeaders() },
      );
    }
    // Never relay an accidentally echoed credential or upstream response headers.
    if (capability !== "demo" && containsSecret(payload, apiSecret)) {
      return Response.json({ detail: "upstream_response_refused" }, { status: 502, headers: noStoreHeaders() });
    }
    return new Response(payload, {
      status: upstream.status,
      headers: noStoreHeaders(
        capability === "demo" ? upstream.headers.get("content-type") ?? "application/json" : "application/json",
      ),
    });
  } catch {
    return Response.json(
      { detail: `${capability.replaceAll("-", "_")}_backend_unavailable` },
      { status: 503, headers: noStoreHeaders() },
    );
  }
}

/** Explicit field selection: no bodies, free text, raw paths, or exception messages. */
function capabilityAudit(request: NextRequest, segments: string[], method: string, capability: Exclude<Capability, "demo">) {
  const started = performance.now();
  const requestId = randomUUID();
  const secret = currentApiSecret();
  const safe = (value: string) => !secret || !value.includes(secret);
  const ids = (value: unknown, fields: readonly string[]) => {
    const object = value && typeof value === "object" ? value as Record<string, unknown> : {};
    return Object.fromEntries(fields.flatMap((field) => {
      const id = object[field];
      return typeof id === "string" && uuidPattern.test(id) && safe(id) ? [[field, id]] : [];
    }));
  };
  const resourceFields = ["event_id", "stage_id", "session_id", "asset_id", "packaging_asset_id", "template_id", "assembly_revision_id", "revision_id", "moment_id", "phrase_list_id"];
  const pathFields: Record<string, string> = { events: "event_id", sessions: "session_id", assets: "asset_id", "packaging-assets": "packaging_asset_id", moments: "candidate_moment_id" };
  const matched = capabilityRoutes[capability].find((entry) => entry.method === method && entry.path.test(segments.join("/")));
  const resources: Record<string, string | string[]> = {};
  // Only extract resources from matched routes, never from an arbitrary refused path.
  if (matched) segments.forEach((segment, index) => {
    const field = pathFields[segments[index - 1]];
    if (field && uuidPattern.test(segment) && safe(segment)) resources[field] = segment;
  });
  let identity: Record<string, string> = {};
  let reasonPresent = false, reasonLength = 0, received = false;
  const address = boundedClientAddress(request);
  const write = (fields: Record<string, unknown>) => console.info("stageflow_capability_command=" + JSON.stringify({
    timestamp: new Date().toISOString(), request_id: requestId, ...fields,
  }));
  const audit = {
    backendStatus: null as number | null,
    body(body: string) {
      try {
        const value = JSON.parse(body);
        identity = ids(value, ["command_id", "operation_id"]);
        // Route scope wins over any contradictory browser-supplied body scope.
        for (const [key, id] of Object.entries(ids(value, resourceFields))) resources[key] ??= id;
        if (value?.content?.kind === "completed_media_asset") Object.assign(resources, ids(value.content, ["asset_id"]));
        if (Array.isArray(value?.explicit)) {
          resources.packaging_revision_ids = value.explicit.flatMap((binding: unknown) => Object.values(ids(binding, ["packaging_revision_id"])));
        }
        reasonPresent = typeof value?.reason === "string";
        reasonLength = reasonPresent ? value.reason.length : 0;
      } catch { /* Malformed commands have no safely extracted identity. */ }
    },
    received(disposition: string) {
      if (received) return;
      received = true;
      write({ phase: "received", capability, method, route_pattern: matched?.path.source ?? null,
        resource_ids: resources, command_id: identity.command_id ?? null, operation_id: identity.operation_id ?? null,
        launch_context_fingerprint: launchContextFingerprint(currentLaunchContext()),
        launch_context_valid: launchContextMatches(request.headers.get(demoLaunchContextHeader)),
        producer_proxy_client_address: isIP(address) && safe(address) ? address : "unavailable",
        disposition, reason_present: reasonPresent, reason_length: reasonLength });
    },
    async finish(response: Response) {
      let value: unknown;
      try { value = await response.clone().json(); } catch { /* Non-JSON upstream response. */ }
      const detail = value && typeof value === "object" && "detail" in value ? value.detail : undefined;
      const code = typeof detail === "string" && /^[a-z][a-z0-9_]{0,95}$/.test(detail) && safe(detail) ? detail : `http_${response.status}`;
      // Existing operator/JSON refusals fit not_allowed; preserve their bounded result code.
      const refusal = code.endsWith("_origin_not_allowed") ? "cross_site"
        : code.endsWith("_launch_context_invalid") ? "launch_context"
        : code.endsWith("_command_too_large") ? "too_large"
        : code.endsWith("_api_authentication_unavailable") ? "secret_unavailable" : "not_allowed";
      audit.received(refusal);
      const object = value && typeof value === "object" ? value as Record<string, unknown> : {};
      write({ phase: "result", backend_status: audit.backendStatus, status: response.status,
        outcome: response.ok ? "succeeded" : response.status >= 400 && response.status < 500 ? "rejected" : "failed",
        error_code: response.ok ? null : code, duration_ms: Math.max(0, Math.round(performance.now() - started)),
        ...ids(value, ["revision_id", "decision_id", "operation_id", "template_id", "packaging_asset_id", "override_id", "review_id", "clip_id", "run_id", "output_id", "phrase_list_id"]),
        ...ids(object.decision, ["review_decision_id", "operation_id"]), ...ids(object.clip, ["clip_id"]),
        ...(Array.isArray(object.candidate_ids) ? { candidate_ids: object.candidate_ids.filter((id) => typeof id === "string" && uuidPattern.test(id) && safe(id)) } : {}),
      });
    },
  };
  return audit;
}

export type Capability = "demo" | "assembly" | "rendering" | "editorial" | "media-timing";
const uuid = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}";
const route = (method: string, path: string) => ({ method, path: new RegExp(`^${path}$`) });
export const capabilityRoutes = {
  assembly: [
    route("GET", `events/${uuid}/templates`),
    route("POST", "templates"),
    route("GET", `events/${uuid}/sessions/${uuid}/revisions`),
    route("POST", `sessions/${uuid}/revisions`),
    route("POST", `sessions/${uuid}/approvals`),
    route("GET", `events/${uuid}/sessions/${uuid}/metadata-overrides`),
    route("POST", `sessions/${uuid}/metadata-overrides`),
    route("GET", `events/${uuid}/packaging-assets`),
    route("GET", `events/${uuid}/packaging-assets/${uuid}/revisions`),
    route("POST", "packaging-assets"),
    route("POST", `packaging-assets/${uuid}/revisions`),
    route("POST", `packaging-assets/${uuid}/approvals`),
  ],
  rendering: [route("GET", "operations"), route("GET", "outputs"), route("POST", "requests")],
  editorial: [
    route("POST", `moments/${uuid}/reviews`),
    route("GET", `sessions/${uuid}/moments`),
    route("GET", `events/${uuid}/review-queue`),
    route("GET", `events/${uuid}/phrase-lists`),
    route("POST", `events/${uuid}/phrase-lists`),
    route("POST", `sessions/${uuid}/derivations`),
  ],
  "media-timing": [route("GET", `events/${uuid}/operations`), route("GET", `assets/${uuid}/latest`)],
} as const;

export function allowedRoute(capability: Exclude<Capability, "demo">, method: string, path: string): boolean {
  return capabilityRoutes[capability].some((entry) => entry.method === method && entry.path.test(path));
}

function upstreamUrl(capability: Capability, path: string, search: string): URL {
  const url = new URL(path, backendBase(capability));
  // Demo historically ignores queries. Other reads need backend pagination and scope.
  if (capability !== "demo") url.search = search;
  return url;
}

/** Server Components use the same read allowlist and transport, without a browser command. */
export async function readCapability(capability: Exclude<Capability, "demo">, path: string): Promise<unknown> {
  const { NextRequest } = await import("next/server.js");
  const url = new URL(`/api/stageflow/${capability}/${path}`, "http://localhost");
  const response = await proxy(new NextRequest(url), url.pathname.split("/").slice(4), "GET", capability);
  if (!response.ok) throw new Error("outputs_read_unavailable");
  return response.json();
}

async function boundedBody(source: Request | Response, limit: number): Promise<ArrayBuffer> {
  if (Number(source.headers.get("content-length") ?? 0) > limit) {
    await source.body?.cancel();
    throw new Error("byte_limit");
  }
  const reader = source.body?.getReader();
  if (!reader) return new ArrayBuffer(0);
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      size += next.value.byteLength;
      if (size > limit) {
        await reader.cancel();
        throw new Error("byte_limit");
      }
      chunks.push(next.value);
    }
  } finally {
    reader.releaseLock();
  }
  const buffer = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { buffer.set(chunk, offset); offset += chunk.byteLength; }
  return buffer.buffer;
}

function containsSecret(payload: ArrayBuffer, secret: string): boolean {
  const text = new TextDecoder().decode(payload);
  if (text.includes(secret)) return true;
  try { return JSON.stringify(JSON.parse(text)).includes(secret); }
  catch { return false; }
}
