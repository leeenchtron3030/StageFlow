import { z } from "zod";
import { capabilityRead, CapabilityReadError, countSchema as count, idSchema as id, timestampSchema as time, revisionSchema as revision, hashSchema, type ApiRead } from "./outputs-api.ts";

const source = z.enum(["none", "estimated", "producer"]);
const reference = z.object({ id, revision });
export const suggestionSchema = z.object({
  suggestion_id: id, run_id: id, event_id: id, stage_id: id,
  policy_id: z.string(), policy_version: z.string(), authorized_use: z.literal("advisory_only"),
  status: z.enum(["open", "confirmed", "rejected", "superseded"]),
  expectation_id: id.nullable(), expectation_revision: revision.nullable(),
  suggested_start: time, suggested_end: time,
  start_edge_kind: z.enum(["freeze", "gap", "coverage", "schedule"]),
  end_edge_kind: z.enum(["freeze", "gap", "coverage", "schedule"]),
  start_plan_offset_seconds: z.number().nullable(), end_plan_offset_seconds: z.number().nullable(),
  start_silence_support: z.boolean(), end_silence_support: z.boolean(), start_cue_support: z.boolean(), end_cue_support: z.boolean(),
  overlap: z.boolean(), strength: z.enum(["weak", "medium", "strong"]),
  timing_qualifications: z.array(z.enum(["unqualified", "qualified", "rejected", "expired"])),
  timing_references: z.array(reference), segmentation_ids: z.array(id), transcript_references: z.array(reference),
  schedule_offset_seconds: z.number().int().optional(), schedule_offset_source: source.optional(),
}).refine((s) => Date.parse(s.suggested_start) < Date.parse(s.suggested_end));
export const runSchema = z.object({
  run_id: id, event_id: id, stage_id: id, input_digest: hashSchema, actor_id: id, created_at: time,
  policy: z.object({ id: z.string(), version: z.string() }),
  skips: z.object({ no_timing_evidence: count, no_segmentation: count, clock_implausible: count, no_coverage: count, no_planned_time: count, already_realized: count }),
  blocks: z.array(z.object({ ordinal: count, first_planned_start: time, last_planned_start: time, talk_count: revision,
    schedule_offset_seconds: z.number().int(), schedule_offset_source: source, estimate_score_margin: z.number(), override_setting_version: revision.nullable() })),
  override_setting_version: revision.nullable(),
  start_cue_list: z.object({ id, version: revision }).nullable(), end_cue_list: z.object({ id, version: revision }).nullable(),
});
export const offsetSchema = z.object({
  event_id: id, stage_id: id, version: revision, command_id: id, set_by: id, set_at: time,
  authorized_use: z.literal("advisory_only"), entries: z.array(z.object({ effective_from: time, offset_seconds: z.number().int().min(-7200).max(7200) })).max(20),
});
export const decisionSchema = z.object({ command_id: id, suggestion_id: id, actor_id: id, decided_at: time,
  kind: z.enum(["confirmed", "rejected"]), reason: z.string().nullable(), session_id: id.nullable(), used_start: time.nullable(), used_end: time.nullable(),
}).refine((d) => d.kind === "confirmed" ? d.session_id !== null && d.used_start !== null && d.used_end !== null && Date.parse(d.used_start) < Date.parse(d.used_end) : d.session_id === null);
export type Suggestion = z.infer<typeof suggestionSchema>;
export type SuggestionRun = z.infer<typeof runSchema>;
export type ScheduleOffset = z.infer<typeof offsetSchema>;
export type SuggestionData = { run: SuggestionRun | null; suggestions: Suggestion[]; offset: ScheduleOffset | null };
export const offsetHistorySchema = z.object({ items: z.array(offsetSchema), limit: revision.max(100), next_after: count.nullable() });

