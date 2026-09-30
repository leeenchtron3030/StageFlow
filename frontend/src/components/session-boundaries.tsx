"use client";

import { useRef, useState, useSyncExternalStore, useTransition } from "react";
import { useRouter } from "next/navigation";
import { boundariesApi, type BoundaryDecisionHistory, type BoundaryProposal } from "../experience/session-boundaries-api.ts";
import { boundarySummary, boundaryTime, boundaryTimes, boundaryTimesLabel, prepareBoundaryCommand, sendBoundaryCommand, type BoundaryCommand } from "../experience/session-boundaries.ts";
import { boundaryLabels as labels } from "../experience/ui-labels.ts";

const subscribe = () => () => undefined;
const zoneSnapshot = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

export function SessionBoundaries({ eventId, proposals, currentStart, currentEnd, authorized, launchContext, serverTimeZone = "UTC" }: {
  eventId: string; proposals?: BoundaryProposal[]; currentStart?: string; currentEnd?: string;
  authorized: boolean; launchContext?: string; serverTimeZone?: string;
}) {
  const router = useRouter();
  const timeZone = useSyncExternalStore(subscribe, zoneSnapshot, () => serverTimeZone);
  const [selection, setSelection] = useState<{ proposal: BoundaryProposal; kind: BoundaryCommand["kind"] }>();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const [retry, setRetry] = useState<BoundaryCommand>(), [uncertain, setUncertain] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refused, setRefused] = useState(false);
  const [refreshPending, startRefresh] = useTransition();
  const submitting = useRef(false);
  const enabled = authorized && Boolean(launchContext) && Boolean(proposals) && !refreshing && !refreshPending;
  const locked = !enabled || busy || Boolean(retry) || refused;
  async function submit(command: BoundaryCommand) {
    if (!enabled || !launchContext || submitting.current) return;
    submitting.current = true; setBusy(true);
    try {
      const result = await sendBoundaryCommand(eventId, command, launchContext);
      setMessage(result.message); setRetry(result.uncertain ? command : undefined); setUncertain(result.uncertain);
      setRefused(!result.saved && !result.uncertain);
      if (!result.saved && !result.uncertain) setSelection(undefined);
      if (result.saved) { setSelection(undefined); setRefreshing(true); router.refresh(); }
    } finally { submitting.current = false; setBusy(false); }
  }
  if (proposals?.length === 0) return null;
  return <section id="suggested-boundaries" className="detail-panel suggestions-panel" aria-labelledby="boundaries-title">
    <div className="section-heading"><h2 id="boundaries-title">{labels.title}</h2></div>
    {proposals ? <ul className="suggestion-rows">{proposals.map((proposal) => {
      const current = proposal.boundary_kind === "start" ? currentStart : currentEnd;
      return <li className="suggestion-row" key={proposal.proposal_id}>
        <div className="suggestion-line">
          <div className="suggestion-info"><strong>{boundarySummary(proposal, current)}</strong>
            <div className="suggestion-facts"><span aria-label={boundaryTimesLabel(current, proposal.boundary_at, timeZone, currentStart)}>{boundaryTimes(current, proposal.boundary_at, timeZone, currentStart)}</span>
            </div>
          </div>
          <div className="suggestion-actions">
            <details className="suggestion-evidence"><summary>{labels.details}</summary>
              <p>These times are estimates. Recorder start and length are unverified unless qualified. Recording changes do not establish content boundaries.</p>
              <p>Proposed {boundaryTime(proposal.proposed_at, timeZone)}</p>
              <dl><dt>Proposal ID</dt><dd>{proposal.proposal_id}</dd><dt>Proposer ID</dt><dd>{proposal.proposer_id}</dd>
                <dt>Evidence IDs</dt><dd>{proposal.evidence_ids.join(", ")}</dd><dt>Policy</dt><dd>{proposal.policy_id} · {proposal.policy_version}</dd>
                <dt>Suggested time</dt><dd>{proposal.boundary_at}</dd><dt>Reason</dt><dd>{proposal.reason}</dd><dt>Authorized use</dt><dd>{proposal.authorized_use}</dd></dl>
            </details>
            <button type="button" disabled={locked || Boolean(selection) || !current} onClick={() => { setSelection({ proposal, kind: "apply" }); setReason(""); setMessage(""); }}>{labels.apply}</button>
            <button type="button" disabled={locked || Boolean(selection)} onClick={() => { setSelection({ proposal, kind: "dismiss" }); setReason(""); setMessage(""); }}>{labels.dismiss}</button>
          </div>
        </div>
        {selection?.proposal.proposal_id === proposal.proposal_id ? <form className="suggestion-confirm" onSubmit={(event) => {
          event.preventDefault(); if (locked) return;
          void submit(prepareBoundaryCommand(proposal, selection.kind, reason));
        }}>
          <p><strong>{selection.kind === "apply" ? `Change the Session's ${proposal.boundary_kind}?` : `Dismiss this suggested ${proposal.boundary_kind}? The Session's time will stay unchanged.`}</strong></p>
          <p aria-label={boundaryTimesLabel(current, proposal.boundary_at, timeZone, currentStart)}>{boundaryTimes(current, proposal.boundary_at, timeZone, currentStart)}</p>
          {selection.kind === "dismiss" ? <><label htmlFor="boundary-dismiss-reason">Reason (optional)</label>
            <select id="boundary-dismiss-reason" disabled={locked} value={reason} onChange={(event) => setReason(event.target.value)}>
              <option value="">No reason</option>{labels.dismissReasons.map((r) => <option key={r}>{r}</option>)}
            </select></> : null}
          <div className="output-dialog-actions"><button type="button" disabled={busy || Boolean(retry)} onClick={() => setSelection(undefined)}>{labels.cancel}</button>
            <button type="submit" disabled={locked}>{selection.kind === "apply" ? labels.confirmApply : labels.confirmDismiss}</button></div>
        </form> : null}
      </li>;
    })}</ul> : <p>{labels.unavailable}</p>}
    {!authorized || !launchContext ? <p>{labels.readOnly}</p> : null}
    {busy || message ? <p role="status">{busy ? labels.working : message}</p> : null}
    {retry ? <button type="button" disabled={!enabled || busy} onClick={() => void submit(retry)}>{labels.retry}</button> : null}
    <button type="button" disabled={busy || uncertain || refreshPending} onClick={() => startRefresh(() => {
      setRefused(false); setSelection(undefined); setMessage(""); router.refresh();
    })}>{labels.refresh}</button>
  </section>;
}

