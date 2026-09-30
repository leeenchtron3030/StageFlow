import assert from "node:assert/strict";
import { test } from "node:test";
import { boundaryCuesApi, cueCatalogSchema, cueCompositionSchema } from "./boundary-cues-api.ts";
import { cueCatalogFixture as catalog, cueCompositionFixture as current, cueCheckpointFixture } from "./boundary-cues-fixtures.ts";
import { addCustomCue, addOptIn, aggregateCues, availableOptIns, catalogMatches, composedTime, compositionDraft, cueError, cueLimits, cueProfileName, cueSummary, evidenceLabels, exceptionEvidence, groupCuePhrases, phraseKey, prepareCueCommand, profileDraft, removeCue, removedCues, restoreCue, sendCueCommand, toggleCueGroup } from "./boundary-cues.ts";
import { boundaryCueLabels as labels } from "./ui-labels.ts";
import { fixtureId as id } from "./session-outputs-fixtures.ts";

test("profiles preselect groups; aggregate follows catalog order, token dedupe and role union", () => {
  const draft = profileDraft(catalog, "conference");
  assert.deepEqual(draft.group_keys, ["openings", "closings", "inside"]);
  const result = aggregateCues(catalog, { ...draft, group_keys: [...draft.group_keys].reverse() });
  assert.deepEqual(result.rows.map((p) => p.text), ["Hello everyone", "Our shared phrase", "Thank you everyone", "Take one"]);
  assert.deepEqual([result.start, result.end], [2, 2]);
  assert.deepEqual(result.byRole.changeover[0].sources, ["Opening greetings", "Closing thanks"]);
  assert.deepEqual(result.byRole.changeover[0].evidence, [labels.scripts, labels.measured]);
  assert.deepEqual(result.byRole.segment.map((p) => p.text), ["Take one"]);
  assert.deepEqual(aggregateCues(catalog, compositionDraft(current)), result);
  assert.equal(cueSummary(catalog, null), labels.none);
  assert.match(cueSummary(catalog, current), /Conference stage · 3 groups · 2 start \/ 2 end phrases · Composed/);
  assert.deepEqual(evidenceLabels("M 1/3, R [2]"), [labels.measured, labels.scripts]);
  assert.equal(composedTime(current.composed_at, "America/Los_Angeles"), "Composed Tue 07:05");
  assert.equal(composedTime(current.composed_at, "UTC"), "Composed Tue 14:05");
});

test("remove excludes every selected default source and removes opt-ins and custom duplicates", () => {
  let draft = addCustomCue(profileDraft(catalog, "conference"), "our SHARED phrase", "start");
  draft = removeCue(catalog, draft, phraseKey("Our shared phrase"));
  assert.deepEqual(draft.exclude, [{ group_key: "openings", phrase: "Our shared phrase" }, { group_key: "closings", phrase: "OUR shared, phrase!" }]);
  assert.deepEqual(draft.custom_phrases, []);
  assert.equal(aggregateCues(catalog, draft).byRole.changeover.length, 0);
  assert.deepEqual(removeCue(catalog, draft, phraseKey("Our shared phrase")), draft);
  for (const group_key of ["openings", "closings"]) draft = addOptIn(catalog, draft, { group_key, phrase: "Optional welcome" });
  assert.equal(aggregateCues(catalog, draft).byRole.changeover[0].warning, true);
  draft = removeCue(catalog, draft, phraseKey("Optional welcome"));
  assert.deepEqual(draft.include, []);
  assert.equal(availableOptIns(catalog, draft).length, 0);
  draft = toggleCueGroup(catalog, draft, "openings");
  assert.deepEqual(draft.exclude, [{ group_key: "closings", phrase: "OUR shared, phrase!" }]);
  assert.throws(() => addOptIn(catalog, draft, { group_key: "openings", phrase: "Optional welcome" }));
  draft = toggleCueGroup(catalog, draft, "openings");
  assert.ok(!aggregateCues(catalog, draft).rows.some((p) => p.text === "Our shared phrase"));
});

