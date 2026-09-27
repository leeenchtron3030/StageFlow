import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import { NextRequest } from "next/server.js";
import { proxy, capabilityRoutes, type Capability } from "./capability-proxy.server.ts";
import { demoLaunchContextHeader } from "./demo-launch-context.ts";
import { fixtureId as id } from "./session-outputs-fixtures.ts";

const secret = "synthetic-audit-secret-0123456789abcdef";
const launch = "synthetic-audit-launch-0123456789abcdef";
const freeText = "Private synthetic operator explanation";
const originalFetch = globalThis.fetch, originalInfo = console.info;
const envKeys = ["STAGEFLOW_API_SHARED_SECRET", "STAGEFLOW_DEMO_LAUNCH_CONTEXT", "STAGEFLOW_DEMO_OPERATOR_ID", "STAGEFLOW_ASSEMBLY_API_BASE_URL"];
const originalEnv = Object.fromEntries(envKeys.map((key) => [key, process.env[key]]));
let lines: string[] = [];
beforeEach(() => {
  lines = []; console.info = (line) => { lines.push(String(line)); };
  process.env.STAGEFLOW_API_SHARED_SECRET = secret;
  process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT = launch;
  process.env.STAGEFLOW_DEMO_OPERATOR_ID = id(9);
  delete process.env.STAGEFLOW_ASSEMBLY_API_BASE_URL;
  globalThis.fetch = async () => Response.json({ revision_id: id(4), reason: freeText });
});
afterEach(() => {
  globalThis.fetch = originalFetch; console.info = originalInfo;
  for (const key of envKeys) { if (originalEnv[key] === undefined) delete process.env[key]; else process.env[key] = originalEnv[key]; }
});
async function command(options: { path?: string; capability?: Exclude<Capability, "demo">; headers?: Record<string, string>; body?: string; method?: string } = {}) {
  const path = options.path ?? `sessions/${id(2)}/revisions`;
  const capability = options.capability ?? "assembly", method = options.method ?? "POST";
  const request = new NextRequest(`http://producer.local/api/stageflow/${capability}/${path}`, {
    method, headers: { origin: "http://producer.local", [demoLaunchContextHeader]: launch, "x-forwarded-for": "127.0.0.1, 10.0.0.1", ...options.headers },
    ...(method === "POST" ? { body: options.body ?? JSON.stringify({ operation_id: id(1), command_id: id(3), template_id: id(5), reason: freeText, note: secret }) } : {}),
  });
  return proxy(request, path.split("/"), method, capability);
}
function pair(disposition: string, outcome: string, backendStatus: number | null) {
  assert.equal(lines.length, 2);
  const records = lines.map((line) => {
    assert.ok(line.startsWith("stageflow_capability_command="));
    return JSON.parse(line.slice("stageflow_capability_command=".length));
  });
  const [received, result] = records;
  assert.equal(received.phase, "received"); assert.equal(result.phase, "result");
  assert.match(received.request_id, /^[a-f0-9-]{14}4[a-f0-9-]{21}$/);
  assert.equal(received.request_id, result.request_id);
  for (const record of records) assert.match(record.timestamp, /^\d{4}-.*Z$/);
  assert.equal(received.disposition, disposition); assert.equal(result.outcome, outcome);
  assert.equal(result.backend_status, backendStatus); assert.ok(result.duration_ms >= 0);
  for (const forbidden of [secret, launch, freeText, "request_body", "response_body"]) assert.ok(!lines.join("\n").includes(forbidden), forbidden);
  return { received, result };
}
test("audit success pairs request/result, safe identities, pattern, launch fingerprint and reason metadata", async () => {
  await command();
  const { received, result } = pair("accepted", "succeeded", 200);
  assert.deepEqual(received.resource_ids, { session_id: id(2), template_id: id(5) });
  assert.equal(received.operation_id, id(1)); assert.equal(received.command_id, id(3));
  assert.equal(received.route_pattern, capabilityRoutes.assembly[3].path.source);
  assert.equal(received.launch_context_valid, true); assert.match(received.launch_context_fingerprint, /^[0-9a-f]{16}$/);
  assert.equal(received.producer_proxy_client_address, "127.0.0.1");
  assert.equal(received.reason_present, true); assert.equal(received.reason_length, freeText.length);
  assert.equal(result.revision_id, id(4));
  lines = []; await command(); assert.notEqual(JSON.parse(lines[0].split("=")[1]).request_id, received.request_id);
});
for (const status of [400, 409, 422, 500, 503]) test(`audit backend ${status}`, async () => {
  globalThis.fetch = async () => Response.json({ detail: "synthetic_bounded_code", reason: freeText }, { status });
  assert.equal((await command()).status, status);
  const { result } = pair("accepted", status < 500 ? "rejected" : "failed", status);
  assert.equal(result.error_code, "synthetic_bounded_code");
});
for (const error of [new TypeError(secret), new DOMException(freeText, "TimeoutError")]) test(`audit transport ${error.name} without exception text`, async () => {
  globalThis.fetch = async () => { throw error; };
  assert.equal((await command()).status, 503);
  pair("accepted", "failed", null);
});
const refusals: Array<{ name: string; options: Parameters<typeof command>[0]; remove?: string; disposition: string; status: number }> = [
  { name: "unknown route", options: { path: `unknown/${freeText}` }, disposition: "not_allowed", status: 404 },
  { name: "read-only capability POST", options: { capability: "media-timing" as const, path: `assets/${id(1)}/latest` }, disposition: "not_allowed", status: 404 },
  { name: "cross origin", options: { headers: { origin: "http://elsewhere.local" } }, disposition: "cross_site", status: 403 },
  { name: "cross site", options: { headers: { "sec-fetch-site": "cross-site" } }, disposition: "cross_site", status: 403 },
  { name: "declared bytes", options: { headers: { "content-length": "32769" } }, disposition: "too_large", status: 413 },
  { name: "actual bytes", options: { body: "x".repeat(32769) }, disposition: "too_large", status: 413 },
  { name: "UTF-8 bytes", options: { body: "é".repeat(16385) }, disposition: "too_large", status: 413 },
  { name: "actor insertion bytes", options: { body: JSON.stringify({ note: "x".repeat(32730) }) }, disposition: "too_large", status: 413 },
  { name: "missing launch", options: { headers: { [demoLaunchContextHeader]: "" } }, disposition: "launch_context", status: 403 },
  { name: "stale launch", options: { headers: { [demoLaunchContextHeader]: "stale" } }, disposition: "launch_context", status: 403 },
  { name: "malformed JSON", options: { body: "{" }, disposition: "not_allowed", status: 422 },
  { name: "array JSON", options: { body: "[]" }, disposition: "not_allowed", status: 422 },
  { name: "null JSON", options: { body: "null" }, disposition: "not_allowed", status: 422 },
  { name: "missing server launch", options: {}, remove: "STAGEFLOW_DEMO_LAUNCH_CONTEXT", disposition: "launch_context", status: 403 },
  { name: "missing operator", options: {}, remove: "STAGEFLOW_DEMO_OPERATOR_ID", disposition: "not_allowed", status: 503 },
  { name: "missing secret", options: {}, remove: "STAGEFLOW_API_SHARED_SECRET", disposition: "secret_unavailable", status: 503 },
];
for (const entry of refusals) test(`audit refusal: ${entry.name}`, async () => {
  if (entry.remove) delete process.env[entry.remove];
  globalThis.fetch = async () => { assert.fail("refused command forwarded"); };
  assert.equal((await command(entry.options)).status, entry.status);
  pair(entry.disposition, entry.status < 500 ? "rejected" : "failed", null);
});
test("invalid configured operator and short secret remain audited refusals", async () => {
  process.env.STAGEFLOW_DEMO_OPERATOR_ID = "invalid";
  assert.equal((await command()).status, 503); pair("not_allowed", "failed", null);
  lines = []; process.env.STAGEFLOW_DEMO_OPERATOR_ID = id(9); process.env.STAGEFLOW_API_SHARED_SECRET = "short";
  assert.equal((await command()).status, 503); pair("secret_unavailable", "failed", null);
});
test("nested resource and Editorial result identities are selected without nested text", async () => {
  globalThis.fetch = async () => Response.json({ decision: { review_decision_id: id(30), operation_id: id(3), reason: freeText }, clip: { clip_id: id(31), notes: freeText } });
  await command({ capability: "editorial", path: `moments/${id(2)}/reviews` });
  let records = pair("accepted", "succeeded", 200);
  assert.equal(records.result.review_decision_id, id(30)); assert.equal(records.result.operation_id, id(3)); assert.equal(records.result.clip_id, id(31));
  lines = [];
  globalThis.fetch = async () => Response.json({ run_id: id(32), candidate_ids: [id(33), freeText] });
  await command({ capability: "editorial", path: `sessions/${id(2)}/derivations`, body: JSON.stringify({ phrase_list_id: id(34), command_id: id(3) }) });
  records = pair("accepted", "succeeded", 200);
  assert.equal(records.received.resource_ids.phrase_list_id, id(34)); assert.deepEqual(records.result.candidate_ids, [id(33)]);
  lines = [];
  await command({ body: JSON.stringify({ explicit: [{ slot_key: freeText, packaging_revision_id: id(35) }], content: { kind: "completed_media_asset", asset_id: id(36) }, session_id: id(99) }) });
  records = pair("accepted", "succeeded", 200);
  assert.deepEqual(records.received.resource_ids.packaging_revision_ids, [id(35)]);
  assert.equal(records.received.resource_ids.asset_id, id(36)); assert.equal(records.received.resource_ids.session_id, id(2));
});
test("streaming command cap cancels and logs both refusal lines", async () => {
  let cancelled = false;
  const path = `sessions/${id(2)}/revisions`;
  const request = new NextRequest(`http://producer.local/${path}`, { method: "POST", duplex: "half", headers: { [demoLaunchContextHeader]: launch }, body: new ReadableStream({ pull(c) { c.enqueue(new Uint8Array(16384)); }, cancel() { cancelled = true; } }) } as ConstructorParameters<typeof NextRequest>[1]);
  assert.equal((await proxy(request, path.split("/"), "POST", "assembly")).status, 413);
  assert.equal(cancelled, true); pair("too_large", "rejected", null);
});
for (const kind of ["response cap", "response stream cap", "echoed secret", "bad backend URL"]) test(`audit failed upstream: ${kind}`, async () => {
  if (kind === "bad backend URL") process.env.STAGEFLOW_ASSEMBLY_API_BASE_URL = "http://remote.invalid/api/v1/assembly";
  else globalThis.fetch = async () => kind === "echoed secret" ? Response.json({ reason: secret }) : kind === "response cap" ? new Response("", { headers: { "content-length": String(12 * 1024 * 1024 + 1) } }) : new Response(new ReadableStream({ pull(c) { c.enqueue(new Uint8Array(1024 * 1024)); } }));
  assert.equal((await command()).status, kind === "bad backend URL" ? 503 : 502);
  pair("accepted", "failed", kind === "bad backend URL" ? null : 200);
});
test("all capability POST patterns audited; GET reads have no request logs", async () => {
  for (const capability of ["assembly", "rendering", "editorial", "media-timing"] as const) {
    for (const entry of capabilityRoutes[capability]) {
      lines = [];
      const path = entry.path.source.slice(1, -1).replaceAll("\\/", "/").replace(/\[0-9a-fA-F\]\{8\}.*?\[0-9a-fA-F\]\{12\}/g, id(2));
      assert.equal((await command({ capability, path, method: entry.method })).status, 200);
      if (entry.method === "POST") pair("accepted", "succeeded", 200); else assert.equal(lines.length, 0);
    }
  }
});
test("untrusted address, invalid IDs, raw error text and other free text never logged", async () => {
  globalThis.fetch = async () => Response.json({ detail: freeText, revision_id: freeText, metadata: { note: freeText }, notes: freeText }, { status: 422 });
  await command({ headers: { "x-forwarded-for": secret }, body: JSON.stringify({ command_id: freeText, operation_id: secret, reason: freeText, notes: secret }) });
  const { received, result } = pair("accepted", "rejected", 422);
  assert.equal(received.producer_proxy_client_address, "unavailable"); assert.equal(received.command_id, null);
  assert.equal(received.operation_id, null); assert.equal(result.error_code, "http_422");
});
