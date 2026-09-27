import { z } from "zod";
import { capabilityRead, countSchema as count, idSchema as id, numberedPageFields, qualificationSchema, revisionSchema as revision, timestampSchema as time, query, type ApiRead } from "./outputs-api.ts";
export const editorialProvenanceSchema = z.object({
  run_id: id, phrase_list_id: id, phrase_list_version: revision, normalized_phrase: z.string(), asset_id: id,
  transcript_evidence_id: id, transcript_revision: revision, segment_id: id, first_word_id: id, last_word_id: id,
  asset_start_microseconds: count, asset_end_microseconds: count, timing_evidence_id: id, timing_revision: revision, timing_qualification: qualificationSchema,
});
export type EditorialProvenance = z.infer<typeof editorialProvenanceSchema>;
export const editorialCandidateSchema = z.object({
  operation_id: id.nullable(), candidate_moment_id: id, session_id: id, expected_session_revision: revision,
  timeline_start_microseconds: count, timeline_end_microseconds: count.nullable(), session_authoritative_start: time, session_authoritative_end: time.nullable(),
  origin: z.enum(["declared", "derived"]), epistemic_kind: z.enum(["declared", "derived"]), source_kind: z.enum(["producer_declaration", "transcript_phrase_match"]),
  reason_code: z.enum(["human_mark_moment", "transcript_phrase_match"]), provenance: editorialProvenanceSchema.nullable().optional(),
  review_state: z.enum(["unreviewed", "approved", "rejected", "revision_requested", "deferred"]), actor_id: id, note: z.string().nullable(),
  created_at: time, updated_at: time, location_conflict: z.boolean(), location_conflict_reason: z.string().nullable(), revision,
});
export const editorialMomentsSchema = z.object({ session_id: id, candidate_count: count, latest_candidate_activity_at: time.nullable(), generation_state: z.enum(["healthy", "unknown"]), location_conflict_count: count, items: z.array(editorialCandidateSchema), items_truncated: z.boolean(), limit: revision.max(100) });
export const editorialDecisionSchema = z.object({
  review_decision_id: id, sequence: revision, operation_id: id, candidate_moment_id: id, candidate_revision: revision, actor_id: id,
  action: z.enum(["approve_and_create_clip", "reject", "revise_range", "defer"]), reason: z.string(), notes: z.string().nullable(),
  adjusted_timeline_start_microseconds: count.nullable(), adjusted_timeline_end_microseconds: count.nullable(), decided_at: time,
});
export const editorialClipSchema = z.object({ clip_id: id, session_id: id, candidate_moment_id: id, candidate_revision: revision, review_decision_id: id, timeline_start_microseconds: count, timeline_end_microseconds: count, created_at: time, revision });
export const editorialReviewResultSchema = z.object({ decision: editorialDecisionSchema, clip: editorialClipSchema.nullable() });
export const editorialQueueSchema = z.object({
  event_id: id, total_candidate_count: count, pending_candidate_count: count, oldest_pending_candidate_at: time.nullable(), oldest_pending_age_seconds: count.nullable(), measured_at: time,
  items: z.array(z.object({ event_id: id, stage_id: id, candidate: editorialCandidateSchema, decisions: z.array(editorialDecisionSchema), clips: z.array(editorialClipSchema), history_truncated: z.boolean() })),
  next_cursor: z.string().nullable(), items_truncated: z.boolean(), limit: revision.max(100),
});
export const phraseListSchema = z.object({ phrase_list_id: id, event_id: id, key: z.string(), version: revision, name: z.string(), phrases: z.array(z.string()), created_by: id, created_at: time });
export const phraseListsSchema = z.object({ items: z.array(phraseListSchema), ...numberedPageFields });
export const derivationRunSchema = z.object({ run_id: id, session_id: id, phrase_list_id: id, phrase_list_version: revision, created_by: id, created_at: time, input_asset_count: count, candidate_ids: z.array(id), skip_counts: z.record(z.string(), count) });
export function editorialApi(read: ApiRead = capabilityRead("editorial")) {
  return {
    moments: async (sessionId: string) => editorialMomentsSchema.parse(await read(`sessions/${id.parse(sessionId)}/moments?limit=100`)),
    queue: async (eventId: string, cursor?: string) => editorialQueueSchema.parse(await read(`events/${id.parse(eventId)}/review-queue?${query({ cursor, limit: 100 })}`)),
    phraseLists: async (eventId: string, key: string, after = 0) => phraseListsSchema.parse(await read(`events/${id.parse(eventId)}/phrase-lists?${query({ key, after, limit: 100 })}`)),
  };
}
