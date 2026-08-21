"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  createDemoCommandEnvelope,
  type DemoSessionWorkspace as DemoWorkspace,
} from "@/experience/demo-api.ts";
import { demoAuthorityHeaders } from "@/experience/demo-launch-context.ts";
import {
  submitDemoPackageApproval,
  type DemoPackageApprovalSummary,
} from "@/experience/demo-package-approval.ts";

const apiRoot = "/api/stageflow/demo";

function formatOffset(microseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(microseconds / 1_000_000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return [hours, minutes, seconds]
    .map((value) => String(value).padStart(2, "0"))
    .join(":");
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

export function DemoSessionWorkspace({
  sessionId,
  actorId,
  authoritativeStart,
  authoritativeEnd,
  initialActivityState,
  initialPackageState,
  initialPackageRevision,
  initialRevision,
  mediaAssociated,
  mediaUnresolved,
  mediaConflicting,
  sessionTitle,
  enabled,
  launchContext,
}: {
  sessionId: string;
  actorId?: string;
  sessionTitle: string;
  authoritativeStart?: string;
  authoritativeEnd?: string;
  initialActivityState: string;
  initialPackageState: string;
  initialRevision: number;
  initialPackageRevision: number;
  enabled: boolean;
  mediaAssociated: number;
  mediaUnresolved: number;
  mediaConflicting: number;
  launchContext?: string;
}) {
  const router = useRouter();
  const [workspace, setWorkspace] = useState<DemoWorkspace>();
  const [loading, setLoading] = useState(enabled);
  const [busy, setBusy] = useState<string>();
  const [message, setMessage] = useState<string>();

  const load = useCallback(async () => {
    if (!enabled) return;
    try {
      const response = await fetch(
        `${apiRoot}/sessions/${encodeURIComponent(sessionId)}/workspace`,
        { cache: "no-store", headers: { Accept: "application/json" } },
      );
      if (!response.ok) throw new Error(await responseDetail(response));
      setWorkspace((await response.json()) as DemoWorkspace);
      setMessage(undefined);
    } catch (error) {
      setMessage(
        error instanceof Error ? readable(error.message) : "Evidence refresh failed",
      );
    } finally {
      setLoading(false);
    }
  }, [enabled, sessionId]);

  useEffect(() => {
    if (!enabled) return;
    const initial = window.setTimeout(() => void load(), 0);
    const interval = window.setInterval(() => void load(), 5_000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(interval);
    };
  }, [enabled, load]);

  const activityState = workspace?.activity_state ?? initialActivityState;
  const packageState = workspace?.package_state ?? initialPackageState;
  const sessionRevision = workspace?.revision ?? initialRevision;

  const packageRevision = workspace?.package_revision ?? initialPackageRevision;
  const approvePackage = useCallback(async () => {
    if (!workspace) {
      setMessage("Unavailable: current package evidence has not loaded.");
      return;
    }
    const summary: DemoPackageApprovalSummary = {
      sessionTitle,
      packageRevision,
      mediaAssociated,
      mediaUnresolved,
      mediaConflicting,
      transcriptionSucceeded: workspace.operations.filter(
        (operation) => operation.status === "succeeded",
      ).length,
      transcriptionFailed: workspace.operations.filter(
        (operation) => operation.status === "terminal_failed",
      ).length,
      transcriptEvidenceCount: workspace.transcript_evidence.length,
      declaredMomentCount: workspace.moments.length,
    };
    setBusy("sessions/approve-package");
    setMessage(undefined);
    try {
      const result = await submitDemoPackageApproval({
        actorId,
        launchContext,
        sessionId,
        activityState,
        packageState,
        summary,
        confirm: window.confirm,
        fetcher: window.fetch.bind(window),
      });
      if (result.status === "not_submitted") {
        if (result.reason === "actor_required") {
          setMessage("Unavailable: configure an explicit Demo operator UUID.");
        } else if (result.reason === "launch_context_required") {
          setMessage("Unavailable: current Demo launcher context is not available.");
        } else if (result.reason === "authority_state_required") {
          setMessage("Unavailable: the exact package revision is not ready for review.");
        }
        return;
      }
      if (!result.response.ok) throw new Error(await responseDetail(result.response));
      setMessage("Package approval recorded durably.");
      await load();
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? readable(error.message) : "Package approval failed");
    } finally {
      setBusy(undefined);
    }
  }, [
    activityState,
    actorId,
    launchContext,
    load,
    mediaAssociated,
    mediaConflicting,
    mediaUnresolved,
    packageRevision,
    packageState,
    router,
    sessionId,
    sessionTitle,
    workspace,
  ]);

  const send = useCallback(
    async (path: string, confirmation: string, values: Record<string, unknown>) => {
      if (!actorId) {
        setMessage("Unavailable: configure an explicit Demo operator UUID.");
        return;
      }
      if (!launchContext) {
        setMessage("Unavailable: current Demo launcher context is not available.");
        return;
      }
      if (!window.confirm(confirmation)) return;
      setBusy(path);
      setMessage(undefined);
      try {
        const response = await fetch(`${apiRoot}/${path}`, {
          method: "POST",
          cache: "no-store",
          headers: demoAuthorityHeaders(launchContext),
          body: JSON.stringify(
            createDemoCommandEnvelope(actorId, {
              session_id: sessionId,
              ...values,
            }),
          ),
        });
        if (!response.ok) throw new Error(await responseDetail(response));
        setMessage("Command recorded durably.");
        await load();
        router.refresh();
      } catch (error) {
        setMessage(error instanceof Error ? readable(error.message) : "Command failed");
      } finally {
        setBusy(undefined);
      }
    },
    [actorId, launchContext, load, router, sessionId],
  );

  const markMoment = useCallback(async () => {
    if (!authoritativeStart) return;
    const start = new Date(authoritativeStart).getTime();
    const end = authoritativeEnd ? new Date(authoritativeEnd).getTime() : Date.now();
    const timelineMicroseconds = Math.max(0, Math.round((end - start) * 1_000));
    await send(
      "moments/mark",
      `Declare a human Editorial Candidate Moment at ${formatOffset(timelineMicroseconds)}?`,
      {
        expected_session_revision: sessionRevision,
        timeline_start_microseconds: timelineMicroseconds,
        note: "Producer Mark Moment",
      },
    );
  }, [authoritativeEnd, authoritativeStart, send, sessionRevision]);

  if (!enabled) return null;
  return (
    <section className="demo-session-workspace" aria-labelledby="transcription-evidence-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Trusted Demo LAN · bounded live projection</span>
          <h2 id="transcription-evidence-title">Transcription Evidence</h2>
        </div>
        <span className="advisory-badge">Evidence only · not Session Transcript truth</span>
      </div>

      <div className="demo-authority-actions" aria-label="Demo Session authority controls">
        <button
          disabled={!actorId || !launchContext || busy !== undefined || activityState !== "presentation_active"}
          onClick={() =>
            void send(
              "sessions/end-presentation",
              "Declare the authoritative Presentation End now?",
              { boundary_at: new Date().toISOString(), reason: "producer ended presentation" },
            )
          }
          type="button"
        >
          End Presentation
        </button>
        <button
          disabled={!actorId || !launchContext || busy !== undefined}
          onClick={() =>
            void send(
              "sessions/process-transcription",
              "Run one bounded media cycle and enqueue local transcription for safely associated media?",
              {},
            )
          }
          type="button"
        >
          Process / Transcribe
        </button>
        <button
          disabled={
            !actorId ||
            busy !== undefined ||
            !launchContext ||
            activityState !== "presentation_ended" ||
            packageState !== "assembling"
          }
          onClick={() =>
            void send(
              "sessions/package-ready",
              "Declare this package revision ready for human review?",
              { reason: "producer reviewed package" },
            )
          }
          type="button"
        >
          Package Ready
        </button>
        <button
          disabled={
            !actorId ||
            !launchContext ||
            busy !== undefined ||
            !workspace ||
            activityState !== "presentation_ended" ||
            packageState !== "ready_for_review"
          }
          onClick={() => void approvePackage()}
          type="button"
        >
          Approve Package
        </button>
        <button
          disabled={!actorId || !launchContext || busy !== undefined || !authoritativeStart}
          onClick={() => void markMoment()}
          type="button"
        >
          Mark Moment
        </button>
        {!actorId ? <span>Commands disabled: explicit operator UUID is not configured.</span> : null}
        {message ? <span role="status">{message}</span> : null}
        {!launchContext ? <span>Commands disabled: current launcher context is unavailable.</span> : null}
      </div>

      <div className="demo-work-summary">
        <div><span>Evidence state</span><strong>{loading ? "Refreshing" : workspace ? "Connected" : "Unavailable"}</strong></div>
        <div><span>Operations</span><strong>{workspace?.operations.length ?? 0}</strong></div>
        <div><span>Evidence revisions</span><strong>{workspace?.transcript_evidence.length ?? 0}</strong></div>
        <div><span>Declared Moments</span><strong>{workspace?.moments.length ?? 0}</strong></div>
      </div>

      {workspace?.operations.length ? (
        <div className="demo-operation-list" aria-label="Bounded transcription Operations">
          {workspace.operations.map((operation) => (
            <article key={operation.operation_id}>
              <strong>{readable(operation.status)}</strong>
              <span>Asset {operation.asset_id.slice(0, 8)}</span>
              <span>Attempt {operation.attempt_count} / {operation.max_attempts}</span>
              {operation.last_reason_code ? <span>{readable(operation.last_reason_code)}</span> : null}
            </article>
          ))}
        </div>
      ) : null}
      {workspace?.operations_truncated ? (
        <p className="bounded-notice">
          Bounded Operation view: at most {workspace.operation_limit} recent Event operations are considered.
        </p>
      ) : null}

      <div className="transcription-evidence-list">
        {workspace?.transcript_evidence.length ? workspace.transcript_evidence.map((evidence) => (
          <article className="transcription-evidence-card" key={evidence.evidence_id}>
            <header>
              <div>
                <strong>{evidence.status.toUpperCase()} · evidence r{evidence.revision}</strong>
                <span>{evidence.language ?? "Language not reported"}</span>
              </div>
              <span>{evidence.provider_id} {evidence.provider_version} · {evidence.model_id} {evidence.model_version}</span>
            </header>
            {evidence.limitations.length ? <p className="evidence-limitations">{evidence.limitations.join(" · ")}</p> : null}
            <div className="transcript-segments">
              {evidence.segments.map((segment) => (
                <section key={segment.segment_id}>
                  <div className="transcript-segment-time">
                    <span>{formatOffset(segment.asset_start_microseconds)}</span>
                    <span>→ {formatOffset(segment.asset_end_microseconds)}</span>
                  </div>
                  <div>
                    {segment.speaker_label ? <span className="eyebrow">{segment.speaker_label} · {readable(segment.speaker_evidence_kind ?? "unknown")}</span> : null}
                    <p>{segment.text}</p>
                    {segment.words.length ? (
                      <details>
                        <summary>Observed word timing · {segment.words.length} shown{segment.words_truncated ? ` of more than ${segment.word_limit}` : ""}</summary>
                        <div className="transcript-word-list">
                          {segment.words.map((word) => (
                            <span key={word.word_id} title={`${formatOffset(word.asset_start_microseconds)}–${formatOffset(word.asset_end_microseconds)}`}>
                              {word.text}
                            </span>
                          ))}
                        </div>
                      </details>
                    ) : null}
                  </div>
                </section>
              ))}
            </div>
            {evidence.segments_truncated ? <p className="bounded-notice">Bounded view: first {evidence.segment_limit} segments shown.</p> : null}
          </article>
        )) : (
          <div className="operational-empty compact-empty">
            <strong>No Transcription Evidence yet</strong>
            <span>Use Process / Transcribe after safely associated media is registered.</span>
          </div>
        )}
      </div>
      {workspace?.transcript_assets_truncated ? (
        <p className="bounded-notice">
          Bounded evidence view: the first {workspace.transcript_asset_limit} Session assets are shown.
        </p>
      ) : null}

      {workspace?.moments.length ? (
        <div className="declared-moment-list" aria-label="Declared Editorial Candidate Moments">
          {workspace.moments.map((moment) => (
            <article key={moment.candidate_moment_id}>
              <strong>{formatOffset(moment.timeline_start_microseconds)}</strong>
              <span>{moment.note ?? "Producer Mark Moment"}</span>
              <span>Declared · Session r{moment.expected_session_revision}</span>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