test("phrase headings use first catalog source per role; evidence badges show only exceptions", () => {
  let draft = profileDraft(catalog, "conference");
  draft = addCustomCue(draft, "Synthetic separate greeting", "start");
  const result = aggregateCues(catalog, { ...draft, group_keys: [...draft.group_keys].reverse() });
  assert.deepEqual(groupCuePhrases(result.byRole.start).map((g) => [g.source, g.phrases.map((p) => p.text)]), [
    ["Opening greetings", ["Hello everyone"]], ["Custom", ["Synthetic separate greeting"]],
  ]);
  const shared = groupCuePhrases(result.byRole.changeover);
  assert.equal(shared.length, 1); assert.equal(shared[0].source, "Opening greetings");
  assert.equal(shared[0].phrases.length, 1); assert.equal(shared[0].phrases[0].sources.length - 1, 1);
  assert.deepEqual(exceptionEvidence(shared[0].phrases[0].evidence), []);
  assert.deepEqual(exceptionEvidence(evidenceLabels("M 1/2")), []);
  assert.deepEqual(exceptionEvidence(evidenceLabels("R [1]")), [labels.scripts]);
  assert.deepEqual(exceptionEvidence(evidenceLabels("R [1], M 1/2")), []);
});

test("default noisy phrases inherit warnings from catalog evidence", () => {
  const catalog = cueCheckpointFixture.catalog;
  let draft = profileDraft(catalog, "conference");
  for (const key of ["wraps", "slate"]) draft = toggleCueGroup(catalog, draft, key);
  const rows = aggregateCues(catalog, draft).rows;
  for (const text of ["moving on", "rolling", "speed", "action", "cut", "reset"]) assert.equal(rows.find((p) => p.text === text)?.warning, true);
  assert.equal(rows.find((p) => p.text === "Hello everyone")?.warning, false);
});

test("Removed deduplicates sources, persists across all group ticks, and Add back clears every exclusion", () => {
  const catalog = cueCheckpointFixture.catalog;
  const key = phraseKey("our shared phrase");
  let draft = removeCue(catalog, profileDraft(catalog, "conference"), key);
  assert.equal(removedCues(draft).length, 1);
  draft = toggleCueGroup(catalog, draft, "extra");
  assert.equal(draft.exclude.length, 3);
  assert.ok(!aggregateCues(catalog, draft).rows.some((p) => p.key === key));
  for (const group of ["openings", "closings", "extra"]) draft = toggleCueGroup(catalog, draft, group);
  assert.deepEqual(draft.exclude, []); assert.equal(removedCues(draft).length, 1);
  for (const group of ["extra", "closings", "openings"]) draft = toggleCueGroup(catalog, draft, group);
  assert.equal(draft.exclude.length, 3);
  assert.ok(!aggregateCues(catalog, draft).rows.some((p) => p.key === key));
  const command = prepareCueCommand(catalog, draft);
  assert.deepEqual(Object.keys(command).sort(), ["authority_kind", "catalog_version", "command_id", "custom_phrases", "exclude", "group_keys", "include", "profile_key"]);
  assert.deepEqual(command.exclude, draft.exclude);
  for (const choice of command.exclude) assert.ok(catalog.groups.find((g) => g.key === choice.group_key && command.group_keys.includes(g.key))?.phrases.some((p) => p.default && p.text === choice.phrase));
  draft = restoreCue(draft, key);
  assert.deepEqual(prepareCueCommand(catalog, draft).exclude, []); assert.deepEqual(removedCues(draft), []);
  assert.equal(aggregateCues(catalog, draft).rows.find((p) => p.key === key)?.sources.length, 3);
});

test("Add back restores removed opt-ins and customs, and stored exclusions seed Removed", () => {
  let draft = profileDraft(catalog, "conference");
  for (const group_key of ["openings", "closings"]) draft = addOptIn(catalog, draft, { group_key, phrase: "Optional welcome" });
  draft = addCustomCue(draft, "optional WELCOME!", "end");
  const before = aggregateCues(catalog, draft);
  const key = phraseKey("Optional welcome");
  draft = removeCue(catalog, draft, key);
  assert.equal(removedCues(draft).length, 1); assert.deepEqual(draft.include, []); assert.deepEqual(draft.custom_phrases, []);
  draft = restoreCue(draft, key);
  assert.equal(draft.include.length, 2); assert.equal(draft.custom_phrases.length, 1);
  assert.deepEqual(aggregateCues(catalog, draft), before);
  const excluded = removeCue(catalog, draft, phraseKey("Our shared phrase")).exclude;
  const stored = compositionDraft({ ...current, exclude: excluded });
  assert.equal(removedCues(stored).length, 1);
  assert.deepEqual(restoreCue(stored, phraseKey("Our shared phrase")).exclude, []);
});

