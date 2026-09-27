"use client";

import { uiLabels } from "../experience/ui-labels.ts";
import { useEffect, useRef, useState } from "react";
import { editorialApi, type EditorialQueue, type PhraseLists, type EditorialCandidate } from "../experience/editorial-api.ts";
import { authorityDisabled, intentError, prepareEditorialCommand, sendEditorialCommand, secondsToMicroseconds, type EditorialAuthority, type EditorialIntent, type EditorialCommand, type EditorialResult, type ReviewAction } from "../experience/editorial-actions.ts";
import { candidateFlags, candidateLabel, queueSummary, reviewLabels, sessionGroups, uniformSuggestionTiming, rangeInput, rangeSeconds } from "../experience/editorial-presentation.ts";
import { phrasePreview } from "../experience/editorial-normalization.ts";
import { fixtureQueue, fixturePhraseLists } from "../experience/editorial-fixtures.ts";

export interface EditorialSurfaceProps {
  context: EditorialAuthority;
  eventName: string;
  sessions: { id: string; title: string }[];
  initialQueue: EditorialQueue | null;
}

export function CandidateDetails({ item }: { item: EditorialQueue["items"][number] }) {
  const candidate = item.candidate;
  const provenance = Object.fromEntries(Object.entries(candidate.provenance ?? {}).filter(([key]) => key !== "normalized_phrase"));
  return <details><summary>{uiLabels.details}</summary><dl className="editorial-details">
    {Object.entries({ origin: candidate.origin, review_state: candidate.review_state, candidate_moment_id: candidate.candidate_moment_id, session_id: candidate.session_id, stage_id: item.stage_id, candidate_revision: candidate.revision, expected_session_revision: candidate.expected_session_revision, operation_id: candidate.operation_id, actor_id: candidate.actor_id, created_at: candidate.created_at, updated_at: candidate.updated_at, source_kind: candidate.source_kind, reason_code: candidate.reason_code, location_conflict_reason: candidate.location_conflict_reason, ...provenance }).filter(([, value]) => value !== null && value !== undefined).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd><code tabIndex={0}>{String(value)}</code></dd></div>)}
  </dl>
    {item.decisions.length ? <details><summary>Review history · {item.decisions.length}{item.history_truncated ? " shown" : ""}</summary>{item.decisions.map((d) => <p key={d.review_decision_id}>{d.action.replaceAll("_", " ")} · {d.reason} · {d.decided_at}<br />{d.adjusted_timeline_start_microseconds !== null ? `Adjusted range: ${d.adjusted_timeline_start_microseconds / 1_000_000}–${d.adjusted_timeline_end_microseconds! / 1_000_000} seconds · ` : ""}<code>{d.review_decision_id}</code>{d.notes ? ` · ${d.notes}` : ""}</p>)}</details> : null}
    {item.clips.length ? <details><summary>Editorial Clips · {item.clips.length}</summary>{item.clips.map((clip) => <p key={clip.clip_id}>{clip.timeline_start_microseconds / 1_000_000}–{clip.timeline_end_microseconds / 1_000_000} seconds · <code>{clip.clip_id}</code></p>)}</details> : null}
    {item.history_truncated ? <p>Earlier decisions or clips are outside the displayed history.</p> : null}
  </details>;
}

