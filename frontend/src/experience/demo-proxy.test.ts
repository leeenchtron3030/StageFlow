import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { NextRequest } from "next/server.js";

import { GET, POST } from "../../app/api/stageflow/demo/[...path]/route.ts";
import { demoAuthorityHeaders, demoLaunchContextHeader } from "./demo-launch-context.ts";

const originalFetch = globalThis.fetch;
const originalBackend = process.env.STAGEFLOW_DEMO_API_BASE_URL;
const originalLaunchContext = process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT;
const originalConsoleInfo = console.info;
const launchContext = "current-launch-context-0123456789abcdef";
const sessionId = "10000000-0000-4000-8000-000000000001";

function context(...path: string[]) {
  return { params: Promise.resolve({ path }) };
}

afterEach(() => {
  globalThis.fetch = originalFetch;
  console.info = originalConsoleInfo;
  if (originalLaunchContext === undefined) {
    delete process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT;
  } else {
    process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT = originalLaunchContext;
  }
  if (originalBackend === undefined) {
    delete process.env.STAGEFLOW_DEMO_API_BASE_URL;
  } else {
    process.env.STAGEFLOW_DEMO_API_BASE_URL = originalBackend;
  }
});

test("GET proxies only an identity-scoped workspace over loopback with no-store", async () => {
  process.env.STAGEFLOW_DEMO_API_BASE_URL = "http://127.0.0.1:8123/api/v1/demo";
  let upstreamUrl: string | undefined;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    upstreamUrl = input.toString();
    return Response.json({
      session_id: sessionId,
      label: "Transcription Evidence",
      authority_notice: "Evidence only; not authoritative Session Transcript truth.",
      transcript_evidence: [{ segments: [{ text: "bounded evidence" }] }],
    });
  }) as typeof fetch;

  const response = await GET(
    new NextRequest(`http://stageflow.demo/api/stageflow/demo/sessions/${sessionId}/workspace`),
    context("sessions", sessionId, "workspace"),
  );

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "no-store, max-age=0");
  assert.equal(response.headers.get("pragma"), "no-cache");
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.equal(
    upstreamUrl,
    `http://127.0.0.1:8123/api/v1/demo/sessions/${sessionId}/workspace`,
  );
  assert.equal((await response.json()).label, "Transcription Evidence");
});

test("GET rejects non-workspace and malformed identity paths", async () => {
  globalThis.fetch = (async () => {
    throw new Error("fetch must not run");
  }) as typeof fetch;

  const unrelated = await GET(
    new NextRequest(`http://stageflow.demo/api/stageflow/demo/sessions/${sessionId}/moments`),
    context("sessions", sessionId, "moments"),
  );
  const malformed = await GET(
    new NextRequest("http://stageflow.demo/api/stageflow/demo/sessions/not-a-uuid/workspace"),
    context("sessions", "not-a-uuid", "workspace"),
  );

  assert.equal(unrelated.status, 404);
  assert.equal(malformed.status, 404);
});

test("proxy refuses non-loopback upstream configuration", async () => {
  process.env.STAGEFLOW_DEMO_API_BASE_URL = "http://192.0.2.10/api/v1/demo";
  globalThis.fetch = (async () => {
    throw new Error("fetch must not run");
  }) as typeof fetch;

  const response = await GET(
    new NextRequest(`http://stageflow.demo/api/stageflow/demo/sessions/${sessionId}/workspace`),
    context("sessions", sessionId, "workspace"),
  );

  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { detail: "demo_backend_unavailable" });
});

test("POST rejects cross-site command relay before reading or forwarding a body", async () => {
  globalThis.fetch = (async () => {
    throw new Error("fetch must not run");
  }) as typeof fetch;

  const response = await POST(
    new NextRequest("http://stageflow.demo/api/stageflow/demo/sessions/start", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        origin: "http://untrusted.example",
        "sec-fetch-site": "cross-site",
      },
      body: "{not read}",
    }),
    context("sessions", "start"),
  );

  assert.equal(response.status, 403);
  assert.deepEqual(await response.json(), { detail: "demo_command_origin_not_allowed" });
});

