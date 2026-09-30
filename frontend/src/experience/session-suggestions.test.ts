import assert from "node:assert/strict";
import { test } from "node:test";
import { capabilityRead, CapabilityReadError } from "./outputs-api.ts";
import { suggestionsApi, suggestionQueue, type Suggestion } from "./session-suggestions-api.ts";
import { localInput, localRange, offsetSummary, prepareConfirm, prepareOffset, prepareReject, prepareRun, sendSuggestionCommand, suggestionError, suggestionExceptions, suggestionSummary, timeOrder, uniformOffset } from "./session-suggestions.ts";
import { suggestionLabels as labels } from "./ui-labels.ts";
import { eventId, stageId, suggestionId as id, suggestionFixture as s, runFixture as run, offsetFixture as offset, suggestionDataFixture as data, queueFixture as item } from "./session-suggestions-fixtures.ts";

test("summaries use latest blocks, exception counts and local time without inventing offset certainty", () => {
  assert.match(suggestionSummary(data, true, "UTC"), /1 suggested · last suggested Sep 29, 14:00 · running about 12 min behind the printed schedule \(estimated\)/);
  assert.equal(suggestionSummary({ run: null, offset: null, suggestions: [] }, true), labels.none);
  assert.match(suggestionSummary({ ...data, suggestions: [{ ...s, status: "confirmed" }] }, true), /^No open suggestions/);
  assert.match(suggestionSummary({ ...data, run: { ...run, blocks: [], skips: { ...run.skips, no_planned_time: 2 } }, suggestions: [] }, false), /^Add the schedule first/);
  assert.match(suggestionSummary({ ...data, suggestions: [{ ...s, strength: "weak" }] }, true), /1 needs a closer look/);
  assert.match(offsetSummary([{ ...run.blocks[0], schedule_offset_source: "producer", schedule_offset_seconds: -600 }]), /10 min ahead of.*set by producer/);
  assert.match(offsetSummary([{ ...run.blocks[0], schedule_offset_source: "none", schedule_offset_seconds: 0 }]), /^no schedule offset applied$/);
  assert.equal(offsetSummary([]), "");
  assert.match(offsetSummary([...run.blocks, { ...run.blocks[0], ordinal: 1, first_planned_start: "2026-09-29T15:00:00Z", schedule_offset_seconds: 0, schedule_offset_source: "producer" }], "UTC"), /from Sep 29, 10:00:.*from Sep 29, 15:00: no schedule offset \(set by producer\)/);
});

test("ranges abbreviate only dates that match in the displayed local timezone", () => {
  assert.equal(localRange("2026-09-29T09:00:00Z", "2026-09-29T09:16:00Z", "UTC"), "Sep 29, 09:00–09:16");
  assert.equal(localRange("2026-09-29T23:00:00Z", "2026-09-30T00:16:00Z", "UTC"), "Sep 29, 23:00–Sep 30, 00:16");
  assert.equal(localRange("2026-09-29T23:00:00Z", "2026-09-30T00:16:00Z", "America/Los_Angeles"), "Sep 29, 16:00–17:16");
  assert.equal(localRange("2026-09-29T06:00:00Z", "2026-09-29T07:16:00Z", "America/Los_Angeles"), "Sep 28, 23:00–Sep 29, 00:16");
  assert.equal(localRange("2026-09-29T09:00:00Z", "2027-09-29T09:16:00Z", "UTC"), "Sep 29, 09:00–Sep 29, 09:16");
});

test("latest-run browser reads accept only the specific no-run 404 and retain all other failures", async () => {
  const original = globalThis.fetch;
  try {
    for (const detail of ["suggestion_run_not_found", "stage_not_found", "event_not_found", undefined, { message: "missing" }]) {
      globalThis.fetch = async () => Response.json({ detail }, { status: 404 });
      const latest = suggestionsApi(capabilityRead("session-suggestions")).latest(eventId, stageId);
      if (detail === "suggestion_run_not_found") assert.equal(await latest, null);
      else await assert.rejects(latest, (error: unknown) => error instanceof CapabilityReadError && error.status === 404);
    }
    globalThis.fetch = async () => new Response("Not found", { status: 404 });
    await assert.rejects(suggestionsApi().latest(eventId, stageId), CapabilityReadError);
    globalThis.fetch = async () => Response.json({ detail: "suggestion_run_not_found" }, { status: 503 });
    await assert.rejects(suggestionsApi().latest(eventId, stageId), CapabilityReadError);
  } finally { globalThis.fetch = original; }
});

test("confirm sends only contract fields, omits unadjusted times, validates local input and preserves seconds", () => {
  const plain = prepareConfirm(s);
  assert.deepEqual(Object.keys(plain.body).sort(), ["authority_kind", "command_id"]);
  const start = localInput(s.suggested_start), end = localInput(s.suggested_end);
  const adjusted = prepareConfirm(s, { start, end });
  assert.equal(adjusted.body.start, "2026-09-29T10:12:00.000Z"); assert.equal(adjusted.body.end, "2026-09-29T11:12:00.000Z");
  for (const invalid of [{ start: end, end: start }, { start, end: start }, { start: "", end }, { start: "2026-02-30T12:00", end }, { start: s.suggested_start, end }]) assert.throws(() => prepareConfirm(s, invalid), /valid local times/);
  assert.notEqual(plain.body.command_id, adjusted.body.command_id);
  const precise = { ...s, suggested_start: "2026-09-29T10:12:00.123Z" };
  assert.equal(prepareConfirm(precise, { start: localInput(precise.suggested_start), end }).body.start, precise.suggested_start);
});

