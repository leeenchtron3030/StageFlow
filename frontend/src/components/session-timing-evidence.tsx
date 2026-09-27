import { uiLabels, timingLabel } from "../experience/ui-labels.ts";
import type { MediaTimingEvidenceView, OperationalWorkspace } from "../experience/model.ts";
import { wallClockLabel, intervalDuration } from "../experience/session-outputs.ts";

export function SessionTimingEvidence({ evidence, status }: {
  evidence: MediaTimingEvidenceView[];
  status: OperationalWorkspace["mediaTimingEvidenceStatus"];
}) {
  const assets = new Set(evidence.map((item) => item.assetId)).size;
  const qualifications = [...new Set(evidence.map((item) => item.qualificationStatus))];
  const summary = status === "unavailable" ? "Timing evidence unavailable"
    : !assets ? "No timing estimates in this view"
    : `${assets} recent ${assets === 1 ? "recording" : "recordings"} · ${qualifications.length === 1 ? timingLabel(qualifications[0]) : "Timing certainty varies"}`;
  return <details className="timing-evidence-panel session-evidence">
    <summary><strong>Timing estimates</strong><span>{summary}</span></summary>
    {status === "unavailable" ? <p role="status">Timing estimates could not be refreshed. No Session decisions changed.</p> : <>
      <p>Recorder timing estimates do not change Session decisions.</p>
      <div className="timing-evidence-list">{evidence.map((item) => {
        const limitations = [...new Set([...item.limitations, ...item.observations.flatMap((observation) => observation.limitations)].map((text) => text.trim()).filter(Boolean))];
        return <details className="timing-evidence-card" key={item.evidenceId}>
          <summary>
            <strong>{uiLabels.estimatedStart}: {wallClockLabel(item.candidateStartedAt)} · {intervalDuration(item.candidateStartedAt && item.candidateEndedAt ? { started_at: item.candidateStartedAt, ended_at: item.candidateEndedAt } : null)}</strong>
            <span>{qualifications.length > 1 ? timingLabel(item.qualificationStatus) : ""} · {uiLabels.details}</span>
          </summary>
          <dl className="definition-grid">
            <div><dt>Evidence revision / qualification</dt><dd>{item.revision} · {item.qualificationStatus}</dd></div>
            <div><dt>Media ID</dt><dd><code className="copyable-id">{item.assetId}</code></dd></div>
            <div><dt>Evidence ID</dt><dd><code>{item.evidenceId}</code></dd></div>
            <div><dt>Provider / full tool identity</dt><dd>{item.providerLabel} · {item.toolLabel}</dd></div>
            <div><dt>Recorder profile</dt><dd>{item.recorderProfileLabel}</dd></div>
            <div><dt>Derived interval (date and zone)</dt><dd>{item.candidateStartedAt ?? "Unknown"} → {item.candidateEndedAt ?? "Unknown"}</dd></div>
            <div><dt>Derivation identity</dt><dd>{item.derivationIdentity ?? item.derivationLabel ?? "No derivation"}</dd></div>
            <div><dt>Inspected at</dt><dd>{item.inspectedAt ?? "Not reported"}</dd></div>
            <div><dt>Precision</dt><dd>{item.precision ?? "Not reported"}</dd></div>
          </dl>
          <h3>Observed facts</h3>
          {item.observations.length ? <ul>{item.observations.map((observation, index) => <li key={index}>{observation.kind.replaceAll("_", " ")}{observation.precision ? ` · ${observation.precision}` : ""}</li>)}</ul> : <p>No normalized observations.</p>}
          {item.qualificationStatus === "unqualified" ? <p>{uiLabels.recorderLimitation}</p> : null}
          {limitations.length ? <><h3>Limitations</h3><ul>{limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></> : null}
        </details>;
      })}</div>
    </>}
  </details>;
}
