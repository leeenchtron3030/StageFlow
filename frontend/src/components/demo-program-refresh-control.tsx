"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import {
  submitDemoProgramRefresh,
  type ProgramChangeResult,
  type ProgramRefreshResult,
} from "@/experience/demo-program-refresh.ts";
import type {
  ProgramExpectationView,
  ProgramSynchronizationView,
} from "@/experience/model.ts";

function readable(value: string): string {
  return value.replaceAll("_", " ");
}

function relativeRefreshTime(value: string | undefined): string {
  if (!value) return "No successful refresh recorded";
  const milliseconds = Date.now() - new Date(value).getTime();
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return value;
  if (milliseconds < 60_000) return "just now";
  const minutes = Math.floor(milliseconds / 60_000);
  return minutes === 1 ? "1 minute ago" : `${minutes} minutes ago`;
}

function changeLabel(change: ProgramChangeResult): string {
  if (change.kind === "withdrawn") return "Withdrawn upstream";
  return change.kind[0].toUpperCase() + change.kind.slice(1);
}

async function responseDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    return typeof payload.detail === "string" ? payload.detail : `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

function ResultSummary({ result }: { result: ProgramRefreshResult }) {
  return (
    <div className="program-refresh-result" role="status">
      <strong>Program refreshed · Devcon · just now</strong>
      <span>
        {result.observed} observed · {result.added} added · {result.changed} changed ·{" "}
        {result.withdrawn} withdrawn · {result.restored} restored · {result.unchanged}{" "}
        unchanged
      </span>
      {result.changes.length ? (
        <details className="diagnostic-details">
          <summary>Review changes</summary>
          <ul>
            {result.changes.map((change) => (
              <li key={`${change.kind}-${change.expectation_id}`}>
                <strong>{changeLabel(change)} · {change.title}</strong>
                {change.external_session_id ? (
                  <span>Devcon session · {change.external_session_id}</span>
                ) : null}
                {change.fields.map((field) => (
                  <span key={field.field}>
                    {field.field}: {field.previous ?? "not reported"} →{" "}
                    {field.current ?? "not reported"}
                  </span>
                ))}
              </li>
            ))}
          </ul>
          {result.changes_truncated ? <p>Additional changes were omitted by the bounded response.</p> : null}
        </details>
      ) : null}
    </div>
  );
}

export function DemoProgramRefreshControl({
  enabled,
  launchContext,
  synchronization,
  currentExpectations,
  withdrawnExpectations,
}: {
  enabled: boolean;
  launchContext?: string;
  synchronization?: ProgramSynchronizationView;
  currentExpectations: ProgramExpectationView[];
  withdrawnExpectations: ProgramExpectationView[];
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ProgramRefreshResult>();
  const [failure, setFailure] = useState<string>();

  if (!enabled) return null;

  async function refreshProgram() {
    setBusy(true);
    setFailure(undefined);
    try {
      const submission = await submitDemoProgramRefresh({ launchContext, fetcher: fetch });
      if (submission.status === "not_submitted") {
        setFailure("Refresh unavailable: current Demo launcher context is not available.");
        return;
      }
      if (!submission.response.ok) {
        const detail = await responseDetail(submission.response);
        setFailure(
          detail === "program_refresh_failed_using_last_successful_snapshot"
            ? "Refresh failed · using last successful Program snapshot"
            : `Refresh failed · ${readable(detail)}`,
        );
        return;
      }
      setResult((await submission.response.json()) as ProgramRefreshResult);
      router.refresh();
    } catch {
      setFailure("Refresh failed · using last successful Program snapshot");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="detail-panel" aria-labelledby="program-refresh-title">
      <div className="section-heading">
        <h2 id="program-refresh-title">External Program Expectations</h2>
        <span>Devcon · external evidence</span>
      </div>
      <p>
        Current items may be selected for a new Session. Withdrawn upstream items remain
        durable historical evidence and are never Session authority.
      </p>
      <dl className="definition-grid">
        <dt>Provider</dt><dd>Devcon</dd>
        <dt>Last successful refresh</dt>
        <dd>{relativeRefreshTime(synchronization?.synchronizedAt)}</dd>
        <dt>Current expectations</dt><dd>{currentExpectations.length}</dd>
      </dl>
      <button
        disabled={busy || !launchContext}
        onClick={() => void refreshProgram()}
        type="button"
      >
        {busy ? "Refreshing…" : "Refresh Program"}
      </button>
      <p>Performs one provider GET and local reconciliation only. It never publishes to Devcon.</p>
      {result ? <ResultSummary result={result} /> : null}
      {failure ? <p role="alert">{failure}</p> : null}
      {withdrawnExpectations.length ? (
        <details className="diagnostic-details">
          <summary>Withdrawn upstream · historical ({withdrawnExpectations.length})</summary>
          <ul>
            {withdrawnExpectations.map((expectation) => (
              <li key={expectation.id}>
                <strong>{expectation.title}</strong>
                <span>External · withdrawn · revision {expectation.revision}</span>
                {expectation.externalSessionId ? (
                  <span>Devcon session · {expectation.externalSessionId}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
