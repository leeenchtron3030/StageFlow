import Link from "next/link";
import type { ReactNode } from "react";

import { scenarioOptions } from "@/experience/fixtures.ts";
import type { OperationalWorkspace } from "@/experience/model.ts";
import { workspaceAttentionLevel } from "@/experience/presentation.ts";

const producerNavigation = [
  ["/", "Mission Control"],
  ["/event", "Event"],
  ["/sessions", "Sessions"],
  ["/infrastructure", "Infrastructure"],
] as const;

function routeHref(path: string, workspace: OperationalWorkspace): string {
  const scenario = workspace.dataSource.scenarioId;
  return scenario ? `${path}?scenario=${encodeURIComponent(scenario)}` : path;
}

function NavLink({
  href,
  label,
  activePath,
  workspace,
  count,
}: {
  href: string;
  label: string;
  activePath: string;
  workspace: OperationalWorkspace;
  count?: number;
}) {
  const active = href === "/" ? activePath === "/" : activePath.startsWith(href);
  return (
    <Link
      aria-current={active ? "page" : undefined}
      className={`nav-link${active ? " nav-link-active" : ""}`}
      href={routeHref(href, workspace)}
    >
      <span>{label}</span>
      {count ? <span className="nav-count">{count}</span> : null}
    </Link>
  );
}

export function OperationalShell({
  workspace,
  activePath,
  children,
}: {
  workspace: OperationalWorkspace;
  activePath: string;
  children: ReactNode;
}) {
  const reviewCount = workspace.attention.filter((item) => item.level === "review").length;
  const interventionCount = workspace.attention.filter(
    (item) => item.level === "intervention",
  ).length;
  const attentionLevel = workspaceAttentionLevel(workspace);
  const modeClass = `mode-${workspace.dataSource.state.replaceAll("_", "-")}`;
  return (
    <div className="app-shell">
      <aside className="navigation-rail">
        <div className="brand-block">
          <span className="brand-mark" aria-hidden="true">SF</span>
          <div>
            <strong>StageFlow</strong>
            <span>Operational console</span>
          </div>
        </div>

        <nav aria-label="Producer navigation">
          <p className="nav-group-label">Producer</p>
          {producerNavigation.map(([href, label]) => (
            <NavLink
              activePath={activePath}
              count={label === "Sessions" ? reviewCount + interventionCount : undefined}
              href={href}
              key={href}
              label={label}
              workspace={workspace}
            />
          ))}
          <p className="nav-group-label nav-group-spaced">Editorial</p>
          <NavLink
            activePath={activePath}
            count={workspace.editorialCandidates.filter((item) => item.state !== "approved").length}
            href="/editorial"
            label="Live Triage"
            workspace={workspace}
          />
        </nav>

        {workspace.dataSource.kind === "fixture" ? (
          <details className="scenario-switcher" open>
            <summary>Review scenarios</summary>
            <div className="scenario-list">
              {scenarioOptions.map((scenario) => (
                <Link
                  aria-current={
                    scenario.id === workspace.dataSource.scenarioId ? "true" : undefined
                  }
                  className={
                    scenario.id === workspace.dataSource.scenarioId
                      ? "scenario-link scenario-link-active"
                      : "scenario-link"
                  }
                  href={`${activePath}?scenario=${encodeURIComponent(scenario.id)}`}
                  key={scenario.id}
                >
                  {scenario.label}
                </Link>
              ))}
            </div>
          </details>
        ) : null}

        <div className={`data-source-block ${modeClass}`}>
          <span className="eyebrow">Data source</span>
          <strong className="mode-status">{workspace.dataSource.statusLabel}</strong>
          <span>{workspace.dataSource.label}</span>
          {workspace.dataSource.scenarioLabel ? (
            <span>{workspace.dataSource.scenarioLabel}</span>
          ) : null}
          <span>
            {workspace.dataSource.authoritative
              ? "Backend projection"
              : "Not production authority"}
          </span>
        </div>
      </aside>

      <div className="workspace-column">
        <header className="event-header">
          <div className="event-identity">
            <span className="eyebrow">Current Event</span>
            <strong>{workspace.event.name}</strong>
          </div>
          <div className="event-state-line">
            <span className={`event-live-dot${workspace.event.ready ? " is-ready" : ""}`} />
            <span>{workspace.event.lifecycle.replace("_", " ")}</span>
            <span className="header-separator">·</span>
            <span>{workspace.event.modeLabel}</span>
          </div>
          <div className={`header-mode-indicator ${modeClass}`} role="status">
            {workspace.dataSource.statusLabel}
          </div>
          <div className="event-clock">
            <span className="eyebrow">Status observed</span>
            <time dateTime={workspace.dataSource.updatedAt}>
              {new Intl.DateTimeFormat("en-US", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
                hour12: false,
              }).format(new Date(workspace.dataSource.updatedAt))}
            </time>
          </div>
        </header>

        {workspace.dataSource.kind === "fixture" ? (
          <div className="fixture-ribbon" role="note">
            Development fixture · interaction review only · no commands change durable state
          </div>
        ) : workspace.dataSource.state === "live_unavailable" ? (
          <div className="live-unavailable-ribbon" role="alert">
            LIVE unavailable · no cached authority is being shown
          </div>
        ) : workspace.dataSource.state === "live_unconfigured" ? (
          <div className="live-unconfigured-ribbon" role="status">
            LIVE backend connected · Kernel configuration is not supplied
          </div>
        ) : null}
        {attentionLevel === "intervention" ? (
          <div className="authority-banner" role="alert">
            <strong>Operational intervention required</strong>
            <span>Review the consequence before relying on affected StageFlow capability.</span>
          </div>
        ) : workspace.event.recovering ? (
          <div className="recovery-banner" role="status">
            <strong>Recovering</strong>
            <span>Fresh reconciliation is required before authoritative actions resume.</span>
          </div>
        ) : null}
        <main className="workspace">{children}</main>
      </div>
    </div>
  );
}
