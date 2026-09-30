"use client";

import { useRef, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { suggestionsApi, type Suggestion, type SuggestionData, type ScheduleOffset } from "../experience/session-suggestions-api.ts";
import { localInput, localRange, localTime, minutes, offsetSummary, prepareConfirm, prepareOffset, prepareReject, prepareRun, sendSuggestionCommand, signedMinutes, strengthExplanation, suggestionExceptions, suggestionSummary, timeOrder, uniformOffset, type OffsetDraft, type SuggestionCommand } from "../experience/session-suggestions.ts";
import { suggestionLabels as labels } from "../experience/ui-labels.ts";

const subscribe = () => () => undefined;
const zoneSnapshot = () => Intl.DateTimeFormat().resolvedOptions().timeZone;
type Titles = Record<string, string>;
const title = (s: Suggestion, titles: Titles) => s.expectation_id ? titles[s.expectation_id] ?? labels.plannedUnavailable : labels.unscheduled;

export function SuggestionRow({ item: s, titles, timeZone, children, decisionForm, offsetInSummary = false }: { item: Suggestion; titles: Titles; timeZone: string; children?: React.ReactNode; decisionForm?: React.ReactNode; offsetInSummary?: boolean }) {
  return <li className="suggestion-row">
    <div className="suggestion-line">
      <div className="suggestion-info"><strong>{title(s, titles)}</strong>
      <div className="suggestion-facts">
      <span>{localRange(s.suggested_start, s.suggested_end, timeZone)}</span>
      <span>{minutes((Date.parse(s.suggested_end) - Date.parse(s.suggested_start)) / 1000)} min</span>
      {s.start_plan_offset_seconds !== null ? <span title="Start difference from printed schedule">{signedMinutes(s.start_plan_offset_seconds)}</span> : null}
      {s.status === "open" ? suggestionExceptions(s, offsetInSummary).map((text) => <span className="cue-badge" key={text}>{text}</span>) : <span>{s.status === "confirmed" ? "Confirmed" : "Rejected"}</span>}
      </div></div>
      <div className="suggestion-actions">
      <details className="suggestion-evidence"><summary>{labels.details}</summary>
        <p>{strengthExplanation(s)}</p>
        <p>Start: {labels.edges[s.start_edge_kind]} · silence {s.start_silence_support ? "supports" : "absent"} · cue phrases {s.start_cue_support ? "support" : "absent"}</p>
        <p>End: {labels.edges[s.end_edge_kind]} · silence {s.end_silence_support ? "supports" : "absent"} · cue phrases {s.end_cue_support ? "support" : "absent"}</p>
        {s.end_plan_offset_seconds !== null ? <p>End difference from printed schedule: {signedMinutes(s.end_plan_offset_seconds)}</p> : null}
        <p>Recorder start and length are unverified unless qualified. Evidence does not establish content boundaries.</p>
        <pre>{JSON.stringify(s, null, 2)}</pre>
      </details>
      {children}
      </div>
    </div>
    {decisionForm}
  </li>;
}

export function StageSuggestions({ eventId, stageId, data, titles, hasPlannedTalks, authorized, launchContext, serverTimeZone = "UTC" }: {
  eventId: string; stageId: string; data?: SuggestionData; titles: Titles; hasPlannedTalks: boolean; authorized: boolean; launchContext?: string; serverTimeZone?: string;
}) {
  const router = useRouter();
  const timeZone = useSyncExternalStore(subscribe, zoneSnapshot, () => serverTimeZone);
  const [selection, setSelection] = useState<{ item: Suggestion; kind: "confirm" | "reject" }>();
  const [adjust, setAdjust] = useState(false), [start, setStart] = useState(""), [end, setEnd] = useState("");
  const [reason, setReason] = useState<string>(labels.rejectionReasons[0]);
  const [editing, setEditing] = useState(false), [draft, setDraft] = useState<OffsetDraft>([]);
  const [offsetReview, setOffsetReview] = useState<SuggestionCommand>();
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const [retry, setRetry] = useState<SuggestionCommand>(), [uncertain, setUncertain] = useState(false);
  const [refreshingData, setRefreshingData] = useState<SuggestionData>();
  const [history, setHistory] = useState<ScheduleOffset[]>([]), [historyAfter, setHistoryAfter] = useState<number | null>(0);
  const [historyBusy, setHistoryBusy] = useState(false), [historyMessage, setHistoryMessage] = useState("");
  const submitting = useRef(false);
  const enabled = authorized && Boolean(launchContext) && Boolean(data) && data !== refreshingData;
  const locked = !enabled || busy || Boolean(retry);
  const open = timeOrder(data?.suggestions.filter((s) => s.status === "open") ?? []);
  const decided = timeOrder(data?.suggestions.filter((s) => s.status === "confirmed" || s.status === "rejected") ?? []);
  const superseded = data?.suggestions.filter((s) => s.status === "superseded").length ?? 0;
  const offsetChanged = data?.run && data.offset && data.offset.version !== data.run.override_setting_version;
  function choose(item: Suggestion, kind: "confirm" | "reject") {
    setSelection({ item, kind }); setAdjust(false); setStart(localInput(item.suggested_start)); setEnd(localInput(item.suggested_end)); setMessage("");
  }
  async function submit(command: SuggestionCommand) {
    if (!enabled || !launchContext || submitting.current) return;
    submitting.current = true; setBusy(true);
    try {
      const result = await sendSuggestionCommand(eventId, stageId, command, launchContext);
      setMessage(result.message); setRetry(result.saved ? undefined : command); setUncertain(result.uncertain);
      if (result.saved) { setSelection(undefined); setEditing(false); setOffsetReview(undefined); setRefreshingData(data); router.refresh(); }
    } finally { submitting.current = false; setBusy(false); }
  }
  async function moreHistory() {
    if (historyAfter === null || historyBusy) return;
    setHistoryBusy(true); setHistoryMessage("");
    try {
      const page = await suggestionsApi().history(eventId, stageId, historyAfter);
      setHistory([...history, ...page.items]); setHistoryAfter(page.next_after);
    } catch { setHistoryMessage(labels.historyFailed); }
    finally { setHistoryBusy(false); }
  }
  const decisionForm = selection ? <form className="suggestion-confirm" onSubmit={(event) => {
      event.preventDefault(); if (locked) return;
      try { void submit(selection.kind === "confirm" ? prepareConfirm(selection.item, adjust ? { start, end } : undefined) : prepareReject(selection.item, reason)); }
      catch (error) { setMessage((error as Error).message); }
    }}>
      <p><strong>{selection.kind === "confirm" ? labels.consequence : labels.rejectSave}: {title(selection.item, titles)}</strong></p>
      <p>{localRange(selection.item.suggested_start, selection.item.suggested_end, timeZone)}</p>
      <fieldset disabled={locked}>
        <legend>{selection.kind === "confirm" ? "Confirm one suggestion" : "Rejection reason"}</legend>
        {selection.kind === "confirm" ? <>
          <label><input type="checkbox" checked={adjust} onChange={(e) => setAdjust(e.target.checked)} />{labels.adjusted}</label>
          {adjust ? <><label htmlFor="suggestion-start">{labels.start}</label><input required id="suggestion-start" type="datetime-local" step="1" value={start} onChange={(e) => setStart(e.target.value)} />
            <label htmlFor="suggestion-end">{labels.end}</label><input required id="suggestion-end" type="datetime-local" step="1" value={end} onChange={(e) => setEnd(e.target.value)} /></> : null}
        </> : <><label htmlFor="suggestion-reason">Reason</label><select id="suggestion-reason" value={reason} onChange={(e) => setReason(e.target.value)}>{labels.rejectionReasons.map((r) => <option key={r}>{r}</option>)}</select></>}
      </fieldset>
      <div className="output-dialog-actions"><button type="button" disabled={busy || Boolean(retry)} onClick={() => setSelection(undefined)}>{labels.cancel}</button><button type="submit" disabled={locked}>{selection.kind === "confirm" ? labels.confirmSave : labels.rejectSave}</button></div>
    </form> : null;
  return <section id="suggested-presentations" className="detail-panel suggestions-panel" aria-labelledby="suggestions-title">
    <div className="section-heading"><div><span className="eyebrow">Producer · Stage</span><h2 id="suggestions-title">{labels.title}</h2></div></div>
    <p><strong>{data ? suggestionSummary(data, hasPlannedTalks, timeZone) : labels.unavailable}</strong></p>
    <p>{labels.honesty}</p>
    {!authorized || !launchContext ? <p>{labels.readOnly}</p> : null}
    <div className="output-dialog-actions">
      <button type="button" disabled={locked || Boolean(selection) || editing} onClick={() => void submit(prepareRun(stageId))}>{data?.run ? labels.again : labels.suggest}</button>
      <button type="button" disabled={busy || uncertain} onClick={() => router.refresh()}>{labels.refresh}</button>
    </div>
    {data?.run ? <ul className="suggestion-skips">{Object.entries(data.run.skips).filter(([key, count]) => key !== "already_realized" && count > 0).map(([key, count]) => <li key={key}>{count} {labels.skips[key as keyof typeof labels.skips][count === 1 ? 0 : 1]}</li>)}</ul> : null}
    <ul className="suggestion-rows" aria-label="Open suggestions">{open.map((item) => <SuggestionRow key={item.suggestion_id} item={item} titles={titles} timeZone={timeZone} offsetInSummary={uniformOffset(open)} decisionForm={selection?.item.suggestion_id === item.suggestion_id ? decisionForm : null}>
      <button type="button" disabled={locked || Boolean(selection) || editing} onClick={() => choose(item, "confirm")}>{labels.confirm}</button>
      <button type="button" disabled={locked || Boolean(selection) || editing} onClick={() => choose(item, "reject")}>{labels.reject}</button>
    </SuggestionRow>)}</ul>

    {decided.length ? <details><summary>Decided · {decided.length}</summary><ul className="suggestion-rows">{decided.map((item) => <SuggestionRow key={item.suggestion_id} item={item} titles={titles} timeZone={timeZone} />)}</ul></details> : null}
    {superseded ? <p>{superseded} superseded {superseded === 1 ? "suggestion" : "suggestions"} hidden</p> : null}
    {data ? <div className="suggestion-offset">
      <h3>{labels.offset}</h3>
      <p>{data.offset?.entries.length ? data.offset.entries.map((entry) => `from ${localTime(entry.effective_from, timeZone)}, ${signedMinutes(entry.offset_seconds)}`).join(" · ") + " (set by producer)" : labels.noOffset}</p>
      {offsetChanged ? <p>{labels.offsetSaved}</p> : null}
      <button type="button" disabled={locked || Boolean(selection) || editing} onClick={() => { setDraft(data.offset?.entries.map((e) => ({ from: localInput(e.effective_from), minutes: String(e.offset_seconds / 60) })) ?? []); setEditing(true); setMessage(""); }}>{labels.editOffset}</button>
      {editing ? <form onSubmit={(event) => { event.preventDefault(); if (locked) return; try { if (offsetReview) void submit(offsetReview); else setOffsetReview(prepareOffset(stageId, draft)); } catch (error) { setMessage((error as Error).message); } }}>
        {offsetReview ? <><p>{labels.offsetConsequence}</p><p>{offsetReview.body.entries?.length ? offsetReview.body.entries.map((e) => `from ${localTime(e.effective_from, timeZone)}, ${signedMinutes(e.offset_seconds)}`).join(" · ") : "Clear the producer override"}</p></> : <fieldset disabled={locked}>
          <legend>{labels.offset}</legend><p>{labels.offsetHelp}</p>
          {draft.map((row, index) => <div className="offset-entry" key={index}>
            <label htmlFor={`offset-from-${index}`}>From (local time)</label><input required type="datetime-local" step="1" id={`offset-from-${index}`} value={row.from} onChange={(e) => setDraft(draft.map((r, i) => i === index ? { ...r, from: e.target.value } : r))} />
            <label htmlFor={`offset-minutes-${index}`}>Offset (± minutes)</label><input required type="number" min="-120" max="120" step="any" id={`offset-minutes-${index}`} value={row.minutes} onChange={(e) => setDraft(draft.map((r, i) => i === index ? { ...r, minutes: e.target.value } : r))} />
            <button type="button" onClick={() => setDraft(draft.filter((_, i) => i !== index))}>{labels.removeOffset}</button>
          </div>)}
          <button type="button" disabled={draft.length >= 20} onClick={() => setDraft([...draft, { from: "", minutes: "0" }])}>{labels.addOffset}</button>
          <button type="button" onClick={() => setDraft([])}>{labels.clearOffset}</button>
        </fieldset>}
        <div className="output-dialog-actions"><button type="button" disabled={busy || Boolean(retry)} onClick={() => { if (offsetReview) setOffsetReview(undefined); else setEditing(false); }}>{offsetReview ? "Back" : labels.cancel}</button><button type="submit" disabled={locked}>{offsetReview ? labels.confirmOffset : labels.publishOffset}</button></div>
      </form> : null}
      <details className="diagnostic-details"><summary>{labels.details}</summary>
        {data.run ? <><p>Latest run: {offsetSummary(data.run.blocks, timeZone)}</p><pre>{JSON.stringify(data.run, null, 2)}</pre></> : null}
        <h4>{labels.history}</h4>
        {data.offset ? <pre>{JSON.stringify(data.offset, null, 2)}</pre> : null}
        {history.filter((h) => h.version !== data.offset?.version).map((h) => <div key={h.version}><p>Version {h.version} · {localTime(h.set_at, timeZone)}</p><pre>{JSON.stringify(h, null, 2)}</pre></div>)}
        {historyAfter !== null ? <button type="button" disabled={historyBusy} onClick={() => void moreHistory()}>{labels.moreHistory}</button> : null}
        {historyMessage ? <p role="status">{historyMessage}</p> : null}
      </details>
    </div> : null}
    {busy || message ? <p role="status">{busy ? labels.working : message}</p> : null}
    {retry ? <div className="output-dialog-actions"><button type="button" disabled={!enabled || busy} onClick={() => void submit(retry)}>{labels.retry}</button>{!uncertain ? <button type="button" disabled={busy} onClick={() => { setRetry(undefined); setOffsetReview(undefined); setMessage(""); }}>Review request</button> : null}</div> : null}
  </section>;
}
