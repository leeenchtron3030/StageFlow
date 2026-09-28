import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import * as assembly from "./assembly-api.ts";
import * as rendering from "./rendering-api.ts";
import * as editorial from "./editorial-api.ts";
import * as timing from "./media-timing-api.ts";
import { capabilityCommand } from "./outputs-api.ts";
import type { DemoMoment } from "./demo-api.ts";
import { fixtureAssembly, fixtureId, fixtureRenderedOutput, fixtureRenderOperation, fixtureTiming } from "./session-outputs-fixtures.ts";
const id = fixtureId(1);
const at = "2026-09-27T12:00:00Z";
const numbered = { limit: 100, next_after: null, items_truncated: false };
const page = { items: [], limit: 100, next_after: null };
const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });
export const provenance = {
  run_id: id, phrase_list_id: id, phrase_list_version: 1, normalized_phrase: "example phrase", asset_id: id,
  transcript_evidence_id: id, transcript_revision: 2, segment_id: id, first_word_id: id, last_word_id: id,
  asset_start_microseconds: 0, asset_end_microseconds: 200, timing_evidence_id: id, timing_revision: 3, timing_qualification: "unqualified",
};
const candidate = {
  operation_id: null, candidate_moment_id: id, session_id: id, expected_session_revision: 1,
  timeline_start_microseconds: 0, timeline_end_microseconds: 200, session_authoritative_start: at, session_authoritative_end: null,
  origin: "derived", epistemic_kind: "derived", source_kind: "transcript_phrase_match", reason_code: "transcript_phrase_match", provenance,
  review_state: "unreviewed", actor_id: id, note: null, created_at: at, updated_at: at, location_conflict: false, location_conflict_reason: null, revision: 1,
};
test("Assembly response contracts parse backend wrappers, frozen ordering, metadata and nullable fields", () => {
  const item = fixtureAssembly();
  assert.equal(assembly.assemblyRevisionsSchema.parse({ event_id: id, session_id: id, items: [item], total_count: 1, ...numbered }).items[0].revision.membership[1].order_evidence_qualification, "unqualified");
  const template = { template_id: id, event_id: id, template_key: "standard", version: 1, name: "Standard", slots: [{ key: "media", role: "session_media", required: true }], required_metadata: ["session_title"], created_at: at };
  assert.equal(assembly.assemblyTemplatesSchema.parse({ event_id: id, items: [template], total_count: 1, items_truncated: false, limit: 100, next_after: null }).items[0].version, 1);
  const override = { override_id: id, session_id: id, field: "session_title", action: "clear", values: [], sequence: 1, actor_id: id, recorded_at: at, reason: "Use program title", authority_kind: "human" };
  assert.equal(assembly.metadataOverridesSchema.parse({ event_id: id, session_id: id, items: [override], total_count: 1, ...numbered }).items[0].action, "clear");
  const decision = { decision_id: id, session_id: id, revision_id: id, sequence: 1, actor_id: id, decided_at: at, action: "approve", reason: "Reviewed", authority_kind: "human" };
  assert.equal(assembly.assemblyItemSchema.parse({ ...item, latest_decision: decision, decision_count: 1, approval_state: "approved" }).latest_decision?.action, "approve");
  assert.equal(assembly.assemblyMemberSchema.parse({ ...item.revision.membership[0], media_started_at: null, order_key_at: null }).order_key_at, null);
  assert.throws(() => assembly.assemblyItemSchema.parse({ ...item, stale: "false" }));
  assert.throws(() => assembly.assemblyMemberSchema.parse({ ...item.revision.membership[0], order_source: "filesystem_time" }));
  assert.throws(() => assembly.assemblyMemberSchema.parse({ ...item.revision.membership[0], order_key_at: "2026-09-27T12:00:00" }));
});
test("Packaging Asset responses retain content kinds, approval state and numeric cursors", () => {
  const asset = { packaging_asset_id: id, event_id: id, stage_id: null, name: "Opening", role: "opening_bumper", created_at: at };
  assert.equal(assembly.packagingAssetsSchema.parse({ event_id: id, items: [{ asset, current_revision_number: 0, decision_count: 0 }], total_count: 1, ...numbered }).items[0].current_revision_number, 0);
  const revision = { revision_id: id, packaging_asset_id: id, revision_number: 1, content: { kind: "completed_media_asset", asset_id: id }, measured_duration_microseconds: null, effective_from: null, effective_until: null, created_at: at };
  const decision = { decision_id: id, packaging_asset_id: id, revision_number: 1, sequence: 1, actor_id: id, decided_at: at, action: "revoke", reason: "Withdrawn" };
  assert.equal(assembly.packagingRevisionsSchema.parse({ event_id: id, packaging_asset_id: id, items: [{ revision, approval_state: "revoked", decision_count: 1, latest_decision: decision }], total_count: 1, ...numbered }).items[0].approval_state, "revoked");
  assert.equal(assembly.packagingRevisionSchema.parse({ ...revision, content: { kind: "external_content", content_key: "opaque", sha256: "a".repeat(64), byte_size: 1, media_type: "video/mp4" } }).content.kind, "external_content");
});
test("render response schemas parse operations and exact output metadata; malformed fields fail", () => {
  assert.equal(rendering.renderOperationsSchema.parse({ ...page, items: [fixtureRenderOperation()] }).items[0].attempt_count, 1);
  assert.equal(rendering.renderedOutputsSchema.parse({ ...page, items: [fixtureRenderedOutput()] }).items[0].frame_count, 1799);
  for (const fields of [{ frame_count: "1799" }, { sha256: "bad" }, { produced_at: "2026-09-27T12:00:00" }]) assert.throws(() => rendering.renderedOutputSchema.parse({ ...fixtureRenderedOutput(), ...fields }));
  assert.throws(() => rendering.renderOperationSchema.parse({ ...fixtureRenderOperation(), state: "invented" }));
});
test("render operation timestamps retain aware backend values and reject absent or naive times", () => {
  const operation = { ...fixtureRenderOperation(), created_at: "2026-09-27T07:00:00.123456-07:00", updated_at: "2026-09-27T14:01:00Z" };
  const parsed = rendering.renderOperationsSchema.parse({ ...page, items: [operation], next_after: id });
  assert.equal(parsed.items[0].created_at, operation.created_at);
  assert.equal(parsed.items[0].updated_at, operation.updated_at);
  assert.equal(parsed.next_after, id);
  for (const field of ["created_at", "updated_at"]) {
    for (const value of [undefined, null, "invalid", "2026-09-27T12:00:00"]) {
      assert.throws(() => rendering.renderOperationSchema.parse({ ...operation, [field]: value }));
    }
  }
});
test("media timing schemas distinguish missing evidence from advisory unqualified evidence", () => {
  assert.equal(timing.mediaTimingSummarySchema.parse({ asset_id: id, evidence: null }).evidence, null);
  assert.equal(timing.mediaTimingSummarySchema.parse(fixtureTiming()).evidence?.qualification, "unqualified");
  const operation = { operation_id: id, asset_id: id, state: "pending", attempt_count: 0, reason_code: null, profile_id: "container-creation-time", profile_version: "1", evidence_id: null };
  assert.equal(timing.mediaTimingOperationsSchema.parse({ ...page, items: [operation] }).items[0].state, "pending");
  assert.throws(() => timing.mediaTimingSummarySchema.parse({ asset_id: id, evidence: { ...fixtureTiming().evidence, authorized_use: "authoritative" } }));
});
test("Editorial response schemas support derived and declared candidates, review history, phrases and derivations", () => {
  const derived = editorial.editorialCandidateSchema.parse(candidate);
  assert.equal(derived.operation_id, null); assert.equal(derived.provenance?.timing_revision, 3);
  const declared = editorial.editorialCandidateSchema.parse({ ...candidate, operation_id: id, origin: "declared", epistemic_kind: "declared", source_kind: "producer_declaration", reason_code: "human_mark_moment", provenance: undefined });
  assert.equal(declared.origin, "declared");
  const demo: DemoMoment = { operation_id: null, candidate_moment_id: id, session_id: id, expected_session_revision: 1, timeline_start_microseconds: 0, timeline_end_microseconds: 200, origin: "derived", epistemic_kind: "derived", reason_code: "transcript_phrase_match", provenance: derived.provenance, actor_id: id, note: null, declared_at: at, revision: 1 };
  assert.equal(demo.provenance?.normalized_phrase, "example phrase");
  const decision = { review_decision_id: id, sequence: 1, operation_id: id, candidate_moment_id: id, candidate_revision: 1, actor_id: id, action: "approve_and_create_clip", reason: "Reviewed", notes: null, adjusted_timeline_start_microseconds: null, adjusted_timeline_end_microseconds: null, decided_at: at };
  const clip = { clip_id: id, session_id: id, candidate_moment_id: id, candidate_revision: 1, review_decision_id: id, timeline_start_microseconds: 0, timeline_end_microseconds: 200, created_at: at, revision: 1 };
  assert.equal(editorial.editorialReviewResultSchema.parse({ decision, clip }).clip?.revision, 1);
  assert.equal(editorial.editorialMomentsSchema.parse({ session_id: id, candidate_count: 1, latest_candidate_activity_at: at, generation_state: "healthy", location_conflict_count: 0, items: [candidate], items_truncated: false, limit: 100 }).items.length, 1);
  assert.equal(editorial.editorialQueueSchema.parse({ event_id: id, total_candidate_count: 1, pending_candidate_count: 0, oldest_pending_candidate_at: null, oldest_pending_age_seconds: null, measured_at: at, items: [{ event_id: id, stage_id: id, candidate, decisions: [decision], clips: [clip], history_truncated: false }], next_cursor: null, items_truncated: false, limit: 100 }).items[0].clips.length, 1);
  const phraseList = { phrase_list_id: id, event_id: id, key: "highlights", version: 1, name: "Highlights", phrases: ["example phrase"], created_by: id, created_at: at };
  assert.equal(editorial.phraseListsSchema.parse({ items: [phraseList], ...numbered }).items[0].phrases[0], "example phrase");
  assert.equal(editorial.derivationRunSchema.parse({ run_id: id, session_id: id, phrase_list_id: id, phrase_list_version: 1, created_by: id, created_at: at, input_asset_count: 1, candidate_ids: [id], skip_counts: { missing_timing: 0 } }).candidate_ids.length, 1);
  assert.throws(() => editorial.editorialCandidateSchema.parse({ ...candidate, origin: "machine" }));
});
test("typed clients construct same-origin reads and preserve scope and cursor parameters", async () => {
  const paths: string[] = [];
  const api = assembly.assemblyApi(async (path) => { paths.push(path); return { event_id: id, session_id: id, items: [], total_count: 0, ...numbered }; });
  await api.revisions(id, id, 7);
  assert.equal(paths[0], `events/${id}/sessions/${id}/revisions?after=7&limit=100`);
  await assert.rejects(api.revisions("../bad", id));
  globalThis.fetch = async (input, init) => {
    assert.equal(String(input), `/api/stageflow/rendering/outputs?event_id=${id}&session_id=${id}&after=${id}&limit=100`);
    assert.equal(init?.cache, "no-store"); assert.equal(new Headers(init?.headers).get("x-stageflow-api-secret"), null);
    return Response.json(page);
  };
  await rendering.renderingApi().outputs(id, id, id);
  let queuePath = "";
  await assert.rejects(editorial.editorialApi(async (path) => { queuePath = path; return {}; }).queue(id, "a+b/="));
  assert.match(queuePath, /cursor=a%2Bb%2F%3D/);
});
test("command transport is explicit, sends launch context and never retries conflict", async () => {
  let calls = 0;
  globalThis.fetch = async (_input, init) => { calls++; assert.equal(init?.method, "POST"); assert.equal(new Headers(init?.headers).get("x-stageflow-demo-launch-context"), "launch"); return Response.json({ detail: "conflict" }, { status: 409 }); };
  await assert.rejects(capabilityCommand("rendering", "requests", { confirmed: "confirmed" }, "launch", rendering.renderOperationSchema), /outputs_http_409/);
  assert.equal(calls, 1);
});