test("reject picker is bounded within backend text contract; run uses server default cue composition", () => {
  for (const reason of labels.rejectionReasons) {
    const command = prepareReject(s, reason);
    assert.equal(command.body.reason, reason); assert.equal(command.path, `suggestions/${s.suggestion_id}/reject`);
    assert.deepEqual(Object.keys(command.body).sort(), ["authority_kind", "command_id", "reason"]);
    assert.ok(reason.trim().length > 0 && reason.length <= 500 && !reason.includes("\0"));
  }
  assert.throws(() => prepareReject(s, "unbounded choice"));
  assert.deepEqual(prepareRun(stageId), { kind: "run", path: `stages/${stageId}/runs`, body: { authority_kind: "human" } });
});

test("offset entries sort into aware timestamps, retain whole seconds, enforce bounds and clear with empty entries", () => {
  const a = localInput("2026-09-29T10:00:00Z"), b = localInput("2026-09-29T12:00:00Z");
  const draft = [{ from: b, minutes: "-120" }, { from: a, minutes: String(10 / 60) }];
  const command = prepareOffset(stageId, draft);
  assert.deepEqual(command.body.entries, [{ effective_from: "2026-09-29T10:00:00.000Z", offset_seconds: 10 }, { effective_from: "2026-09-29T12:00:00.000Z", offset_seconds: -7200 }]);
  draft[0].minutes = "20"; assert.equal(command.body.entries![1].offset_seconds, -7200);
  assert.deepEqual(prepareOffset(stageId, []).body.entries, []);
  for (const entries of [[{ from: a, minutes: "121" }], [{ from: a, minutes: "" }], [{ from: a, minutes: ".001" }], [{ from: "", minutes: "0" }], [{ from: a, minutes: "0" }, { from: a, minutes: "1" }], Array.from({ length: 21 }, () => ({ from: a, minutes: "0" }))]) assert.throws(() => prepareOffset(stageId, entries), /up to 20 entries/);
});

test("read APIs page every status, distinguish no run from outage, enforce scope and detect changed run", async () => {
  const paths: string[] = [];
  const api = suggestionsApi(async (path) => {
    paths.push(path);
    if (path.endsWith("runs/latest")) return run;
    if (path.endsWith("schedule-offset")) return { current: offset };
    if (path.includes("history?")) return { items: [offset], limit: 50, next_after: null };
    if (path.endsWith(s.suggestion_id) && !path.includes("?")) return s;
    const query = new URL(`http://test/${path}`).searchParams, status = query.get("status") as Suggestion["status"];
    return { items: status === "open" ? [{ ...s, suggestion_id: query.has("after") ? id(10) : s.suggestion_id }] : [], limit: 100, next_after: status === "open" && !query.has("after") ? s.suggestion_id : null };
  });
  const loaded = await api.load(eventId, stageId); assert.equal(loaded.suggestions.length, 2); assert.equal(loaded.offset?.version, 1);
  assert.equal((await api.read(eventId, stageId, s.suggestion_id)).suggestion_id, s.suggestion_id);
  assert.equal((await api.history(eventId, stageId)).items.length, 1);
  for (const status of ["open", "confirmed", "rejected", "superseded"]) assert.ok(paths.some((p) => p.includes(`status=${status}`)));
  assert.ok(paths.some((p) => p.includes(`after=${s.suggestion_id}`)));
  assert.equal(await suggestionsApi(async () => { throw new CapabilityReadError(404, "suggestion_run_not_found"); }).latest(eventId, stageId), null);
  await assert.rejects(suggestionsApi(async () => { throw new CapabilityReadError(503); }).latest(eventId, stageId));
  await assert.rejects(suggestionsApi(async () => ({ ...run, stage_id: id(99) })).latest(eventId, stageId), /scope_mismatch/);
  await assert.rejects(suggestionsApi(async () => ({ ...s, suggestion_id: id(99) })).read(eventId, stageId, s.suggestion_id), /scope_mismatch/);
  await assert.rejects(suggestionsApi(async () => ({ current: { ...offset, event_id: id(99) } })).current(eventId, stageId), /scope_mismatch/);
  await assert.rejects(suggestionsApi(async () => ({ items: [], limit: 50, next_after: 1 })).history(eventId, stageId, 1), /cursor_not_advancing/);
  let latestCalls = 0;
  await assert.rejects(suggestionsApi(async (path) => path.endsWith("latest") ? { ...run, run_id: ++latestCalls === 1 ? run.run_id : id(99) } : path.endsWith("schedule-offset") ? { current: null } : { items: [], next_after: null, limit: 100 }).load(eventId, stageId), /changed_during_read/);
  await assert.rejects(suggestionsApi(async (path) => path.endsWith("latest") ? run : path.endsWith("schedule-offset") ? { current: null } : { items: [{ ...s, status: new URL(`http://test/${path}`).searchParams.get("status") }], next_after: null, limit: 100 }).load(eventId, stageId), /changed_during_read/);
});

