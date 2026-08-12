import Link from "next/link";

import type {
  EditorialCandidateView,
  MediaTimingEvidenceView,
  OperationalWorkspace,
  SessionView,
  StageView,
} from "@/experience/model.ts";
import {
  authorityActionsEnabled,
  formatActivityState,
  formatMediaSummary,
  formatPackageState,
  isSessionProminent,
  relativeTimeLabel,
} from "@/experience/presentation.ts";

import { AttentionPanel, WorkspaceTitle } from "./mission-control";

function href(path: string, workspace: OperationalWorkspace): string {
  return workspace.dataSource.scenarioId
    ? `${path}?scenario=${encodeURIComponent(workspace.dataSource.scenarioId)}`
    : path;
}

function Definition({ label, value }: { label: string; value: string }) {
  return <div className="definition"><dt>{label}</dt><dd>{value}</dd></div>;
}

function AuthorityControls({ workspace }: { workspace: OperationalWorkspace }) {
  const enabled = authorityActionsEnabled(workspace);
  return (
    <section className="authority-panel" aria-labelledby="authority-title">
      <div className="section-heading">
        <div><span className="eyebrow">Declared operational facts</span><h2 id="authority-title">Authority</h2></div>
        <span>Read-only MVP</span>
      </div>
      <div className="authority-copy">
        <strong>Authority commands are not exposed by the current HTTP boundary.</strong>
        <p>
          The Kernel supports human Session/package commands internally, but this interface
          consumes only the bounded status projection. Frontend state will not substitute for
          durable backend truth.
        </p>
      </div>
      <div className="authority-actions" aria-label="Unavailable authority actions">
        {[
          "Arm Event",
          "Start Session",
          "End Presentation",
          "Package Ready",
          "Approve Package",
        ].map((label) => <button disabled={!enabled} key={label} type="button">{label}</button>)}
      </div>
      <p className="disabled-explanation">
        Unavailable: no reviewed command API is connected. Status remains useful and read-only.
      </p>
    </section>
  );
}

export function EventOperationalView({ workspace }: { workspace: OperationalWorkspace }) {
  return (
    <>
      <WorkspaceTitle
        eyebrow="Producer · Event"
        title={workspace.event.name}
        summary="Event context, readiness, and authority remain distinct from downstream work."
      />
      <div className="summary-grid">
        <section className="summary-panel">
          <span className="eyebrow">Event lifecycle</span>
          <strong className="summary-value">{workspace.event.lifecycle.replace("_", " ")}</strong>
          <p>{workspace.event.modeLabel}</p>
        </section>
        <section className="summary-panel">
          <span className="eyebrow">Operational readiness</span>
          <strong className="summary-value">{workspace.event.ready ? "Ready" : "Not ready"}</strong>
          <p>{workspace.event.recovering ? "Fresh reconciliation required." : "Current status is not recovering."}</p>
        </section>
        <section className="summary-panel">
          <span className="eyebrow">Stage scope</span>
          <strong className="summary-value">{workspace.event.stageCount}</strong>
          <p>Configured Stage positions in the current projection.</p>
        </section>
        <section className="summary-panel">
          <span className="eyebrow">Data authority</span>
          <strong className="summary-value">{workspace.dataSource.authoritative ? "Kernel" : "Fixture"}</strong>
          <p>{workspace.dataSource.authoritative ? "Read-only durable projection." : "Development interaction state only."}</p>
        </section>
      </div>
      <AuthorityControls workspace={workspace} />
      <AttentionPanel attention={workspace.attention} />
    </>
  );
}

function SessionRow({ session, workspace }: { session: SessionView; workspace: OperationalWorkspace }) {
  return (
    <Link className="session-row" href={href(`/sessions/${encodeURIComponent(session.id)}`, workspace)}>
      <div className="session-row-identity"><strong>{session.title}</strong><span>{session.stageName}</span></div>
      <div><span className="cell-label">Presentation</span><strong>{formatActivityState(session)}</strong></div>
      <div><span className="cell-label">Package</span><strong>{formatPackageState(session)} · r{session.packageRevision}</strong></div>
      <div><span className="cell-label">Media</span><strong>{formatMediaSummary(session.media)}</strong></div>
      <div><span className="cell-label">Attention</span><strong>{session.attentionText ?? "None"}</strong></div>
      <span className="row-chevron" aria-hidden="true">›</span>
    </Link>
  );
}

