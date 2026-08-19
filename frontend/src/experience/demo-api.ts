import { generateUuidV4, type UuidCryptoSource } from "../shared/ids/uuid-v4.ts";

export interface DemoCommandEnvelope {
  operation_id: string;
  actor_id: string;
  confirmed: "confirmed";
  [key: string]: unknown;
}

export function createDemoCommandEnvelope(
  actorId: string,
  fields: Record<string, unknown>,
  source?: UuidCryptoSource,
): DemoCommandEnvelope {
  return {
    ...fields,
    operation_id: generateUuidV4(source),
    actor_id: actorId,
    confirmed: "confirmed",
  };
}

export interface DemoOperation {
  operation_id: string;
  asset_id: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  last_reason_code: string | null;
  created_at: string;
  updated_at: string;
}

export interface DemoTranscriptWord {
  word_id: string;
  ordinal: number;
  text: string;
  asset_start_microseconds: number;
  asset_end_microseconds: number;
  confidence: number | null;
  confidence_semantics: string | null;
}

export interface DemoTranscriptSegment {
  segment_id: string;
  ordinal: number;
  text: string;
  asset_start_microseconds: number;
  asset_end_microseconds: number;
  speaker_label: string | null;
  speaker_evidence_kind: string | null;
  confidence: number | null;
  confidence_semantics: string | null;
  limitations: string[];
  words: DemoTranscriptWord[];
  words_truncated: boolean;
  word_limit: number;
}

export interface DemoTranscriptEvidence {
  evidence_id: string;
  operation_id: string;
  asset_id: string;
  revision: number;
  status: "complete" | "partial" | "failed";
  language: string | null;
  provider_id: string;
  provider_version: string;
  model_id: string;
  model_version: string;
  produced_at: string;
  applied_at: string;
  limitations: string[];
  partial_reason: string | null;
  failure_reason: string | null;
  segments: DemoTranscriptSegment[];
  segments_truncated: boolean;
  segment_limit: number;
}

export interface DemoMoment {
  operation_id: string;
  candidate_moment_id: string;
  session_id: string;
  expected_session_revision: number;
  timeline_start_microseconds: number;
  timeline_end_microseconds: number | null;
  origin: "declared";
  epistemic_kind: "declared";
  reason_code: "human_mark_moment";
  actor_id: string;
  note: string | null;
  declared_at: string;
  revision: number;
}

export interface DemoSessionWorkspace {
  session_id: string;
  activity_state: string;
  package_state: string;
  package_revision: number;
  revision: number;
  label: "Transcription Evidence";
  authority_notice: string;
  work: {
    counts: Record<string, number>;
    oldest_eligible_at: string | null;
    active_lease_count: number;
    attention_codes: string[];
  };
  operations: DemoOperation[];
  operations_truncated: boolean;
  operation_limit: number;
  transcript_evidence: DemoTranscriptEvidence[];
  transcript_assets_truncated: boolean;
  transcript_asset_limit: number;
  moments: DemoMoment[];
}
