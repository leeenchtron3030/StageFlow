"use client";

import { uiLabels } from "../experience/ui-labels.ts";
import { useEffect, useState } from "react";
import { editorialApi, type EditorialMoments, type EditorialCandidate } from "../experience/editorial-api.ts";
import { momentsSummary, reviewLabels, timelinePosition } from "../experience/editorial-presentation.ts";

function MomentTable({ items }: { items: EditorialCandidate[] }) {
  return <table className="editorial-moments-table"><thead><tr><th>Timeline position</th><th>Origin</th><th>Review state</th><th>{uiLabels.details}</th></tr></thead><tbody>{items.map((m) => <tr key={m.candidate_moment_id}><td>{timelinePosition(m.timeline_start_microseconds)}</td><td>{uiLabels.origin[m.origin]}{m.origin === "derived" && m.provenance ? ` · “${m.provenance.normalized_phrase}”` : ""}</td><td>{reviewLabels[m.review_state]}</td><td><details><summary>{uiLabels.details}</summary><pre>{JSON.stringify(m, null, 2)}</pre></details></td></tr>)}</tbody></table>;
}
export function MomentsSummary({ moments }: { moments: EditorialMoments }) {
  return <section aria-label="Editorial moments" className="session-moments">
    <p>{momentsSummary(moments.items)}{moments.items_truncated ? ` · ${moments.items.length} of ${moments.candidate_count} shown` : ""}</p>
    {moments.items.length ? <MomentTable items={moments.items.slice(0, 5)} /> : <p>No moments.</p>}
    {moments.items.length > 5 ? <details><summary>{moments.items.length - 5} more moments</summary><MomentTable items={moments.items.slice(5)} /></details> : null}
    <a href="/editorial">{uiLabels.editorial}</a>
  </section>;
}
export function SessionMoments({ sessionId, refreshToken }: { sessionId: string; refreshToken: string }) {
  const [value, setValue] = useState<{ sessionId: string; attempt: number; moments: EditorialMoments | null; staleSince?: string }>();
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    void editorialApi().moments(sessionId).then((moments) => {
      if (moments.session_id !== sessionId || moments.items.some((m) => m.session_id !== sessionId)) throw new Error();
      if (!cancelled) setValue({ sessionId, attempt, moments });
    }).catch(() => {
      if (!cancelled) setValue((previous) => ({
        sessionId, attempt, moments: previous?.sessionId === sessionId ? previous.moments : null,
        staleSince: previous?.sessionId === sessionId && previous.staleSince ? previous.staleSince : new Date().toLocaleTimeString("en-GB", { hour12: false }),
      }));
    });
    return () => { cancelled = true; };
  }, [sessionId, refreshToken, attempt]);
  if (!value || value.sessionId !== sessionId) return <p role="status">Loading Editorial moments…</p>;
  if (!value.moments) return <p role="status">Editorial moments unavailable. <button type="button" onClick={() => setAttempt((n) => n + 1)}>Reload moments</button> <a href="/editorial">{uiLabels.editorial}</a></p>;
  return <>{value.attempt !== attempt ? <p role="status">Refreshing Editorial moments…</p> : null}
    {value.staleSince ? <small role="status">Editorial moments stale since {value.staleSince}</small> : null}
    <MomentsSummary moments={value.moments} />
    <button type="button" disabled={value.attempt !== attempt} onClick={() => setAttempt((n) => n + 1)}>Reload moments</button>
  </>;
}