export function SessionsOperationalView({ workspace }: { workspace: OperationalWorkspace }) {
  const prominent = workspace.sessions.filter(isSessionProminent);
  const completed = workspace.sessions.filter((session) => !isSessionProminent(session));
  return (
    <>
      <WorkspaceTitle eyebrow="Producer" title="Sessions" summary={`${prominent.length} active or assembling · ${completed.length} complete`} />
      <section className="operational-section">
        <div className="section-heading"><div><span className="eyebrow">Current responsibility</span><h2>Active and assembling</h2></div><span>Bounded Event view</span></div>
        <div className="session-list">
          {prominent.length ? prominent.map((item) => <SessionRow key={item.id} session={item} workspace={workspace} />) : <div className="operational-empty"><strong>No active or assembling Sessions</strong><span>Completed Sessions remain discoverable below.</span></div>}
        </div>
      </section>
      <section className="operational-section completed-section">
        <div className="section-heading"><div><span className="eyebrow">Historical · read only</span><h2>Completed</h2></div><span>Quiet after settlement</span></div>
        <div className="session-list">
          {completed.length ? completed.map((item) => <SessionRow key={item.id} session={item} workspace={workspace} />) : <div className="operational-empty compact-empty"><strong>No completed Sessions in this view</strong></div>}
        </div>
      </section>
    </>
  );
}

export function InfrastructureOperationalView({ workspace }: { workspace: OperationalWorkspace }) {
  return (
    <>
      <WorkspaceTitle eyebrow="Producer" title="Infrastructure" summary="Health, operational impact, and Attention are separate." />
      <div className="infrastructure-detail-list">
        {workspace.infrastructure.map((item) => (
          <section className={`infrastructure-detail health-${item.health}`} key={item.id}>
            <div className="infrastructure-identity"><span className="eyebrow">{item.label}</span><strong>{item.state}</strong></div>
            <div><span className="cell-label">Health</span><strong>{item.health}</strong></div>
            <div><span className="cell-label">Operational impact</span><p>{item.impact}</p></div>
            <div><span className="cell-label">Attention</span><strong>{item.attentionLevel ?? "None"}</strong>{item.detail ? <p>{item.detail}</p> : null}</div>
          </section>
        ))}
      </div>
    </>
  );
}

function SessionContext({ label, session }: { label: string; session?: SessionView }) {
  return (
    <div className="context-column">
      <span className="eyebrow">{label}</span>
      {session ? <><strong>{session.title}</strong><span>{formatActivityState(session)}</span><span>Package {formatPackageState(session)}</span></> : <><strong>None</strong><span>No realized Session</span></>}
    </div>
  );
}