export function EditorialReviewSurface({ context, eventName, sessions, initialQueue }: EditorialSurfaceProps) {
  const [queue, setQueue] = useState(initialQueue);
  const [cursor, setCursor] = useState<string>();
  const [previous, setPrevious] = useState<(string | undefined)[]>([]);
  const [reading, setReading] = useState(false);
  const [fresh, setFresh] = useState(Boolean(initialQueue));
  const [message, setMessage] = useState("");
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<{ intent: EditorialIntent; consequence: string; snapshot: string }>();
  const [result, setResult] = useState<EditorialResult>();
  const [resultKind, setResultKind] = useState<EditorialIntent["kind"]>();
  const [retry, setRetry] = useState<EditorialCommand>();
  const [phraseRefresh, setPhraseRefresh] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const status = useRef<HTMLParagraphElement>(null);
  const submitting = useRef(false);
  const snapshot = JSON.stringify({ context, queue });
  const disabled = authorityDisabled(context) ?? (!fresh ? "Refresh the queue before acting." : undefined);
  const locked = busy || reading || Boolean(retry);

  useEffect(() => {
    if (pending) dialog.current?.showModal();
    else if (dialog.current?.open) {
      dialog.current.close();
      (returnFocus.current?.isConnected && !(returnFocus.current as HTMLButtonElement).disabled ? returnFocus.current : status.current)?.focus();
    }
  }, [pending]);

  async function readPage(next?: string): Promise<boolean> {
    setReading(true); setMessage("");
    try {
      const page = context.fixture ? fixtureQueue(next) : await editorialApi().queue(context.eventId, next);
      if (page.event_id !== context.eventId || page.items.some((i) => i.event_id !== context.eventId)) throw new Error();
      setQueue(page); setCursor(next); setFresh(true); return true;
    } catch { setFresh(false); setMessage("Review queue unavailable. Displayed rows may be stale; refresh to continue."); return false; }
    finally { setReading(false); }
  }
  async function refresh() { await readPage(cursor); setPhraseRefresh((n) => n + 1); }
  function begin(intent: EditorialIntent, consequence: string) {
    if (disabled || locked || intentError(intent)) return;
    returnFocus.current = document.activeElement as HTMLElement | null;
    setPending({ intent, consequence, snapshot });
  }
  async function execute(command: EditorialCommand) {
    if (submitting.current) return;
    submitting.current = true; setBusy(true); setResult(undefined); setResultKind(command.kind);
    try {
      const outcome = await sendEditorialCommand(command, fetch, refresh);
      setResult(outcome); setRetry(outcome.kind === "network_failure" ? command : undefined);
    } finally { submitting.current = false; setBusy(false); }
  }
  function confirm() {
    if (!pending || pending.snapshot !== snapshot || disabled || locked) return;
    const command = prepareEditorialCommand(context, pending.intent, true);
    if (!command) return;
    setPending(undefined); void execute(command);
  }
  return <div className="editorial-surface">
    <header><span className="eyebrow">Editorial · {eventName}</span><h1>{uiLabels.editorial}</h1><p>{queue ? queueSummary(queue) : "Review queue unavailable"}</p><p>{uiLabels.humanReview}</p></header>
    <p ref={status} tabIndex={-1} role="status">{busy ? "Working…" : reading ? "Refreshing…" : message || disabled || (retry ? "Resolve the pending command before another action." : "")}</p>
    {result && resultKind !== "derive" ? <div><p role="status">{result.message}</p>{result.identifiers ? <details><summary>Result details</summary><pre>{JSON.stringify(result.identifiers, null, 2)}</pre></details> : null}</div> : null}
    {retry ? <button type="button" disabled={busy || reading || context.launchContext !== retry.launchContext} onClick={() => void execute(retry)}>Retry same command</button> : null}
    <div className="editorial-paging">
      <button type="button" disabled={locked} onClick={() => void readPage(cursor)}>Refresh queue</button>
      <button type="button" disabled={locked || !previous.length} onClick={async () => { const before = previous.at(-1); if (await readPage(before)) { setPrevious(previous.slice(0, -1)); setSelected(""); } }}>Previous page</button>
      <span>Page {previous.length + 1} · {queue?.items.length ?? 0} shown (up to 100)</span>
      <button type="button" disabled={locked || !fresh || !queue?.next_cursor} onClick={async () => { if (await readPage(queue!.next_cursor!)) { setPrevious([...previous, cursor]); setSelected(""); } }}>Next page</button>
    </div>
    <div aria-label="Event review queue">{queue && sessionGroups(queue).map((group) => {
      const sharedTiming = uniformSuggestionTiming(group.items);
      return <section className="editorial-session" key={group.sessionId} aria-labelledby={`session-${group.sessionId}`}>
        <h2 id={`session-${group.sessionId}`}>{sessions.find((s) => s.id === group.sessionId)?.title || "Session title unavailable"}</h2>
        {sharedTiming ? <p>All suggestions use {sharedTiming.toLowerCase()}</p> : null}
        <ul className="editorial-queue">{group.items.map((item) => {
      const candidate = item.candidate;
      return <li key={candidate.candidate_moment_id}>
        <div className="editorial-row"><button type="button" disabled={locked} aria-pressed={selected === candidate.candidate_moment_id} onClick={() => setSelected(candidate.candidate_moment_id)}>{candidateLabel(candidate)}</button>
          <span>{uiLabels.origin[candidate.origin]}{candidate.origin === "derived" && candidate.provenance ? ` · “${candidate.provenance.normalized_phrase}”` : ""}</span>
          {candidate.review_state !== "unreviewed" ? <span>{reviewLabels[candidate.review_state]}</span> : null}
          {candidateFlags(candidate).filter((flag) => flag !== sharedTiming).map((flag) => <strong key={flag}>{flag}</strong>)}
          <CandidateDetails item={item} /></div>
        {selected === candidate.candidate_moment_id ? <ReviewForm key={`${candidate.candidate_moment_id}:${JSON.stringify(item.decisions)}`} candidate={candidate} title={sessions.find((s) => s.id === candidate.session_id)?.title} disabled={Boolean(disabled) || locked} begin={begin} /> : null}
      </li>;
    })}</ul></section>;
    })}</div>
    {fresh && queue?.items.length === 0 ? <p>No moments on this page.</p> : null}
    {!queue?.items.some((i) => i.candidate.candidate_moment_id === selected) ? <p>Select a moment to review.</p> : null}
    <details className="editorial-tools"><summary>Phrase lists and derivation</summary>
      <PhraseTools context={context} sessions={sessions} disabled={Boolean(disabled) || locked} refresh={phraseRefresh} begin={begin} result={resultKind === "derive" ? result : undefined} />
    </details>
    <dialog ref={dialog} className="output-confirmation" aria-labelledby="editorial-consequence" onCancel={(event) => { event.preventDefault(); setPending(undefined); }} onClose={() => { setPending(undefined); (returnFocus.current?.isConnected && !(returnFocus.current as HTMLButtonElement).disabled ? returnFocus.current : status.current)?.focus(); }}>
      <form onSubmit={(event) => { event.preventDefault(); confirm(); }}>
        <p id="editorial-consequence">{pending?.consequence}</p>
        {pending?.snapshot !== snapshot ? <p>State changed. Cancel and review the current state.</p> : null}
        <div className="output-dialog-actions"><button autoFocus type="button" onClick={() => setPending(undefined)}>Cancel</button><button type="submit" disabled={!pending || pending.snapshot !== snapshot || Boolean(disabled) || locked}>Confirm action</button></div>
      </form>
    </dialog>
  </div>;
}

