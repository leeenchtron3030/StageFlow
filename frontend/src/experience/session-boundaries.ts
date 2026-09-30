import { demoAuthorityHeaders } from "./demo-launch-context.ts";
import { generateUuidV4 } from "../shared/ids/uuid-v4.ts";
import { boundaryDecisionSchema, type BoundaryBadges, type BoundaryProposal } from "./session-boundaries-api.ts";
import { boundaryLabels as labels } from "./ui-labels.ts";

export function boundaryTime(value: string, timeZone: string, withDate = true) {
  return new Intl.DateTimeFormat("en-US", { ...(withDate ? { month: "short", day: "numeric", year: "numeric" } as const : {}), hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false, timeZone }).format(new Date(value));
}
function sameDay(left: string, right: string, timeZone: string) {
  const day = new Intl.DateTimeFormat("en-US", { year: "numeric", month: "numeric", day: "numeric", timeZone });
  return day.format(new Date(left)) === day.format(new Date(right));
}
export function boundaryTimes(current: string | undefined, suggested: string, timeZone: string, sessionStart = current) {
  const crossing = Boolean(current && !sameDay(current, suggested, timeZone));
  const currentDate = crossing || !sessionStart || Boolean(current && !sameDay(current, sessionStart, timeZone));
  const suggestedDate = crossing || !sessionStart || (!sameDay(suggested, sessionStart, timeZone) && (!current || !sameDay(current, suggested, timeZone)));
  return `${current ? boundaryTime(current, timeZone, currentDate) : labels.timeUnavailable} → ${boundaryTime(suggested, timeZone, suggestedDate)}`;
}
export function boundaryTimesLabel(current: string | undefined, suggested: string, timeZone: string, sessionStart = current) {
  const [from, to] = boundaryTimes(current, suggested, timeZone, sessionStart).split(" → ");
  return `current ${from}, suggested ${to}`;
}
export function sessionBoundaryRange(start: string | undefined, end: string | undefined, timeZone: string) {
  return `${start ? boundaryTime(start, timeZone) : labels.timeUnavailable}–${end ? boundaryTime(end, timeZone, !start || !sameDay(start, end, timeZone)) : labels.notEnded}`;
}
export function boundaryStageCount(badges?: BoundaryBadges) {
  const count = Object.values(badges?.sessions ?? {}).reduce((total, n) => total + n, 0);
  return count ? ` · ${count} ${count === 1 ? labels.suggestion : labels.suggestions}` : "";
}
export function boundaryDifference(current: string | undefined, suggested: string) {
  return current ? (Date.parse(suggested) - Date.parse(current)) / 1000 : undefined;
}
export function boundaryDuration(seconds: number) {
  const absolute = Math.abs(seconds), minutes = Math.floor(absolute / 60), rest = Number((absolute % 60).toFixed(3));
  return [minutes ? `${minutes} min` : "", rest || !minutes ? `${rest} s` : ""].filter(Boolean).join(" ");
}
export function boundarySummary(p: BoundaryProposal, current?: string) {
  const difference = boundaryDifference(current, p.boundary_at);
  const edge = p.boundary_kind === "start" ? "Start" : "End";
  const change = difference === undefined ? `${edge} could change` : difference === 0 ? `${edge} matches the current time` : `${edge} could be ${boundaryDuration(difference)} ${difference < 0 ? "earlier" : "later"}`;
  return `${change} — ${p.reason === "cue_supported" ? "supported by" : "at"} ${labels.reasons[p.reason]}`;
}
export type BoundaryCommand = { proposalId: string; sessionId: string; kind: "apply" | "dismiss"; body: { authority_kind: "human"; command_id: string; reason?: string } };
export function prepareBoundaryCommand(p: BoundaryProposal, kind: BoundaryCommand["kind"], reason = ""): BoundaryCommand {
  if (reason && (kind !== "dismiss" || !labels.dismissReasons.some((r) => r === reason))) throw new Error("Choose a dismissal reason from the list.");
  return { proposalId: p.proposal_id, sessionId: p.session_id, kind, body: { authority_kind: "human", command_id: generateUuidV4(), ...(reason ? { reason } : {}) } };
}
export function boundaryError(status: number, payload: unknown) {
  const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : undefined;
  if (status === 401 || status === 403) return labels.readOnly;
  if (status === 409) return detail === "boundary_proposal_stale" ? labels.stale : detail === "boundary_proposal_decided" ? labels.decided : labels.conflict;
  if (status === 422 || status === 413) return labels.invalid;
  if (status === 404) return labels.missing;
  return labels.failed;
}
export async function sendBoundaryCommand(event: string, command: BoundaryCommand, launch: string, fetcher: typeof fetch = fetch) {
  try {
    const response = await fetcher(`/api/stageflow/session-suggestions/events/${event}/sessions/${command.sessionId}/boundary-proposals/${command.proposalId}/${command.kind}`, {
      method: "POST", cache: "no-store", redirect: "error", headers: demoAuthorityHeaders(launch), body: JSON.stringify(command.body),
    });
    let payload: unknown;
    try { payload = await response.json(); } catch { /* Map refusals even without JSON. */ }
    if (!response.ok) return { saved: false, uncertain: ![401, 403, 404, 409, 413, 422].includes(response.status), message: boundaryError(response.status, payload) };
    const value = boundaryDecisionSchema.parse(payload);
    if (value.session_id !== command.sessionId || value.proposal_id !== command.proposalId || value.command_id !== command.body.command_id || value.kind !== (command.kind === "apply" ? "applied" : "dismissed")) throw new Error("decision_mismatch");
    return { saved: true, uncertain: false, message: command.kind === "apply" ? labels.applied : labels.dismissed };
  } catch { return { saved: false, uncertain: true, message: labels.unknown }; }
}
