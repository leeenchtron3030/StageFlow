import assert from "node:assert/strict";
import { test } from "node:test";
import { boundariesApi, loadBoundaryBadges, type BoundaryProposal } from "./session-boundaries-api.ts";
import { boundaryError, boundarySummary, boundaryTimes, boundaryTimesLabel, boundaryStageCount, sessionBoundaryRange, prepareBoundaryCommand, sendBoundaryCommand } from "./session-boundaries.ts";
import { boundaryLabels as labels } from "./ui-labels.ts";
import { eventId, suggestionId as id, suggestionFixture as suggestion } from "./session-suggestions-fixtures.ts";
import { sessionId, startProposal as start, endProposal as end, currentStart, boundaryDecision, boundaryHistoryDecision, boundaryKernelFixture } from "./session-boundaries-fixtures.ts";
import { getFixtureWorkspace } from "./fixtures.ts";
import { adaptKernelStatus } from "./kernel-adapter.ts";

test("open proposals use the Session route, validate scope, at most one per edge, and sort start first", async () => {
  const read = async (path: string) => { assert.equal(path, `events/${eventId}/sessions/${sessionId}/boundary-proposals`); return { items: [end, start] }; };
  assert.deepEqual(await boundariesApi(read).open(eventId, sessionId), [start, end]);
  for (const items of [[{ ...start, session_id: id(99) }], [start, start], [start, end, start], [{ ...start, boundary_at: "2026-09-29T10:00:00" }], [{ ...start, authorized_use: "automatic" }], [{ ...start, reason: "schedule_only" }]]) {
    await assert.rejects(boundariesApi(async () => ({ items })).open(eventId, sessionId));
  }
  assert.deepEqual(await boundariesApi(async () => ({ items: [] })).open(eventId, sessionId), []);
});

test("decision history pages explicitly with UUID cursors and rejects mixed Sessions or repeated cursors", async () => {
  const decision = boundaryHistoryDecision({ command_id: id(51) });
  const api = boundariesApi(async (path) => { assert.equal(path, `events/${eventId}/sessions/${sessionId}/boundary-proposals/history?limit=50&after=${id(50)}`); return { items: [decision], limit: 50, next_after: id(51) }; });
  assert.equal((await api.history(eventId, sessionId, id(50))).next_after, id(51));
  for (const page of [{ items: [{ ...decision, session_id: id(99) }], next_after: null }, { items: [decision], next_after: id(50) }, { items: [decision, decision], next_after: null }, { items: [], next_after: id(51) }]) {
    await assert.rejects(boundariesApi(async () => ({ limit: 50, ...page })).history(eventId, sessionId, id(50)));
  }
});

test("history requires a start/end field on every row while command responses stay unchanged", async () => {
  const items = [boundaryHistoryDecision({ command_id: id(50) }, start), boundaryHistoryDecision({ command_id: id(51) }, end, true)];
  const page = await boundariesApi(async () => ({ items, limit: 50, next_after: null })).history(eventId, sessionId);
  assert.deepEqual(page.items, items);
  for (const boundary_kind of [undefined, null, "middle"]) {
    await assert.rejects(boundariesApi(async () => ({ items: [{ ...items[0], boundary_kind }], limit: 50, next_after: null })).history(eventId, sessionId));
  }
});

test("reason labels, second precision, local dates, signed direction and day crossings remain readable", () => {
  assert.equal(boundarySummary(start, currentStart), "Start could be 1 min 20 s later — at a still-image changeover");
  assert.equal(boundarySummary(end, "2026-09-29T11:00:00Z"), "End could be 45 s earlier — at a recording gap");
  for (const reason of Object.keys(labels.reasons) as BoundaryProposal["reason"][]) assert.ok(boundarySummary({ ...start, reason }, currentStart).includes(labels.reasons[reason]));
  const times = boundaryTimes(currentStart, start.boundary_at, "America/Los_Angeles");
  assert.equal(times, "03:00:00 → 03:01:20");
  assert.equal(boundaryTimesLabel(currentStart, start.boundary_at, "America/Los_Angeles"), "current 03:00:00, suggested 03:01:20");
  const crossing = boundaryTimes("2026-09-29T23:59:30Z", "2026-09-30T00:01:00Z", "UTC");
  assert.match(crossing, /Sep 29.*Sep 30/);
  assert.match(boundaryTimes(undefined, start.boundary_at, "UTC"), /unavailable → Sep 29/);
  const nextDay = boundaryTimes("2026-09-30T01:00:00Z", "2026-09-30T01:01:00Z", "UTC", currentStart);
  assert.equal(nextDay, "Sep 30, 2026, 01:00:00 → 01:01:00");
  // The local Session date, rather than its UTC date, controls omission.
  assert.equal(boundaryTimes("2026-09-30T01:00:00Z", "2026-09-30T01:01:00Z", "America/Los_Angeles", currentStart), "18:00:00 → 18:01:00");
  assert.equal(sessionBoundaryRange(currentStart, "2026-09-29T11:00:00Z", "UTC"), "Sep 29, 2026, 10:00:00–11:00:00");
  assert.match(sessionBoundaryRange(currentStart, "2026-09-30T01:00:00Z", "UTC"), /Sep 29.*Sep 30/);
  assert.match(sessionBoundaryRange(currentStart, undefined, "UTC"), /–not ended$/);
});

test("Stage summary omits zero, counts both edges, and uses singular or plural", () => {
  assert.equal(boundaryStageCount(), "");
  assert.equal(boundaryStageCount({ sessions: {}, incomplete: false }), "");
  assert.equal(boundaryStageCount({ sessions: { [sessionId]: 1 }, incomplete: false }), " · 1 boundary suggestion");
  assert.equal(boundaryStageCount({ sessions: { [sessionId]: 2 }, incomplete: false }), " · 2 boundary suggestions");
  assert.equal(boundaryStageCount({ sessions: { [sessionId]: 2, [id(50)]: 1 }, incomplete: true }), " · 3 boundary suggestions");
});

