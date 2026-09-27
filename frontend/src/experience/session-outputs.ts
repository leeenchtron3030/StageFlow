import { assemblyApi, type AssemblyItem, type AssemblyMember } from "./assembly-api.ts";
import { renderingApi, type RenderOperation, type RenderedOutput } from "./rendering-api.ts";
import { mediaTimingApi, type MediaTimingSummary } from "./media-timing-api.ts";
import type { ApiRead } from "./outputs-api.ts";

export type ReadResult<T> = { state: "available"; value: T } | { state: "unavailable" };
export type OutputSummary = Pick<RenderedOutput, "output_id" | "assembly_revision_id" | "profile_id" | "profile_version" | "duration_microseconds" | "frame_count" | "sha256" | "produced_at">;
export interface SessionOutputs {
  fixture: boolean;
  assembly: ReadResult<AssemblyItem | null>;
  operations: ReadResult<{ items: RenderOperation[]; truncated: boolean }>;
  outputs: ReadResult<{ items: OutputSummary[]; truncated: boolean }>;
  timing: Array<{ assetId: string; result: ReadResult<MediaTimingSummary> }>;
  timingTruncated: boolean;
}
export function orderingSourceLabel(source: AssemblyMember["order_source"]): string {
  return { media_timing: "Media start time", timing_evidence: "Recorder timing evidence", registration_time: "Registration time fallback" }[source];
}
export function qualificationLabel(value: AssemblyMember["order_evidence_qualification"]): string {
  if (value === null) return "Recorder timing qualification not supplied";
  return { unqualified: "Unqualified recorder timing", qualified: "Qualified recorder timing", rejected: "Rejected recorder timing", expired: "Expired recorder timing qualification" }[value];
}
export function assemblyConsequence(item: AssemblyItem): string {
  if (item.stale) return "Review required · Assembly inputs have changed. Prior decisions remain recorded.";
  if (item.revision.validation.state === "invalid") return "Review required · Assembly validation has unresolved issues.";
  if (item.approval_state === "approved") return "Assembly approved · No render is started automatically.";
  return "Review required · Assembly is not approved.";
}
export function outputSummary(output: RenderedOutput): OutputSummary {
  return { output_id: output.output_id, assembly_revision_id: output.assembly_revision_id, profile_id: output.profile_id, profile_version: output.profile_version, duration_microseconds: output.duration_microseconds, frame_count: output.frame_count, sha256: output.sha256.slice(0, 12), produced_at: output.produced_at };
}
async function available<T>(read: () => Promise<T>): Promise<ReadResult<T>> {
  try { return { state: "available", value: await read() }; }
  catch { return { state: "unavailable" }; }
}

/** Independent failures stay local to their section. No fixture fallback or command. */
export async function readSessionOutputs(eventId: string, sessionId: string, recentAssetIds: string[], reads: { assembly: ApiRead; rendering: ApiRead; timing: ApiRead }): Promise<SessionOutputs> {
  const assemblies = assemblyApi(reads.assembly);
  const renders = renderingApi(reads.rendering);
  const timing = mediaTimingApi(reads.timing);
  const [assembly, operations, outputs] = await Promise.all([
    available(async () => {
      const first = await assemblies.revisions(eventId, sessionId);
      if (first.event_id !== eventId || first.session_id !== sessionId) throw new Error("scope_mismatch");
      if (!first.items.length) {
        if (first.total_count !== 0 || first.items_truncated) throw new Error("incomplete_revision_read");
        return null;
      }
      const current = Math.max(...first.items.map((item) => item.current_revision_number));
      // The backend pages oldest first. Jump to the known current number, never
      // present the last row of the first page as the current revision.
      const page = first.items.some((item) => item.revision.revision_number === current)
        ? first : await assemblies.revisions(eventId, sessionId, current - 1);
      if (page.event_id !== eventId || page.session_id !== sessionId) throw new Error("scope_mismatch");
      const item = page.items.find((entry) => entry.revision.revision_number === entry.current_revision_number);
      if (!item || item.revision.event_id !== eventId || item.revision.session_id !== sessionId) throw new Error("current_revision_unavailable");
      return item;
    }),
    available(async () => { const page = await renders.operations(eventId, sessionId); return { items: page.items, truncated: page.next_after !== null }; }),
    available(async () => { const page = await renders.outputs(eventId, sessionId); return { items: page.items.map(outputSummary), truncated: page.next_after !== null }; }),
  ]);
  const memberIds = assembly.state === "available" ? assembly.value?.revision.membership.map((item) => item.asset_id) ?? [] : [];
  const assetIds = [...new Set([...memberIds, ...recentAssetIds])];
  // Keep reads bounded and avoid launching one request per asset simultaneously.
  const summaries: SessionOutputs["timing"] = [];
  const bounded = assetIds.slice(0, 100);
  for (let start = 0; start < bounded.length; start += 8) {
    summaries.push(...await Promise.all(bounded.slice(start, start + 8).map(async (assetId) => ({
      assetId, result: await available(async () => {
        const summary = await timing.latest(assetId);
        if (summary.asset_id !== assetId) throw new Error("scope_mismatch");
        return summary;
      }),
    }))));
  }
  return { fixture: false, assembly, operations, outputs, timing: summaries, timingTruncated: assetIds.length > bounded.length };
}
