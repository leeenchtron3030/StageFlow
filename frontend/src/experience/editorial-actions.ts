import { uiLabels } from "./ui-labels.ts";
import { generateUuidV4 } from "../shared/ids/uuid-v4.ts";
import { demoAuthorityHeaders } from "./demo-launch-context.ts";
import { idSchema } from "./outputs-api.ts";
import { derivationRunSchema, editorialReviewResultSchema, phraseListSchema, type EditorialCandidate, type DerivationRun } from "./editorial-api.ts";
import { phrasePreview } from "./editorial-normalization.ts";
import { derivationSummary } from "./editorial-presentation.ts";

export type ReviewAction = "approve_and_create_clip" | "reject" | "revise_range" | "defer";
export interface EditorialAuthority { eventId: string; fixture: boolean; authoritative: boolean; operatorAvailable: boolean; launchContext?: string }
export type EditorialIntent =
  | { kind: "review"; candidate: EditorialCandidate; action: ReviewAction; reason: string; start?: number; end?: number }
  | { kind: "publish"; key: string; name: string; version: number; text: string }
  | { kind: "derive"; sessionId: string; phraseListId: string; version: number };
export interface EditorialCommand { kind: EditorialIntent["kind"]; path: string; body: Readonly<Record<string, unknown>>; launchContext: string }
/** Decimal input to integer microseconds without binary floating-point rounding. */
export function secondsToMicroseconds(value: string): number {
  const match = /^(\d+)(?:\.(\d{1,6}))?$/.exec(value.trim());
  if (!match) return NaN;
  const result = Number(match[1]) * 1_000_000 + Number((match[2] ?? "").padEnd(6, "0"));
  return Number.isSafeInteger(result) ? result : NaN;
}
export function authorityDisabled(context: EditorialAuthority): string | undefined {
  if (context.fixture) return "Development fixture · commands disabled";
  if (!context.authoritative || !idSchema.safeParse(context.eventId).success) return "Commands unavailable: refresh live Event state.";
  if (!context.launchContext) return "Commands unavailable: launcher context missing.";
  if (!context.operatorAvailable) return "Commands unavailable: operator identity missing.";
}
export function intentError(intent: EditorialIntent): string | undefined {
  if (intent.kind === "review") {
    if (!idSchema.safeParse(intent.candidate.candidate_moment_id).success || !Number.isSafeInteger(intent.candidate.revision) || intent.candidate.revision < 1) return uiLabels.refreshMoment;
    if (!intent.reason.trim() || Array.from(intent.reason.trim()).length > 500) return "A reason of 1–500 characters is required.";
    const hasRange = intent.start !== undefined || intent.end !== undefined;
    if (intent.action === "revise_range" || hasRange) {
      if (!["revise_range", "approve_and_create_clip"].includes(intent.action)) return "This action cannot adjust a range.";
      if (!Number.isSafeInteger(intent.start) || !Number.isSafeInteger(intent.end) || intent.start! < 0 || intent.end! < intent.start!) return "Enter a nonnegative range with end at or after start.";
    }
    if (intent.action === "approve_and_create_clip" && !hasRange && intent.candidate.timeline_end_microseconds === null) return "Set a range before creating a clip.";
  } else if (intent.kind === "publish") {
    if (!intent.key.trim() || Array.from(intent.key.trim()).length > 100 || !intent.name.trim() || Array.from(intent.name.trim()).length > 200) return "Enter a key (1–100 characters) and name (1–200 characters).";
    if (!phrasePreview(intent.text).valid) return "Resolve phrase preview rejections.";
  } else if (!idSchema.safeParse(intent.sessionId).success || !idSchema.safeParse(intent.phraseListId).success) return "Choose a Session and phrase-list version.";
  if (intent.kind !== "review" && (!Number.isSafeInteger(intent.version) || intent.version < 1)) return "Version must be a positive integer.";
}
export function prepareEditorialCommand(context: EditorialAuthority, intent: EditorialIntent, confirmed: boolean): EditorialCommand | undefined {
  if (!confirmed || authorityDisabled(context) || intentError(intent)) return;
  const commandId = generateUuidV4();
  let path: string, body: Record<string, unknown>;
  if (intent.kind === "review") {
    path = `moments/${intent.candidate.candidate_moment_id}/reviews`;
    const adjusted = intent.start !== undefined && (intent.action === "revise_range" ||
      intent.candidate.timeline_end_microseconds === null ||
      intent.start !== intent.candidate.timeline_start_microseconds || intent.end !== intent.candidate.timeline_end_microseconds);
    body = { operation_id: commandId, confirmed: "confirmed", expected_candidate_revision: intent.candidate.revision, action: intent.action, reason: intent.reason.trim(),
      ...(adjusted ? { adjusted_timeline_start_microseconds: intent.start, adjusted_timeline_end_microseconds: intent.end } : {}) };
  } else if (intent.kind === "publish") {
    path = `events/${context.eventId}/phrase-lists`;
    body = { command_id: commandId, confirmed: "confirmed", key: intent.key.trim(), name: intent.name.trim(), version: intent.version, phrases: phrasePreview(intent.text).rows.map((r) => r.phrase) };
    Object.freeze(body.phrases);
  } else {
    path = `sessions/${intent.sessionId}/derivations`;
    body = { command_id: commandId, confirmed: "confirmed", phrase_list_id: intent.phraseListId, version: intent.version };
  }
  return Object.freeze({ kind: intent.kind, path: `/api/stageflow/editorial/${path}`, body: Object.freeze(body), launchContext: context.launchContext! });
}
export type EditorialResult = { kind: "succeeded" | "conflict" | "network_failure" | "failed"; message: string; identifiers?: Record<string, unknown>; run?: DerivationRun };
/** Same-ID retry is exposed only after transport failure. HTTP failures never retry. */
export async function sendEditorialCommand(command: EditorialCommand, fetcher: typeof fetch, refresh: () => Promise<void>): Promise<EditorialResult> {
  let response: Response;
  try { response = await fetcher(command.path, { method: "POST", cache: "no-store", redirect: "error", headers: demoAuthorityHeaders(command.launchContext), body: JSON.stringify(command.body) }); }
  catch { return { kind: "network_failure", message: "Connection lost; outcome unknown. Retry the same command." }; }
  let payload: unknown;
  try { payload = await response.json(); } catch { /* An HTTP response never permits same-ID transport retry. */ }
  if (!response.ok) {
    const detail = (payload as { detail?: unknown } | undefined)?.detail;
    const code = typeof detail === "string" && /^[a-z][a-z0-9_]{0,95}$/.test(detail) ? detail : `http_${response.status}`;
    if (response.status === 409) { await refresh(); return { kind: "conflict", message: `State changed (${code}); refreshed. Review before acting again.` }; }
    return { kind: "failed", message: `Command not confirmed (${code}).` };
  }
  await refresh();
  if (command.kind === "derive") {
    const parsed = derivationRunSchema.safeParse(payload);
    if (parsed.success) return { kind: "succeeded", message: derivationSummary(parsed.data), identifiers: { run_id: parsed.data.run_id, candidate_ids: parsed.data.candidate_ids, phrase_list_id: parsed.data.phrase_list_id, phrase_list_version: parsed.data.phrase_list_version }, run: parsed.data };
  } else if (command.kind === "publish") {
    const parsed = phraseListSchema.safeParse(payload);
    if (parsed.success) return { kind: "succeeded", message: `${parsed.data.name} · version ${parsed.data.version} published.`, identifiers: { phrase_list_id: parsed.data.phrase_list_id } };
  } else {
    const parsed = editorialReviewResultSchema.safeParse(payload);
    if (parsed.success) return { kind: "succeeded", message: parsed.data.clip ? "Approved · Editorial Clip created." : uiLabels.reviewOutcome[parsed.data.decision.action], identifiers: { review_decision_id: parsed.data.decision.review_decision_id, clip_id: parsed.data.clip?.clip_id } };
  }
  return { kind: "failed", message: "Command response incomplete; refreshed. Check current state." };
}