test("suggestion paging rejects duplicate cursors and cross-scope or wrong-status rows; time order is chronological", async () => {
  await assert.rejects(suggestionsApi(async () => ({ items: [], limit: 100, next_after: id(10) })).list(eventId, stageId, "open"), /cursor_not_advancing/);
  for (const row of [{ ...s, event_id: id(90) }, { ...s, status: "rejected" }]) await assert.rejects(suggestionsApi(async () => ({ items: [row], limit: 100, next_after: null })).list(eventId, stageId, "open"));
  const later = { ...s, suggestion_id: id(20), suggested_start: "2026-09-29T11:00:00Z" };
  assert.deepEqual(timeOrder([later, s]), [s, later]);
});

test("Work Queue reads mounted producer path, follows encoded cursors and keeps only suggestion items", async () => {
  const paths: string[] = [];
  const items = await suggestionQueue(eventId, async (path) => { paths.push(path); return { event_id: eventId, items: paths.length === 1 ? [{ ...item, decision_type: "assembly_approval_pending" }] : [item], next_cursor: paths.length === 1 ? "test+/=" : null, items_truncated: paths.length === 1, limit: 100 }; });
  assert.deepEqual(items, [item]); assert.match(paths[1], /work-queue\?limit=100&cursor=test%2B%2F%3D/);
  await assert.rejects(suggestionQueue(eventId, async () => ({ event_id: id(99), items: [], next_cursor: null, items_truncated: false, limit: 100 })), /scope_mismatch/);
  await assert.rejects(suggestionQueue(eventId, async () => ({ event_id: eventId, items: [], next_cursor: "same", items_truncated: true, limit: 100 })), /cursor_not_advancing/);
});

test("commands verify response identity, map refusals and retain identical request bodies for explicit retries", async () => {
  const commands = [prepareRun(stageId), prepareConfirm(s), prepareReject(s, labels.rejectionReasons[0]), prepareOffset(stageId, [])];
  for (const command of commands) {
    const bodies: string[] = [];
    const failed: typeof fetch = async (url, init) => { assert.equal(url, `/api/stageflow/session-suggestions/events/${eventId}/${command.path}`); assert.equal(init?.redirect, "error"); assert.equal(init?.cache, "no-store"); bodies.push(String(init?.body)); return Response.json({}, { status: 503 }); };
    assert.equal((await sendSuggestionCommand(eventId, stageId, command, "synthetic", failed)).saved, false);
    await sendSuggestionCommand(eventId, stageId, command, "synthetic", failed); assert.equal(bodies[0], bodies[1]);
    const decision = { command_id: command.body.command_id, suggestion_id: s.suggestion_id, actor_id: id(4), decided_at: run.created_at, kind: command.kind === "confirm" ? "confirmed" : "rejected", reason: command.body.reason ?? null, session_id: command.kind === "confirm" ? id(30) : null, used_start: command.kind === "confirm" ? s.suggested_start : null, used_end: command.kind === "confirm" ? s.suggested_end : null };
    const payload = command.kind === "run" ? run : command.kind === "offset" ? { ...offset, command_id: command.body.command_id } : decision;
    assert.equal((await sendSuggestionCommand(eventId, stageId, command, "synthetic", async () => Response.json(payload))).saved, true);
    assert.equal((await sendSuggestionCommand(eventId, stageId, command, "synthetic", async () => Response.json({ ...payload, event_id: id(99), command_id: id(99) }))).uncertain, true);
    assert.equal((await sendSuggestionCommand(eventId, stageId, command, "synthetic", async () => new Response("bad"))).uncertain, true);
  }
  for (const [status, detail, expected] of [[409, "stale_expectation_revision", labels.stale], [409, "expectation_already_realized", labels.linked], [409, "suggestion_not_open", labels.closed], [409, "kernel conflict private", labels.conflict], [422, "private", labels.invalid], [500, "private", labels.failed], [403, "private", labels.readOnly], [404, "private", labels.missing]] as const) assert.equal(suggestionError(status, { detail }), expected);
});

test("producer offset badge appears only when rows differ from the offset stated in the summary", () => {
  const a = { ...s, schedule_offset_source: "producer" as const, schedule_offset_seconds: 480 };
  const b = { ...a, suggestion_id: id(21) };
  assert.equal(uniformOffset([a, b]), true);
  assert.ok(!suggestionExceptions(a, uniformOffset([a, b])).includes("Offset set by producer"));
  const c = { ...a, suggestion_id: id(22), schedule_offset_source: "estimated" as const, schedule_offset_seconds: 300 };
  assert.equal(uniformOffset([a, c]), false);
  assert.ok(suggestionExceptions(a, uniformOffset([a, c])).includes("Offset set by producer"));
  assert.ok(suggestionExceptions(a).includes("Offset set by producer"));
});
