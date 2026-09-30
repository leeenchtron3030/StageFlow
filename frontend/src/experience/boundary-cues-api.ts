import { z } from "zod";
import { capabilityRead, idSchema, hashSchema, timestampSchema, revisionSchema, type ApiRead } from "./outputs-api.ts";

export const cueRoleSchema = z.enum(["start", "end", "changeover", "segment"]);
const choiceSchema = z.object({ group_key: z.string(), phrase: z.string() });
const customSchema = z.object({ text: z.string(), role: z.enum(["start", "end", "changeover"]) });
export const cueCatalogSchema = z.object({
  id: z.string(), version: revisionSchema, digest: hashSchema,
  profiles: z.array(z.object({ key: z.string(), name: z.string(), group_keys: z.array(z.string()) })),
  groups: z.array(z.object({ key: z.string(), version: revisionSchema, name: z.string(), category: z.string(),
    phrases: z.array(z.object({ text: z.string(), role: cueRoleSchema, default: z.boolean(), evidence: z.string() })) })),
});
const referenceSchema = z.object({ id: idSchema, version: revisionSchema });
export const cueCompositionSchema = z.object({
  event_id: idSchema, version: revisionSchema, command_id: idSchema, request_digest: hashSchema,
  catalog_id: z.string(), catalog_version: revisionSchema, catalog_digest: hashSchema, profile_key: z.string().nullable(),
  groups: z.array(z.object({ key: z.string(), version: revisionSchema })),
  include: z.array(choiceSchema), exclude: z.array(choiceSchema), custom_phrases: z.array(customSchema),
  segment_phrases: z.array(z.object({ text: z.string(), source_group: z.string() })),
  composed_by: idSchema, composed_at: timestampSchema, start_cue_list: referenceSchema, end_cue_list: referenceSchema,
});
export const cueHistorySchema = z.object({ items: z.array(cueCompositionSchema), limit: revisionSchema.max(100), next_after: z.number().int().nonnegative().nullable() });
export type CueCatalog = z.infer<typeof cueCatalogSchema>;
export type CueComposition = z.infer<typeof cueCompositionSchema>;
export type CueHistory = z.infer<typeof cueHistorySchema>;
export type CueRole = z.infer<typeof cueRoleSchema>;
export type CueChoice = z.infer<typeof choiceSchema>;
export type CueCustom = z.infer<typeof customSchema>;
export type BoundaryCueData = { catalog: CueCatalog; current: CueComposition | null; history: CueHistory };

export function boundaryCuesApi(read: ApiRead = capabilityRead("session-suggestions")) {
  const scope = (eventId: string) => `events/${idSchema.parse(eventId)}`;
  const check = (eventId: string, items: CueComposition[]) => {
    if (items.some((item) => item.event_id !== eventId)) throw new Error("scope_mismatch");
  };
  const api = {
    catalog: async (eventId: string) => cueCatalogSchema.parse(await read(`${scope(eventId)}/boundary-cue-catalog`)),
    current: async (eventId: string) => {
      const { current } = z.object({ current: cueCompositionSchema.nullable() }).parse(await read(`${scope(eventId)}/boundary-cues`));
      check(eventId, current ? [current] : []); return current;
    },
    history: async (eventId: string, after = 0) => {
      const page = cueHistorySchema.parse(await read(`${scope(eventId)}/boundary-cues/history?after=${z.number().int().nonnegative().parse(after)}&limit=50`));
      check(eventId, page.items);
      if (page.next_after !== null && page.next_after <= after) throw new Error("cursor_not_advancing");
      return page;
    },
  };
  return { ...api, load: async (eventId: string): Promise<BoundaryCueData> => {
    const [catalog, current, history] = await Promise.all([api.catalog(eventId), api.current(eventId), api.history(eventId)]);
    return { catalog, current, history };
  } };
}
