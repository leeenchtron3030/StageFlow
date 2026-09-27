import { uiLabels, timingLabel } from "./ui-labels.ts";
import type { EditorialCandidate, EditorialQueue, DerivationRun } from "./editorial-api.ts";

export const reviewLabels = uiLabels.review;
export function momentsRefreshToken(moments: readonly { candidate_moment_id: string }[]): string {
  return JSON.stringify([moments.length, moments.map((moment) => moment.candidate_moment_id).sort()]);
}
export function timelinePosition(microseconds: number): string {
  const seconds = Math.floor(microseconds / 1_000_000);
  return [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60].map((v) => String(v).padStart(2, "0")).join(":");
}
export function candidateLabel(candidate: EditorialCandidate, title?: string): string {
  const length = candidate.timeline_end_microseconds === null ? uiLabels.singlePoint : `${(candidate.timeline_end_microseconds - candidate.timeline_start_microseconds) / 1_000_000} s`;
  return `${title ? `${title} · ` : ""}${timelinePosition(candidate.timeline_start_microseconds)} · ${length}`;
}
export function candidateFlags(candidate: EditorialCandidate): string[] {
  return [candidate.location_conflict ? "Outside Session" : "",
    candidate.origin === "derived" ? timingLabel(candidate.provenance?.timing_qualification) : "",
  ].filter(Boolean);
}
export function queueSummary(queue: EditorialQueue): string {
  const derived = queue.items.filter((i) => i.candidate.origin === "derived").length;
  const outside = queue.items.filter((i) => i.candidate.location_conflict).length;
  return `${queue.pending_candidate_count} awaiting review · ${queue.total_candidate_count} total · this page: ${derived} suggested${outside ? ` · ${outside} outside Session` : ""}`;
}
export function momentsSummary(items: EditorialCandidate[]): string {
  const counts = (["declared", "derived"] as const).map((origin) => `${items.filter((m) => m.origin === origin).length} ${uiLabels.origin[origin].toLowerCase()}`);
  for (const [state, label] of Object.entries(reviewLabels)) {
    const count = items.filter((m) => m.review_state === state).length;
    if (count) counts.push(`${count} ${label.toLowerCase()}`);
  }
  return counts.join(" · ");
}
export function derivationSummary(run: DerivationRun): string {
  return [`${run.candidate_ids.length} ${run.candidate_ids.length === 1 ? uiLabels.moment.toLowerCase() : uiLabels.momentPlural}`, ...Object.entries(run.skip_counts).filter(([, count]) => count > 0).map(([reason, count]) => `${count} skipped: ${reason.replaceAll("_", " ")}`)].join(" · ");
}

/** First-seen Session order and original row order within each group are preserved. */
export function sessionGroups(queue: EditorialQueue) {
  const groups = new Map<string, EditorialQueue["items"]>();
  for (const item of queue.items) {
    const id = item.candidate.session_id;
    if (!groups.has(id)) groups.set(id, []);
    groups.get(id)!.push(item);
  }
  return [...groups].map(([sessionId, items]) => ({ sessionId, items }));
}
export function uniformSuggestionTiming(items: EditorialQueue["items"]): string {
  const suggestions = items.filter((item) => item.candidate.origin === "derived");
  const labels = suggestions.map((item) => timingLabel(item.candidate.provenance?.timing_qualification));
  return labels.length && labels[0] && labels.every((label) => label === labels[0]) ? labels[0] : "";
}
/** Display minutes without losing the API's microsecond precision. */
export function rangeInput(microseconds: number): string {
  const minutes = Math.floor(microseconds / 60_000_000);
  const seconds = Math.floor(microseconds / 1_000_000) % 60;
  const fraction = String(microseconds % 1_000_000).padStart(6, "0").replace(/0+$/, "");
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}${fraction ? `.${fraction}` : ""}`;
}
export function rangeSeconds(value: string): string {
  const match = /^(\d+):([0-5]\d)(\.\d{1,6})?$/.exec(value.trim());
  // Retain decimal-seconds input compatibility; commands still receive microseconds.
  return match ? `${Number(match[1]) * 60 + Number(match[2])}${match[3] ?? ""}` : value;
}
