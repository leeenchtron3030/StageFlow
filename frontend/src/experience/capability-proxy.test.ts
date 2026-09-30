import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import { NextRequest } from "next/server.js";
import * as assembly from "../../app/api/stageflow/assembly/[...path]/route.ts";
import * as rendering from "../../app/api/stageflow/rendering/[...path]/route.ts";
import * as editorial from "../../app/api/stageflow/editorial/[...path]/route.ts";
import * as suggestions from "../../app/api/stageflow/session-suggestions/[...path]/route.ts";
import * as timing from "../../app/api/stageflow/media-timing/[...path]/route.ts";
import * as demo from "../../app/api/stageflow/demo/[...path]/route.ts";
import { readCapability } from "./capability-proxy.server.ts";
import { demoLaunchContextHeader } from "./demo-launch-context.ts";

const id = "10000000-0000-4000-8000-000000000001";
const secret = "test-only-capability-secret-0123456789abcdef";
const launch = "test-only-capability-launch-0123456789abcdef";
const originalFetch = globalThis.fetch;
const envKeys = ["STAGEFLOW_API_SHARED_SECRET", "STAGEFLOW_DEMO_LAUNCH_CONTEXT", "STAGEFLOW_DEMO_OPERATOR_ID", ...["ASSEMBLY", "RENDERING", "EDITORIAL", "MEDIA_TIMING", "SESSION_SUGGESTIONS"].map((name) => `STAGEFLOW_${name}_API_BASE_URL`)];
const originalEnv = Object.fromEntries(envKeys.map((key) => [key, process.env[key]]));
beforeEach(() => { process.env.STAGEFLOW_API_SHARED_SECRET = secret; process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT = launch; process.env.STAGEFLOW_DEMO_OPERATOR_ID = id; });
afterEach(() => {
  globalThis.fetch = originalFetch;
  for (const key of envKeys) { const value = originalEnv[key]; if (value === undefined) delete process.env[key]; else process.env[key] = value; }
});
const cases = [
  { name: "session-suggestions", handlers: suggestions, reads: [`events/${id}/boundary-cue-catalog`, `events/${id}/boundary-cues`, `events/${id}/boundary-cues/history`], commands: [`events/${id}/boundary-cues`] },
  { name: "assembly", handlers: assembly, reads: [`events/${id}/templates`, `events/${id}/sessions/${id}/revisions`, `events/${id}/sessions/${id}/metadata-overrides`, `events/${id}/packaging-assets`, `events/${id}/packaging-assets/${id}/revisions`], commands: ["templates", `sessions/${id}/revisions`, `sessions/${id}/approvals`, `sessions/${id}/metadata-overrides`, "packaging-assets", `packaging-assets/${id}/revisions`, `packaging-assets/${id}/approvals`] },
  { name: "rendering", handlers: rendering, reads: ["operations", "outputs"], commands: ["requests"] },
  { name: "editorial", handlers: editorial, reads: [`sessions/${id}/moments`, `events/${id}/review-queue`, `events/${id}/phrase-lists`], commands: [`moments/${id}/reviews`, `events/${id}/phrase-lists`, `sessions/${id}/derivations`] },
  { name: "media-timing", handlers: timing, reads: [`events/${id}/operations`, `assets/${id}/latest`], commands: [] },
] as const;
const methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] as const;
test("session suggestions refuses run, confirm, reject, suggestion and schedule-offset routes", async () => {
  globalThis.fetch = async () => { assert.fail("must not forward"); };
  for (const suffix of [`stages/${id}/runs`, `stages/${id}/schedule-offset`, `stages/${id}/schedule-offset/history`, `stages/${id}/suggestions`, `suggestions/${id}`, `suggestions/${id}/confirm`, `suggestions/${id}/reject`]) {
    const path = `events/${id}/${suffix}`;
    for (const method of methods) assert.equal((await suggestions[method](request("session-suggestions", path, method), context(path))).status, 404);
  }
});
function request(capability: string, path: string, method: string, headers: Record<string, string> = {}, body = "{}") {
  return new NextRequest(`http://producer.local/api/stageflow/${capability}/${path}`, { method, headers: { origin: "http://producer.local", "sec-fetch-site": "same-origin", [demoLaunchContextHeader]: launch, ...headers }, ...(method === "POST" ? { body } : {}) });
}
function context(path: string) { return { params: Promise.resolve({ path: path.split("?")[0].split("/") }) }; }
for (const entry of cases) {
  test(`${entry.name}: exact method/path matrix; UUID, traversal and adjacent routes refused`, async () => {
    let calls = 0;
    globalThis.fetch = async () => { calls++; return Response.json({ accepted: true }); };
    const paths: string[] = [...entry.reads, ...entry.commands, "unknown", "moments/mark", ...entry.reads.map((path) => path.toUpperCase()), `events/${id}/requests`, ...entry.reads.map((path) => `${path}/extra`), ...entry.reads.filter((path) => path.includes(id)).flatMap((path) => [path.replace(id, "not-a-uuid"), path.replace(id, "------------------------------------"), path.replace(id, "00000000-0000-0000-0000-000000000000"), path.replace(id, "%2e%2e")])];
    for (const path of new Set(paths)) for (const method of methods) {
      const allowed = method === "GET" ? (entry.reads as readonly string[]).includes(path) : method === "POST" && (entry.commands as readonly string[]).includes(path);
      const before = calls;
      const result = await entry.handlers[method](request(entry.name, path, method), context(path));
      assert.equal(result.status, allowed ? 200 : 404, `${method} ${entry.name}/${path}`);
      assert.equal(calls - before, allowed ? 1 : 0);
      assert.equal(result.headers.get("cache-control"), "no-store, max-age=0");
    }
  });
  test(`${entry.name}: loopback-only, no redirects, server credential only, query scope retained`, async () => {
    const path = `${entry.reads[0]}?limit=7&after=${id}&event_id=${id}&session_id=${id}`;
    const key = `STAGEFLOW_${entry.name.toUpperCase().replaceAll("-", "_")}_API_BASE_URL`;
    process.env[key] = `http://127.0.0.1:8123/api/v1/${entry.name}`;
    globalThis.fetch = async (input, init) => {
      assert.equal(String(input), `http://127.0.0.1:8123/api/v1/${entry.name}/${path}`);
      assert.equal(init?.redirect, "error"); assert.equal(init?.cache, "no-store");
      const headers = new Headers(init?.headers);
      assert.equal(headers.get("x-stageflow-api-secret"), secret);
      assert.equal(headers.get(demoLaunchContextHeader), null);
      return Response.json({ value: "safe" }, { headers: { "x-stageflow-api-secret": secret, "set-cookie": `secret=${secret}` } });
    };
    const result = await entry.handlers.GET(request(entry.name, path, "GET"), context(path));
    assert.equal(result.status, 200); assert.doesNotMatch(await result.text(), new RegExp(secret));
    assert.equal(result.headers.get("x-stageflow-api-secret"), null); assert.equal(result.headers.get("set-cookie"), null);
    assert.equal(result.headers.get("pragma"), "no-cache"); assert.equal(result.headers.get("x-content-type-options"), "nosniff");
    globalThis.fetch = async () => { assert.fail("must not forward"); };
    for (const base of ["https://localhost", "http://192.0.2.10", "http://localhost.evil.example", "http://user:password@localhost"]) {
      process.env[key] = `${base}/api/v1/${entry.name}`;
      assert.equal((await entry.handlers.GET(request(entry.name, path, "GET"), context(path))).status, 503);
    }
    delete process.env.STAGEFLOW_API_SHARED_SECRET;
    assert.equal((await entry.handlers.GET(request(entry.name, path, "GET"), context(path))).status, 503);
  });
  test(`${entry.name}: cross-site reads refused; responses capped and echoed secrets refused`, async () => {
    const path = entry.reads[0];
    globalThis.fetch = async () => { assert.fail("must not forward"); };
    for (const headers of [{ origin: "http://other.local" }, { "sec-fetch-site": "cross-site" }] as Record<string, string>[]) {
      assert.equal((await entry.handlers.GET(request(entry.name, path, "GET", headers), context(path))).status, 403);
    }
    globalThis.fetch = async () => new Response("x".repeat(12 * 1024 * 1024 + 1));
    assert.equal((await entry.handlers.GET(request(entry.name, path, "GET"), context(path))).status, 502);
    globalThis.fetch = async () => Response.json({ accidentally_echoed: secret });
    const response = await entry.handlers.GET(request(entry.name, path, "GET"), context(path));
    assert.equal(response.status, 502); assert.doesNotMatch(await response.text(), new RegExp(secret));
    globalThis.fetch = async () => new Response(JSON.stringify({ value: secret }).replaceAll("e", "\\u0065"));
    assert.equal((await entry.handlers.GET(request(entry.name, path, "GET"), context(path))).status, 502);
    let cancelled = false;
    globalThis.fetch = async () => new Response(new ReadableStream({
      pull(controller) { controller.enqueue(new Uint8Array(1024 * 1024)); },
      cancel() { cancelled = true; },
    }));
    assert.equal((await entry.handlers.GET(request(entry.name, path, "GET"), context(path))).status, 502);
    assert.equal(cancelled, true);
    globalThis.fetch = async () => Response.json({ safe: true }, { headers: { "content-type": secret } });
    const safe = await entry.handlers.GET(request(entry.name, path, "GET"), context(path));
    assert.equal(safe.headers.get("content-type"), "application/json");
  });
  for (const path of entry.commands) {
    test(`${entry.name} POST ${path}: origin, launch and command byte caps before forwarding`, async () => {
      globalThis.fetch = async () => { assert.fail("must not forward"); };
      for (const headers of [{ origin: "http://other.local" }, { "sec-fetch-site": "cross-site" }, { [demoLaunchContextHeader]: "stale" }, { [demoLaunchContextHeader]: "" }] as Record<string, string>[]) {
        assert.equal((await entry.handlers.POST(request(entry.name, path, "POST", headers), context(path))).status, 403);
      }
      for (const [headers, body] of [[{ "content-length": "32769" }, "{}"], [{}, "x".repeat(32769)], [{}, "\u00e9".repeat(16385)]] as const) {
        assert.equal((await entry.handlers.POST(request(entry.name, path, "POST", headers, body), context(path))).status, 413);
      }
      let cancelled = false;
      const stream = new ReadableStream({
        pull(controller) { controller.enqueue(new Uint8Array(16384)); },
        cancel() { cancelled = true; },
      });
      const streamed = new NextRequest(`http://producer.local/api/stageflow/${entry.name}/${path}`, {
        method: "POST", body: stream, duplex: "half", headers: { origin: "http://producer.local", [demoLaunchContextHeader]: launch },
      } as ConstructorParameters<typeof NextRequest>[1]);
      assert.equal((await entry.handlers.POST(streamed, context(path))).status, 413);
      assert.equal(cancelled, true);
      // Replacing a browser actor must not grow a forwarded body beyond the cap.
      const padded = JSON.stringify({ note: "x".repeat(32730) });
      assert.equal((await entry.handlers.POST(request(entry.name, path, "POST", {}, padded), context(path))).status, 413);
      let forwarded = false;
      globalThis.fetch = async (_input, init) => { forwarded = true; assert.equal(JSON.parse(String(init?.body)).actor_id, id); return Response.json({ accepted: true }); };
      assert.equal((await entry.handlers.POST(request(entry.name, path, "POST", {}, JSON.stringify({ actor_id: "browser-chosen", confirmed: "confirmed" })), context(path))).status, 200);
      assert.equal(forwarded, true);
      forwarded = false; delete process.env.STAGEFLOW_DEMO_OPERATOR_ID;
      assert.equal((await entry.handlers.POST(request(entry.name, path, "POST"), context(path))).status, 503);
      assert.equal(forwarded, false);
    });
  }
}
test("media timing has no command surface, including with stale launch context and oversized body", async () => {
  globalThis.fetch = async () => { assert.fail("must not forward"); };
  const path = `events/${id}/requests`;
  const response = await timing.POST(request("media-timing", path, "POST", { [demoLaunchContextHeader]: "stale" }, "x".repeat(32769)), context(path));
  assert.equal(response.status, 404);
});
test("server-side capability reads use the same allowlist and retain query parameters", async () => {
  globalThis.fetch = async (input) => { assert.equal(String(input), `http://127.0.0.1:8000/api/v1/rendering/outputs?event_id=${id}&session_id=${id}`); return Response.json({ items: [] }); };
  assert.deepEqual(await readCapability("rendering", `outputs?event_id=${id}&session_id=${id}`), { items: [] });
  await assert.rejects(readCapability("rendering", "requests"));
});

