import { z } from "zod";
import { capabilityRead, countSchema as count, idSchema as id, numberedPageFields, pageFields, qualificationSchema, revisionSchema as revision, timestampSchema as time, hashSchema, query, type ApiRead } from "./outputs-api.ts";

const metadataField = z.enum(["session_title", "participant_names"]);
const packagingRole = z.enum(["opening_bumper", "title_card", "sponsor_card", "outro"]);
const approvalState = z.enum(["unreviewed", "approved", "rejected", "revoked"]);
export const assemblyTemplateSchema = z.object({
  template_id: id, event_id: id, template_key: z.string(), version: revision, name: z.string(),
  slots: z.array(z.object({ key: z.string(), role: z.enum(["opening_bumper", "title_card", "session_media", "sponsor_card", "outro"]), required: z.boolean() })),
  required_metadata: z.array(metadataField), created_at: time,
});
export const assemblyMemberSchema = z.object({
  asset_id: id, association_revision: revision, media_started_at: time.nullable(),
  order_source: z.enum(["media_timing", "timing_evidence", "registration_time"]), order_key_at: time.nullable(),
  order_evidence_id: id.nullable(), order_evidence_revision: revision.nullable(), order_evidence_qualification: qualificationSchema.nullable(),
});
export const assemblyRevisionSchema = z.object({
  revision_id: id, session_id: id, event_id: id, revision_number: revision,
  supersedes_id: id.nullable(), template_id: id, package_revision: revision, completion_decision_id: id.nullable(),
  membership: z.array(assemblyMemberSchema),
  bindings: z.array(z.object({ slot_key: z.string(), outcome: z.enum(["bound", "unresolved", "ambiguous", "invalid_explicit", "session_media"]), packaging_revision_id: id.nullable() })),
  metadata: z.array(z.object({ field: metadataField, values: z.array(z.string()), source: z.enum(["program_expectation", "operator_override"]), source_id: id, source_revision: revision })),
  validation: z.object({ state: z.enum(["valid", "invalid"]), issues: z.array(z.object({ code: z.enum(["ineligible_package", "completion_membership_unavailable", "media_timing_unavailable", "unresolved_required_slot", "ambiguous_binding", "invalid_explicit_binding", "missing_required_metadata"]), subject: z.string().nullable() })) }),
  actor_id: id, created_at: time,
});
export const assemblyDecisionSchema = z.object({
  decision_id: id, session_id: id, revision_id: id, sequence: revision, actor_id: id,
  decided_at: time, action: z.enum(["approve", "reject"]), reason: z.string(), authority_kind: z.literal("human"),
});
export const assemblyItemSchema = z.object({
  revision: assemblyRevisionSchema, current_revision_number: revision, stale: z.boolean(),
  approval_state: approvalState, decision_count: count, latest_decision: assemblyDecisionSchema.nullable(),
});
export const assemblyRevisionsSchema = z.object({
  event_id: id, session_id: id, items: z.array(assemblyItemSchema), total_count: count, ...numberedPageFields,
});
export const assemblyTemplatesSchema = z.object({ event_id: id, items: z.array(assemblyTemplateSchema), total_count: count, items_truncated: z.boolean(), ...pageFields });
export const metadataOverrideSchema = z.object({ override_id: id, session_id: id, field: metadataField, action: z.enum(["set", "clear"]), values: z.array(z.string()), sequence: revision, actor_id: id, recorded_at: time, reason: z.string(), authority_kind: z.literal("human") });
export const metadataOverridesSchema = z.object({ event_id: id, session_id: id, items: z.array(metadataOverrideSchema), total_count: count, ...numberedPageFields });
export const packagingAssetSchema = z.object({ packaging_asset_id: id, event_id: id, stage_id: id.nullable(), name: z.string(), role: packagingRole, created_at: time });
export const packagingRevisionSchema = z.object({
  revision_id: id, packaging_asset_id: id, revision_number: revision,
  content: z.discriminatedUnion("kind", [z.object({ kind: z.literal("external_content"), content_key: z.string(), sha256: hashSchema, byte_size: count, media_type: z.string() }), z.object({ kind: z.literal("completed_media_asset"), asset_id: id })]),
  measured_duration_microseconds: count.nullable(), effective_from: time.nullable(), effective_until: time.nullable(), created_at: time,
});
export const packagingDecisionSchema = z.object({ decision_id: id, packaging_asset_id: id, revision_number: revision, sequence: revision, actor_id: id, decided_at: time, action: z.enum(["approve", "reject", "revoke"]), reason: z.string() });
export const packagingAssetsSchema = z.object({ event_id: id, items: z.array(z.object({ asset: packagingAssetSchema, current_revision_number: count, decision_count: count })), total_count: count, items_truncated: z.boolean(), ...pageFields });
export const packagingRevisionsSchema = z.object({ event_id: id, packaging_asset_id: id, items: z.array(z.object({ revision: packagingRevisionSchema, approval_state: approvalState, decision_count: count, latest_decision: packagingDecisionSchema.nullable() })), total_count: count, ...numberedPageFields });
export type AssemblyItem = z.infer<typeof assemblyItemSchema>;
export type AssemblyMember = z.infer<typeof assemblyMemberSchema>;

export function assemblyApi(read: ApiRead = capabilityRead("assembly")) {
  return {
    revisions: async (eventId: string, sessionId: string, after = 0) => assemblyRevisionsSchema.parse(await read(`events/${id.parse(eventId)}/sessions/${id.parse(sessionId)}/revisions?${query({ after, limit: 100 })}`)),
    templates: async (eventId: string, after?: string) => assemblyTemplatesSchema.parse(await read(`events/${id.parse(eventId)}/templates?${query({ after, limit: 100 })}`)),
    metadataOverrides: async (eventId: string, sessionId: string, after = 0) => metadataOverridesSchema.parse(await read(`events/${id.parse(eventId)}/sessions/${id.parse(sessionId)}/metadata-overrides?${query({ after, limit: 100 })}`)),
    packagingAssets: async (eventId: string, after?: string) => packagingAssetsSchema.parse(await read(`events/${id.parse(eventId)}/packaging-assets?${query({ after, limit: 100 })}`)),
    packagingRevisions: async (eventId: string, assetId: string, after = 0) => packagingRevisionsSchema.parse(await read(`events/${id.parse(eventId)}/packaging-assets/${id.parse(assetId)}/revisions?${query({ after, limit: 100 })}`)),
  };
}
