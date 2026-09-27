import { assemblyConsequence, orderingSourceLabel, qualificationLabel, type SessionOutputs } from "../experience/session-outputs.ts";
import type { AssemblyItem } from "../experience/assembly-api.ts";

function Unavailable({ section }: { section: string }) {
  return <p role="status">{section} unavailable · Current state cannot be verified. Other Session information remains available. Refresh to try again.</p>;
}
function Assembly({ item }: { item: AssemblyItem }) {
  const revision = item.revision;
  return <>
    <p>{assemblyConsequence(item)}</p>
    <dl className="outputs-facts">
      <div><dt>Current revision</dt><dd>{revision.revision_number}</dd></div>
      <div><dt>Validation</dt><dd>{revision.validation.state === "valid" ? "Valid" : "Invalid · Review required"}</dd></div>
      <div><dt>Approval</dt><dd>{item.approval_state}</dd></div>
      <div><dt>Staleness</dt><dd>{item.stale ? "Stale · Inputs changed" : "Current · Inputs unchanged"}</dd></div>
      <div><dt>Package revision</dt><dd>{revision.package_revision}</dd></div>
    </dl>
    {revision.validation.issues.length ? <ul aria-label="Assembly validation issue codes">{revision.validation.issues.map((issue, index) => <li key={index}>{issue.code}{issue.subject ? ` · ${issue.subject}` : ""}</li>)}</ul> : <p>No validation issues reported.</p>}
    <h4>Member order</h4>
    <p>Frozen proposal order. Recorder timing evidence is advisory; registration time is an ordering fallback, not captured-content time.</p>
    <ol className="outputs-rows" aria-label="Assembly members in frozen position order">
      {revision.membership.map((member, index) => <li key={member.asset_id}>
        <strong>Position {index + 1} · Media {member.asset_id}</strong>
        <span>Ordering source: {orderingSourceLabel(member.order_source)} <code>({member.order_source})</code></span>
        <span className="outputs-qualification">{qualificationLabel(member.order_evidence_qualification)}</span>
        <span>Ordering key (wall-clock): {member.order_key_at ? <time dateTime={member.order_key_at}>{member.order_key_at}</time> : "Unavailable"}{member.order_evidence_revision ? ` · Frozen evidence revision ${member.order_evidence_revision}` : ""}</span>
      </li>)}
    </ol>
    {!revision.membership.length ? <p>No members in this revision.</p> : null}
    <h4>Slot bindings</h4>
    <ul className="outputs-rows" aria-label="Assembly slot bindings">{revision.bindings.map((binding) => <li key={binding.slot_key}>
      <strong>{binding.slot_key}</strong><span>{binding.outcome.replaceAll("_", " ")}{binding.packaging_revision_id ? ` · Packaging revision ${binding.packaging_revision_id}` : ""}</span>
    </li>)}</ul>
    {!revision.bindings.length ? <p>No slot bindings.</p> : null}
  </>;
}
export function SessionOutputsPanel({ outputs }: { outputs: SessionOutputs }) {
  return <section className="detail-panel outputs-panel" aria-labelledby="session-outputs-title">
    <div className="section-heading"><h2 id="session-outputs-title">Outputs</h2><span>Read-only</span></div>
    {outputs.fixture ? <p><strong>Development fixture · Synthetic outputs · Not production authority</strong></p> : null}
    <div className="outputs-section">
      <h3>Assembly</h3>
      {outputs.assembly.state === "unavailable" ? <Unavailable section="Assembly" /> : outputs.assembly.value ? <Assembly item={outputs.assembly.value} /> : <p>No Assembly revision proposed for this Session.</p>}
    </div>
    <div className="outputs-section">
      <h3>Render operations</h3>
      {outputs.operations.state === "unavailable" ? <Unavailable section="Render operations" /> : <>
        {!outputs.operations.value.items.length ? <p>No render operations reported for this Session.</p> : null}
        <ul className="outputs-rows" aria-label="Render operations">{outputs.operations.value.items.map((operation) => <li key={operation.operation_id}>
          <strong>Render {operation.operation_id}</strong><span>State: {operation.state.replaceAll("_", " ")} · Attempts: {operation.attempt_count}</span>
          <span>Profile {operation.profile_id} · version {operation.profile_version}</span>
          <span>Assembly revision {operation.assembly_revision_id}</span>
          {operation.reason_code ? <span>Reason: {operation.reason_code}</span> : null}
        </li>)}</ul>
        {outputs.operations.value.truncated ? <p>Showing the first 100 render operations. More operations exist.</p> : null}
      </>}
    </div>
    <div className="outputs-section">
      <h3>Rendered Outputs</h3>
      <p>Recorded outputs may belong to earlier Assembly revisions.</p>
      {outputs.outputs.state === "unavailable" ? <Unavailable section="Rendered Outputs" /> : <>
        {!outputs.outputs.value.items.length ? <p>No Rendered Outputs reported for this Session.</p> : null}
        <ul className="outputs-rows" aria-label="Rendered Outputs">{outputs.outputs.value.items.map((output) => <li key={output.output_id}>
          <strong>Output {output.output_id}</strong>
          <span>Profile {output.profile_id} · version {output.profile_version}</span>
          <span>Duration: {(output.duration_microseconds / 1000000).toFixed(3)} seconds · Frames: {output.frame_count}</span>
          <span>SHA-256 prefix: <code>{output.sha256}</code></span>
          <span>Produced (wall-clock): <time dateTime={output.produced_at}>{output.produced_at}</time></span>
          <span>Assembly revision {output.assembly_revision_id}</span>
        </li>)}</ul>
        {outputs.outputs.value.truncated ? <p>Showing the first 100 Rendered Outputs. More outputs exist.</p> : null}
      </>}
    </div>
    <div className="outputs-section">
      <h3>Media timing</h3>
      <p>Advisory summaries for Assembly members and bounded recent Session media. Latest evidence can differ from the frozen Assembly evidence. These reads do not establish complete Session membership.</p>
      {!outputs.timing.length ? <p>No media assets available in this bounded view.</p> : null}
      <ul className="outputs-rows" aria-label="Media timing per asset">{outputs.timing.map(({ assetId, result }) => <li key={assetId}>
        <strong>Media {assetId}</strong>
        {result.state === "unavailable" ? <Unavailable section="Media timing" /> : result.value.evidence ? <>
          <span className="outputs-qualification">{qualificationLabel(result.value.evidence.qualification)}</span>
          <span>Latest evidence revision {result.value.evidence.revision} · Advisory only</span>
          <span>Derived candidate start (wall-clock): {result.value.evidence.candidate_interval?.started_at ?? "Unavailable"}</span>
          {result.value.evidence.limitations.length ? <span>Limitations: {result.value.evidence.limitations.join(" · ")}</span> : null}
          {result.value.evidence.limitations_truncated ? <span>Additional limitations are not shown.</span> : null}
        </> : <span>No timing evidence recorded.</span>}
      </li>)}</ul>
      {outputs.timingTruncated ? <p>Showing timing for the first 100 assets. Additional assets are not shown.</p> : null}
    </div>
  </section>;
}
