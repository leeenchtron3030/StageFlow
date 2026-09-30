import { demoAuthorityHeaders } from "./demo-launch-context.ts";
import { generateUuidV4 } from "../shared/ids/uuid-v4.ts";
import { decisionSchema, offsetSchema, runSchema, type Suggestion, type SuggestionData, type SuggestionRun } from "./session-suggestions-api.ts";
import { suggestionLabels as labels } from "./ui-labels.ts";

export function localTime(value: string, timeZone?: string) {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone }).format(new Date(value));
}
export function localRange(start: string, end: string, timeZone?: string) {
  const date = new Intl.DateTimeFormat("en-US", { year: "numeric", month: "numeric", day: "numeric", timeZone });
  const sameDay = date.format(new Date(start)) === date.format(new Date(end));
  const finish = sameDay ? new Intl.DateTimeFormat("en-US", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone }).format(new Date(end)) : localTime(end, timeZone);
  return `${localTime(start, timeZone)}–${finish}`;
}
export const closerLook = (count: number) => `${count} ${count === 1 ? "needs" : "need"} a closer look`;
export function localInput(value: string) {
  const date = new Date(value), pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}
function inputInstant(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(value)) throw new Error(labels.invalidTimes);
  const date = new Date(value);
  // Reject invalid calendar values and times skipped by daylight saving, rather than normalizing silently.
  if (!Number.isFinite(date.getTime()) || localInput(date.toISOString()) !== (value.length === 16 ? `${value}:00` : value)) throw new Error(labels.invalidTimes);
  return date.toISOString();
}
export const minutes = (seconds: number) => Number((seconds / 60).toFixed(1));
export const signedMinutes = (seconds: number) => `${seconds >= 0 ? "+" : "−"}${Math.abs(minutes(seconds))} min`;
export const timeOrder = (items: Suggestion[]) => [...items].sort((a, b) => Date.parse(a.suggested_start) - Date.parse(b.suggested_start) || a.suggestion_id.localeCompare(b.suggestion_id));
export function offsetSummary(blocks: SuggestionRun["blocks"], zone?: string): string {
  if (!blocks.length) return "";
  const description = (b: typeof blocks[number]) => b.schedule_offset_source === "none" ? "no schedule offset applied" :
    `${b.schedule_offset_seconds === 0 ? "no schedule offset" : `running about ${Math.abs(minutes(b.schedule_offset_seconds))} min ${b.schedule_offset_seconds < 0 ? "ahead of" : "behind"} the printed schedule`} (${b.schedule_offset_source === "producer" ? "set by producer" : "estimated"})`;
  const first = blocks[0];
  return blocks.every((b) => b.schedule_offset_seconds === first.schedule_offset_seconds && b.schedule_offset_source === first.schedule_offset_source)
    ? description(first) : blocks.map((b) => `from ${localTime(b.first_planned_start, zone)}: ${description(b)}`).join(" · ");
}
export function suggestionSummary(data: SuggestionData, hasPlannedTalks: boolean, zone?: string) {
  const open = data.suggestions.filter((s) => s.status === "open"), weak = open.filter((s) => s.strength === "weak").length;
  const decided = data.suggestions.some((s) => s.run_id === data.run?.run_id && (s.status === "confirmed" || s.status === "rejected"));
  return [!hasPlannedTalks ? labels.scheduleFirst : "", open.length ? `${open.length} suggested` : hasPlannedTalks ? decided ? labels.noneOpen : labels.none : "", weak ? closerLook(weak) : "",
    data.run ? `last suggested ${localTime(data.run.created_at, zone)}` : "", offsetSummary(data.run?.blocks ?? [], zone)].filter(Boolean).join(" · ");
}
/** True when every suggestion shares one offset source and value; the summary line then states it once. */
export function uniformOffset(items: readonly Suggestion[]) {
  return items.every((s) => s.schedule_offset_source === items[0]?.schedule_offset_source && s.schedule_offset_seconds === items[0]?.schedule_offset_seconds);
}
export function suggestionExceptions(s: Suggestion, offsetInSummary = false) {
  return [s.strength === "weak" ? labels.weak : "", s.overlap ? labels.overlap : "", [s.start_edge_kind, s.end_edge_kind].includes("schedule") ? labels.fallback : "", s.schedule_offset_source === "producer" && !offsetInSummary ? labels.producer : ""].filter(Boolean);
}
export function strengthExplanation(s: Suggestion) {
  if (s.strength === "weak") return "Needs review because this is unscheduled, overlaps another suggestion, or uses a schedule-only boundary.";
  if (s.strength === "strong") return "Changeover boundaries have silence or cue phrase support. This is still an estimate.";
  return "Changeover boundaries have no silence or cue phrase support. This is still an estimate.";
}
export type OffsetDraft = { from: string; minutes: string }[];
export type SuggestionCommand = { path: string; kind: "run" | "confirm" | "reject" | "offset"; body: { authority_kind: "human"; command_id?: string; start?: string; end?: string; reason?: string; entries?: { effective_from: string; offset_seconds: number }[] } };
export function prepareRun(stage: string): SuggestionCommand {
  return { kind: "run", path: `stages/${stage}/runs`, body: { authority_kind: "human" } };
}
export function prepareConfirm(s: Suggestion, adjusted?: { start: string; end: string }): SuggestionCommand {
  // An untouched input retains its original instant, including the later occurrence of a repeated local hour.
  const instant = (input: string, original: string) => input === localInput(original) ? new Date(original).toISOString() : inputInstant(input);
  const times = adjusted ? { start: instant(adjusted.start, s.suggested_start), end: instant(adjusted.end, s.suggested_end) } : undefined;
  if (times && Date.parse(times.start) >= Date.parse(times.end)) throw new Error(labels.invalidTimes);
  return { kind: "confirm", path: `suggestions/${s.suggestion_id}/confirm`, body: { authority_kind: "human", command_id: generateUuidV4(), ...times } };
}
export function prepareReject(s: Suggestion, reason: string): SuggestionCommand {
  if (!labels.rejectionReasons.some((r) => r === reason)) throw new Error("Choose a rejection reason.");
  return { kind: "reject", path: `suggestions/${s.suggestion_id}/reject`, body: { authority_kind: "human", command_id: generateUuidV4(), reason } };
}
export function prepareOffset(stage: string, draft: OffsetDraft): SuggestionCommand {
  try {
    if (draft.length > 20) throw new Error();
    const entries = draft.map((row) => {
      const seconds = Number(row.minutes) * 60, rounded = Math.round(seconds);
      if (!row.minutes.trim() || !Number.isFinite(seconds) || Math.abs(seconds - rounded) > 1e-8 || Math.abs(rounded) > 7200) throw new Error();
      return { effective_from: inputInstant(row.from), offset_seconds: rounded };
    }).sort((a, b) => a.effective_from.localeCompare(b.effective_from));
    if (entries.some((row, i) => i > 0 && row.effective_from === entries[i - 1].effective_from)) throw new Error();
    return { kind: "offset", path: `stages/${stage}/schedule-offset`, body: { authority_kind: "human", command_id: generateUuidV4(), entries } };
  } catch { throw new Error(labels.invalidOffset); }
}
export function suggestionError(status: number, payload: unknown): string {
  const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : undefined;
  if (status === 401 || status === 403) return labels.readOnly;
  if (status === 409) return detail === "stale_expectation_revision" ? labels.stale : detail === "expectation_already_realized" ? labels.linked : detail === "suggestion_not_open" ? labels.closed : labels.conflict;
  if (status === 422 || status === 413) return labels.invalid;
  if (status === 404) return labels.missing;
  return labels.failed;
}
export async function sendSuggestionCommand(event: string, stage: string, command: SuggestionCommand, launch: string, fetcher: typeof fetch = fetch) {
  try {
    const response = await fetcher(`/api/stageflow/session-suggestions/events/${event}/${command.path}`, {
      method: "POST", cache: "no-store", redirect: "error", headers: demoAuthorityHeaders(launch), body: JSON.stringify(command.body),
    });
    let payload: unknown;
    try { payload = await response.json(); } catch { /* Status mapping remains usable without a JSON body. */ }
    if (!response.ok) return { saved: false, message: suggestionError(response.status, payload), uncertain: response.status >= 500 };
    if (command.kind === "run") {
      const value = runSchema.parse(payload);
      if (value.event_id !== event || value.stage_id !== stage) throw new Error();
    } else if (command.kind === "offset") {
      const value = offsetSchema.parse(payload);
      if (value.event_id !== event || value.stage_id !== stage || value.command_id !== command.body.command_id) throw new Error();
    } else {
      const value = decisionSchema.parse(payload);
      if (value.command_id !== command.body.command_id || value.suggestion_id !== command.path.split("/")[1] || value.kind !== (command.kind === "confirm" ? "confirmed" : "rejected")) throw new Error();
    }
    return { saved: true, uncertain: false, message: command.kind === "offset" ? labels.offsetSaved : command.kind === "run" ? labels.ran : labels.saved };
  } catch { return { saved: false, uncertain: true, message: labels.unknown }; }
}
