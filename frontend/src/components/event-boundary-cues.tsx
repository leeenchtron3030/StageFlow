"use client";

import { useRef, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { boundaryCuesApi, type BoundaryCueData, type CueComposition, type CueCustom, type CueRole } from "../experience/boundary-cues-api.ts";
import { addCustomCue, addOptIn, aggregateCues, availableOptIns, catalogMatches, composedTime, compositionDraft, cueLimits, cueProfileName, cueSummary, evidenceLabels, exceptionEvidence, groupCuePhrases, hasCueEdits, phraseKey, prepareCueCommand, profileDraft, removeCue, removedCues, restoreCue, sendCueCommand, toggleCueGroup, type CueDraft } from "../experience/boundary-cues.ts";
import { boundaryCueLabels as labels, uiLabels } from "../experience/ui-labels.ts";

const subscribeTimeZone = () => () => undefined;
const localTimeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

function CompositionDetails({ item, timeZone }: { item: CueComposition; timeZone: string }) {
  return <li>
    <p>Version {item.version} · <time dateTime={item.composed_at}>{composedTime(item.composed_at, timeZone)}</time></p>
    <dl className="outputs-facts">
      <div><dt>Operator ID</dt><dd><code className="copyable-id" tabIndex={0}>{item.composed_by}</code></dd></div>
      <div><dt>{labels.catalog}</dt><dd>{item.catalog_id} · version {item.catalog_version}</dd></div>
      <div><dt>Profile key</dt><dd>{item.profile_key ?? "None"}</dd></div>
      <div><dt>Group keys</dt><dd>{item.groups.map((g) => `${g.key} (v${g.version})`).join(", ") || "None"}</dd></div>
      <div><dt>Catalog digest</dt><dd><code className="copyable-id" tabIndex={0}>{item.catalog_digest}</code></dd></div>
      <div><dt>Command ID</dt><dd><code className="copyable-id" tabIndex={0}>{item.command_id}</code></dd></div>
      <div><dt>Start list</dt><dd>{item.start_cue_list.id} · version {item.start_cue_list.version}</dd></div>
      <div><dt>End list</dt><dd>{item.end_cue_list.id} · version {item.end_cue_list.version}</dd></div>
    </dl>
  </li>;
}

export function EventBoundaryCues({ eventId, data, authorized, launchContext, serverTimeZone = "UTC" }: {
  eventId: string; data?: BoundaryCueData; authorized: boolean; launchContext?: string; serverTimeZone?: string;
}) {
  const router = useRouter();
  // Hydrate with the server's zone, then show the viewer's local time without a mismatch.
  const timeZone = useSyncExternalStore(subscribeTimeZone, localTimeZone, () => serverTimeZone);
  const initial = data ? data.current ? compositionDraft(data.current) : profileDraft(data.catalog, data.catalog.profiles[0]?.key ?? null) : undefined;
  const [draft, setDraft] = useState<CueDraft | undefined>(initial);
  const [editing, setEditing] = useState(false);
  const [review, setReview] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [pendingProfile, setPendingProfile] = useState<string>();
  const [customText, setCustomText] = useState("");
  const [customRole, setCustomRole] = useState<CueCustom["role"]>("start");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [removalNotice, setRemovalNotice] = useState(0);
  const [retry, setRetry] = useState<ReturnType<typeof prepareCueCommand>>();
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const [history, setHistory] = useState(data?.history);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [historyMessage, setHistoryMessage] = useState("");
  const submitting = useRef(false);
  const compatible = Boolean(data && (!data.current || catalogMatches(data.catalog, data.current)));
  const enabled = authorized && Boolean(launchContext) && compatible && !needsRefresh;
  const counts = data && draft ? aggregateCues(data.catalog, draft) : undefined;
  const limits = [...(data && draft ? cueLimits(data.catalog, draft) : []), ...(customText.trim() ? [labels.pendingCustom] : [])];
  function change(next: CueDraft) { setDraft(next); setDirty(true); setMessage(""); setRemovalNotice(0); }
  function selectProfile(key: string) {
    if (!data) return;
    setDraft(profileDraft(data.catalog, key)); setDirty(false); setPendingProfile(undefined); setCustomText(""); setMessage(""); setRemovalNotice(0);
  }
  async function submit(command: ReturnType<typeof prepareCueCommand>) {
    if (!enabled || !launchContext || submitting.current) return;
    submitting.current = true; setBusy(true);
    try {
      const result = await sendCueCommand(eventId, command, launchContext);
      setMessage(result.message); setRetry(result.retry ? command : undefined);
      if (result.saved || result.message === labels.conflict) {
        setEditing(false); setReview(false); setNeedsRefresh(result.saved); router.refresh();
      } else if (!result.retry) setReview(false);
    } finally { submitting.current = false; setBusy(false); }
  }
  async function moreHistory() {
    if (!history || history.next_after === null || historyBusy) return;
    setHistoryBusy(true); setHistoryMessage("");
    try {
      const page = await boundaryCuesApi().history(eventId, history.next_after);
      setHistory({ ...page, items: [...history.items, ...page.items.filter((p) => !history.items.some((old) => old.version === p.version))] });
    } catch { setHistoryMessage(labels.historyFailed); }
    finally { setHistoryBusy(false); }
  }
  const versions = history ? [...history.items, ...(data?.current && !history.items.some((p) => p.version === data.current!.version) ? [data.current] : [])].sort((a, b) => b.version - a.version) : [];
  const groupControl = (group: BoundaryCueData["catalog"]["groups"][number]) => <label key={group.key}>
    <input type="checkbox" checked={draft!.group_keys.includes(group.key)} onChange={() => {
      const next = toggleCueGroup(data!.catalog, draft!, group.key);
      change(next);
      if (!draft!.group_keys.includes(group.key)) setRemovalNotice(new Set(next.exclude.filter((c) => c.group_key === group.key).map((c) => phraseKey(c.phrase))).size);
    }} />
    {group.name} <span>· {group.phrases.filter((p) => p.default).length} default / {group.phrases.filter((p) => !p.default).length} optional phrases</span>
  </label>;
  return <section className="detail-panel boundary-cues-panel" aria-labelledby="boundary-cues-title">
    <div className="section-heading"><div><span className="eyebrow">{labels.kicker}</span><h2 id="boundary-cues-title">{labels.title}</h2></div></div>
    {data && draft && counts ? <>
      <p><strong>{editing ? `${cueProfileName(data.catalog, draft)} · ${draft.group_keys.length} groups · ${counts.start} start / ${counts.end} end phrases` : cueSummary(data.catalog, data.current, timeZone)}</strong></p>
      {!compatible ? <p role="alert">{labels.catalogMismatch}</p> : null}
      {!editing ? <button type="button" disabled={!enabled || busy || Boolean(retry)} onClick={() => { setDraft(initial); setDirty(false); setCustomText(""); setEditing(true); setMessage(""); setRemovalNotice(0); }}>{labels.edit}</button> : null}
      {!authorized || !launchContext ? <p>{labels.readOnly}</p> : null}
      {editing ? <form onSubmit={(event) => { event.preventDefault(); if (!enabled || busy || retry || limits.length || pendingProfile !== undefined) return; if (review) void submit(prepareCueCommand(data.catalog, draft)); else setReview(true); }}>
        {review ? <>
          <p>{labels.consequence}</p>
          <p>{cueProfileName(data.catalog, draft)} · {draft.group_keys.length} groups · {counts.start} start / {counts.end} end phrases</p>
          <p>{labels.honesty}</p>
        </> : <fieldset disabled={busy || Boolean(retry) || !enabled} className="cue-editor">
          <legend>{labels.title}</legend>
          <label htmlFor="cue-profile">{labels.profile}</label>
          <select id="cue-profile" value={draft.profile_key ?? ""} onChange={(event) => {
            const next = event.target.value;
            if (dirty || hasCueEdits(data.catalog, draft) || customText.trim()) setPendingProfile(next); else selectProfile(next);
          }}><option value="" disabled>{labels.customProfile}</option>{data.catalog.profiles.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}</select>
          {pendingProfile !== undefined ? <div role="alert" className="cue-profile-confirm">
            <p>{labels.profileReset}</p><p>{data.catalog.profiles.find((p) => p.key === pendingProfile)?.name}</p>
            <button type="button" onClick={() => selectProfile(pendingProfile)}>{labels.confirmProfile}</button>
            <button type="button" onClick={() => setPendingProfile(undefined)}>{labels.keepEditing}</button>
          </div> : null}
          <h3>{labels.groups}</h3>
          <div className="cue-groups cue-selected-groups">{data.catalog.groups.filter((g) => draft.group_keys.includes(g.key)).map(groupControl)}</div>
          <details className="cue-more-groups"><summary>{labels.moreGroups}</summary>
            {Array.from(new Set(data.catalog.groups.filter((g) => !draft.group_keys.includes(g.key)).map((g) => g.category))).map((category) => <fieldset key={category} className="cue-groups"><legend>{category}</legend>
              {data.catalog.groups.filter((g) => g.category === category && !draft.group_keys.includes(g.key)).map(groupControl)}
            </fieldset>)}
          </details>
          <h3>{labels.aggregate}</h3>
          <p>{labels.evidenceLegend} {labels.honesty}</p>
          {(Object.keys(labels.roles) as CueRole[]).map((role) => <details key={role} className="cue-role"><summary>{labels.roles[role]} · {counts.byRole[role].length} phrases{role === "segment" ? ` · ${labels.segmentNote}` : ""}</summary>
            {groupCuePhrases(counts.byRole[role]).map(({ source, phrases }) => <div key={source} className="cue-source">
              <h4>{source}</h4>
              <ul className="cue-phrases">{phrases.map((phrase) => <li key={phrase.key} className="cue-phrase-line">
                <span className="cue-phrase-text">{phrase.text}
                  {phrase.sources.filter((s) => s !== labels.custom).length > 1 ? <small>{labels.alsoIn(phrase.sources.filter((s) => s !== labels.custom).length - 1)}</small> : null}
                  {exceptionEvidence(phrase.evidence).map((evidence) => <span className="cue-badge" key={evidence}>{evidence}</span>)}
                  {phrase.warning ? <span className="cue-badge">{labels.warning}</span> : null}
                </span>
                <button type="button" aria-label={`${labels.remove}: ${phrase.text}`} onClick={() => change(removeCue(data.catalog, draft, phrase.key))}>{labels.remove}</button>
              </li>)}</ul>
            </div>)}
          </details>)}
          {removalNotice > 0 ? <p role="status">{labels.stayRemoved(removalNotice)}</p> : null}
          <details className="cue-role cue-removed"><summary>{labels.removed} · {removedCues(draft).length}</summary>
            <ul className="cue-phrases">{removedCues(draft).map((phrase) => <li key={phrase.key} className="cue-phrase-line">
              <span>{phrase.text}</span><button type="button" aria-label={`${labels.addBack}: ${phrase.text}`} onClick={() => change(restoreCue(draft, phrase.key))}>{labels.addBack}</button>
            </li>)}</ul>
          </details>
          <details className="cue-role"><summary>{labels.optIns} · {availableOptIns(data.catalog, draft).length}</summary>
            <ul className="outputs-rows">{availableOptIns(data.catalog, draft).map(({ group, phrase }) => <li key={`${group.key}:${phrase.text}`}>
              <div className="cue-phrase-line"><strong>{phrase.text}</strong><button type="button" aria-label={`${labels.add}: ${phrase.text} (${group.name})`} onClick={() => change(addOptIn(data.catalog, draft, { group_key: group.key, phrase: phrase.text }))}>{labels.add}</button></div>
              <div className="cue-badges"><span>{group.name}</span><span>{labels.roles[phrase.role]}</span>{exceptionEvidence(evidenceLabels(phrase.evidence)).map((e) => <span className="cue-badge" key={e}>{e}</span>)}<span className="cue-badge">{labels.warning}</span></div>
            </li>)}</ul>
          </details>
          <label htmlFor="cue-custom">{labels.customPhrase}</label><input id="cue-custom" value={customText} onChange={(event) => setCustomText(event.target.value)} />
          <label htmlFor="cue-custom-role">{labels.role}</label><select id="cue-custom-role" value={customRole} onChange={(event) => setCustomRole(event.target.value as CueCustom["role"])}>
            {(["start", "end", "changeover"] as const).map((role) => <option key={role} value={role}>{labels.roles[role]}</option>)}
          </select>
          <button type="button" onClick={() => { try { change(addCustomCue(draft, customText, customRole)); setCustomText(""); } catch { setMessage(labels.invalidCustom); } }}>{labels.addCustom}</button>
        </fieldset>}
        <p role="status">Start: {counts.start} / 200 · End: {counts.end} / 200</p>
        {limits.length ? <div role="alert">{limits.map((error) => <p key={error}>{error}</p>)}</div> : null}
        <div className="output-dialog-actions">
          <button type="button" disabled={busy || Boolean(retry)} onClick={() => { if (review) setReview(false); else { setEditing(false); setPendingProfile(undefined); } }}>{review ? labels.back : labels.cancel}</button>
          <button type="submit" disabled={!enabled || busy || Boolean(retry) || limits.length > 0 || pendingProfile !== undefined}>{review ? labels.confirm : labels.publish}</button>
        </div>
      </form> : null}
      <details className="diagnostic-details"><summary>{uiLabels.details}</summary>
        <h3>{labels.history}</h3>
        {versions.length ? <ul className="outputs-rows">{versions.map((item) => <CompositionDetails key={item.version} item={item} timeZone={timeZone} />)}</ul> : <p>No published versions.</p>}
        {history?.next_after !== null && history?.next_after !== undefined ? <button type="button" disabled={historyBusy} onClick={() => void moreHistory()}>{labels.moreHistory}</button> : null}
        {historyMessage ? <p role="status">{historyMessage}</p> : null}
        <p>{labels.catalog}: {data.catalog.id} · version {data.catalog.version}</p>
        <dl className="outputs-facts">{data.catalog.profiles.map((p) => <div key={p.key}><dt>{p.name}</dt><dd>{p.key}</dd></div>)}{data.catalog.groups.map((g) => <div key={g.key}><dt>{g.name}</dt><dd>{g.key} · version {g.version}</dd></div>)}</dl>
      </details>
    </> : <p>{labels.unavailable}</p>}
    {busy || message ? <p role="status">{busy ? labels.working : message}</p> : null}
    {retry ? <button type="button" disabled={!enabled || busy} onClick={() => void submit(retry)}>{labels.retry}</button> : null}
  </section>;
}
