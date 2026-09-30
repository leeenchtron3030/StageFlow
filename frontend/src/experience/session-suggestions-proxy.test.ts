import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { NextRequest } from "next/server.js";
import { capabilityRoutes, proxy, readCapability } from "./capability-proxy.server.ts";
import { suggestionsApi } from "./session-suggestions-api.ts";
import { CapabilityReadError } from "./outputs-api.ts";
import { demoLaunchContextHeader } from "./demo-launch-context.ts";
import { eventId, stageId, suggestionFixture as s, suggestionId as id } from "./session-suggestions-fixtures.ts";

test("all suggestion POSTs audit bounded identities and results, substitute server actor, and omit titles/reasons", async () => {
  const keys = ["STAGEFLOW_API_SHARED_SECRET", "STAGEFLOW_DEMO_LAUNCH_CONTEXT", "STAGEFLOW_DEMO_OPERATOR_ID"];
  const previous = keys.map((k) => process.env[k]), original = globalThis.fetch, log = console.info;
  process.env.STAGEFLOW_API_SHARED_SECRET = "synthetic-secret-0123456789abcdef0123456789"; process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT = "synthetic-launch-0123456789abcdef0123456789"; process.env.STAGEFLOW_DEMO_OPERATOR_ID = id(4);
  const lines: string[] = []; console.info = (line) => lines.push(String(line));
  try {
    const routes = [`stages/${stageId}/runs`, `suggestions/${s.suggestion_id}/confirm`, `suggestions/${s.suggestion_id}/reject`, `stages/${stageId}/schedule-offset`];
    for (const suffix of routes) {
      const path = `events/${eventId}/${suffix}`;
      globalThis.fetch = async (url, init) => {
        assert.equal(String(url), `http://127.0.0.1:8000/api/v1/session-suggestions/${path}`);
        assert.equal(JSON.parse(String(init?.body)).actor_id, id(4));
        return Response.json({ command_id: id(20), run_id: id(21), suggestion_id: s.suggestion_id, session_id: id(22), version: 2 });
      };
      const request: NextRequest = new NextRequest(`http://localhost/api/stageflow/session-suggestions/${path}`, { method: "POST", headers: { origin: "http://localhost", [demoLaunchContextHeader]: process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT! }, body: JSON.stringify({ actor_id: id(99), command_id: id(20), reason: "private reason", title: "private title", phrases: ["private phrase"] }) });
      assert.equal((await proxy(request, path.split("/"), "POST", "session-suggestions")).status, 200);
    }
    const records = lines.map((line) => JSON.parse(line.split("=")[1]));
    assert.equal(records.length, 8);
    for (let i = 0; i < records.length; i += 2) {
      assert.equal(records[i].phase, "received"); assert.equal(records[i + 1].phase, "result");
      assert.equal(records[i].request_id, records[i + 1].request_id); assert.equal(records[i].command_id, id(20));
      assert.equal(records[i].resource_ids.event_id, eventId); assert.equal(records[i + 1].session_id, id(22));
      assert.equal(records[i + 1].outcome, "succeeded");
    }
    assert.equal(records[0].resource_ids.stage_id, stageId); assert.equal(records[2].resource_ids.suggestion_id, s.suggestion_id);
    assert.equal(records[7].setting_version, 2);
    for (const privateValue of ["private reason", "private title", "private phrase", "synthetic-secret", "synthetic-launch"]) assert.ok(!lines.join(" ").includes(privateValue));
  } finally { globalThis.fetch = original; console.info = log; keys.forEach((key, i) => { if (previous[i] === undefined) delete process.env[key]; else process.env[key] = previous[i]; }); }
});

test("server read retains status for latest-run 404 and producer capability uses mounted route", async () => {
  const previous = process.env.STAGEFLOW_API_SHARED_SECRET, original = globalThis.fetch;
  process.env.STAGEFLOW_API_SHARED_SECRET = "synthetic-secret-0123456789abcdef0123456789";
  try {
    globalThis.fetch = async () => Response.json({ detail: "suggestion_run_not_found" }, { status: 404 });
    await assert.rejects(readCapability("session-suggestions", `events/${eventId}/stages/${stageId}/runs/latest`), (e: unknown) => e instanceof CapabilityReadError && e.status === 404 && e.detail === "suggestion_run_not_found");
    const api = suggestionsApi((path) => readCapability("session-suggestions", path));
    assert.equal(await api.latest(eventId, stageId), null);
    globalThis.fetch = async () => Response.json({ detail: "stage_not_found" }, { status: 404 });
    await assert.rejects(api.latest(eventId, stageId), (e: unknown) => e instanceof CapabilityReadError && e.status === 404 && e.detail === "stage_not_found");
    globalThis.fetch = async (url) => { assert.equal(String(url), `http://127.0.0.1:8000/api/v1/producer/events/${eventId}/work-queue`); return Response.json({ items: [] }); };
    assert.deepEqual(await readCapability("producer", `events/${eventId}/work-queue`), { items: [] });
  } finally { globalThis.fetch = original; if (previous === undefined) delete process.env.STAGEFLOW_API_SHARED_SECRET; else process.env.STAGEFLOW_API_SHARED_SECRET = previous; }
});

test("README documents every producer and session-suggestions allowlist route and optional base", () => {
  const readme = readFileSync(new URL("../../README.md", import.meta.url), "utf8");
  for (const capability of ["producer", "session-suggestions"] as const) {
    assert.ok(readme.includes(`STAGEFLOW_${capability.toUpperCase().replaceAll("-", "_")}_API_BASE_URL`));
    const rows = [...readme.matchAll(new RegExp(`\\| ${capability} \\| (GET|POST) \\| \x60([^\x60]+)\x60 \\|`, "g"))];
    assert.equal(rows.length, capabilityRoutes[capability].length);
    for (const route of capabilityRoutes[capability]) assert.equal(rows.filter(([, method, path]) => method === route.method && route.path.test(path.replaceAll("U", eventId))).length, 1);
  }
  assert.ok(readme.includes("http://127.0.0.1:8000/api/v1/producer"));
});
