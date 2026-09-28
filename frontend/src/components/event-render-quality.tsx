"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { RenderPreset, RenderSettingHistory } from "../experience/rendering-api.ts";
import { prepareQualityCommand, sendQualityCommand, videoChoices } from "../experience/render-quality.ts";
import { renderQualityLabel, renderQualityLabels as labels, renderSettingProvenance, videoBitrateLabel, audioBitrateLabel } from "../experience/ui-labels.ts";

export function EventRenderQuality({ history, presets, launchContext, authorized }: {
  history?: RenderSettingHistory; presets?: RenderPreset[]; launchContext?: string; authorized: boolean;
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [review, setReview] = useState(false);
  const [selected, setSelected] = useState(history?.current.profile_id ?? "");
  const [video, setVideo] = useState(history?.current.effective_video_bit_rate ?? 0);
  const [audio, setAudio] = useState(history?.current.effective_audio_bit_rate ?? 0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [retry, setRetry] = useState<ReturnType<typeof prepareQualityCommand>>();
  const submitting = useRef(false);
  const preset = presets?.find((p) => p.profile_id === selected);
  const enabled = authorized && Boolean(launchContext) && Boolean(history && presets);
  const proposed = preset ? renderQualityLabel({ ...preset, video_bit_rate: video, audio_bit_rate: audio }) : "";
  async function submit(command: ReturnType<typeof prepareQualityCommand>) {
    if (submitting.current || !enabled || !history || !launchContext) return;
    submitting.current = true; setBusy(true);
    try {
      const result = await sendQualityCommand(history.current.event_id, command, launchContext);
      setMessage(result.message); setRetry(result.retry ? command : undefined);
      setEditing(false); setReview(false);
      if (!result.retry) router.refresh();
    } finally { submitting.current = false; setBusy(false); }
  }
  return <section className="detail-panel" aria-labelledby="render-quality-title">
    <h2 id="render-quality-title">{labels.title}</h2>
    {history && presets ? <>
      <p><strong>{renderQualityLabel(history.current)}</strong> · {renderSettingProvenance(history.current)}</p>
      {!editing ? <button type="button" disabled={!enabled || busy || Boolean(retry)} onClick={() => { setEditing(true); setMessage(""); }}>{labels.change}</button> : null}
      {!enabled ? <p>{labels.readOnly}</p> : null}
      {editing && preset ? <form onSubmit={(event) => { event.preventDefault(); if (review) void submit(prepareQualityCommand(history, preset, video, audio)); else setReview(true); }}>
        {review ? <><p>{labels.consequence}</p><p>{proposed}</p></> : <>
          <label htmlFor="render-preset">{labels.preset}</label>
          <select id="render-preset" value={selected} onChange={(event) => {
            const next = presets.find((p) => p.profile_id === event.target.value)!;
            setSelected(next.profile_id); setVideo(next.video_bit_rate); setAudio(next.audio_bit_rate);
          }}>{presets.map((p) => <option key={p.profile_id} value={p.profile_id}>{labels.presets[p.profile_id]}</option>)}</select>
          <label htmlFor="render-video">{labels.video}</label>
          <select id="render-video" value={video} onChange={(event) => setVideo(Number(event.target.value))}>{videoChoices(preset).map((value) => <option key={value} value={value}>{videoBitrateLabel(value)}</option>)}</select>
          <label htmlFor="render-audio">{labels.audio}</label>
          <select id="render-audio" value={audio} onChange={(event) => setAudio(Number(event.target.value))}>{preset.audio_choices.map((value) => <option key={value} value={value}>{audioBitrateLabel(value)}</option>)}</select>
        </>}
        <div className="output-dialog-actions"><button type="button" disabled={busy} onClick={() => { setEditing(false); setReview(false); }}>{labels.cancel}</button>
          <button type="submit" disabled={!enabled || busy}>{review ? labels.confirm : labels.review}</button></div>
      </form> : null}
      {history.history.length > 1 ? <details><summary>{labels.history}</summary><ul>{history.history.filter((item) => item.version !== history.current.version).map((item) => <li key={item.version}>{renderQualityLabel(item)} · {renderSettingProvenance(item)}</li>)}</ul></details> : null}
    </> : <p>{labels.unavailable}</p>}
    {busy || message ? <p role="status">{busy ? labels.working : message}</p> : null}
    {retry ? <button type="button" disabled={!enabled || busy} onClick={() => void submit(retry)}>{labels.retry}</button> : null}
  </section>;
}
