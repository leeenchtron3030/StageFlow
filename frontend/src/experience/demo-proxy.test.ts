import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { NextRequest } from "next/server.js";

import { GET, POST } from "../../app/api/stageflow/demo/[...path]/route.ts";

const originalFetch = globalThis.fetch;
const originalBackend = process.env.STAGEFLOW_DEMO_API_BASE_URL;
const sessionId = "10000000-0000-4000-8000-000000000001";

function context(...path: string[]) {
  return { params: Promise.resolve({ path }) };
}

afterEach(() => {
  globalThis.fetch = originalFetch;
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
