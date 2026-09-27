import type { EditorialCandidate, EditorialQueue, DerivationRun } from "./editorial-api.ts";

export const reviewLabels = { unreviewed: "Awaiting review", approved: "Approved", rejected: "Rejected", revision_requested: "Range revision requested", deferred: "Deferred" };
export function momentsRefreshToken(moments: readonly { candidate_moment_id: string }[]): string {
  return JSON.stringify([moments.length, moments.map((moment) => moment.candidate_moment_id).sort()]);
}
export function timelinePosition(microseconds: number): string {
  const seconds = Math.floor(microseconds / 1_000_000);
  return [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60].map((v) => String(v).padStart(2, "0")).join(":");
}
export function candidateLabel(candidate: EditorialCandidate, title?: string): string {
  const length = candidate.timeline_end_microseconds === null ? "Point mark · range needed" : `${(candidate.timeline_end_microseconds - candidate.timeline_start_microseconds) / 1_000_000} s`;
  return `${title || "Session title unavailable"} · ${timelinePosition(candidate.timeline_start_microseconds)} · ${length}`;
}
export function candidateFlags(candidate: EditorialCandidate): string[] {
  return [candidate.location_conflict ? "Outside Session" : "",
    candidate.origin === "derived" && candidate.provenance?.timing_qualification === "unqualified" ? "Unqualified timing" : "",
    candidate.origin === "derived" && ["rejected", "expired"].includes(candidate.provenance?.timing_qualification ?? "") ? `Timing ${candidate.provenance!.timing_qualification}` : "",
  ].filter(Boolean);
}
export function queueSummary(queue: EditorialQueue): string {
  const derived = queue.items.filter((i) => i.candidate.origin === "derived").length;
  const outside = queue.items.filter((i) => i.candidate.location_conflict).length;
  return `${queue.pending_candidate_count} awaiting review · ${queue.total_candidate_count} total · this page: ${derived} derived${outside ? ` · ${outside} outside Session` : ""}`;
}
export function momentsSummary(items: EditorialCandidate[]): string {
  const counts = ["declared", "derived"].map((origin) => `${items.filter((m) => m.origin === origin).length} ${origin}`);
  for (const [state, label] of Object.entries(reviewLabels)) {
    const count = items.filter((m) => m.review_state === state).length;
    if (count) counts.push(`${count} ${label.toLowerCase()}`);
  }
  return counts.join(" · ");
}
export function derivationSummary(run: DerivationRun): string {
  return [`${run.candidate_ids.length} candidates`, ...Object.entries(run.skip_counts).filter(([, count]) => count > 0).map(([reason, count]) => `${count} skipped: ${reason.replaceAll("_", " ")}`)].join(" · ");
}
