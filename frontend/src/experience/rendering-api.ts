import { z } from "zod";
import { capabilityRead, countSchema as count, idSchema as id, hashSchema, operationStateSchema, pageFields, timestampSchema, query, type ApiRead } from "./outputs-api.ts";
const qualityFields = { video_bit_rate: z.number().int().positive().nullable().optional(), audio_bit_rate: z.number().int().positive().nullable().optional(), event_render_setting_version: z.number().int().positive().nullable().optional() };
export const renderPresetSchema = z.object({
  profile_id: z.enum(["h264-nvenc-1080p-video", "h264-nvenc-1080p-high", "h264-nvenc-720p"]), profile_version: z.string(),
  width: z.number().int().positive(), height: z.number().int().positive(), video_bit_rate: z.number().int().positive(),
  video_min: z.number().int().positive(), video_max: z.number().int().positive().max(20000000), video_step: z.literal(500000),
  audio_bit_rate: z.number().int().positive(), audio_choices: z.array(z.number().int().positive()).min(1).max(4), default: z.boolean(),
}).refine((p) => p.video_min <= p.video_max && p.video_bit_rate >= p.video_min && p.video_bit_rate <= p.video_max && p.audio_choices.includes(p.audio_bit_rate));
export const renderPresetsSchema = z.object({ items: z.array(renderPresetSchema).length(3) });
export const eventRenderSettingSchema = z.object({
  event_id: id, version: z.number().int().positive().nullable(), profile_id: z.string(), profile_version: z.string(),
  video_bit_rate: z.number().int().positive().nullable(), audio_bit_rate: z.number().int().positive().nullable(),
  effective_video_bit_rate: z.number().int().positive(), effective_audio_bit_rate: z.number().int().positive(),
  selected_by: id.nullable(), selected_at: timestampSchema.nullable(), command_id: id.nullable(),
});
export const renderSettingHistorySchema = z.object({ current: eventRenderSettingSchema, history: z.array(eventRenderSettingSchema) });
export type RenderPreset = z.infer<typeof renderPresetSchema>;
export type EventRenderSetting = z.infer<typeof eventRenderSettingSchema>;
export type RenderSettingHistory = z.infer<typeof renderSettingHistorySchema>;
export const renderOperationSchema = z.object({ ...qualityFields, operation_id: id, state: operationStateSchema, assembly_revision_id: id, profile_id: z.string(), profile_version: z.string(), attempt_count: count, reason_code: z.string().nullable(), rendered_output_id: id.nullable(), created_at: timestampSchema, updated_at: timestampSchema });
export const renderedOutputSchema = z.object({
  ...qualityFields, output_id: id, assembly_revision_id: id, profile_id: z.string(), profile_version: z.string(), operation_id: id, producing_attempt_id: id,
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
    presets: async () => renderPresetsSchema.parse(await read("presets")),
    setting: async (eventId: string) => {
      const result = renderSettingHistorySchema.parse(await read(`events/${id.parse(eventId)}/render-setting`));
      if ([result.current, ...result.history].some((setting) => setting.event_id !== eventId)) throw new Error("scope_mismatch");
      return result;
    },
    operations: async (eventId: string, sessionId: string, after?: string) => renderOperationsSchema.parse(await read(`operations?${scope(eventId, sessionId, after)}`)),
    outputs: async (eventId: string, sessionId: string, after?: string) => renderedOutputsSchema.parse(await read(`outputs?${scope(eventId, sessionId, after)}`)),
  };
}
