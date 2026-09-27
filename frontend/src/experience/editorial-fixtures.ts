import type { EditorialCandidate, EditorialQueue, PhraseLists } from "./editorial-api.ts";
const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
export const editorialFixtureEvent = id(1);
export const editorialFixtureSessions = [{ id: id(2), title: "Synthetic opening Session" }];
export function fixtureCandidate(index = 0): EditorialCandidate {
  return { candidate_moment_id: id(100 + index), operation_id: index % 2 ? null : id(200 + index), session_id: id(2), expected_session_revision: 1,
    timeline_start_microseconds: (1122 + index * 10) * 1_000_000, timeline_end_microseconds: index === 0 ? null : (1130 + index * 10) * 1_000_000,
    session_authoritative_start: "2026-09-27T10:00:00Z", session_authoritative_end: null, origin: index % 2 ? "derived" : "declared", epistemic_kind: index % 2 ? "derived" : "declared",
    source_kind: index % 2 ? "transcript_phrase_match" : "producer_declaration", reason_code: index % 2 ? "transcript_phrase_match" : "human_mark_moment",
    provenance: index % 2 ? { run_id: id(3), phrase_list_id: id(4), phrase_list_version: 1, normalized_phrase: "silver lantern", asset_id: id(5), transcript_evidence_id: id(6), transcript_revision: 2, segment_id: id(7), first_word_id: id(8), last_word_id: id(9), asset_start_microseconds: 0, asset_end_microseconds: 8_000_000, timing_evidence_id: id(10), timing_revision: 3, timing_qualification: index === 1 ? "unqualified" : "qualified" } : null,
    review_state: index === 2 ? "deferred" : "unreviewed", actor_id: id(11), note: null, created_at: "2026-09-27T10:30:00Z", updated_at: "2026-09-27T10:30:00Z", location_conflict: index === 3, location_conflict_reason: index === 3 ? "partially_excluded" : null, revision: 1 };
}
export function fixtureQueue(cursor?: string): EditorialQueue {
  const offset = cursor === "fixture-page-2" ? 3 : 0;
  return { event_id: id(1), total_candidate_count: 6, pending_candidate_count: 6, oldest_pending_candidate_at: "2026-09-27T10:30:00Z", oldest_pending_age_seconds: 60, measured_at: "2026-09-27T10:31:00Z", items: Array.from({ length: 3 }, (_, i) => ({ event_id: id(1), stage_id: id(12), candidate: fixtureCandidate(offset + i), decisions: [], clips: [], history_truncated: false })), next_cursor: offset ? null : "fixture-page-2", items_truncated: !offset, limit: 3 };
}
export function fixturePhraseLists(): PhraseLists {
  return { items: [{ phrase_list_id: id(4), event_id: id(1), key: "highlights", name: "Synthetic phrases", version: 1, phrases: ["silver lantern"], created_by: id(11), created_at: "2026-09-27T10:00:00Z" }], items_truncated: false, next_after: null, limit: 100 };
}
