import Link from "next/link";

import type {
  AttentionItemView,
  InfrastructureItemView,
  OperationalWorkspace,
  StageView,
} from "@/experience/model.ts";
import {
  formatActivityState,
  formatMediaSummary,
  formatPackageState,
  relativeTimeLabel,
  stageOperationalLabel,
} from "@/experience/presentation.ts";

function scenarioHref(path: string, workspace: OperationalWorkspace): string {
  return workspace.dataSource.scenarioId
    ? `${path}?scenario=${encodeURIComponent(workspace.dataSource.scenarioId)}`
    : path;
}

export function WorkspaceTitle({
  eyebrow,
  title,
  summary,
}: {
  eyebrow: string;
  title: string;
  summary: string;
}) {
  return (
    <header className="workspace-title">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
      </div>
      <p>{summary}</p>
    </header>
  );
}

function StageRow({ stage, workspace }: { stage: StageView; workspace: OperationalWorkspace }) {
  const state = stageOperationalLabel(stage);
  return (
    <Link
      className={`stage-row attention-${stage.attentionLevel ?? "none"}`}
      href={scenarioHref(`/stages/${encodeURIComponent(stage.key)}`, workspace)}
      aria-label={`${stage.name}: ${state}. ${stage.currentSession?.title ?? "No active Session"}`}
    >
      <div className="stage-identity-cell">
        <strong>{stage.name}</strong>
        <span>{stage.key}</span>
      </div>
      <div className="session-cell">
        <strong>{stage.currentSession?.title ?? "No active Session"}</strong>
        <span>{formatActivityState(stage.currentSession)}</span>
      </div>
      <div className="package-cell">
        <span className="cell-label">Package</span>
        <strong>{formatPackageState(stage.currentSession)}</strong>
        <span>{stage.currentSession ? `Revision ${stage.currentSession.packageRevision}` : "No revision"}</span>
      </div>
      <div className="media-cell">
        <span className="cell-label">Media</span>
        <strong>{formatMediaSummary(stage.media)}</strong>
        <span>Last activity {relativeTimeLabel(stage.media.lastActivityAt)}</span>
      </div>
      <div className="source-cell">
        <span className="cell-label">Source</span>
        <strong>{stage.sourceLabel}</strong>
        <span>{relativeTimeLabel(stage.media.lastActivityAt)} last media</span>
      </div>
      <div className="state-cell">
        <span className={`state-marker state-${stage.attentionLevel ?? "normal"}`} />
        <strong>{state}</strong>
        <span>{stage.attentionText ?? "No attention requested"}</span>
      </div>
      <span className="row-chevron" aria-hidden="true">›</span>
    </Link>
  );
}

export function StageMatrix({ workspace }: { workspace: OperationalWorkspace }) {
  return (
    <section className="operational-section" aria-labelledby="stage-matrix-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Configured order</span>
          <h2 id="stage-matrix-title">Stages</h2>
        </div>
        <span>{workspace.stages.length} operational positions</span>
      </div>
      <div className="stage-grid-header" aria-hidden="true">
        <span>Stage</span><span>Session</span><span>Package</span><span>Media</span>
        <span>Source</span><span>State</span>
      </div>
      <div className="stage-matrix">
        {workspace.stages.length ? (
          workspace.stages.map((stage) => (
            <StageRow key={stage.id} stage={stage} workspace={workspace} />
          ))
        ) : (
          <div className="operational-empty">
            <strong>No Stage status available</strong>
            <span>Configure and bootstrap the Kernel or select a development fixture.</span>
          </div>
        )}
      </div>
    </section>
  );
}

function EventPulse({ workspace }: { workspace: OperationalWorkspace }) {
  const stageAttention = workspace.stages.filter((stage) => stage.attentionLevel).length;
  const active = workspace.sessions.filter(
    (session) => session.activityState === "presentation_active",
  ).length;
  const assembling = workspace.sessions.filter(
    (session) => session.activityState === "presentation_ended" && session.packageState !== "complete",
  ).length;
  const media = workspace.stages.reduce(
    (totals, stage) => ({
      registered: totals.registered + stage.media.registered,
      associated: totals.associated + stage.media.associated,
      unresolved: totals.unresolved + stage.media.unresolved,
      conflicting: totals.conflicting + stage.media.conflicting,
      stabilizing: totals.stabilizing + stage.media.stabilizing,
    }),
    { registered: 0, associated: 0, unresolved: 0, conflicting: 0, stabilizing: 0 },
  );
  return (
    <section className="event-pulse" aria-label="Event operational summary">
      <div>
        <span className="eyebrow">Event operation</span>
        <strong>{workspace.event.ready ? "Operating normally" : workspace.event.recovering ? "Recovering" : "Not ready"}</strong>
      </div>
      <div>
        <span className="eyebrow">Stages</span>
        <strong>{workspace.stages.length - stageAttention} clear · {stageAttention} need attention</strong>
      </div>
      <div>
        <span className="eyebrow">Sessions</span>
        <strong>{active} active · {assembling} assembling</strong>
      </div>
      <div>
        <span className="eyebrow">Media preserved</span>
        <strong>{media.registered} registered · {media.associated} associated</strong>
        <span>{media.unresolved} unresolved · {media.conflicting} conflicts · {media.stabilizing} stabilizing</span>
      </div>
    </section>
  );
}

