import { boundaryProposalSchema, type BoundaryDecision, type BoundaryDecisionHistory } from "./session-boundaries-api.ts";
import { suggestionId as id } from "./session-suggestions-fixtures.ts";
import { eventId, stageId, suggestionFixture } from "./session-suggestions-fixtures.ts";
import type { KernelStatusPayload } from "./kernel-adapter.ts";
export const sessionId = id(40);
export const currentStart = "2026-09-29T10:00:00Z", currentEnd = "2026-09-29T11:00:00Z";
export const startProposal = boundaryProposalSchema.parse({ proposal_id: id(41), session_id: sessionId, boundary_kind: "start", boundary_at: "2026-09-29T10:01:20Z", epistemic_kind: "derived", proposer_id: id(42), evidence_ids: [id(43)], policy_id: "boundary-suggestion", policy_version: "3", reason: "changeover_edge", proposed_at: "2026-09-29T14:00:00Z", authorized_use: "advisory_only" });
export const endProposal = boundaryProposalSchema.parse({ ...startProposal, proposal_id: id(44), boundary_kind: "end", boundary_at: "2026-09-29T10:59:15Z", reason: "recording_gap" });
export const realizedSessionFixture = {
  id: sessionId, title: "Talk 1", stageKey: "main", stageName: "Stage A", programExpectationId: suggestionFixture.expectation_id!,
  activityState: "presentation_ended" as const, packageState: "assembling" as const, packageRevision: 1, sessionRevision: 1,
  authoritativeStart: currentStart, authoritativeEnd: currentEnd, provenance: "declared" as const,
  media: { discovered: 0, stabilizing: 0, ready: 0, registered: 0, associated: 0, unresolved: 0, conflicting: 0 },
};
export function boundaryDecision(body: Record<string, unknown>, dismiss = false): BoundaryDecision {
  return { command_id: String(body.command_id), proposal_id: startProposal.proposal_id, session_id: sessionId, actor_id: id(4), decided_at: "2026-09-29T14:05:00Z", kind: dismiss ? "dismissed" : "applied", reason: typeof body.reason === "string" ? body.reason : null };
}

export function boundaryHistoryDecision(body: Record<string, unknown>, proposal = startProposal, dismiss = false): BoundaryDecisionHistory {
  return { ...boundaryDecision(body, dismiss), proposal_id: proposal.proposal_id, boundary_kind: proposal.boundary_kind };
}

export function boundaryKernelFixture(): KernelStatusPayload {
  const session = { session_id: sessionId, activity_state: "presentation_ended", package_state: "assembling", package_revision: 1, revision: 1, authoritative_start: currentStart, authoritative_end: currentEnd, program_expectation_title: "Talk 1", program_expectation_id: suggestionFixture.expectation_id };
  return {
    configured: true, configuration_supplied: true, configuration_valid: true, runtime_composed: true,
    event_id: eventId, event_key: "event", event_name: "Test Event", database_available: true, ready: true,
    recovering: false, reconciliation_status: "completed", reconciliation_started_at: currentStart, reconciliation_completed_at: currentStart, attention_codes: [],
    stages: [{ stage_id: stageId, key: "main", name: "Stage A", source_available: true, session_id: sessionId,
      assembling_sessions: [session], recent_sessions: [session], session_activity_state: "presentation_ended", session_package_state: "assembling", session_package_revision: 1, session_revision: 1,
      session_authoritative_start: currentStart, session_authoritative_end: currentEnd, last_media_arrived_at: currentEnd,
      discovered: 0, stabilizing: 0, ready: 0, registered: 0, associated: 0, unresolved: 0, conflicting: 0, attention_codes: [] }],
  };
}