for (const entry of [
  ...cases.map((entry) => ({ name: entry.name, handler: entry.handlers.GET, method: "GET", path: entry.reads[0] })),
  { name: "rendering", handler: rendering.POST, method: "POST", path: "requests" },
  { name: "demo", handler: demo.POST, method: "POST", path: "sessions/start" },
]) {
  test(`${entry.name} ${entry.method}: loopback alias matrix preserves origin restrictions`, async () => {
    let calls = 0;
    globalThis.fetch = async () => { calls++; return Response.json({ accepted: true }); };
    async function check(own: string, origin: string | null, expected: number, fetchSite = "same-origin") {
      const headers: Record<string, string> = { "sec-fetch-site": fetchSite, [demoLaunchContextHeader]: launch };
      if (origin !== null) headers.origin = origin;
      const request = new NextRequest(`${own}/api/stageflow/${entry.name}/${entry.path}`, {
        method: entry.method, headers, ...(entry.method === "POST" ? { body: "{}" } : {}),
      });
      const before = calls;
      const response = await entry.handler(request, context(entry.path));
      assert.equal(response.status, expected, `${own} <- ${origin} (${fetchSite})`);
      assert.equal(calls - before, expected === 200 ? 1 : 0);
      assert.doesNotMatch(await response.text(), new RegExp(secret));
    }
    for (const own of ["localhost", "127.0.0.1", "[::1]"]) {
      for (const supplied of ["localhost", "127.0.0.1", "[::1]"]) {
        await check(`http://${own}:3000`, `http://${supplied}:3000`, 200);
        await check(`https://${own}:3000`, `https://${supplied}:3000`, 200);
        await check(`http://${own}:3000`, `http://${supplied}:3001`, 403);
        await check(`http://${own}:3000`, `https://${supplied}:3000`, 403);
        await check(`https://${own}:3000`, `http://${supplied}:3000`, 403);
        await check(`http://${own}:3000`, `http://${supplied}:3000`, 403, "cross-site");
      }
      for (const origin of ["http://producer.local:3000", "http://localhost.evil:3000", "null", "garbage", "http://user@localhost:3000", "http://localhost:3000/path", "http://localhost:3000?x=1"]) {
        await check(`http://${own}:3000`, origin, 403);
      }
      await check(`http://${own}:3000`, null, 200);
      await check(`http://${own}:3000`, null, 403, "cross-site");
      await check("http://producer.local:3000", `http://${own}:3000`, 403);
    }
    await check("http://producer.local:3000", "http://producer.local:3000", 200);
    for (const origin of ["http://other.local:3000", "http://PRODUCER.local:3000", "http://producer.local:3001", "https://producer.local:3000", "null"]) {
      await check("http://producer.local:3000", origin, 403);
    }
    await check("http://producer.local:3000", null, 200);
    await check("http://producer.local:3000", "http://producer.local:3000", 403, "cross-site");
    // NextURL normalizes these unapproved request hosts to localhost; they must
    // not acquire the new alias exception. Historical exact/null behavior stays.
    for (const own of ["127.0.0.2", "127.1.2.3"]) {
      await check(`http://${own}:3000`, "http://127.0.0.1:3000", 403);
      await check(`http://${own}:3000`, "http://[::1]:3000", 403);
      await check(`http://${own}:3000`, "http://localhost:3000", 200);
      await check(`http://${own}:3000`, null, 200);
    }
  });
}