/** Mounted inside the Session's existing collapsed Details, including after the last proposal is decided. */
export function BoundaryDecisionHistory({ eventId, sessionId, serverTimeZone = "UTC" }: { eventId: string; sessionId: string; serverTimeZone?: string }) {
  const timeZone = useSyncExternalStore(subscribe, zoneSnapshot, () => serverTimeZone);
  const [items, setItems] = useState<BoundaryDecisionHistory[]>([]), [after, setAfter] = useState<string | null>();
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const loading = useRef(false);
  async function more() {
    if (loading.current || after === null) return;
    loading.current = true; setBusy(true); setMessage("");
    try {
      const page = await boundariesApi().history(eventId, sessionId, after);
      if (page.items.some((next) => items.some((old) => old.command_id === next.command_id))) throw new Error("repeated_history");
      setItems([...items, ...page.items]); setAfter(page.next_after);
    } catch { setMessage(labels.historyFailed); }
    finally { loading.current = false; setBusy(false); }
  }
  return <div><h3>{labels.history}</h3>
    <ul>{items.map((item) => {
      const time = new Intl.DateTimeFormat("en-US", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone }).format(new Date(item.decided_at));
      return <li key={item.command_id}>{labels.edges[item.boundary_kind]} {labels.outcomes[item.kind]} · {time} · {item.reason || `by ${labels.producer}`}
        <details><summary>{labels.details}</summary><dl>
          <dt>Proposal ID</dt><dd>{item.proposal_id}</dd><dt>Command / decision ID</dt><dd>{item.command_id}</dd>
          <dt>Actor ID</dt><dd>{item.actor_id}</dd><dt>Decided at</dt><dd>{item.decided_at}</dd>
          <dt>Decision</dt><dd>{item.kind}</dd><dt>Reason</dt><dd>{item.reason ?? "None"}</dd>
          <dt>Boundary</dt><dd>{item.boundary_kind}</dd>
        </dl></details></li>;
    })}</ul>
    {after === null && !items.length ? <p>No boundary decisions</p> : null}
    {after !== null ? <button type="button" disabled={busy} onClick={() => void more()}>{items.length ? labels.moreHistory : labels.loadHistory}</button> : null}
    {message ? <p role="status">{message}</p> : null}
  </div>;
}
