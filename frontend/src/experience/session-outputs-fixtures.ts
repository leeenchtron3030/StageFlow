import { assemblyItemSchema } from "./assembly-api.ts";
import { renderedOutputSchema, renderOperationSchema } from "./rendering-api.ts";
import { mediaTimingSummarySchema } from "./media-timing-api.ts";
import { outputSummary, type SessionOutputs } from "./session-outputs.ts";

// Synthetic, local-only evidence. No event recording, path, transcript, or credential.
export const fixtureId = (n: number) => `10000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const at = "2026-09-27T12:00:00Z";
export function fixtureAssembly() {
  return assemblyItemSchema.parse({
    revision: {
      revision_id: fixtureId(1), session_id: fixtureId(2), event_id: fixtureId(3), revision_number: 2,
      supersedes_id: fixtureId(4), template_id: fixtureId(5), package_revision: 1, completion_decision_id: fixtureId(6),
      membership: ["media_timing", "timing_evidence", "registration_time"].map((source, index) => ({
        asset_id: fixtureId(10 + index), association_revision: 1, media_started_at: index === 0 ? at : null,
        order_source: source, order_key_at: at, order_evidence_id: index === 1 ? fixtureId(20) : null,
        order_evidence_revision: index === 1 ? 3 : null, order_evidence_qualification: index === 1 ? "unqualified" : null,
      })),
      bindings: [{ slot_key: "opening", outcome: "bound", packaging_revision_id: fixtureId(7) }, { slot_key: "presentation", outcome: "session_media", packaging_revision_id: null }],
      metadata: [], validation: { state: "valid", issues: [] }, actor_id: fixtureId(8), created_at: at,
    }, current_revision_number: 2, stale: false, approval_state: "unreviewed", decision_count: 0, latest_decision: null,
  });
}
export function fixtureRenderOperation() {
  return renderOperationSchema.parse({ operation_id: fixtureId(30), state: "succeeded", assembly_revision_id: fixtureId(4), profile_id: "h264-nvenc-1080p-video", profile_version: "2", attempt_count: 1, reason_code: null, rendered_output_id: fixtureId(31), created_at: at, updated_at: at });
}
export function fixtureRenderedOutput() {
  return renderedOutputSchema.parse({
    output_id: fixtureId(31), assembly_revision_id: fixtureId(4), profile_id: "h264-nvenc-1080p-video", profile_version: "2", operation_id: fixtureId(30), producing_attempt_id: fixtureId(32),
    content_key: "synthetic-output", sha256: "a".repeat(64), manifest_content_key: "synthetic-manifest", manifest_sha256: "b".repeat(64), byte_size: 1024, media_type: "video/mp4",
    duration_microseconds: 60000000, frame_count: 1799, ffmpeg_version: "synthetic", ffmpeg_sha256: "c".repeat(64), produced_at: at,
  });
}
export function fixtureTiming() {
  return mediaTimingSummarySchema.parse({ asset_id: fixtureId(11), evidence: { evidence_id: fixtureId(20), revision: 3, qualification: "unqualified", limitations: ["captured_content_start_not_qualified"], limitations_truncated: false, candidate_interval: { started_at: at, ended_at: "2026-09-27T12:01:00Z" }, authorized_use: "advisory_only" } });
}
export function getFixtureSessionOutputs(): SessionOutputs {
  return {
    fixture: true, assembly: { state: "available", value: fixtureAssembly() },
    operations: { state: "available", value: { items: [fixtureRenderOperation()], truncated: false } },
    outputs: { state: "available", value: { items: [outputSummary(fixtureRenderedOutput())], truncated: false } },
    timing: [10, 11, 12].map((n) => ({ assetId: fixtureId(n), result: { state: "available", value: n === 11 ? fixtureTiming() : { asset_id: fixtureId(n), evidence: null } } })), timingTruncated: false,
  };
}