test("POST forwards an explicit current-launch Start Session and records bounded attribution", async () => {
  process.env.STAGEFLOW_DEMO_API_BASE_URL = "http://127.0.0.1:8123/api/v1/demo";
  process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT = launchContext;
  const operationId = "20000000-0000-4000-8000-000000000001";
  const correlationId = "30000000-0000-4000-8000-000000000001";
  const logMessages: string[] = [];
  let upstreamRequest: { headers?: HeadersInit; url: string } | undefined;
  console.info = (message?: unknown) => logMessages.push(String(message));
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    upstreamRequest = { headers: init?.headers, url: input.toString() };
    return Response.json({ session_id: sessionId, authority: "human_session_start" });
  }) as typeof fetch;

  const response = await POST(
    new NextRequest("http://stageflow.demo/api/stageflow/demo/sessions/start", {
      method: "POST",
      headers: {
        ...demoAuthorityHeaders(launchContext),
        origin: "http://stageflow.demo",
        "sec-fetch-site": "same-origin",
        "x-forwarded-for": "10.0.0.51",
      },
      body: JSON.stringify({
        operation_id: operationId,
        correlation_id: correlationId,
        note: "request-body-must-not-be-logged",
      }),
    }),
    context("sessions", "start"),
  );

  assert.equal(response.status, 200);
  assert.equal(
    upstreamRequest?.url,
    "http://127.0.0.1:8123/api/v1/demo/sessions/start",
  );
  const upstreamHeaders = new Headers(upstreamRequest?.headers);
  assert.equal(upstreamHeaders.get(demoLaunchContextHeader), null);
  assert.equal(logMessages.length, 1);
  const attribution = JSON.parse(
    logMessages[0].slice("stageflow_demo_authority_request=".length),
  ) as Record<string, unknown>;
  assert.equal(attribution.command, "sessions/start");
  assert.equal(attribution.operation_id, operationId);
  assert.equal(attribution.correlation_id, correlationId);
  assert.equal(attribution.producer_proxy_client_address, "10.0.0.51");
  assert.equal(attribution.launch_context_valid, true);
  assert.match(String(attribution.launch_context_fingerprint), /^[0-9a-f]{16}$/);
  assert.doesNotMatch(logMessages[0], new RegExp(launchContext));
  assert.doesNotMatch(logMessages[0], /request-body-must-not-be-logged/);
});

test("POST fails closed for stale and absent launch contexts before forwarding", async (t) => {
  process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT = launchContext;

  for (const [name, presented] of [
    ["stale", "prior-launch-context-0123456789abcdef"],
    ["absent", undefined],
  ] as const) {
    await t.test(name, async () => {
      let forwarded = false;
      const logMessages: string[] = [];
      console.info = (message?: unknown) => logMessages.push(String(message));
      globalThis.fetch = (async () => {
        forwarded = true;
        throw new Error("fetch must not run");
      }) as typeof fetch;
      const headers: Record<string, string> = {
        "content-type": "application/json",
        origin: "http://stageflow.demo",
        "sec-fetch-site": "same-origin",
      };
      if (presented) headers[demoLaunchContextHeader] = presented;

      const response = await POST(
        new NextRequest("http://stageflow.demo/api/stageflow/demo/sessions/start", {
          method: "POST",
          headers,
          body: JSON.stringify({
            operation_id: "20000000-0000-4000-8000-000000000002",
          }),
        }),
        context("sessions", "start"),
      );

      assert.equal(response.status, 403);
      assert.deepEqual(await response.json(), { detail: "demo_launch_context_invalid" });
      assert.equal(forwarded, false);
      assert.equal(logMessages.length, 1);
      assert.match(logMessages[0], /"launch_context_valid":false/);
      assert.doesNotMatch(logMessages[0], new RegExp(launchContext));
      if (presented) assert.doesNotMatch(logMessages[0], new RegExp(presented));
    });
  }
});

test("authority header helper omits unavailable context and includes only the current value", () => {
  assert.deepEqual(demoAuthorityHeaders(undefined), {
    "Content-Type": "application/json",
  });
  assert.deepEqual(demoAuthorityHeaders(launchContext), {
    "Content-Type": "application/json",
    [demoLaunchContextHeader]: launchContext,
  });
});
