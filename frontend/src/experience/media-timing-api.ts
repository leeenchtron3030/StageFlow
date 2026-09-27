import { z } from "zod";
import { capabilityRead, countSchema as count, idSchema as id, operationStateSchema, pageFields, qualificationSchema, revisionSchema, timestampSchema as time, query, type ApiRead } from "./outputs-api.ts";
export const mediaTimingOperationSchema = z.object({ operation_id: id, asset_id: id, state: operationStateSchema, attempt_count: count, reason_code: z.string().nullable(), profile_id: z.string(), profile_version: z.string(), evidence_id: id.nullable() });
export const mediaTimingOperationsSchema = z.object({ items: z.array(mediaTimingOperationSchema), ...pageFields });
export const mediaTimingSummarySchema = z.object({ asset_id: id, evidence: z.object({
  evidence_id: id, revision: revisionSchema, qualification: qualificationSchema, limitations: z.array(z.string()), limitations_truncated: z.boolean(),
  candidate_interval: z.object({ started_at: time, ended_at: time }).nullable(), authorized_use: z.literal("advisory_only"),
}).nullable() });
export type MediaTimingSummary = z.infer<typeof mediaTimingSummarySchema>;
export function mediaTimingApi(read: ApiRead = capabilityRead("media-timing")) {
  return {
    latest: async (assetId: string) => mediaTimingSummarySchema.parse(await read(`assets/${id.parse(assetId)}/latest`)),
    operations: async (eventId: string, after?: string) => mediaTimingOperationsSchema.parse(await read(`events/${id.parse(eventId)}/operations?${query({ after, limit: 100 })}`)),
  };
}
