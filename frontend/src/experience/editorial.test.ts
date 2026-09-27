import assert from "node:assert/strict";
import { test } from "node:test";
import { editorialApi, editorialQueueSchema, type DerivationRun } from "./editorial-api.ts";
import { fixtureCandidate, fixtureQueue, fixturePhraseLists, editorialFixtureEvent as eventId } from "./editorial-fixtures.ts";
import { candidateLabel, candidateFlags, queueSummary, momentsSummary, momentsRefreshToken, derivationSummary, timelinePosition } from "./editorial-presentation.ts";
import { normalizePhrase, wordTokens, phrasePreview } from "./editorial-normalization.ts";
import { authorityDisabled, intentError, prepareEditorialCommand, sendEditorialCommand, secondsToMicroseconds, type EditorialAuthority, type EditorialIntent } from "./editorial-actions.ts";
import { loadEditorialQueue } from "./editorial.server.ts";
import { getFixtureWorkspace } from "./fixtures.ts";
import { createReadBudget } from "./read-budget.ts";

const context: EditorialAuthority = { eventId, fixture: false, authoritative: true, operatorAvailable: true, launchContext: "synthetic-launch" };
const candidate = fixtureCandidate(1);
const review = (action: "approve_and_create_clip" | "reject" | "revise_range" | "defer" = "approve_and_create_clip"): EditorialIntent => ({ kind: "review", candidate, action, reason: "Synthetic review reason" });
const publish: EditorialIntent = { kind: "publish", key: " highlights ", name: "Synthetic phrases", version: 2, text: "silver lantern\nBlue moon" };
const derive: EditorialIntent = { kind: "derive", sessionId: candidate.session_id, phraseListId: candidate.provenance!.phrase_list_id, version: 1 };
export function runFixture(): DerivationRun {
  return { run_id: candidate.provenance!.run_id, session_id: candidate.session_id, phrase_list_id: candidate.provenance!.phrase_list_id, phrase_list_version: 1, created_by: candidate.actor_id, created_at: candidate.created_at, input_asset_count: 4, candidate_ids: [candidate.candidate_moment_id], skip_counts: { no_transcript: 0, no_timing_evidence: 2, outside_session: 1, limit_reached: 0 } };
}
function reviewResult() {
  return { decision: { review_decision_id: candidate.candidate_moment_id, sequence: 1, operation_id: candidate.candidate_moment_id, candidate_moment_id: candidate.candidate_moment_id, candidate_revision: 1, actor_id: candidate.actor_id, action: "defer", reason: "Synthetic reason", notes: null, adjusted_timeline_start_microseconds: null, adjusted_timeline_end_microseconds: null, decided_at: candidate.created_at }, clip: null };
}