export function ReviewForm({ candidate, title, disabled, begin }: { candidate: EditorialCandidate; title?: string; disabled: boolean; begin: (intent: EditorialIntent, consequence: string) => void }) {
  const [action, setAction] = useState<ReviewAction | "">(candidate.review_state === "approved" || candidate.review_state === "rejected" ? "" : "approve_and_create_clip");
  const [reason, setReason] = useState("");
  const [start, setStart] = useState(rangeInput(candidate.timeline_start_microseconds));
  const [end, setEnd] = useState(candidate.timeline_end_microseconds === null ? "" : rangeInput(candidate.timeline_end_microseconds));
  const range = action === "approve_and_create_clip" || action === "revise_range";
  const intent: EditorialIntent | undefined = action ? { kind: "review", candidate, action, reason, ...(range ? { start: secondsToMicroseconds(rangeSeconds(start)), end: secondsToMicroseconds(rangeSeconds(end)) } : {}) } : undefined;
  const approvalLabel = candidate.review_state === "approved" ? "Approve & create another clip" : "Approve & create clip";
  const label = action ? { approve_and_create_clip: approvalLabel, reject: "Reject", revise_range: "Revise range", defer: "Defer" }[action] : "Choose a review action";
  const consequence = action === "approve_and_create_clip" ? `Create ${candidate.review_state === "approved" ? "another" : "an"} Editorial Clip for ${title || "this Session"} at ${start}–${end} into the Session. No render or publication is requested.`
    : action === "revise_range" ? `Record a range revision request for ${start}–${end} into the Session. The moment location stays unchanged; a later approval must explicitly use the desired range.`
    : `${action === "reject" ? "Reject" : "Defer"} this moment. Previous decisions and clips are preserved.`;
  return <section className="editorial-review" aria-label="Selected moment review"><h2>{uiLabels.reviewMoment}</h2>
    <form onSubmit={(event) => { event.preventDefault(); if (!disabled && intent && !intentError(intent)) begin(intent, `${consequence}${candidateFlags(candidate).length ? ` ${candidateFlags(candidate).join(" · ")}.` : ""}`); }}>
      <label htmlFor="editorial-action">Review action</label><select autoFocus id="editorial-action" value={action} onChange={(event) => setAction(event.target.value as ReviewAction | "")} disabled={disabled} required><option value="" disabled>Choose a review action</option><option value="approve_and_create_clip">{approvalLabel}</option><option value="reject">Reject</option><option value="revise_range">Revise range</option><option value="defer">Defer</option></select>
      {range ? <div className="editorial-range"><label htmlFor="editorial-start">Start — {uiLabels.rangeTime}</label><input id="editorial-start" type="text" inputMode="decimal" value={start} onChange={(e) => setStart(e.target.value)} required disabled={disabled} /><label htmlFor="editorial-end">End — {uiLabels.rangeTime}</label><input id="editorial-end" type="text" inputMode="decimal" value={end} onChange={(e) => setEnd(e.target.value)} required disabled={disabled} /></div> : null}
      <label htmlFor="editorial-reason">Reason (required)</label><textarea id="editorial-reason" maxLength={500} required value={reason} onChange={(e) => setReason(e.target.value)} disabled={disabled} />
      <button type="submit" disabled={disabled || !intent || Boolean(intentError(intent))}>{label}</button>
    </form>
  </section>;
}

