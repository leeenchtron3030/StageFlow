import { z } from "zod";
import { capabilityRead, countSchema as count, idSchema as id, hashSchema, operationStateSchema, pageFields, timestampSchema, query, type ApiRead } from "./outputs-api.ts";
export const renderOperationSchema = z.object({ operation_id: id, state: operationStateSchema, assembly_revision_id: id, profile_id: z.string(), profile_version: z.string(), attempt_count: count, reason_code: z.string().nullable(), rendered_output_id: id.nullable() });
export const renderedOutputSchema = z.object({
  output_id: id, assembly_revision_id: id, profile_id: z.string(), profile_version: z.string(), operation_id: id, producing_attempt_id: id,
  content_key: z.string(), sha256: hashSchema, manifest_content_key: z.string(), manifest_sha256: hashSchema,
  byte_size: count, media_type: z.string(), duration_microseconds: count, frame_count: count,
  ffmpeg_version: z.string(), ffmpeg_sha256: hashSchema, produced_at: timestampSchema,
});
export const renderOperationsSchema = z.object({ items: z.array(renderOperationSchema), ...pageFields });
export const renderedOutputsSchema = z.object({ items: z.array(renderedOutputSchema), ...pageFields });
export type RenderOperation = z.infer<typeof renderOperationSchema>;
export type RenderedOutput = z.infer<typeof renderedOutputSchema>;
export function renderingApi(read: ApiRead = capabilityRead("rendering")) {
  const scope = (eventId: string, sessionId: string, after?: string) => query({ event_id: id.parse(eventId), session_id: id.parse(sessionId), after, limit: 100 });
  return {
    operations: async (eventId: string, sessionId: string, after?: string) => renderOperationsSchema.parse(await read(`operations?${scope(eventId, sessionId, after)}`)),
    outputs: async (eventId: string, sessionId: string, after?: string) => renderedOutputsSchema.parse(await read(`outputs?${scope(eventId, sessionId, after)}`)),
  };
}
