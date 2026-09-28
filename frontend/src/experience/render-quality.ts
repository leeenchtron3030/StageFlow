import { eventRenderSettingSchema, type RenderPreset, type RenderSettingHistory } from "./rendering-api.ts";
import { demoAuthorityHeaders } from "./demo-launch-context.ts";
import { generateUuidV4 } from "../shared/ids/uuid-v4.ts";
import { renderQualityLabels } from "./ui-labels.ts";

export function videoChoices(preset: RenderPreset): number[] {
  return Array.from({ length: (preset.video_max - preset.video_min) / preset.video_step + 1 }, (_, i) => preset.video_min + i * preset.video_step);
}
export function prepareQualityCommand(history: RenderSettingHistory, preset: RenderPreset, video: number, audio: number) {
  if (!videoChoices(preset).includes(video) || !preset.audio_choices.includes(audio)) throw new Error("render_adjustment_out_of_bounds");
  return Object.freeze({ command_id: generateUuidV4(), confirmed: "confirmed", authority_kind: "human",
    expected_version: history.current.version, profile_id: preset.profile_id, profile_version: preset.profile_version,
    video_bit_rate: video === preset.video_bit_rate ? null : video, audio_bit_rate: audio === preset.audio_bit_rate ? null : audio });
}
export async function sendQualityCommand(eventId: string, command: ReturnType<typeof prepareQualityCommand>, launchContext: string, fetcher: typeof fetch = fetch) {
  let response: Response;
  try {
    response = await fetcher(`/api/stageflow/rendering/events/${eventId}/render-setting`, { method: "POST", cache: "no-store", redirect: "error", headers: demoAuthorityHeaders(launchContext), body: JSON.stringify(command) });
  } catch { return { retry: true, message: renderQualityLabels.unknown }; }
  if (response.status === 409) return { retry: false, message: renderQualityLabels.changed };
  if (!response.ok) return { retry: false, message: renderQualityLabels.failed };
  try {
    const setting = eventRenderSettingSchema.parse(await response.json());
    if (setting.event_id !== eventId || setting.command_id !== command.command_id) throw new Error();
    return { retry: false, message: renderQualityLabels.saved };
  } catch { return { retry: false, message: renderQualityLabels.failed }; }
}
