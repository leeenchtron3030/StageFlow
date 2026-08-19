import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const commandPaths = new Set([
  "sessions/start",
  "sessions/end-presentation",
  "sessions/process-transcription",
  "sessions/package-ready",
  "moments/mark",
]);
const workspacePath = /^sessions\/[0-9a-f-]{36}\/workspace$/i;
const maximumCommandBytes = 32 * 1024;
const maximumResponseBytes = 12 * 1024 * 1024;

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

async function proxy(
  request: NextRequest,
  segments: string[],
  method: "GET" | "POST",
): Promise<Response> {
  const path = segments.join("/");
  if (
    (method === "GET" && !workspacePath.test(path)) ||
    (method === "POST" && !commandPaths.has(path))
  ) {
    return Response.json(
      { detail: "demo_proxy_path_not_allowed" },
      { status: 404, headers: noStoreHeaders() },
    );
  }
  if (method === "POST" && !isSameOriginCommand(request)) {
    return Response.json(
      { detail: "demo_command_origin_not_allowed" },
      { status: 403, headers: noStoreHeaders() },
    );
  }

  let body: string | undefined;
  if (method === "POST") {
    const declaredLength = Number(request.headers.get("content-length") ?? "0");
    if (declaredLength > maximumCommandBytes) {
      return Response.json(
        { detail: "demo_command_too_large" },
        { status: 413, headers: noStoreHeaders() },
      );
    }
    body = await request.text();
    if (new TextEncoder().encode(body).byteLength > maximumCommandBytes) {
      return Response.json(
        { detail: "demo_command_too_large" },
        { status: 413, headers: noStoreHeaders() },
      );
    }
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
