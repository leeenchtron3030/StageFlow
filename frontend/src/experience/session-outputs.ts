import { uiLabels, timingLabel, renderLabel } from "./ui-labels.ts";
import { assemblyApi, type AssemblyItem, type AssemblyMember } from "./assembly-api.ts";
import { renderingApi, type RenderOperation, type RenderedOutput, type EventRenderSetting } from "./rendering-api.ts";
import { mediaTimingApi, type MediaTimingSummary } from "./media-timing-api.ts";
import type { ApiRead } from "./outputs-api.ts";
import { createReadBudget, type ReadBudget } from "./read-budget.ts";

export type ReadResult<T> = { state: "available"; value: T } | { state: "unavailable" };
export type OutputSummary = Pick<RenderedOutput, "output_id" | "assembly_revision_id" | "profile_id" | "profile_version" | "duration_microseconds" | "frame_count" | "sha256" | "produced_at" | "video_bit_rate" | "audio_bit_rate" | "event_render_setting_version">;
export interface SessionOutputs {
  fixture: boolean;
  renderSetting?: ReadResult<EventRenderSetting>;
  assembly: ReadResult<AssemblyItem | null>;
  operations: ReadResult<{ items: RenderOperation[]; truncated: boolean }>;
  outputs: ReadResult<{ items: OutputSummary[]; truncated: boolean }>;
  timing: Array<{ assetId: string; result: ReadResult<MediaTimingSummary> }>;
  timingTruncated: boolean;
  knownRevisions?: Array<{ revisionId: string; number: number }>;
  packaging?: Array<{ revisionId: string; name: string; role: string }>;
}
export function renderStateRank(state: RenderOperation["state"]): number {
  return ["pending", "leased", "running"].includes(state) ? 0 : state === "succeeded" ? 1 : 2;
}
export function sortedRenderOperations(items: RenderOperation[]) {
  // Python timestamps retain microseconds; Date.parse alone truncates them.
  const micros = (value: string) => Number((value.match(/\.(\d+)/)?.[1] ?? "").padEnd(6, "0").slice(3, 6));
  return [...items].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)
    || micros(b.created_at) - micros(a.created_at) || (b.operation_id > a.operation_id ? 1 : b.operation_id < a.operation_id ? -1 : 0));
}
export function renderTimeLabel(value: string): string {
  // Fixed UTC display avoids server/browser timezone and hydration differences.
  return new Date(value).toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
}
export function newestOutputs(items: OutputSummary[]) {
  return [...items].sort((a, b) => Date.parse(b.produced_at) - Date.parse(a.produced_at));
}
export function outputDuration(output: OutputSummary) {
  return `${(output.duration_microseconds / 1000000).toFixed(3)} seconds`;
}
export function currentRenderSummary(revisionId: string, operations?: SessionOutputs["operations"], outputs?: SessionOutputs["outputs"]): string | undefined {
  if (operations?.state !== "available") return undefined;
  const matching = operations.value.items.filter((operation) => operation.assembly_revision_id === revisionId);
  if (matching.some((operation) => renderStateRank(operation.state) === 0)) return uiLabels.render.pending;
  if (matching.some((operation) => operation.state === "succeeded")) {
    const output = outputs?.state === "available" ? newestOutputs(outputs.value.items.filter((output) => output.assembly_revision_id === revisionId))[0] : undefined;
    return `${uiLabels.render.succeeded}${output ? ` · ${outputDuration(output)}` : ""}`;
  }
  const failed = matching.find((operation) => operation.state === "terminal_failed");
  if (failed) return `${uiLabels.render.terminal_failed} · ${failed.reason_code ?? "Unknown reason"}`;
  if (matching.length) return renderLabel(matching[0].state);
}
export function orderingSourceLabel(source: AssemblyMember["order_source"]): string {
  return uiLabels.order[source];
}
export function qualificationLabel(value: AssemblyMember["order_evidence_qualification"]): string {
  return timingLabel(value);
}
export function memberOrderingLabel(member: AssemblyMember): string {
  return member.order_source === "timing_evidence"
    ? timingLabel(member.order_evidence_qualification) || uiLabels.order.timing_evidence
    : orderingSourceLabel(member.order_source);
}
export function memberOrderSummary(members: AssemblyMember[]) {
  const counts = new Map<string, number>();
  for (const member of members) {
    const label = memberOrderingLabel(member);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  const [baseline] = [...counts].sort((a, b) => b[1] - a[1])[0] ?? ["", 0];
  const arrivals = members.filter((member) => member.order_source === "registration_time").length;
  const recorder = members.length - arrivals;
  const certainties = [...counts].filter(([label]) => label !== uiLabels.order.media_timing && label !== uiLabels.order.registration_time);
  return {
    baseline,
    text: [recorder ? uiLabels.orderedByRecorder : "",
      ...certainties.map(([label, count]) => `${label}${count === recorder ? "" : ` (${count} ${count === 1 ? "recording" : "recordings"})`}`),
      arrivals ? `${arrivals} ${arrivals === 1 ? "recording" : "recordings"} ordered by arrival time (no recorder time)` : "",
    ].filter(Boolean).join(" · "),
  };
}
export function wallClockLabel(value?: string | null): string {
  // Preserve the timestamp's supplied zone; never use the server's local timezone.
  return value?.match(/T(\d{2}:\d{2}:\d{2})/)?.[1] ?? "Start unknown";
}
export function intervalDuration(interval?: { started_at: string; ended_at: string } | null): string {
  if (!interval) return "Duration unknown";
  const seconds = (Date.parse(interval.ended_at) - Date.parse(interval.started_at)) / 1000;
  if (!Number.isFinite(seconds) || seconds < 0) return "Duration unknown";
  return `${Math.floor(seconds / 60)}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`;
}
export function assemblyConsequence(item: AssemblyItem): string {
  if (item.stale) return "Review required · Assembly inputs have changed. Prior decisions remain recorded.";
  if (item.revision.validation.state === "invalid") return "Review required · Assembly validation has unresolved issues.";
  if (item.approval_state === "approved") return "Assembly approved · No render is started automatically.";
  return "Review required · Assembly is not approved.";
}
export function outputSummary(output: RenderedOutput): OutputSummary {
  return { output_id: output.output_id, assembly_revision_id: output.assembly_revision_id, profile_id: output.profile_id, profile_version: output.profile_version, duration_microseconds: output.duration_microseconds, frame_count: output.frame_count, sha256: output.sha256.slice(0, 12), produced_at: output.produced_at, video_bit_rate: output.video_bit_rate, audio_bit_rate: output.audio_bit_rate, event_render_setting_version: output.event_render_setting_version };
}
async function available<T>(read: () => Promise<T>): Promise<ReadResult<T>> {
  try { return { state: "available", value: await read() }; }
  catch { return { state: "unavailable" }; }
}

/** Independent failures stay local to their section. No fixture fallback or command. */
export async function readSessionOutputs(eventId: string, sessionId: string, recentAssetIds: string[], reads: { assembly: ApiRead; rendering: ApiRead; timing: ApiRead; packaging?: ApiRead }, sharedBudget?: ReadBudget): Promise<SessionOutputs> {
  const budget = sharedBudget ?? createReadBudget();
  try {
    const boundedRead = (read: ApiRead): ApiRead => (path) => budget.read(() => read(path));
    const assemblies = assemblyApi(boundedRead(reads.assembly));
    const renders = renderingApi(boundedRead(reads.rendering));
    const timing = mediaTimingApi(boundedRead(reads.timing));
    const knownRevisions: NonNullable<SessionOutputs["knownRevisions"]> = [];
    const remember = (items: AssemblyItem[]) => {
      for (const item of items) if (item.revision.event_id === eventId && item.revision.session_id === sessionId) {
        knownRevisions.push({ revisionId: item.revision.revision_id, number: item.revision.revision_number });
      }
    };
    const operationsRead = available(async () => { const page = await renders.operations(eventId, sessionId); return { items: page.items, truncated: page.next_after !== null }; });
    const outputsRead = available(async () => { const page = await renders.outputs(eventId, sessionId); return { items: page.items.map(outputSummary), truncated: page.next_after !== null }; });
    const assembly = await available(async () => {
        const first = await assemblies.revisions(eventId, sessionId);
        if (first.event_id !== eventId || first.session_id !== sessionId) throw new Error("scope_mismatch");
        remember(first.items);
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
        if (page !== first) remember(page.items);
        const item = page.items.find((entry) => entry.revision.revision_number === entry.current_revision_number);
        if (!item || item.revision.event_id !== eventId || item.revision.session_id !== sessionId) throw new Error("current_revision_unavailable");
        return item;
      });
    const packagingRead = readSlotPackaging(eventId, assembly, reads.packaging ? assemblyApi(boundedRead(reads.packaging)) : undefined);
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
    const [operations, outputs] = await Promise.all([operationsRead, outputsRead]);
    return { fixture: false, assembly, operations, outputs, timing: summaries, timingTruncated: assetIds.length > bounded.length, knownRevisions, packaging: await packagingRead };
  } finally {
    if (!sharedBudget) budget.dispose();
  }
}

async function readSlotPackaging(eventId: string, assembly: SessionOutputs["assembly"], api?: ReturnType<typeof assemblyApi>): Promise<NonNullable<SessionOutputs["packaging"]>> {
  const wanted = new Set(assembly.state === "available" ? assembly.value?.revision.bindings.flatMap((binding) => binding.packaging_revision_id ? [binding.packaging_revision_id] : []) : []);
  if (!api || !wanted.size) return [];
  const assets = await available(() => api.packagingAssets(eventId));
  if (assets.state !== "available" || assets.value.event_id !== eventId) return [];
  const resolved: NonNullable<SessionOutputs["packaging"]> = [];
  // One asset page and one revision page per asset; at most eight reads at once.
  // Missing, truncated or failed matches stay unavailable, never guessed by role.
  const bounded = assets.value.items.slice(0, 100).filter(({ asset }) => asset.event_id === eventId);
  for (let start = 0; start < bounded.length && wanted.size; start += 8) {
    const matches = await Promise.all(bounded.slice(start, start + 8).map(async ({ asset }) => {
      const page = await available(() => api.packagingRevisions(eventId, asset.packaging_asset_id));
      if (page.state !== "available" || page.value.event_id !== eventId || page.value.packaging_asset_id !== asset.packaging_asset_id) return [];
      return page.value.items.flatMap(({ revision }) =>
        revision.packaging_asset_id === asset.packaging_asset_id && wanted.has(revision.revision_id)
          ? [{ revisionId: revision.revision_id, name: asset.name, role: asset.role }] : []);
    }));
    for (const match of matches.flat()) { resolved.push(match); wanted.delete(match.revisionId); }
  }
  return resolved;
}