test("apply and optional bounded dismiss bodies match the backend without actor, time edits or free text", () => {
  const apply = prepareBoundaryCommand(start, "apply"), dismiss = prepareBoundaryCommand(start, "dismiss");
  assert.deepEqual(Object.keys(apply.body).sort(), ["authority_kind", "command_id"]);
  assert.deepEqual(Object.keys(dismiss.body).sort(), ["authority_kind", "command_id"]);
  assert.equal(apply.body.authority_kind, "human"); assert.notEqual(apply.body.command_id, dismiss.body.command_id);
  for (const reason of labels.dismissReasons) assert.equal(prepareBoundaryCommand(start, "dismiss", reason).body.reason, reason);
  assert.throws(() => prepareBoundaryCommand(start, "dismiss", "arbitrary free text"));
  assert.throws(() => prepareBoundaryCommand(start, "apply", labels.dismissReasons[0]));
});

test("refusals map only bounded codes, never backend free text", () => {
  for (const [status, detail, message] of [[409, "boundary_proposal_stale", labels.stale], [409, "boundary_proposal_decided", labels.decided], [409, "secret free text", labels.conflict], [422, "private", labels.invalid], [413, "private", labels.invalid], [401, "", labels.readOnly], [403, "", labels.readOnly], [404, "", labels.missing], [503, "", labels.failed]] as const) assert.equal(boundaryError(status, { detail }), message);
});

test("commands validate decision identity and kind; network, malformed or mismatched success stays uncertain", async () => {
  const command = prepareBoundaryCommand(start, "apply");
  const fetcher: typeof fetch = async (url, init) => {
    assert.equal(String(url), `/api/stageflow/session-suggestions/events/${eventId}/sessions/${sessionId}/boundary-proposals/${start.proposal_id}/apply`);
    assert.equal(init?.method, "POST"); assert.equal(init?.cache, "no-store"); assert.equal(init?.redirect, "error");
    return Response.json(boundaryDecision(JSON.parse(String(init?.body))));
  };
  assert.equal((await sendBoundaryCommand(eventId, command, "synthetic", fetcher)).saved, true);
  for (const patch of [{ session_id: id(99) }, { proposal_id: id(99) }, { command_id: id(99) }, { kind: "dismissed" }]) {
    const result = await sendBoundaryCommand(eventId, command, "synthetic", async () => Response.json({ ...boundaryDecision(command.body), ...patch }));
    assert.equal(result.saved, false); assert.equal(result.uncertain, true);
  }
  for (const fetcher of [async () => { throw new Error(); }, async () => new Response("broken", { status: 200 })]) assert.equal((await sendBoundaryCommand(eventId, command, "synthetic", fetcher)).message, labels.unknown);
});

test("Stage badge reads linked Sessions once each without latest-run suggestions; unlinked and other Stages are excluded", async () => {
  const base = getFixtureWorkspace("turnover").sessions[0];
  const session = { ...base, id: sessionId, stageKey: "main", programExpectationId: suggestion.expectation_id! };
  const calls: string[] = [];
  const result = await loadBoundaryBadges(eventId, "main", [session, session, { ...session, id: id(62), stageKey: "other" }, { ...session, id: id(63), programExpectationId: undefined }], async (path) => { calls.push(path); return { items: [start, end] }; });
  assert.equal(calls.length, 1); assert.deepEqual(result, { sessions: { [sessionId]: 2 }, incomplete: false });
  assert.deepEqual(await loadBoundaryBadges(eventId, "main", [session], async () => ({ items: [] })), { sessions: {}, incomplete: false });
});

test("Stage reads cap at 50 Sessions and four concurrent requests; unavailable reads are disclosed", async () => {
  const base = getFixtureWorkspace("turnover").sessions[0];
  const sessions = Array.from({ length: 55 }, (_, n) => ({ ...base, id: id(100 + n), stageKey: "main", programExpectationId: id(200 + n) }));
  let calls = 0, active = 0, max = 0;
  const result = await loadBoundaryBadges(eventId, "main", sessions, async () => { calls++; active++; max = Math.max(max, active); await new Promise((resolve) => setTimeout(resolve, 0)); active--; return { items: [] }; });
  assert.equal(calls, 50); assert.equal(max, 4); assert.equal(result.incomplete, true);
  assert.equal((await loadBoundaryBadges(eventId, "main", sessions.slice(0, 1), async () => { throw new Error(); })).incomplete, true);
});

test("Kernel adaptation retains the existing expectation identity for active and historical Sessions, never matching titles", async () => {
  const payload = boundaryKernelFixture();
  const workspace = adaptKernelStatus(payload, currentStart);
  assert.equal(workspace.sessions[0].programExpectationId, suggestion.expectation_id);
  assert.equal(workspace.stages[0].currentSession?.programExpectationId, suggestion.expectation_id);
  payload.stages[0].session_id = null;
  payload.stages[0].assembling_sessions = [];
  const historical = adaptKernelStatus(payload, currentStart);
  assert.equal(historical.sessions[0].programExpectationId, suggestion.expectation_id);
  delete payload.stages[0].recent_sessions[0].program_expectation_id;
  const legacy = adaptKernelStatus(payload, currentStart);
  assert.equal(legacy.sessions[0].programExpectationId, undefined);
  assert.deepEqual(await loadBoundaryBadges(eventId, "main", legacy.sessions, async () => { assert.fail("a title is not an identity"); }), { sessions: {}, incomplete: false });
});
