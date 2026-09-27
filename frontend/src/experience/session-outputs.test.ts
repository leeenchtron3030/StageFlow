import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as presentation from "./session-outputs.ts";
import { loadSessionOutputs } from "./session-outputs.server.ts";
import { getFixtureWorkspace } from "./fixtures.ts";
import { fixtureAssembly, fixtureId, fixtureRenderedOutput, fixtureRenderOperation, fixtureTiming, getFixtureSessionOutputs } from "./session-outputs-fixtures.ts";
const require = createRequire(import.meta.url);
const source = readFileSync(new URL("../components/session-outputs-panel.tsx", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS } });
const exports: { SessionOutputsPanel?: React.ComponentType<{ outputs: presentation.SessionOutputs }> } = {};
runInNewContext(compiled.outputText, { exports, require: (id: string) => id === "../experience/session-outputs.ts" ? presentation : require(id) });
const render = (outputs: presentation.SessionOutputs) => renderToStaticMarkup(React.createElement(exports.SessionOutputsPanel!, { outputs }));
const page = { items: [], next_after: null, limit: 100 };
const eventId = fixtureId(3), sessionId = fixtureId(2);
const revisions = (items = [fixtureAssembly()]) => ({ ...page, event_id: eventId, session_id: sessionId, items, total_count: items.length, items_truncated: false });

test("real Outputs panel renders frozen position order and all ordering/qualification labels", () => {
  const output = render(getFixtureSessionOutputs());
  for (const label of ["Outputs", "Read-only", "Development fixture", "Not production authority", "Current revision", "Unqualified recorder timing", "media_timing", "timing_evidence", "registration_time", "Registration time fallback", "Slot bindings", "Latest evidence revision 3", "Advisory only", "SHA-256 prefix:", "aaaaaaaaaaaa", "60.000 seconds", "1799", "version 2", "2026-09-27T12:00:00Z"]) assert.ok(output.includes(label), label);
  assert.ok(output.indexOf("Position 1") < output.indexOf("Position 2")); assert.ok(output.indexOf("Position 2") < output.indexOf("Position 3"));
  assert.match(output, /aria-label="Assembly members in frozen position order"/);
  assert.match(output, /Recorder timing qualification not supplied/);
  assert.doesNotMatch(output, /<button|<video|<audio|synthetic-output|synthetic-manifest|content_key|ffmpeg_sha256/);
});
test("qualified, rejected, expired and absent qualifications remain distinct text", () => {
  const expected = ["Unqualified recorder timing", "Qualified recorder timing", "Rejected recorder timing", "Expired recorder timing qualification", "Recorder timing qualification not supplied"];
  for (const [index, value] of (["unqualified", "qualified", "rejected", "expired", null] as const).entries()) assert.equal(presentation.qualificationLabel(value), expected[index]);
});
test("staleness, issue codes, approval and bounded reads have visible consequences", () => {
  const outputs = getFixtureSessionOutputs();
  if (outputs.assembly.state !== "available" || !outputs.assembly.value || outputs.operations.state !== "available" || outputs.outputs.state !== "available") assert.fail();
  outputs.assembly.value.stale = true;
  outputs.assembly.value.approval_state = "approved";
  outputs.assembly.value.revision.validation = { state: "invalid", issues: [{ code: "unresolved_required_slot", subject: "opening" }] };
  outputs.operations.value.truncated = true; outputs.outputs.value.truncated = true; outputs.timingTruncated = true;
  const html = render(outputs);
  for (const text of ["Inputs changed", "Prior decisions remain recorded", "unresolved_required_slot", "approved", "More operations exist", "More outputs exist", "Additional assets are not shown"]) assert.ok(html.includes(text), text);
});
test("empty, unavailable and missing evidence are distinct; no fixture fallback", () => {
  const outputs = getFixtureSessionOutputs(); outputs.fixture = false; outputs.assembly = { state: "available", value: null }; outputs.operations = { state: "unavailable" }; outputs.outputs = { state: "available", value: { items: [], truncated: false } };
  const html = render(outputs);
  for (const label of ["No Assembly revision proposed", "Render operations unavailable", "No Rendered Outputs reported", "No timing evidence recorded"]) assert.ok(html.includes(label));
  assert.doesNotMatch(html, /Development fixture/);
});
test("read model jumps to the backend current revision beyond the first page without reordering members", async () => {
  const paths: string[] = [];
  const current = fixtureAssembly(); current.current_revision_number = 101; current.revision.revision_number = 101;
  current.revision.membership.reverse();
  const old = fixtureAssembly(); old.current_revision_number = 101;
  const result = await presentation.readSessionOutputs(eventId, sessionId, [], {
    assembly: async (path) => { paths.push(path); return path.includes("after=100") ? revisions([current]) : { ...revisions([old]), total_count: 101, items_truncated: true, next_after: 2 }; },
    rendering: async (path) => path.startsWith("outputs") ? { ...page, items: [fixtureRenderedOutput()] } : { ...page, items: [fixtureRenderOperation()] },
    timing: async (path) => ({ asset_id: path.split("/")[1], evidence: null }),
  });
  assert.equal(paths.length, 2); assert.ok(paths[1].includes("after=100"));
  assert.equal(result.assembly.state, "available");
  if (result.assembly.state === "available") assert.deepEqual(result.assembly.value?.revision.membership.map((m) => m.asset_id), current.revision.membership.map((m) => m.asset_id));
  assert.equal(result.fixture, false); assert.equal(result.timing.length, 3);
  if (result.outputs.state === "available") { assert.equal(result.outputs.value.items[0].sha256.length, 12); assert.equal("content_key" in result.outputs.value.items[0], false); }
});
test("capability failure does not hide other reads, and mismatched asset evidence is refused", async () => {
  const result = await presentation.readSessionOutputs(eventId, sessionId, [fixtureId(11), fixtureId(12)], {
    assembly: async () => { throw new Error("unavailable"); },
    rendering: async () => page,
    timing: async () => fixtureTiming(),
  });
  assert.equal(result.assembly.state, "unavailable"); assert.equal(result.outputs.state, "available");
  assert.equal(result.timing[0].result.state, "available"); assert.equal(result.timing[1].result.state, "unavailable");
  assert.equal(result.fixture, false);
});
test("current revision races, invalid schemas and cross-Session responses are unavailable", async () => {
  const wrong = fixtureAssembly(); wrong.revision.session_id = fixtureId(90);
  for (const response of [{}, revisions([wrong]), { ...revisions([]), total_count: 3 }, { ...revisions(), session_id: fixtureId(90) }, revisions([{ ...fixtureAssembly(), current_revision_number: 99 }])]) {
    const result = await presentation.readSessionOutputs(eventId, sessionId, [], { assembly: async () => response, rendering: async () => page, timing: async () => { assert.fail(); } });
    assert.equal(result.assembly.state, "unavailable");
  }
});
test("per-asset reads are deduplicated, bounded to 100 and at most eight run together", async () => {
  let active = 0, peak = 0, count = 0;
  const result = await presentation.readSessionOutputs(eventId, sessionId, [...Array.from({ length: 105 }, (_, n) => fixtureId(n + 100)), fixtureId(100)], {
    assembly: async () => revisions([]), rendering: async () => page,
    timing: async (path) => { active++; count++; peak = Math.max(peak, active); await Promise.resolve(); active--; return { asset_id: path.split("/")[1], evidence: null }; },
  });
  assert.equal(count, 100); assert.ok(peak <= 8); assert.equal(result.timingTruncated, true);
});