test("removing a partially excluded stored phrase keeps one undo entry and restores all sources", () => {
  const key = phraseKey("Our shared phrase");
  const stored = compositionDraft({ ...current, exclude: [{ group_key: "openings", phrase: "Our shared phrase" }] });
  const removed = removeCue(catalog, stored, key);
  assert.equal(removedCues(removed).length, 1); assert.equal(removed.exclude.length, 2);
  assert.equal(stored.exclude.length, 1); // Editing leaves stored provenance intact.
  const restored = restoreCue(removed, key);
  assert.deepEqual(restored.exclude, []); assert.deepEqual(removedCues(restored), []);
  assert.equal(aggregateCues(catalog, restored).rows.find((p) => p.key === key)?.sources.length, 2);
  assert.deepEqual(restoreCue(restored, key), restored);
});

test("draft and stored summaries derive Custom from groups, includes, excludes and customs", () => {
  const base = profileDraft(catalog, "conference");
  assert.equal(cueProfileName(catalog, base), "Conference stage");
  assert.equal(cueProfileName(catalog, { ...base, group_keys: [...base.group_keys].reverse() }), "Conference stage");
  const edits = [toggleCueGroup(catalog, base, "inside"),
    addOptIn(catalog, base, { group_key: "openings", phrase: "Optional welcome" }),
    removeCue(catalog, base, phraseKey("Hello everyone")), addCustomCue(base, "Synthetic custom", "end")];
  for (const draft of edits) {
    assert.equal(cueProfileName(catalog, draft), "Custom (based on Conference stage)");
    const stored = { ...current, groups: draft.group_keys.map((key) => ({ key, version: 1 })), include: draft.include, exclude: draft.exclude, custom_phrases: draft.custom_phrases };
    assert.match(cueSummary(catalog, stored), /^Custom \(based on Conference stage\)/);
  }
  assert.equal(cueProfileName(catalog, restoreCue(edits[2], phraseKey("Hello everyone"))), "Conference stage");
  assert.equal(cueProfileName(catalog, toggleCueGroup(catalog, edits[0], "inside")), "Conference stage");
});

test("custom additions validate text and roles, normalize unicode, and union with catalog roles", () => {
  let draft = addCustomCue(profileDraft(catalog, "conference"), "  ＨＥＬＬＯ everyone!  ", "end");
  assert.equal(aggregateCues(catalog, draft).byRole.changeover.length, 2);
  draft = addCustomCue(draft, "Private synthetic phrase", "changeover");
  assert.deepEqual(aggregateCues(catalog, draft).rows.at(-1)?.sources, [labels.custom]);
  for (const text of ["", "!!!", "x".repeat(101), "one\ntwo"]) assert.throws(() => addCustomCue(draft, text, "start"));
  assert.throws(() => addCustomCue(draft, "phrase", "segment" as "start"));
  assert.equal(addCustomCue(draft, "a".repeat(100), "start").custom_phrases.at(-1)?.text.length, 100);
});

test("list counters block zero and 201, allow 200, and do not count inside-session phrases", () => {
  const empty = profileDraft(catalog, null);
  assert.equal(cueLimits(catalog, empty).length, 2);
  assert.throws(() => prepareCueCommand(catalog, empty));
  const draft = { ...empty, custom_phrases: Array.from({ length: 200 }, (_, i) => ({ text: `synthetic phrase ${i}`, role: "changeover" as const })) };
  assert.deepEqual(cueLimits(catalog, draft), []);
  assert.deepEqual([aggregateCues(catalog, draft).start, aggregateCues(catalog, draft).end], [200, 200]);
  const large = addCustomCue(draft, "one more phrase", "start");
  assert.match(cueLimits(catalog, large)[0], /Start: 201 phrases.*200-phrase limit/);
  assert.equal(cueLimits(catalog, large).length, 1);
  assert.throws(() => prepareCueCommand(catalog, large));
  const inside = { ...empty, group_keys: ["inside"] };
  assert.deepEqual([aggregateCues(catalog, inside).start, aggregateCues(catalog, inside).end], [0, 0]);
  assert.equal(cueLimits(catalog, { ...draft, custom_phrases: Array(401).fill(draft.custom_phrases[0]) }).at(-1), labels.tooManyChoices);
});

test("API parses scoped fixtures and pages; malformed timestamps, scopes and cursors are refused", async () => {
  const paths: string[] = [];
  const api = boundaryCuesApi(async (path) => { paths.push(path); return path.endsWith("catalog") ? catalog : path.includes("history?") ? { items: [current], limit: 50, next_after: 1 } : { current }; });
  const result = await api.load(current.event_id);
  assert.deepEqual(result.current, current); assert.equal(result.history.next_after, 1);
  assert.ok(paths.includes(`events/${current.event_id}/boundary-cue-catalog`));
  await assert.rejects(api.history(current.event_id, 1), /cursor_not_advancing/);
  await assert.rejects(api.current(id(90)), /scope_mismatch/);
  await assert.rejects(api.history(id(90)), /scope_mismatch/);
  assert.equal(await boundaryCuesApi(async () => ({ current: null })).current(current.event_id), null);
  assert.deepEqual(cueCatalogSchema.parse(catalog), catalog);
  assert.throws(() => cueCompositionSchema.parse({ ...current, composed_at: "2026-09-29T12:00:00" }));
  assert.equal(catalogMatches(catalog, { ...current, catalog_digest: "c".repeat(64) }), false);
  assert.match(cueSummary(catalog, { ...current, catalog_version: 2 }), /phrase counts unavailable/);
});