export function suggestionsApi(read: ApiRead = capabilityRead("session-suggestions")) {
  const scope = (event: string, stage: string) => `events/${id.parse(event)}/stages/${id.parse(stage)}`;
  function check<T extends { event_id: string; stage_id: string }>(value: T, event: string, stage: string): T {
    if (value.event_id !== event || value.stage_id !== stage) throw new Error("scope_mismatch");
    return value;
  }
  const api = {
    async latest(event: string, stage: string) {
      try { return check(runSchema.parse(await read(`${scope(event, stage)}/runs/latest`)), event, stage); }
      catch (error) { if (error instanceof CapabilityReadError && error.status === 404 && error.detail === "suggestion_run_not_found") return null; throw error; }
    },
    async current(event: string, stage: string) {
      const { current } = z.object({ current: offsetSchema.nullable() }).parse(await read(`${scope(event, stage)}/schedule-offset`));
      return current ? check(current, event, stage) : null;
    },
    async history(event: string, stage: string, after = 0) {
      const page = offsetHistorySchema.parse(await read(`${scope(event, stage)}/schedule-offset/history?after=${count.parse(after)}&limit=50`));
      page.items.forEach((item) => check(item, event, stage));
      if (page.next_after !== null && page.next_after <= after) throw new Error("cursor_not_advancing");
      return page;
    },
    async read(event: string, stage: string, suggestion: string) {
      const value = check(suggestionSchema.parse(await read(`events/${id.parse(event)}/suggestions/${id.parse(suggestion)}`)), event, stage);
      if (value.suggestion_id !== suggestion) throw new Error("scope_mismatch");
      return value;
    },
    async list(event: string, stage: string, status: Suggestion["status"]) {
      const items: Suggestion[] = [], seen = new Set<string>(), identities = new Set<string>(); let after: string | null = null;
      do {
        const page = z.object({ items: z.array(suggestionSchema), next_after: id.nullable(), limit: revision.max(100) }).parse(
          await read(`${scope(event, stage)}/suggestions?status=${status}&limit=100${after ? `&after=${after}` : ""}`));
        for (const item of page.items) {
          check(item, event, stage);
          if (item.status !== status || identities.has(item.suggestion_id)) throw new Error("suggestions_changed_during_read");
          identities.add(item.suggestion_id);
          items.push(item);
        }
        after = page.next_after;
        if (after && seen.has(after)) throw new Error("cursor_not_advancing");
        if (after) seen.add(after);
      } while (after);
      return items;
    },
  };
  return { ...api, async load(event: string, stage: string): Promise<SuggestionData> {
    const run = await api.latest(event, stage);
    const [offset, ...pages] = await Promise.all([api.current(event, stage), ...(["open", "confirmed", "rejected", "superseded"] as const).map((status) => api.list(event, stage, status))]);
    const suggestions = pages.flat();
    const latest = await api.latest(event, stage);
    if (run?.run_id !== latest?.run_id || new Set(suggestions.map((s) => s.suggestion_id)).size !== suggestions.length || suggestions.some((s) => s.status === "open" && s.run_id !== run?.run_id)) throw new Error("suggestions_changed_during_read");
    return { run, offset, suggestions };
  } };
}

const queueItemSchema = z.object({ event_id: id, stage_id: id, decision_type: z.string(), subject_kind: z.string(), reason_codes: z.array(z.string()), action_reference: z.string() });
export type SuggestionQueueItem = z.infer<typeof queueItemSchema>;
export async function suggestionQueue(event: string, read: ApiRead = capabilityRead("producer")): Promise<SuggestionQueueItem[]> {
  const items: SuggestionQueueItem[] = [], seen = new Set<string>(); let cursor: string | null = null;
  do {
    const page = z.object({ event_id: id, items: z.array(queueItemSchema), next_cursor: z.string().nullable(), items_truncated: z.boolean(), limit: revision.max(100) }).parse(
      await read(`events/${id.parse(event)}/work-queue?limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`));
    if (page.event_id !== event || page.items.some((item) => item.event_id !== event)) throw new Error("scope_mismatch");
    items.push(...page.items.filter((item) => item.decision_type === "presentation_confirmation_pending" && item.subject_kind === "stage_suggestions"));
    cursor = page.next_cursor;
    if (cursor && seen.has(cursor)) throw new Error("cursor_not_advancing");
    if (cursor) seen.add(cursor);
  } while (cursor);
  return items;
}
