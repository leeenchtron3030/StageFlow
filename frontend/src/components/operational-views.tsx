import Link from "next/link";

import type {
  EditorialCandidateView,
  MediaAssetView,
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

function readableCode(value: string): string {
  return value.replaceAll("_", " ");
}

function MediaUncertaintyPanel({
  assets,
  workspace,
}: {
  assets: MediaAssetView[];
  workspace: OperationalWorkspace;
}) {
  const uncertain = assets.filter(
    (asset) => asset.associationStatus === "unresolved" || asset.associationStatus === "conflict",
  );
  if (!uncertain.length) return null;
  return (
    <section className="media-uncertainty-panel" aria-labelledby="media-uncertainty-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Membership uncertainty · bounded recent evidence</span>
          <h2 id="media-uncertainty-title">Affected media</h2>
        </div>
        <span>{uncertain.length} shown · media preserved</span>
      </div>
      <div className="uncertainty-list">
        {uncertain.map((asset) => {
          const considered = asset.consideredSessionIds
            .map((id) => workspace.sessions.find((session) => session.id === id)?.title ?? `Session ${id.slice(0, 8)}`)
            .join(" · ");
          const timing = workspace.mediaTimingEvidence.find((item) => item.assetId === asset.assetId);
          return (
            <article className={`uncertainty-card uncertainty-${asset.associationStatus}`} key={asset.candidateId}>
              <div className="uncertainty-identity">
                <div>
                  <span className="eyebrow">{asset.stageName} · {asset.registrationState}</span>
                  <strong>{asset.assetId ? `Asset ${asset.assetId.slice(0, 12)}` : `Candidate ${asset.candidateId.slice(0, 12)}`}</strong>
                </div>
                <span className={`association-badge association-${asset.associationStatus}`}>
                  {asset.associationStatus === "conflict" ? "Conflict · Review" : "Unresolved · Review"}
                </span>
              </div>
              <p className="operator-explanation">{asset.explanation}</p>
              <dl className="definition-grid uncertainty-definitions">
                <Definition
                  label="Sessions considered by policy"
                  value={considered || "None recorded in bounded evidence"}
                />
                <Definition
                  label="Association reason"
                  value={asset.associationReasonCodes.map(readableCode).join(" · ") || "No reason reported"}
                />
                <Definition
                  label="Timing evidence"
                  value={
                    timing
                      ? `${timing.qualificationStatus} · candidate interval is Derived and advisory`
                      : "No timing evidence in this bounded read"
                  }
                />
                <Definition label="Last observed" value={asset.lastObservedAt} />
              </dl>
              <details className="diagnostic-details">
                <summary>Evidence and provenance</summary>
                <p>Source binding: {asset.sourceBindingKey}</p>
                <p>Policy: {asset.associationPolicy ?? "Not reported"}</p>
                <p>Epistemic kinds: {asset.epistemicKinds.join(" · ") || "Not reported"}</p>
                <p>Diagnostic codes: {asset.diagnosticCodes.map(readableCode).join(" · ") || "None"}</p>
              </details>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function AuthorityControls({ workspace }: { workspace: OperationalWorkspace }) {
  const enabled = authorityActionsEnabled(workspace);
  const actions = [
    ["Arm Event", "Would assert that the configured Event may enter operational mode."],
    ["Start Session", "Would declare a realized Session and authoritative occurrence time."],
    ["End Presentation", "Would declare an authoritative Presentation End occurrence time."],
    ["Package Ready", "Would assert the current package revision is ready for human review."],
    ["Approve Package", "Would record an attributable human decision for one package revision."],
  ] as const;
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
        {actions.map(([label, description]) => (
          <button
            aria-label={`${label}. ${description} Disabled because no reviewed command API is connected.`}
            disabled={!enabled}
            key={label}
            title={`${description} Disabled: no reviewed command API is connected.`}
            type="button"
          >
            {label}
          </button>
        ))}
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
          <h2 id="timing-evidence-title">Media Timing Evidence</h2>
        </div>
        <span className="advisory-badge">Advisory only · never authority</span>
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
                <span>{item.qualificationStatus.toUpperCase()} · {item.recorderProfileLabel}</span>
              </div>
              <div className="epistemic-split">
                <section>
                  <span className="epistemic-label observed-label">Observed</span>
                  <strong>{item.providerLabel} · {item.toolLabel}</strong>
                  <span>{item.observations.length ? `${item.observations.length} recorder/media facts` : "No normalized observations"}</span>
                </section>
                <section>
                  <span className="epistemic-label derived-label">Derived</span>
                  <strong>Candidate media interval</strong>
                  <span>
                    {item.candidateStartedAt && item.candidateEndedAt
                      ? `${item.candidateStartedAt} → ${item.candidateEndedAt}`
                      : "No candidate interval derived"}
                  </span>
                </section>
              </div>
              <dl className="definition-grid">
                <Definition label="Provider / tool" value={`${item.providerLabel} · ${item.toolLabel}`} />
                <Definition label="Source / recorder profile" value={item.recorderProfileLabel} />
                <Definition label="Evidence revision" value={String(item.revision)} />
                <Definition label="Derivation identity" value={item.derivationIdentity ?? item.derivationLabel ?? "No derivation"} />
                <Definition
                  label="Qualification"
                  value={`${item.qualificationStatus} recorder profile · does not grant authority`}
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
              {item.observations.length ? (
                <details className="diagnostic-details">
                  <summary>Observed facts and limitations</summary>
                  <ul>
                    {item.observations.map((observation, index) => (
                      <li key={`${observation.kind}-${index}`}>
                        <strong>{readableCode(observation.kind)}</strong>
                        <span>{[observation.precision, ...observation.limitations].filter(Boolean).join(" · ") || "No additional limitation reported"}</span>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
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
          <button
            aria-label="Mark Moment. Would record an attributable human Editorial mark. Disabled because durable operator-mark execution is not implemented."
            disabled
            title="Would record an attributable human Editorial mark. Disabled: durable operator-mark execution is not implemented."
            type="button"
          >
            Mark Moment
          </button>
          <p className="disabled-explanation">Unavailable: durable operator-mark execution is not implemented.</p>
        </section>
      </div>
      <MediaUncertaintyPanel
        assets={workspace.mediaAssets.filter((item) => item.stageKey === stage.key)}
        workspace={workspace}
      />
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
          <div className="media-metric-grid" aria-label="Stage media context for this Session">
            <div><span>Registered</span><strong>{session.media.registered}</strong></div>
            <div><span>Associated</span><strong>{session.media.associated}</strong></div>
            <div><span>Stabilizing</span><strong>{session.media.stabilizing}</strong></div>
            <div><span>Unresolved</span><strong>{session.media.unresolved}</strong></div>
            <div><span>Conflicting</span><strong>{session.media.conflicting}</strong></div>
          </div>
          <p>Stage aggregate context · bounded Session evidence appears below. Physical recording boundaries and filesystem timestamps are not content truth.</p>
          {session.media.unresolved ? <div className="review-callout"><strong>{session.media.unresolved} unplaced / time unknown</strong><span>Media preserved. Ownership remains unresolved.</span></div> : null}
        </section>
      </div>
      <MediaUncertaintyPanel
        assets={workspace.mediaAssets.filter(
          (item) => item.sessionId === session.id || item.consideredSessionIds.includes(session.id),
        )}
        workspace={workspace}
      />
      <TimingEvidencePanel
        evidence={workspace.mediaTimingEvidence.filter(
          (item) =>
            item.sessionId === session.id ||
            workspace.mediaAssets.some(
              (asset) =>
                asset.assetId === item.assetId && asset.consideredSessionIds.includes(session.id),
            ),
        )}
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
      <button
        aria-label={`Review ${candidate.sessionTitle} Candidate Moment. Disabled because Editorial review execution is not implemented.`}
        disabled
        title="Fixture-only Candidate Moment. Disabled: Editorial review execution is not implemented."
        type="button"
      >
        Review
      </button>
    </article>
  );
}

export function EditorialShellView({ workspace }: { workspace: OperationalWorkspace }) {
  const current = workspace.sessions.find((session) => session.activityState === "presentation_active") ?? workspace.sessions[0];
  const hotMoments = workspace.editorialCandidates.filter((item) => item.state === "priority");
  const pendingReview = workspace.editorialCandidates.filter(
    (item) => item.state === "candidate" || item.state === "priority" || item.state === "deferred",
  );
  return (
    <>
      <WorkspaceTitle eyebrow={`Editorial · ${workspace.event.name}`} title="Editorial workspace" summary={workspace.editorialCandidates.length ? `${pendingReview.length} simulated review items · ${hotMoments.length} Hot Moments` : "No Editorial runtime connected"} />
      <div className="editorial-notice" role="note"><strong>{workspace.dataSource.kind === "fixture" ? "Development Editorial fixture" : "Editorial workflow frame"}</strong><span>No transcript, model, or Editorial decision runtime is connected. Fixture Candidates, Hot Moments, and Clips are simulated and never Producer Attention.</span></div>
      <div className="editorial-summary-grid">
        <section><span className="eyebrow">Session context</span><strong>{current?.title ?? "No Session selected"}</strong><span>{current ? `${current.stageName} · ${formatActivityState(current)}` : "Unavailable"}</span></section>
        <section><span className="eyebrow">Transcript</span><strong>{workspace.transcriptState.label}</strong><span>{workspace.transcriptState.detail}</span></section>
        <section><span className="eyebrow">Candidate Moments</span><strong>{workspace.editorialCandidates.length}</strong><span>{pendingReview.length} awaiting human judgment</span></section>
        <section><span className="eyebrow">Hot Moments</span><strong>{hotMoments.length}</strong><span>Editorial urgency · not Producer Attention</span></section>
        <section><span className="eyebrow">Approved Editorial Clips</span><strong>{workspace.editorialClips.length}</strong><span>Fixture-only approved surface</span></section>
        <section><span className="eyebrow">Human review</span><strong>{pendingReview.length ? "Judgment pending" : "Caught up"}</strong><span>No automatic approval authority</span></section>
      </div>
      <div className="editorial-layout">
        <section className="media-workspace">
          <div className="section-heading"><div><span className="eyebrow">Session context</span><h2>{current?.title ?? "No Session selected"}</h2></div><span>{current ? formatActivityState(current) : "Unavailable"}</span></div>
          <div className="media-placeholder"><span>Media / timeline workspace</span><strong>Playback not implemented</strong><p>Future media remains anchored to one Session timeline. No synthetic media is shown.</p></div>
          <div className="timeline-placeholder"><span className="timeline-line" /><span className="timeline-playhead" /><div><span>00:00</span><span>Session timeline placeholder</span><span>LIVE</span></div></div>
          <section className="transcript-placeholder"><span className="eyebrow">Transcript surface</span><strong>{workspace.transcriptState.label}</strong><p>{workspace.transcriptState.detail}</p><p>Transcript text remains intentionally absent because no transcription execution is implemented.</p></section>
        </section>
        <aside className="candidate-panel"><div className="section-heading"><h2>Candidate Moments</h2><span>{workspace.dataSource.kind === "fixture" ? "Simulated fixture" : "Not connected"}</span></div>{workspace.editorialCandidates.length ? workspace.editorialCandidates.map((item) => <CandidateRow candidate={item} key={item.id} />) : <div className="operational-empty"><strong>Caught up</strong><span>No Candidate evidence is available.</span></div>}</aside>
      </div>
      <section className="approved-clips-panel" aria-labelledby="approved-clips-title">
        <div className="section-heading"><div><span className="eyebrow">Human-approved surface</span><h2 id="approved-clips-title">Approved Editorial Clips</h2></div><span>Fixture only · no rendering</span></div>
        {workspace.editorialClips.length ? workspace.editorialClips.map((clip) => (
          <article className="approved-clip-row" key={clip.id}>
            <div><strong>{clip.sessionTitle}</strong><span>{clip.rangeLabel}</span></div>
            <span>{clip.reviewLabel}</span>
            <button
              aria-label={`Open approved Editorial Clip for ${clip.sessionTitle}. Disabled because Clip playback and persistence are not implemented.`}
              disabled
              title="Fixture-only approved Clip. Disabled: Clip playback and persistence are not implemented."
              type="button"
            >
              Open Clip
            </button>
          </article>
        )) : <div className="operational-empty compact-empty"><strong>No approved Editorial Clips</strong><span>Approval and Clip persistence are not implemented.</span></div>}
      </section>
    </>
  );
}