test("legacy invalid Assembly timing stays visible without inventing a timestamp", () => {
  const outputs = getFixtureSessionOutputs();
  if (outputs.assembly.state !== "available" || !outputs.assembly.value) assert.fail();
  outputs.assembly.value.revision.membership[0].order_key_at = null;
  outputs.assembly.value.revision.membership[0].media_started_at = null;
  const html = render(outputs);
  assert.match(html, /Ordering key \(wall-clock\): Unavailable/);
  assert.doesNotMatch(html, /dateTime="null"/);
});

test("fixture Session loading never calls a backend and keeps the fixture label", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { assert.fail("fixture must not fetch"); };
  try {
    const workspace = getFixtureWorkspace("quiet");
    const result = await loadSessionOutputs(workspace, workspace.sessions[0].id);
    assert.equal(result.fixture, true);
    assert.match(render(result), /Development fixture/);
  } finally { globalThis.fetch = originalFetch; }
});
test("Kernel Session loading uses protected server reads and strips output content references", async () => {
  const originalFetch = globalThis.fetch;
  const originalSecret = process.env.STAGEFLOW_API_SHARED_SECRET;
  const secret = "synthetic-kernel-read-secret-0123456789";
  process.env.STAGEFLOW_API_SHARED_SECRET = secret;
  const seen: string[] = [];
  globalThis.fetch = async (input, init) => {
    const url = new URL(String(input)); seen.push(url.pathname);
    assert.equal(url.hostname, "127.0.0.1"); assert.equal(init?.method, "GET");
    assert.equal(new Headers(init?.headers).get("x-stageflow-api-secret"), secret);
    if (url.pathname.endsWith("/revisions")) return Response.json(revisions());
    if (url.pathname.endsWith("/operations")) return Response.json({ ...page, items: [fixtureRenderOperation()] });
    if (url.pathname.endsWith("/outputs")) return Response.json({ ...page, items: [fixtureRenderedOutput()] });
    return Response.json({ asset_id: url.pathname.split("/")[5], evidence: null });
  };
  try {
    const workspace = getFixtureWorkspace("quiet"); workspace.dataSource.kind = "kernel"; workspace.event.id = eventId; workspace.mediaAssets = [];
    const result = await loadSessionOutputs(workspace, sessionId);
    assert.equal(result.fixture, false); assert.equal(result.assembly.state, "available");
    assert.equal(result.operations.state, "available"); assert.equal(result.outputs.state, "available");
    assert.equal(seen.length, 6);
    for (const item of result.timing) assert.equal(item.result.state, "available");
    const html = render(result);
    assert.doesNotMatch(html, /Development fixture|synthetic-output|synthetic-manifest/);
    assert.doesNotMatch(html, new RegExp(secret));
  } finally {
    globalThis.fetch = originalFetch;
    if (originalSecret === undefined) delete process.env.STAGEFLOW_API_SHARED_SECRET; else process.env.STAGEFLOW_API_SHARED_SECRET = originalSecret;
  }
});
