import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import { NextRequest } from "next/server.js";
import * as handlers from "../../app/api/stageflow/session-suggestions/[...path]/route.ts";
import { demoLaunchContextHeader } from "./demo-launch-context.ts";
import { eventId, suggestionId as id } from "./session-suggestions-fixtures.ts";
import { sessionId, startProposal as proposal, boundaryDecision } from "./session-boundaries-fixtures.ts";
import { prepareBoundaryCommand } from "./session-boundaries.ts";

const keys = ["STAGEFLOW_API_SHARED_SECRET", "STAGEFLOW_DEMO_LAUNCH_CONTEXT", "STAGEFLOW_DEMO_OPERATOR_ID"];
const previous = keys.map((k) => process.env[k]), originalFetch = globalThis.fetch, originalLog = console.info;
const secret = "synthetic-secret-0123456789abcdef0123456789", launch = "synthetic-launch-0123456789abcdef0123456789";
let lines: string[] = [];
beforeEach(() => { process.env.STAGEFLOW_API_SHARED_SECRET = secret; process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT = launch; process.env.STAGEFLOW_DEMO_OPERATOR_ID = id(4); lines = []; console.info = (line) => lines.push(String(line)); });
afterEach(() => { globalThis.fetch = originalFetch; console.info = originalLog; keys.forEach((key, i) => { if (previous[i] === undefined) delete process.env[key]; else process.env[key] = previous[i]; }); });
const base = `events/${eventId}/sessions/${sessionId}/boundary-proposals`;
function request(path: string, method: string, body: unknown = {}, headers: Record<string, string> = {}) {
  return new NextRequest(`http://localhost/api/stageflow/session-suggestions/${path}`, { method, headers: { origin: "http://localhost", [demoLaunchContextHeader]: launch, ...headers }, ...(method === "POST" ? { body: JSON.stringify(body) } : {}) });
}
const context = (path: string) => ({ params: Promise.resolve({ path: path.split("?")[0].split("/") }) });

test("boundary proxy permits exactly the four method/path additions and refuses adjacent or unrelated routes", async () => {
  const gets = [base, `${base}/history`], posts = [`${base}/${proposal.proposal_id}/apply`, `${base}/${proposal.proposal_id}/dismiss`];
  let calls = 0; globalThis.fetch = async () => { calls++; return Response.json({}); };
  const paths = [...gets, ...posts, `${base}/apply`, `${base}/batch-apply`, `${base}/${proposal.proposal_id}`, `${base}/${proposal.proposal_id}/correct`, `${base}/${proposal.proposal_id}/history`, `${base}/history/extra`, `events/${eventId}/sessions/${sessionId}/boundary-history`, `events/${eventId}/sessions/${sessionId}/correct-session-boundary`, `events/${eventId}/markers`, `events/${eventId}/work-queue`, ...[...gets, ...posts].map((p) => `${p}/extra`), ...posts.map((p) => p.replace(proposal.proposal_id, "not-a-uuid")), base.replace(sessionId, "%2e%2e"), base.replace(eventId, "00000000-0000-0000-0000-000000000000")];
  for (const path of paths) for (const method of ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] as const) {
    const allowed = method === "GET" ? gets.includes(path) : method === "POST" && posts.includes(path);
    const before = calls, result = await handlers[method](request(path, method), context(path));
    assert.equal(result.status, allowed ? 200 : 404, `${method} ${path}`); assert.equal(calls - before, allowed ? 1 : 0);
  }
});

test("apply/dismiss forward backend contract with server actor and audit safe identities without reason text", async () => {
  for (const kind of ["apply", "dismiss"] as const) {
    const command = prepareBoundaryCommand(proposal, kind, kind === "dismiss" ? "Keep current time" : "");
    const path = `${base}/${proposal.proposal_id}/${kind}`;
    globalThis.fetch = async (url, init) => {
      assert.equal(String(url), `http://127.0.0.1:8000/api/v1/session-suggestions/${path}`);
      assert.equal(init?.cache, "no-store"); assert.equal(init?.redirect, "error");
      const body = JSON.parse(String(init?.body));
      assert.deepEqual(body, { ...command.body, actor_id: id(4) });
      assert.equal(new Headers(init?.headers).get("x-stageflow-api-secret"), secret);
      return Response.json(boundaryDecision(body, kind === "dismiss"));
    };
    const result = await handlers.POST(request(path, "POST", { ...command.body, actor_id: id(99) }), context(path));
    assert.equal(result.status, 200);
  }
  const records = lines.map((line) => JSON.parse(line.slice(line.indexOf("=") + 1)));
  assert.equal(records.length, 4);
  for (let i = 0; i < 4; i += 2) {
    assert.deepEqual(records[i].resource_ids, { event_id: eventId, session_id: sessionId, proposal_id: proposal.proposal_id });
    assert.equal(records[i].request_id, records[i + 1].request_id); assert.equal(records[i + 1].proposal_id, proposal.proposal_id);
    assert.equal(records[i + 1].outcome, "succeeded");
  }
  assert.equal(records[2].reason_present, true); assert.equal(records[2].reason_length, "Keep current time".length);
  for (const value of ["Keep current time", secret, launch]) assert.ok(!lines.join(" ").includes(value));
});

test("new commands retain existing origin, launch and operator authorization; reads remain read-only", async () => {
  const path = `${base}/${proposal.proposal_id}/apply`;
  globalThis.fetch = async () => { assert.fail("unauthorized command forwarded"); };
  assert.equal((await handlers.POST(request(path, "POST", {}, { origin: "https://other.invalid" }), context(path))).status, 403);
  assert.equal((await handlers.POST(request(path, "POST", {}, { [demoLaunchContextHeader]: "wrong" }), context(path))).status, 403);
  delete process.env.STAGEFLOW_DEMO_OPERATOR_ID;
  assert.equal((await handlers.POST(request(path, "POST"), context(path))).status, 503);
  globalThis.fetch = async (url) => { assert.ok(String(url).endsWith(`${base}/history?limit=50&after=${id(50)}`)); return Response.json({ items: [], next_after: null, limit: 50 }); };
  const readPath = `${base}/history?limit=50&after=${id(50)}`;
  assert.equal((await handlers.GET(request(readPath, "GET", {}, { [demoLaunchContextHeader]: "" }), context(readPath))).status, 200);
});

test("refused and failed new POSTs audit status without free-text payloads", async () => {
  for (const status of [409, 422, 503]) {
    const path = `${base}/${proposal.proposal_id}/dismiss`;
    globalThis.fetch = async () => Response.json({ detail: "private reason text" }, { status });
    assert.equal((await handlers.POST(request(path, "POST", { command_id: id(55), reason: "private reason text" }), context(path))).status, status);
  }
  const results = lines.map((line) => JSON.parse(line.slice(line.indexOf("=") + 1))).filter((r) => r.phase === "result");
  assert.deepEqual(results.map((r) => r.outcome), ["rejected", "rejected", "failed"]);
  assert.deepEqual(results.map((r) => r.error_code), ["http_409", "http_422", "http_503"]);
  assert.ok(!lines.join(" ").includes("private reason text"));
});
