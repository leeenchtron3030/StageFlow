"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import {
  submitDemoStartSession,
  type DemoStartSessionSelection,
} from "@/experience/demo-start-session.ts";
import type { ProgramExpectationView } from "@/experience/model.ts";

const plannedTimeFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

function plannedTime(value: string | undefined): string {
  if (!value) return "Not scheduled";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "Invalid planned time"
    : plannedTimeFormatter.format(parsed);
}

function plannedWindow(expectation: ProgramExpectationView): string {
  const start = plannedTime(expectation.plannedStart);
  return expectation.plannedEnd
    ? `${start} – ${plannedTime(expectation.plannedEnd)}`
    : start;
}

function readable(value: string): string {
  return value.replaceAll("_", " ");
}

async function responseDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    return typeof payload.detail === "string" ? payload.detail : `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

export function DemoStartSessionControl({
  stageId,
  actorId,
  enabled,
  hasCurrentSession,
  launchContext,
  programExpectations,
}: {
  stageId: string;
  actorId?: string;
  enabled: boolean;
  hasCurrentSession: boolean;
  launchContext?: string;
  programExpectations: ProgramExpectationView[];
}) {
  const router = useRouter();
  const [selectedValue, setSelectedValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string>();
  const selectedExpectation = programExpectations.find(
    (expectation) => selectedValue === `expectation:${expectation.id}`,
  );
  const selection: DemoStartSessionSelection | undefined =
    selectedValue === "ad_hoc"
      ? { kind: "ad_hoc" }
      : selectedExpectation
        ? {
            kind: "expectation",
            expectationId: selectedExpectation.id,
            title: selectedExpectation.title,
          }
        : undefined;

  async function startSession() {
    if (hasCurrentSession) return;
    setBusy(true);
    setMessage(undefined);
    try {
      const result = await submitDemoStartSession({
        actorId,
        stageId,
        launchContext,
        selection,
        authoritativeStart: new Date().toISOString(),
        confirm: (confirmation) => window.confirm(confirmation),
        fetcher: fetch,
      });
      if (result.status === "not_submitted") {
        if (result.reason === "actor_required") {
          setMessage("Unavailable: configure an explicit Demo operator UUID.");
        } else if (result.reason === "launch_context_required") {
          setMessage("Unavailable: current Demo launcher context is not available.");
        } else if (result.reason === "selection_required") {
          setMessage("Select one Program Expectation or explicitly choose Ad hoc.");
        }
        return;
      }
      if (!result.response.ok) {
        throw new Error(await responseDetail(result.response));
      }
      setMessage("Session start recorded durably.");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? readable(error.message) : "Command failed");
    } finally {
      setBusy(false);
    }
  }

  if (!enabled) return null;
  const commandsDisabled = busy || hasCurrentSession;
  return (
    <section className="demo-command-panel" aria-labelledby="demo-start-title">
      <div className="demo-start-heading">
        <span className="eyebrow">Demo authority · attributable human command</span>
        <h2 id="demo-start-title">Session control</h2>
        <p>
          Program Expectations remain external evidence until an explicit human command realizes
          one as a Session.
        </p>
      </div>

      <fieldset className="program-expectation-selection" disabled={commandsDisabled}>
        <legend>External Program Expectations</legend>
        <p>External evidence only · selecting an item does not create Session authority.</p>
        <div className="program-expectation-options">
          {programExpectations.map((expectation, index) => (
            <label className="program-expectation-option" key={expectation.id}>
              <input
                checked={selectedValue === `expectation:${expectation.id}`}
                name={`demo-start-selection-${stageId}`}
                onChange={() => setSelectedValue(`expectation:${expectation.id}`)}
                type="radio"
                value={`expectation:${expectation.id}`}
              />
              <span className="program-expectation-copy">
                <span className="program-expectation-title-row">
                  <strong>{expectation.title}</strong>
                  <span className="advisory-badge">
                    {index === 0 ? "Next · " : ""}External · {expectation.provider ?? "provider unknown"}
                  </span>
                </span>
                <span>{expectation.speakers.length ? expectation.speakers.join(" · ") : "Speakers not reported"}</span>
                <span>{plannedWindow(expectation)}</span>
                {expectation.externalSessionId ? (
                  <span className="program-expectation-external-id">
                    Devcon session · {expectation.externalSessionId}
                  </span>
                ) : null}
              </span>
            </label>
          ))}
          {programExpectations.length === 0 ? (
            <span className="program-expectation-empty">
              No external Program Expectations are currently reported for this Stage.
            </span>
          ) : null}
        </div>
        <label className="program-expectation-option ad-hoc-session-option">
          <input
            checked={selectedValue === "ad_hoc"}
            name={`demo-start-selection-${stageId}`}
            onChange={() => setSelectedValue("ad_hoc")}
            type="radio"
            value="ad_hoc"
          />
          <span className="program-expectation-copy">
            <strong>Ad hoc / unscheduled Session</strong>
            <span>Explicitly start without linking a Program Expectation.</span>
          </span>
        </label>
      </fieldset>

      <div className="demo-start-actions">
        <button
          disabled={
            commandsDisabled || !actorId || !launchContext || selection === undefined
          }
          onClick={() => void startSession()}
          type="button"
        >
          {busy ? "Recording…" : "Start Session"}
        </button>
        {hasCurrentSession ? <span>An active or assembling Session already exists.</span> : null}
        {!actorId ? <span>Commands disabled: explicit operator UUID is not configured.</span> : null}
        {!launchContext ? <span>Commands disabled: current launcher context is unavailable.</span> : null}
        {!selection && !hasCurrentSession ? (
          <span>Select one Program Expectation or explicitly choose Ad hoc.</span>
        ) : null}
        {message ? <span role="status">{message}</span> : null}
      </div>
    </section>
  );
}