export function PhraseTools({ context, sessions, disabled, refresh, begin, result }: { result?: EditorialResult; context: EditorialAuthority; sessions: EditorialSurfaceProps["sessions"]; disabled: boolean; refresh: number; begin: (intent: EditorialIntent, consequence: string) => void }) {
  const [key, setKey] = useState("highlights");
  const [loadedKey, setLoadedKey] = useState("");
  const [page, setPage] = useState<PhraseLists>();
  const [after, setAfter] = useState(0);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [name, setName] = useState("");
  const [version, setVersion] = useState("1");
  const [text, setText] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [phraseId, setPhraseId] = useState("");
  const [loadedRefresh, setLoadedRefresh] = useState(refresh);
  const preview = phrasePreview(text);
  const publish: EditorialIntent = { kind: "publish", key, name, version: Number(version), text };
  const chosen = page?.items.find((p) => `${p.phrase_list_id}:${p.version}` === phraseId);
  const stale = loadedKey !== key.trim() || loadedRefresh !== refresh;
  const requestSequence = useRef(0);
  async function load(next = 0) {
    const request = ++requestSequence.current;
    setLoading(true); setMessage(""); setPhraseId("");
    try {
      const data = context.fixture ? fixturePhraseLists() : await editorialApi().phraseLists(context.eventId, key.trim(), next);
      if (data.items.some((p) => p.event_id !== context.eventId || p.key !== key.trim())) throw new Error();
      if (request !== requestSequence.current) return;
      setPage(data); setAfter(next); setLoadedKey(key.trim()); setLoadedRefresh(refresh);
    } catch { setPage(undefined); setMessage("Phrase-list versions unavailable. Try loading again."); }
    finally { if (request === requestSequence.current) setLoading(false); }
  }
  return <div className="editorial-phrase-tools">
    <h2>Event phrase-list versions</h2>
    <form onSubmit={(event) => { event.preventDefault(); if (!loading && key.trim()) void load(); }}><label htmlFor="phrase-key">Phrase-list key</label><input id="phrase-key" value={key} maxLength={100} required disabled={loading} onChange={(e) => setKey(e.target.value)} /><button type="submit" disabled={loading || !key.trim()}>Load versions</button></form>
    <p>Versions are looked up by Event and phrase-list key.</p>
    {message ? <p role="status">{message}</p> : null}
    {stale && page ? <p>Reload versions after changes before deriving.</p> : null}
    {page ? <><ul>{page.items.map((p) => <li key={`${p.phrase_list_id}:${p.version}`}><strong>{p.name} · version {p.version}</strong><details><summary>Phrase-list details</summary><p>{p.phrases.join(" · ")}</p><code>{p.phrase_list_id}</code><p>Created {p.created_at} · <code>{p.created_by}</code></p></details></li>)}</ul>{!page.items.length ? <p>No versions for this key.</p> : null}<div className="editorial-paging"><button type="button" disabled={loading || after === 0} onClick={() => void load()}>First versions</button><button type="button" disabled={loading || stale || page.next_after === null} onClick={() => void load(page.next_after!)}>Next versions</button></div></> : null}
    <details><summary>Publish a new version</summary><form onSubmit={(event) => { event.preventDefault(); if (!disabled && !intentError(publish)) begin(publish, `Publish immutable version ${version} of ${name} under “${key}” with ${preview.rows.length} phrases. Existing versions are preserved.`); }}>
      <label htmlFor="phrase-name">List name</label><input id="phrase-name" value={name} maxLength={200} required onChange={(e) => setName(e.target.value)} />
      <label htmlFor="phrase-version">New version</label><input id="phrase-version" type="number" min="1" step="1" value={version} required onChange={(e) => setVersion(e.target.value)} />
      <label htmlFor="phrase-text">Phrases (one per line, 1–200)</label><textarea id="phrase-text" value={text} required onChange={(e) => setText(e.target.value)} />
      <p>Normalization preview · NFKC, casefold, whitespace, alphanumeric tokens</p>
      {preview.error ? <p role="alert">{preview.error}</p> : null}
      <ol className="editorial-preview">{preview.rows.slice(0, 201).map((r) => <li key={r.line}>{r.tokens.join(" · ") || "Empty token sequence"}{r.error ? <strong> — {r.error}</strong> : null}</li>)}</ol>
      <button type="submit" disabled={disabled || Boolean(intentError(publish))}>Publish version</button>
    </form></details>
    <h2>Suggest moments</h2><form onSubmit={(event) => { event.preventDefault(); if (!disabled && !stale && chosen && sessions.some((s) => s.id === sessionId)) begin({ kind: "derive", sessionId, phraseListId: chosen.phrase_list_id, version: chosen.version }, `Suggest moments for ${sessions.find((s) => s.id === sessionId)!.title} using ${chosen.name} version ${chosen.version}. ${uiLabels.humanReview}`); }}>
      <label htmlFor="derivation-session">Session (available Event Sessions)</label><select id="derivation-session" value={sessionId} onChange={(e) => setSessionId(e.target.value)} required><option value="">Choose a Session</option>{sessions.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}</select>
      <label htmlFor="derivation-phrases">Phrase list and version</label><select id="derivation-phrases" value={phraseId} disabled={stale || loading} onChange={(e) => setPhraseId(e.target.value)} required><option value="">Choose a loaded version</option>{page?.items.map((p) => <option key={`${p.phrase_list_id}:${p.version}`} value={`${p.phrase_list_id}:${p.version}`}>{p.name} · version {p.version}</option>)}</select>
      <div className="derivation-control"><button type="submit" disabled={disabled || stale || loading || !chosen || !sessions.some((s) => s.id === sessionId)}>Run derivation</button>
      {result ? <div className="derivation-result"><p role="status">{result.message}</p>{result.identifiers ? <details><summary>{uiLabels.details}</summary><pre>{JSON.stringify(result.identifiers, null, 2)}</pre></details> : null}</div> : null}</div>
    </form>
  </div>;
}