test("publish body matches composition API, snapshots edits, preserves retry and validates result identity", async () => {
  const draft = addCustomCue(addOptIn(catalog, profileDraft(catalog, "conference"), { group_key: "openings", phrase: "Optional welcome" }), "Custom closing", "end");
  const command = prepareCueCommand(catalog, draft);
  assert.deepEqual(Object.keys(command).sort(), ["authority_kind", "catalog_version", "command_id", "custom_phrases", "exclude", "group_keys", "include", "profile_key"]);
  assert.equal(command.authority_kind, "human"); assert.equal(command.catalog_version, 1);
  assert.deepEqual(command.include, draft.include); assert.deepEqual(command.custom_phrases, draft.custom_phrases);
  draft.group_keys.pop(); assert.equal(command.group_keys.length, 3);
  const bodies: string[] = [];
  const failed: typeof fetch = async (url, init) => {
    assert.equal(url, `/api/stageflow/session-suggestions/events/${current.event_id}/boundary-cues`);
    assert.equal(init?.method, "POST"); assert.equal(init?.redirect, "error"); assert.equal(init?.cache, "no-store");
    bodies.push(String(init?.body)); throw new Error("synthetic offline");
  };
  assert.equal((await sendCueCommand(current.event_id, command, "synthetic", failed)).retry, true);
  await sendCueCommand(current.event_id, command, "synthetic", failed); assert.equal(bodies[0], bodies[1]);
  const success = await sendCueCommand(current.event_id, command, "synthetic", async () => Response.json({ ...current, command_id: command.command_id }));
  assert.equal(success.saved, true);
  for (const payload of [{ ...current, command_id: id(90) }, { ...current, command_id: command.command_id, event_id: id(90) }, {}]) {
    assert.equal((await sendCueCommand(current.event_id, command, "synthetic", async () => Response.json(payload))).retry, true);
  }
});

test("backend refusals use readable messages, counts and conflict guidance without raw details", async () => {
  assert.match(cueError(422, { detail: { code: "cue_list_empty", role: "end", count: 0 } }), /End: 0 phrases.*Add at least one/);
  assert.match(cueError(422, { detail: { code: "cue_list_too_large", role: "start", count: 205 } }), /Start: 205 phrases.*200-phrase limit/);
  assert.equal(cueError(409, {}), labels.conflict);
  for (const [status, expected] of [[403, labels.readOnly], [413, labels.tooLarge], [422, labels.invalidChoices], [503, labels.failed], [404, labels.eventUnavailable]] as const) assert.equal(cueError(status, { detail: "private_raw_key" }), expected);
  const command = prepareCueCommand(catalog, profileDraft(catalog, "conference"));
  const result = await sendCueCommand(current.event_id, command, "synthetic", async () => Response.json({ detail: "command_conflict" }, { status: 409 }));
  assert.equal(result.retry, false); assert.equal(result.saved, false); assert.equal(result.message, labels.conflict);
  const nonJson = await sendCueCommand(current.event_id, command, "synthetic", async () => new Response("", { status: 409 }));
  assert.equal(nonJson.message, labels.conflict); assert.equal(nonJson.retry, false);
});

test("re-adding a removed phrase as custom un-removes it everywhere; notice wording is singular for one", () => {
  const catalog = cueCheckpointFixture.catalog;
  const key = phraseKey("our shared phrase");
  let draft = removeCue(catalog, profileDraft(catalog, "conference"), key);
  assert.equal(removedCues(draft).length, 1);
  draft = addCustomCue(draft, "Our shared phrase", "start");
  assert.deepEqual(removedCues(draft), []);
  assert.ok(!draft.exclude.some((c) => phraseKey(c.phrase) === key));
  assert.ok(aggregateCues(catalog, draft).rows.some((p) => p.key === key));
  assert.equal(labels.stayRemoved(1), "1 removed phrase stays removed");
  assert.equal(labels.stayRemoved(2), "2 removed phrases stay removed");
});
