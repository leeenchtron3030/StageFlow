import { runSchema, suggestionSchema, offsetSchema, type SuggestionData, type SuggestionQueueItem } from "./session-suggestions-api.ts";

export const suggestionId = (n: number) => `10000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
export const eventId = suggestionId(1), stageId = suggestionId(2);
export const runFixture = runSchema.parse({ run_id: suggestionId(3), event_id: eventId, stage_id: stageId, actor_id: suggestionId(4), created_at: "2026-09-29T14:00:00Z", input_digest: "a".repeat(64),
  policy: { id: "boundary-suggestion", version: "3" }, skips: { no_timing_evidence: 0, no_segmentation: 0, clock_implausible: 0, no_coverage: 0, no_planned_time: 0 },
  blocks: [{ ordinal: 0, first_planned_start: "2026-09-29T10:00:00Z", last_planned_start: "2026-09-29T12:00:00Z", talk_count: 3, schedule_offset_seconds: 720, schedule_offset_source: "estimated", estimate_score_margin: 20, override_setting_version: null }],
  override_setting_version: null, start_cue_list: null, end_cue_list: null });
export const suggestionFixture = suggestionSchema.parse({ suggestion_id: suggestionId(5), run_id: runFixture.run_id, event_id: eventId, stage_id: stageId, policy_id: "boundary-suggestion", policy_version: "3", authorized_use: "advisory_only", status: "open",
  expectation_id: suggestionId(6), expectation_revision: 1, suggested_start: "2026-09-29T10:12:00Z", suggested_end: "2026-09-29T11:12:00Z", start_edge_kind: "freeze", end_edge_kind: "gap", start_plan_offset_seconds: 720, end_plan_offset_seconds: 720,
  start_silence_support: true, end_silence_support: false, start_cue_support: false, end_cue_support: true, overlap: false, strength: "strong", timing_qualifications: ["unqualified"], timing_references: [{ id: suggestionId(7), revision: 1 }], segmentation_ids: [suggestionId(8)], transcript_references: [], schedule_offset_seconds: 720, schedule_offset_source: "estimated" });
export const offsetFixture = offsetSchema.parse({ event_id: eventId, stage_id: stageId, version: 1, command_id: suggestionId(9), set_by: suggestionId(4), set_at: "2026-09-29T14:01:00Z", authorized_use: "advisory_only", entries: [{ effective_from: "2026-09-29T09:00:00Z", offset_seconds: 600 }] });
export const suggestionDataFixture: SuggestionData = { run: runFixture, offset: null, suggestions: [suggestionFixture] };
export const suggestionNoneFixture: SuggestionData = { run: null, offset: null, suggestions: [] };
export const queueFixture: SuggestionQueueItem = { event_id: eventId, stage_id: stageId, decision_type: "presentation_confirmation_pending", subject_kind: "stage_suggestions", reason_codes: ["open_count:9", "weak_count:2"], action_reference: `stage:${stageId}:suggestions` };
export const titlesFixture = { [suggestionId(6)]: "Talk 1" };