function TimingEvidencePanel({
  evidence,
  status,
}: {
  evidence: MediaTimingEvidenceView[];
  status: OperationalWorkspace["mediaTimingEvidenceStatus"];
}) {
  if (!evidence.length && status !== "unavailable") return null;
  return (
    <section className="timing-evidence-panel" aria-labelledby="timing-evidence-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Media evidence · drill-down</span>
          <h2 id="timing-evidence-title">Recorder timing</h2>
        </div>
        <span>Advisory only</span>
      </div>
      {status === "unavailable" ? (
        <div className="operational-empty compact-empty">
          <strong>Timing evidence unavailable</strong>
          <span>The bounded evidence read could not be refreshed. No authority changed.</span>
        </div>
      ) : (
        <div className="timing-evidence-list">
          {evidence.map((item) => (
            <article className="timing-evidence-card" key={item.evidenceId}>
              <div className="timing-evidence-identity">
                <strong>Asset {item.assetId.slice(0, 8)} · evidence r{item.revision}</strong>
                <span>{item.recorderProfileLabel}</span>
              </div>
              <dl className="definition-grid">
                <Definition
                  label="Candidate interval · Derived"
                  value={
                    item.candidateStartedAt && item.candidateEndedAt
                      ? `${item.candidateStartedAt} → ${item.candidateEndedAt}`
                      : "No candidate interval derived"
                  }
                />
                <Definition label="Evidence · Observed" value={item.evidenceLabel} />
                <Definition
                  label="Derivation"
                  value={item.derivationLabel ?? "No derivation"}
                />
                <Definition
                  label="Qualification"
                  value={`${item.qualificationStatus} recorder profile`}
                />
                <Definition
                  label="Precision / limitations"
                  value={
                    [item.precision, ...item.limitations].filter(Boolean).join(" · ") ||
                    "No additional precision reported"
                  }
                />
                <Definition label="Use" value="Advisory only · never Session authority" />
              </dl>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export function StageOperationalView({ stage, workspace }: { stage?: StageView; workspace: OperationalWorkspace }) {
  if (!stage) return <><WorkspaceTitle eyebrow="Producer · Stage" title="Stage unavailable" summary="The requested Stage is not present in this bounded projection." /><Link className="text-link" href={href("/", workspace)}>Return to Mission Control</Link></>;
  return (
    <>
      <WorkspaceTitle eyebrow={`Producer · Stage · ${stage.key}`} title={stage.name} summary={stage.attentionText ?? "No operational attention requested"} />
      <div className="stage-context-grid">
        <SessionContext label="Previous" session={stage.previousSession} />
        <SessionContext label="Current" session={stage.currentSession} />
        <div className="context-column"><span className="eyebrow">Next · external</span><strong>{stage.nextExpectation ?? "Not reported"}</strong><span>Program Expectation is not Session authority.</span></div>
      </div>
      <div className="stage-detail-grid">
        <section className="detail-panel">
          <div className="section-heading"><h2>Current operation</h2><span>{stage.sourceLabel}</span></div>
          <dl className="definition-grid">
            <Definition label="Presentation" value={formatActivityState(stage.currentSession)} />
            <Definition label="Package" value={formatPackageState(stage.currentSession)} />
            <Definition label="Media" value={formatMediaSummary(stage.media)} />
            <Definition label="Last meaningful media" value={relativeTimeLabel(stage.media.lastActivityAt)} />
            <Definition label="Source" value={stage.sourceLabel} />
            <Definition label="Source consequence" value={stage.sourceImpact} />
          </dl>
        </section>
        <section className="detail-panel">
          <div className="section-heading"><h2>Authority</h2><span>Read only</span></div>
          <p>Declared boundaries are shown in Session detail. No command API is connected.</p>
          <button disabled type="button">Mark Moment</button>
          <p className="disabled-explanation">Unavailable: durable operator-mark execution is not implemented.</p>
        </section>
      </div>
      <TimingEvidencePanel
        evidence={workspace.mediaTimingEvidence.filter((item) => item.stageKey === stage.key)}
        status={workspace.mediaTimingEvidenceStatus}
      />
      <AttentionPanel attention={workspace.attention.filter((item) => item.scope.includes(stage.name) || item.scope === "Event")} />
    </>
  );
}

export function SessionOperationalView({ session, workspace }: { session?: SessionView; workspace: OperationalWorkspace }) {
  if (!session) return <><WorkspaceTitle eyebrow="Producer · Session" title="Session unavailable" summary="The requested Session is outside this bounded projection." /><Link className="text-link" href={href("/sessions", workspace)}>Return to Sessions</Link></>;
  return (
    <>
      <WorkspaceTitle eyebrow={`Producer · ${session.stageName}`} title={session.title} summary={`${formatActivityState(session)} · Package ${formatPackageState(session)}`} />
      <div className="session-detail-grid">
        <section className="detail-panel">
          <div className="section-heading"><h2>Operational lifecycle</h2><span>{session.provenance.toUpperCase()}</span></div>
          <dl className="definition-grid">
            <Definition label="Presentation" value={formatActivityState(session)} />
            <Definition label="Package" value={`${formatPackageState(session)} · revision ${session.packageRevision}`} />
            <Definition label="Session revision" value={String(session.sessionRevision)} />
            <Definition label="Stage" value={session.stageName} />
            <Definition label="Declared start" value={session.authoritativeStart ?? "Not declared"} />
            <Definition label="Declared end" value={session.authoritativeEnd ?? "Not declared"} />
          </dl>
        </section>
        <section className="detail-panel">
          <div className="section-heading"><h2>Media membership</h2><span>Aggregate</span></div>
          <strong className="summary-value compact-value">{formatMediaSummary(session.media)}</strong>
          <p>Physical recording boundaries remain secondary. Filesystem timestamps are not presented as content truth.</p>
          {session.media.unresolved ? <div className="review-callout"><strong>{session.media.unresolved} unplaced / time unknown</strong><span>Media preserved. Ownership remains unresolved.</span></div> : null}
        </section>
      </div>
      <TimingEvidencePanel
        evidence={workspace.mediaTimingEvidence.filter((item) => item.sessionId === session.id)}
        status={workspace.mediaTimingEvidenceStatus}
      />
      <AuthorityControls workspace={workspace} />
    </>
  );
}

function CandidateRow({ candidate }: { candidate: EditorialCandidateView }) {
  return (
    <article className={`candidate-row candidate-${candidate.state}`}>
      <div className="candidate-marker" aria-hidden="true">{candidate.origin === "producer" ? "◆" : "✦"}</div>
      <div className="candidate-time"><strong>{candidate.at}</strong><span>{candidate.stageName}</span></div>
      <div className="candidate-copy"><span className="eyebrow">{candidate.origin} · {candidate.state}</span><strong>{candidate.sessionTitle}</strong><p>{candidate.excerpt}</p><span>{candidate.reason}</span></div>
      <button disabled type="button">Review</button>
    </article>
  );
}

export function EditorialShellView({ workspace }: { workspace: OperationalWorkspace }) {
  const current = workspace.sessions.find((session) => session.activityState === "presentation_active") ?? workspace.sessions[0];
  return (
    <>
      <WorkspaceTitle eyebrow={`Editorial · ${workspace.event.name}`} title="Live Triage" summary={workspace.editorialCandidates.length ? `${workspace.editorialCandidates.length} development Candidates available` : "No Candidate runtime connected"} />
      <div className="editorial-notice" role="note"><strong>Development Editorial shell</strong><span>No transcript, model, or Editorial decision runtime is connected. Synthetic Candidates are labeled fixture data.</span></div>
      <div className="editorial-layout">
        <section className="media-workspace">
          <div className="section-heading"><div><span className="eyebrow">Session context</span><h2>{current?.title ?? "No Session selected"}</h2></div><span>{current ? formatActivityState(current) : "Unavailable"}</span></div>
          <div className="media-placeholder"><span>Media / timeline workspace</span><strong>Playback not implemented</strong><p>Future media remains anchored to one Session timeline. No synthetic media is shown.</p></div>
          <div className="timeline-placeholder"><span className="timeline-line" /><span className="timeline-playhead" /><div><span>00:00</span><span>Session timeline placeholder</span><span>LIVE</span></div></div>
          <section className="transcript-placeholder"><span className="eyebrow">Transcript</span><strong>Not available</strong><p>Transcription execution is not implemented. This space preserves the accepted temporal workspace structure.</p></section>
        </section>
        <aside className="candidate-panel"><div className="section-heading"><h2>Candidates</h2><span>Fixture only</span></div>{workspace.editorialCandidates.length ? workspace.editorialCandidates.map((item) => <CandidateRow candidate={item} key={item.id} />) : <div className="operational-empty"><strong>Caught up</strong><span>No Candidate evidence is available.</span></div>}</aside>
      </div>
    </>
  );
}