test("queue uses bounded Event pages and opaque cursors, summaries distinguish global and page counts", async () => {
  const paths: string[] = [];
  const api = editorialApi(async (path) => { paths.push(path); return fixtureQueue(paths.length > 1 ? "fixture-page-2" : undefined); });
  const first = await api.queue(eventId), second = await api.queue(eventId, first.next_cursor!);
  assert.equal(first.items.length, 3); assert.equal(second.items.length, 3);
  assert.equal(new Set([...first.items, ...second.items].map((i) => i.candidate.candidate_moment_id)).size, 6);
  assert.equal(second.next_cursor, null);
  assert.match(paths[0], new RegExp(`events/${eventId}/review-queue\\?limit=100$`));
  assert.match(paths[1], /cursor=fixture-page-2&limit=100$/);
  assert.equal(queueSummary(first), "6 awaiting review · 6 total · this page: 1 suggested");
  assert.equal(queueSummary(second), "6 awaiting review · 6 total · this page: 2 suggested · 1 outside Session");
  await assert.rejects(() => api.queue("untrusted/path"));
  assert.throws(() => editorialQueueSchema.parse({ ...first, limit: 101 }));
});
test("phrase-list client carries Event/key/version paging; Session moments are bounded", async () => {
  const paths: string[] = [];
  const api = editorialApi(async (path) => { paths.push(path); return fixturePhraseLists(); });
  await api.phraseLists(eventId, "a & b", 3);
  assert.match(paths[0], /key=a\+%26\+b&after=3&limit=100$/);
  const momentsApi = editorialApi(async (path) => { paths.push(path); return { session_id: candidate.session_id, candidate_count: 1, latest_candidate_activity_at: null, generation_state: "healthy", location_conflict_count: 0, items: [candidate], items_truncated: false, limit: 100 }; });
  const moments = await momentsApi.moments(candidate.session_id);
  assert.equal(moments.items[0].review_state, "unreviewed");
  assert.match(paths[1], /\/moments\?limit=100$/);
});
test("row labels use Session timeline and duration, exception flags never repeat qualified timing", () => {
  assert.equal(candidateLabel(candidate, "Opening Session"), "Opening Session · 00:18:52 · 8 s");
  assert.equal(timelinePosition(3661000000), "01:01:01");
  assert.match(candidateLabel(fixtureCandidate()), /Single point: set start and end/);
  assert.match(candidateLabel(candidate), /^00:18:52/);
  assert.deepEqual(candidateFlags(candidate), ["Recorder time (unverified)"]);
  assert.deepEqual(candidateFlags(fixtureCandidate(3)), ["Outside Session", "Recorder time (verified)"]);
  assert.deepEqual(candidateFlags(fixtureCandidate(2)), []);
  assert.deepEqual(candidateFlags({ ...candidate, provenance: { ...candidate.provenance!, timing_qualification: "expired" } }), ["Recorder time (verification expired)"]);
});
test("normalization mirrors backend fullwidth, sharp-s, punctuation and empty-token cases", () => {
  // backend/tests/test_derived_editorial_candidates.py:96–114
  assert.equal(normalizePhrase("  ＳＩＬＶＥＲ\tLantern  "), "silver lantern");
  assert.equal(normalizePhrase("Straße"), "strasse");
  for (const text of [" ＳＩＬＶＥＲ\tLantern \nsilver lantern", "Straße\nSTRASSE", "a, b\na b"]) {
    assert.equal(phrasePreview(text).rows[1].error, "Duplicate token sequence");
    assert.equal(phrasePreview(text).valid, false);
  }
  assert.equal(phrasePreview("!").rows[0].error, "No word tokens");
  assert.deepEqual(wordTokens("a_b"), ["a", "b"]);
});
test("Unicode casefold, whitespace, numeric and combining token parity", () => {
  assert.equal(normalizePhrase("ΟΣ ος ẞ ﬃ İ Ꭰ ꭰ"), "οσ οσ ss ffi i\u0307 Ꭰ Ꭰ");
  assert.equal(normalizePhrase("a\u001cb\u0085c\ufeffd"), "a b c\ufeffd");
  assert.deepEqual(wordTokens("İ ¼ 中文 e\u0301"), ["i", "1", "4", "中文", "é"]);
  assert.equal(phrasePreview("😀".repeat(2)).valid, false);
  assert.equal(phrasePreview("𐐀".repeat(100)).valid, true);
  assert.equal(phrasePreview("x".repeat(101)).valid, false);
  assert.equal(phrasePreview(Array.from({ length: 200 }, (_, i) => String(i)).join("\n")).valid, true);
  assert.equal(phrasePreview(Array.from({ length: 201 }, (_, i) => String(i)).join("\n")).valid, false);
  assert.equal(phrasePreview("\nword").valid, true);
});
test("blank phrase lines are ignored while duplicates and punctuation remain invalid", () => {
  const text = "\n  \r\nsilver lantern\r\n\t\n Blue moon \n\n";
  const preview = phrasePreview(text);
  assert.equal(preview.valid, true);
  assert.deepEqual(preview.rows.map((row) => [row.line, row.phrase]), [[3, "silver lantern"], [5, "Blue moon"]]);
  assert.deepEqual(prepareEditorialCommand(context, { ...publish, text } as EditorialIntent, true)?.body.phrases, ["silver lantern", "Blue moon"]);
  for (const invalid of [" \n\t\n", "silver lantern\n\nSILVER LANTERN\n", "silver lantern\n\n!!!\n"]) {
    assert.equal(phrasePreview(invalid).valid, false);
    assert.equal(prepareEditorialCommand(context, { ...publish, text: invalid } as EditorialIntent, true), undefined);
  }
});
test("approval sends adjusted range only for a changed range or a point mark", () => {
  const start = candidate.timeline_start_microseconds, end = candidate.timeline_end_microseconds!;
  const unchanged = prepareEditorialCommand(context, { ...review(), start, end } as EditorialIntent, true)!;
  assert.equal("adjusted_timeline_start_microseconds" in unchanged.body, false);
  assert.equal("adjusted_timeline_end_microseconds" in unchanged.body, false);
  for (const range of [{ start: start + 1, end }, { start, end: end + 1 }]) {
    const changed = prepareEditorialCommand(context, { ...review(), ...range } as EditorialIntent, true)!;
    assert.equal(changed.body.adjusted_timeline_start_microseconds, range.start);
    assert.equal(changed.body.adjusted_timeline_end_microseconds, range.end);
  }
  const point = fixtureCandidate();
  const ranged = prepareEditorialCommand(context, { ...review(), candidate: point, start: point.timeline_start_microseconds, end: point.timeline_start_microseconds + 1 } as EditorialIntent, true)!;
  assert.equal(ranged.body.adjusted_timeline_start_microseconds, point.timeline_start_microseconds);
  assert.equal(ranged.body.adjusted_timeline_end_microseconds, point.timeline_start_microseconds + 1);
});
test("moments refresh token follows identity and count, not workspace object or ordering", () => {
  const moments = [fixtureCandidate(), candidate];
  assert.equal(momentsRefreshToken(moments), momentsRefreshToken(moments.map((item) => ({ ...item })).reverse()));
  assert.notEqual(momentsRefreshToken(moments), momentsRefreshToken([moments[0]]));
  assert.notEqual(momentsRefreshToken(moments), momentsRefreshToken([moments[0], fixtureCandidate(2)]));
});
test("newer browser Unicode characters retain backend empty-token and separator semantics", () => {
  // Python 3.13 / Unicode 15.1 leaves these unassigned; newer engines map or classify them.
  for (const value of ["\u{1ccd6}", "\u1c89", "\u{1e5d0}"]) {
    assert.equal(normalizePhrase(value), value);
    assert.deepEqual(wordTokens(value), []);
    assert.equal(phrasePreview(value).rows[0].error, "No word tokens");
    assert.deepEqual(wordTokens(`a${value}b`), ["a", "b"]);
  }
  assert.equal(normalizePhrase("e\u0301\u{1ccd6}A\u030a"), "é\u{1ccd6}å");
});
for (const action of ["approve_and_create_clip", "reject", "revise_range", "defer"] as const) test(`${action} requires confirmation, reason and candidate revision; range fields follow backend`, () => {
  const intent = { ...review(action), ...(action === "revise_range" ? { start: 0, end: 1_000_000 } : {}) } as EditorialIntent;
  assert.equal(prepareEditorialCommand(context, intent, false), undefined);
  assert.equal(prepareEditorialCommand(context, { ...intent, reason: " " } as EditorialIntent, true), undefined);
  const command = prepareEditorialCommand(context, intent, true)!;
  assert.equal(command.path, `/api/stageflow/editorial/moments/${candidate.candidate_moment_id}/reviews`);
  assert.match(command.body.operation_id as string, /^[\da-f]{8}-[\da-f]{4}-4[\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/);
  assert.equal(command.body.expected_candidate_revision, 1);
  assert.equal(command.body.action, action); assert.equal(command.body.reason, "Synthetic review reason");
  assert.equal(command.body.confirmed, "confirmed"); assert.equal(command.body.actor_id, undefined);
  assert.equal(command.body.expected_decision_count, undefined);
  assert.equal(command.body.adjusted_timeline_start_microseconds, action === "revise_range" ? 0 : undefined);
  assert.ok(Object.isFrozen(command.body));
});
test("range validation handles point marks, reversals, fractions, and forbidden action fields", () => {
  assert.match(intentError({ ...review(), candidate: fixtureCandidate() } as EditorialIntent)!, /Set a range/);
  assert.equal(intentError({ ...review(), start: 0, end: 0 } as EditorialIntent), undefined);
  for (const range of [{ start: -1, end: 10 }, { start: 2, end: 1 }, { start: NaN, end: 3 }, { start: 0.5, end: 3 }, { start: 1 }]) assert.ok(intentError({ ...review(), ...range } as EditorialIntent));
  assert.ok(intentError(review("revise_range")));
  assert.ok(intentError({ ...review("reject"), start: 1, end: 2 } as EditorialIntent));
  assert.ok(intentError({ ...review("defer"), start: 1, end: 2 } as EditorialIntent));
});
test("Session decimal seconds preserve microseconds without floating-point false rejections", () => {
  assert.equal(secondsToMicroseconds("0.000249"), 249);
  assert.equal(secondsToMicroseconds("1123.123456"), 1123123456);
  assert.equal(secondsToMicroseconds("0"), 0);
  for (const input of ["", "-1", "0.1234567", "1e9", "9999999999999999999"]) assert.ok(Number.isNaN(secondsToMicroseconds(input)));
});
test("all commands gate fixture, unavailable runtime, operator, launch and invalid Event", () => {
  const intents: EditorialIntent[] = [review(), publish, derive];
  for (const patch of [{ fixture: true }, { authoritative: false }, { operatorAvailable: false }, { launchContext: undefined }, { eventId: "unknown" }]) {
    assert.ok(authorityDisabled({ ...context, ...patch }));
    intents.forEach((intent) => assert.equal(prepareEditorialCommand({ ...context, ...patch }, intent, true), undefined));
  }
});
test("publish and derive commands use distinct UUIDs, exact version and no browser actor", () => {
  const published = prepareEditorialCommand(context, publish, true)!;
  assert.deepEqual({ ...published.body, command_id: undefined }, { command_id: undefined, confirmed: "confirmed", key: "highlights", name: "Synthetic phrases", version: 2, phrases: ["silver lantern", "Blue moon"] });
  const derived = prepareEditorialCommand(context, derive, true)!;
  assert.deepEqual({ ...derived.body, command_id: undefined }, { command_id: undefined, confirmed: "confirmed", phrase_list_id: candidate.provenance!.phrase_list_id, version: 1 });
  assert.notEqual(published.body.command_id, derived.body.command_id);
  assert.ok(intentError({ ...publish, text: "a,b\na b" }));
  assert.ok(intentError({ ...derive, version: 0 }));
});
test("derivation and moments summaries show nonzero exceptions and actual review state counts", () => {
  assert.equal(derivationSummary(runFixture()), "1 moment · 2 skipped: no timing evidence · 1 skipped: outside session");
  assert.equal(momentsSummary([fixtureCandidate(), candidate, fixtureCandidate(2)]), "2 marked · 1 suggested · 2 awaiting review · 1 deferred");
});
test("same command object retries only after transport failure; success refreshes and parses run", async () => {
  const command = prepareEditorialCommand(context, derive, true)!;
  const bodies: string[] = []; let refreshes = 0;
  const fetcher: typeof fetch = async (url, init) => { assert.equal(url, command.path); bodies.push(String(init?.body)); assert.equal(init?.cache, "no-store"); if (bodies.length === 1) throw new TypeError(); return Response.json(runFixture()); };
  assert.equal((await sendEditorialCommand(command, fetcher, async () => { refreshes++; })).kind, "network_failure");
  assert.equal(bodies.length, 1); assert.equal(refreshes, 0);
  const success = await sendEditorialCommand(command, fetcher, async () => { refreshes++; });
  assert.equal(success.kind, "succeeded"); assert.equal(success.message, derivationSummary(runFixture()));
  assert.equal(bodies[0], bodies[1]); assert.equal(refreshes, 1);
});
for (const status of [409, 422, 503]) test(`HTTP ${status} never retries and only conflict refreshes`, async () => {
  let calls = 0, refreshes = 0;
  const result = await sendEditorialCommand(prepareEditorialCommand(context, review(), true)!, async () => { calls++; return Response.json({ detail: "synthetic_conflict" }, { status }); }, async () => { refreshes++; });
  assert.equal(calls, 1); assert.equal(refreshes, status === 409 ? 1 : 0);
  assert.equal(result.kind, status === 409 ? "conflict" : "failed");
});
test("review and publish success parse identifiers; malformed success refreshes without replay", async () => {
  for (const [intent, payload, expected] of [[review("defer"), reviewResult(), "Moment deferred."], [publish, fixturePhraseLists().items[0], "Synthetic phrases · version 1 published."], [review(), {}, "Command response incomplete; refreshed. Check current state."]] as const) {
    let refreshed = false;
    const result = await sendEditorialCommand(prepareEditorialCommand(context, intent, true)!, async () => Response.json(payload), async () => { refreshed = true; });
    assert.ok(refreshed); assert.equal(result.message, expected); assert.notEqual(result.kind, "network_failure");
  }
});
test("server fixture loader shares real schema and never contacts runtime", async () => {
  const original = globalThis.fetch; globalThis.fetch = async () => { assert.fail("fixture must not read runtime"); };
  const budget = createReadBudget();
  try { assert.deepEqual(await loadEditorialQueue(getFixtureWorkspace(), budget), editorialQueueSchema.parse(fixtureQueue())); }
  finally { globalThis.fetch = original; budget.dispose(); }
});
test("server runtime loader uses secret-holding allowlist and handles wrong Event/unavailability", async () => {
  const original = globalThis.fetch, secret = process.env.STAGEFLOW_API_SHARED_SECRET;
  process.env.STAGEFLOW_API_SHARED_SECRET = "synthetic-editorial-secret-0123456789abcdef";
  const workspace = getFixtureWorkspace(); workspace.dataSource.kind = "kernel"; workspace.event.id = eventId;
  const budget = createReadBudget();
  try {
    globalThis.fetch = async (url, init) => { assert.match(String(url), /\/api\/v1\/editorial\/events\/.*\/review-queue\?limit=100$/); assert.ok(new Headers(init?.headers).get("x-stageflow-api-secret")); return Response.json(fixtureQueue()); };
    assert.equal((await loadEditorialQueue(workspace, budget))?.items.length, 3);
    globalThis.fetch = async () => Response.json({ ...fixtureQueue(), event_id: candidate.session_id });
    assert.equal(await loadEditorialQueue(workspace, budget), null);
    globalThis.fetch = async () => { throw new TypeError(); };
    assert.equal(await loadEditorialQueue(workspace, budget), null);
  } finally { globalThis.fetch = original; if (secret === undefined) delete process.env.STAGEFLOW_API_SHARED_SECRET; else process.env.STAGEFLOW_API_SHARED_SECRET = secret; budget.dispose(); }
});