function AttentionItem({ item }: { item: AttentionItemView }) {
  return (
    <article className={`attention-item attention-item-${item.level}`}>
      <div className="attention-level-column">
        <span className="attention-level">{item.level}</span>
        <span>{item.since}</span>
      </div>
      <div className="attention-content">
        <span className="eyebrow">{item.scope}</span>
        <h3>{item.title}</h3>
        <dl className="consequence-grid">
          <div><dt>Impact</dt><dd>{item.impact}</dd></div>
          <div><dt>Continuing safely</dt><dd>{item.safeContinuation}</dd></div>
          <div><dt>Human action</dt><dd>{item.action}</dd></div>
        </dl>
      </div>
    </article>
  );
}

export function AttentionPanel({ attention }: { attention: AttentionItemView[] }) {
  const bounded = [...attention]
    .sort((a, b) => {
      const order = { intervention: 3, review: 2, information: 1 };
      return order[b.level] - order[a.level];
    })
    .slice(0, 6);
  return (
    <section className="attention-panel" aria-labelledby="attention-title">
      <div className="section-heading">
        <div><span className="eyebrow">Bounded operational attention</span><h2 id="attention-title">Attention</h2></div>
        <span>{attention.length ? `${attention.length} requiring awareness` : "Quiet"}</span>
      </div>
      {bounded.length ? (
        <div className="attention-list">{bounded.map((item) => <AttentionItem item={item} key={item.id} />)}</div>
      ) : (
        <div className="quiet-state" role="status">
          <span className="quiet-indicator" aria-hidden="true" />
          <div><strong>No Producer work waiting</strong><span>Event operation is healthy. Routine processing remains quiet.</span></div>
        </div>
      )}
    </section>
  );
}

function InfrastructureCell({ item }: { item: InfrastructureItemView }) {
  return (
    <div className={`infrastructure-cell health-${item.health}`}>
      <span className="eyebrow">{item.label}</span>
      <strong>{item.state}</strong>
      <span>{item.impact}</span>
      <span className={`attention-tag attention-tag-${item.attentionLevel ?? "none"}`}>
        {item.attentionLevel ?? "No action"}
      </span>
    </div>
  );
}

export function InfrastructureStrip({ items }: { items: InfrastructureItemView[] }) {
  return (
    <section className="infrastructure-strip" aria-labelledby="infrastructure-strip-title">
      <div className="section-heading compact-heading">
        <h2 id="infrastructure-strip-title">Infrastructure</h2>
        <span>Health · impact · attention</span>
      </div>
      <div className="infrastructure-grid">
        {items.slice(0, 5).map((item) => <InfrastructureCell item={item} key={item.id} />)}
      </div>
    </section>
  );
}

export function MissionControl({ workspace }: { workspace: OperationalWorkspace }) {
  const interventions = workspace.attention.filter((item) => item.level === "intervention").length;
  const reviews = workspace.attention.filter((item) => item.level === "review").length;
  const summary = interventions
    ? `${interventions} intervention${interventions === 1 ? "" : "s"} · ${reviews} review${reviews === 1 ? "" : "s"}`
    : reviews
      ? `${reviews} item${reviews === 1 ? " requires" : "s require"} review · no intervention`
      : "No intervention required";
  return (
    <>
      <WorkspaceTitle eyebrow="Producer" title="Mission Control" summary={summary} />
      <EventPulse workspace={workspace} />
      <StageMatrix workspace={workspace} />
      <div className="mission-lower-grid">
        <AttentionPanel attention={workspace.attention} />
        <InfrastructureStrip items={workspace.infrastructure} />
      </div>
    </>
  );
}
