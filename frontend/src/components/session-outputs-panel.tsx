import { uiLabels, renderLabel, renderQualityLabel, slotLabel } from "../experience/ui-labels.ts";
import { assemblyConsequence, memberOrderingLabel, memberOrderSummary, intervalDuration, wallClockLabel, qualificationLabel, sortedRenderOperations, renderTimeLabel, newestOutputs, outputDuration, type SessionOutputs } from "../experience/session-outputs.ts";
import type { AssemblyItem, AssemblyMember } from "../experience/assembly-api.ts";

function Unavailable({ section }: { section: string }) {
  return <p role="status">{section} unavailable · Current state cannot be verified. Other Session information remains available. Refresh to try again.</p>;
}
function memberEvidenceLabel(member: AssemblyMember, timing?: SessionOutputs["timing"][number]) {
  const evidence = timing?.result.state === "available" ? timing.result.value.evidence : null;
  const sameEvidence = evidence && member.order_evidence_id === evidence.evidence_id && member.order_evidence_revision === evidence.revision;
  if (evidence) return member.order_evidence_revision && !sameEvidence ? uiLabels.newerTiming : "";
  return timing?.result.state === "unavailable" || !timing ? "Media timing unavailable" : "No timing evidence recorded.";
}
function memberStart(member: AssemblyMember, timing?: SessionOutputs["timing"][number]) {
  const evidence = timing?.result.state === "available" ? timing.result.value.evidence : null;
  return member.media_started_at ?? evidence?.candidate_interval?.started_at
    ?? (member.order_source === "timing_evidence" ? member.order_key_at : null);
}
function Member({ member, index, timing, baseline, evidenceBaseline, columns }: { member: AssemblyMember; index: number; timing?: SessionOutputs["timing"][number]; baseline: string; evidenceBaseline: string; columns: { start: boolean; duration: boolean; flags: boolean } }) {
  const evidence = timing?.result.state === "available" ? timing.result.value.evidence : null;
  const start = memberStart(member, timing);
  const ordering = memberOrderingLabel(member);
  const sameEvidence = evidence && member.order_evidence_id === evidence.evidence_id && member.order_evidence_revision === evidence.revision;
  const evidenceLabel = memberEvidenceLabel(member, timing);
  return <tr>
    <th scope="row">{index + 1}</th>
    {columns.start ? <td>{wallClockLabel(start)}</td> : null}
    {columns.duration ? <td>{intervalDuration(evidence?.candidate_interval)}</td> : null}
    {columns.flags ? <td className="member-flags">
      {ordering !== baseline ? <span className="outputs-qualification">{ordering}</span> : null}
      {evidenceLabel && evidenceLabel !== evidenceBaseline ? <span>{evidenceLabel}</span> : null}
    </td> : null}
    <td>
      <details className="diagnostic-details">
        <summary>{uiLabels.details}</summary>
        <dl className="outputs-facts">
          <div><dt>Media ID (select to copy)</dt><dd><code className="copyable-id" tabIndex={0}>{member.asset_id}</code></dd></div>
          <div><dt>Start (date and zone)</dt><dd>{start ?? "Unknown"}</dd></div>
          <div><dt>Start source</dt><dd>{member.media_started_at ? "Media start time" : evidence?.candidate_interval ? "Latest Derived candidate interval · advisory only" : member.order_source === "timing_evidence" && start ? "Frozen timing evidence · advisory only" : "Unknown"}</dd></div>
          <div><dt>Ordering key (wall-clock)</dt><dd>{member.order_key_at ?? "Unavailable"}</dd></div>
          <div><dt>Evidence revision</dt><dd>{member.order_evidence_revision ?? "None"} · latest {evidence?.revision ?? "None"}</dd></div>
          <div><dt>Qualification</dt><dd>{member.order_evidence_qualification ?? "Not applicable"} · latest {evidence?.qualification ?? "None"}</dd></div>
          <div><dt>Ordering source</dt><dd><code>{member.order_source}</code></dd></div>
        </dl>
        {evidence && !sameEvidence ? <p>Latest evidence: {qualificationLabel(evidence.qualification)} · advisory only. Latest timing does not replace frozen ordering evidence.</p> : null}
        {evidence?.qualification === "unqualified" ? <p>{uiLabels.recorderLimitation}</p> : null}
        {evidence?.limitations.length ? <p>Limitations: {[...new Set(evidence.limitations)].join(" · ")}</p> : null}
        {evidence?.limitations_truncated ? <p>Additional limitations are not shown.</p> : null}
      </details>
    </td>
  </tr>;
}
function Assembly({ item, timing, packaging }: { item: AssemblyItem; timing: SessionOutputs["timing"]; packaging: SessionOutputs["packaging"] }) {
  const revision = item.revision;
  const order = memberOrderSummary(revision.membership);
  const evidenceCounts = new Map<string, number>();
  for (const member of revision.membership) {
    const label = memberEvidenceLabel(member, timing.find((entry) => entry.assetId === member.asset_id));
    evidenceCounts.set(label, (evidenceCounts.get(label) ?? 0) + 1);
  }
  const evidenceBaseline = evidenceCounts.size === 1 ? [...evidenceCounts.keys()][0] : "";
  const starts = revision.membership.map((member) => wallClockLabel(memberStart(member, timing.find((entry) => entry.assetId === member.asset_id))));
  const durations = revision.membership.map((member) => {
    const entry = timing.find((entry) => entry.assetId === member.asset_id);
    return intervalDuration(entry?.result.state === "available" ? entry.result.value.evidence?.candidate_interval : null);
  });
  const columns = {
    start: new Set(starts).size > 1,
    duration: new Set(durations).size > 1,
    flags: revision.membership.some((member) => memberOrderingLabel(member) !== order.baseline) || evidenceCounts.size > 1,
  };
  return <>
    <p>{assemblyConsequence(item)}</p>
    <dl className="outputs-facts">

      <div><dt>Validation</dt><dd>{revision.validation.state === "valid" ? "Valid" : "Invalid · Review required"}</dd></div>
      <div><dt>Approval</dt><dd>{uiLabels.approval[item.approval_state]}</dd></div>
      <div><dt>Status</dt><dd>{item.stale ? uiLabels.outOfDate : uiLabels.upToDate}</dd></div>

    </dl>
    {revision.validation.issues.length ? <ul aria-label="Assembly validation issue codes">{revision.validation.issues.map((issue, index) => <li key={index}>{issue.code}{issue.subject ? ` · ${issue.subject}` : ""}</li>)}</ul> : <p>No validation issues reported.</p>}
    <details><summary>{uiLabels.details}</summary><p>Current revision: {revision.revision_number} · Package revision: {revision.package_revision}</p><p>Validation: {revision.validation.state} · Approval: {item.approval_state} · Stale: {String(item.stale)}</p><p>Recorder timing evidence is advisory; registration time is an ordering fallback, not captured-content time.</p></details>
    <h4>{uiLabels.recordings}</h4>
    <p>{uiLabels.lockedOrder}</p>
    {revision.membership.length ? <>
      <p>{order.text}{evidenceBaseline ? ` · ${evidenceBaseline}` : ""}{!columns.start ? ` · Start: ${starts[0]} (all members)` : ""}{!columns.duration ? ` · ${durations[0] === "Duration unknown" ? durations[0] : `Duration: ${durations[0]}`} (all members)` : ""}</p>
      <div className="member-table-scroll">
        <table className="member-table" aria-label="Assembly members in frozen position order">
          <thead><tr><th scope="col">Position</th>{columns.start ? <th scope="col">Start</th> : null}{columns.duration ? <th scope="col">Duration</th> : null}{columns.flags ? <th scope="col">Flags</th> : null}<th scope="col">Details</th></tr></thead>
          <tbody>{revision.membership.map((member, index) => <Member key={member.asset_id} member={member} index={index} timing={timing.find((entry) => entry.assetId === member.asset_id)} baseline={order.baseline} evidenceBaseline={evidenceBaseline} columns={columns} />)}</tbody>
        </table>
      </div>
    </> : null}
    {!revision.membership.length ? <p>No members in this revision.</p> : null}
    <p>{uiLabels.layout}: {revision.bindings.map((binding) => {
      const asset = packaging?.find((asset) => asset.revisionId === binding.packaging_revision_id);
      return asset ? `${slotLabel(asset.role)} (${asset.name})` : binding.packaging_revision_id ? `${slotLabel(binding.slot_key)} (Packaging asset unavailable)` : binding.outcome === "session_media" ? slotLabel("session_media") : `${slotLabel(binding.slot_key)} (${binding.outcome.replaceAll("_", " ")})`;
    }).join(" → ") || "No layout"}</p>
    <details><summary>{uiLabels.details}</summary><ul aria-label="Assembly slot bindings">{revision.bindings.map((binding) => <li key={binding.slot_key}><code>{binding.slot_key} · {binding.outcome} · {binding.packaging_revision_id} · {packaging?.find((asset) => asset.revisionId === binding.packaging_revision_id)?.role}</code></li>)}</ul></details>
  </>;
}
function OutsideTiming({ entry, index, sharedQualification }: { entry: SessionOutputs["timing"][number]; index: number; sharedQualification: string }) {
  const evidence = entry.result.state === "available" ? entry.result.value.evidence : null;
  const certainty = evidence ? qualificationLabel(evidence.qualification) : "";
  return <li>
    <strong>Recording {index + 1}</strong>
    {entry.result.state === "unavailable" ? <Unavailable section="Media timing" /> : evidence ? <>
      {certainty && certainty !== sharedQualification ? <span className="outputs-qualification">{certainty}</span> : null}
      <span>{uiLabels.estimatedStart}: {wallClockLabel(evidence.candidate_interval?.started_at)}</span>
    </> : <span>No timing evidence recorded.</span>}
    <details><summary>{uiLabels.details}</summary><p>Media ID: <code>{entry.assetId}</code></p>
      {evidence ? <><p>Evidence revision {evidence.revision} · {evidence.qualification} · {evidence.authorized_use}</p>
        <p>Candidate interval: {evidence.candidate_interval?.started_at ?? "Unavailable"} → {evidence.candidate_interval?.ended_at ?? "Unavailable"}</p>
        {evidence.qualification === "unqualified" ? <p>{uiLabels.recorderLimitation}</p> : null}
        {evidence.limitations.length ? <p>Limitations: {evidence.limitations.join(" · ")}</p> : null}
        {evidence.limitations_truncated ? <p>Additional limitations are not shown.</p> : null}
      </> : null}
    </details>
  </li>;
}
export function SessionOutputsPanel({ outputs, actions }: { outputs: SessionOutputs; actions?: import("react").ReactNode }) {
  const assembly = outputs.assembly.state === "available" ? outputs.assembly.value : null;
  const memberIds = new Set(assembly?.revision.membership.map((member) => member.asset_id));
  const outside = outputs.timing.filter((entry) => !memberIds.has(entry.assetId));
  const outsideQualifications = outside.map((entry) => entry.result.state === "available" && entry.result.value.evidence ? qualificationLabel(entry.result.value.evidence.qualification) : "");
  const sharedQualification = outsideQualifications.length && outsideQualifications.every((label) => label === outsideQualifications[0]) ? outsideQualifications[0] : "";
  const revisionLabel = (id: string) => {
    const number = assembly?.revision.revision_id === id ? assembly.revision.revision_number
      : outputs.knownRevisions?.find((revision) => revision.revisionId === id)?.number;
    return number === undefined ? "earlier revision" : `Revision ${number}`;
  };
  return <section className="detail-panel outputs-panel" aria-labelledby="session-outputs-title">
    <div className="section-heading"><h2 id="session-outputs-title">Outputs</h2>{actions ? null : <span>Read-only</span>}</div>
    {outputs.fixture ? <p><strong>Development fixture · Synthetic outputs · Not production authority</strong></p> : null}
    <div className="outputs-section">
      <h3>Assembly</h3>
      {actions}
      {outputs.assembly.state === "unavailable" ? <Unavailable section="Assembly" /> : outputs.assembly.value ? <Assembly item={outputs.assembly.value} timing={outputs.timing} packaging={outputs.packaging} /> : <p>No Assembly revision proposed for this Session.</p>}
    </div>
    <div className="outputs-section">
      <h3>Render operations</h3>
      {outputs.operations.state === "unavailable" ? <Unavailable section="Render operations" /> : <>
        {!outputs.operations.value.items.length ? <p>No render operations reported for this Session.</p> : null}
        {outputs.operations.value.items.length ? <>
          <p>{uiLabels.renderNewestFirst}</p>
          <div className="member-table-scroll"><table className="member-table" aria-label="Render operations">
            <thead><tr><th scope="col">State</th><th scope="col">Format</th><th scope="col">{uiLabels.renderCreated}</th><th scope="col">Details</th></tr></thead>
            <tbody>{sortedRenderOperations(outputs.operations.value.items).map((operation) => <tr key={operation.operation_id}>
              <th scope="row">{renderLabel(operation.state)}{operation.reason_code ? ` · ${operation.reason_code}` : ""}</th>
              <td>{renderQualityLabel(operation)}</td>
              <td><time dateTime={operation.created_at}>{renderTimeLabel(operation.created_at)}</time></td>
              <td><details><summary>{uiLabels.details}</summary><p>{revisionLabel(operation.assembly_revision_id)} · {operation.state} · profile version {operation.profile_version}</p><dl className="outputs-facts">
                <div><dt>Operation ID</dt><dd><code className="copyable-id" tabIndex={0}>{operation.operation_id}</code></dd></div>
                <div><dt>Assembly revision ID</dt><dd><code>{operation.assembly_revision_id}</code></dd></div>
                <div><dt>Profile ID</dt><dd>{operation.profile_id}</dd></div>
                <div><dt>Attempts</dt><dd>{operation.attempt_count}</dd></div>
                <div><dt>{uiLabels.renderUpdated}</dt><dd><time dateTime={operation.updated_at}>{renderTimeLabel(operation.updated_at)}</time></dd></div>
                {operation.rendered_output_id ? <div><dt>Output ID</dt><dd><code>{operation.rendered_output_id}</code></dd></div> : null}
              </dl></details></td>
            </tr>)}</tbody>
          </table></div>
        </> : null}
        {outputs.operations.value.truncated ? <p>{uiLabels.renderMoreOperations}</p> : null}
      </>}
    </div>
    <div className="outputs-section">
      <h3>Rendered Outputs</h3>
      <p>Newest produced time first among the outputs shown. Recorded outputs may belong to earlier Assembly revisions.</p>
      {outputs.outputs.state === "unavailable" ? <Unavailable section="Rendered Outputs" /> : <>
        {!outputs.outputs.value.items.length ? <p>No Rendered Outputs reported for this Session.</p> : null}
        {outputs.outputs.value.items.length ? <div className="member-table-scroll"><table className="member-table" aria-label="Rendered Outputs">
          <thead><tr><th scope="col">State</th><th scope="col">Format</th><th scope="col">Duration / frames</th><th scope="col">Produced time</th><th scope="col">Details</th></tr></thead>
          <tbody>{newestOutputs(outputs.outputs.value.items).map((output) => <tr key={output.output_id}>
            <th scope="row">{uiLabels.render.succeeded}</th><td>{renderQualityLabel(output)}</td>
            <td>{outputDuration(output)} · {output.frame_count} frames</td>
            <td><time dateTime={output.produced_at}>{output.produced_at}</time></td>
            <td><details><summary>{uiLabels.details}</summary><p>{revisionLabel(output.assembly_revision_id)} · profile version {output.profile_version}</p><dl className="outputs-facts">
              <div><dt>Output ID</dt><dd><code className="copyable-id" tabIndex={0}>{output.output_id}</code></dd></div>
              <div><dt>Assembly revision ID</dt><dd><code>{output.assembly_revision_id}</code></dd></div>
              <div><dt>Profile ID</dt><dd>{output.profile_id}</dd></div>
              <div><dt>SHA-256 prefix:</dt><dd><code>{output.sha256.slice(0, 12)}</code></dd></div>
            </dl></details></td>
          </tr>)}</tbody>
        </table></div> : null}
        {outputs.outputs.value.truncated ? <p>Showing the first 100 Rendered Outputs. More outputs exist.</p> : null}
      </>}
    </div>
    <div className="outputs-section">
      <h3>Media timing</h3>
      {assembly && !outside.length ? <p>{outputs.timingTruncated ? "Recordings shown above; additional media may be outside this view." : "All recordings shown are in the Assembly."}</p> : <p>{assembly ? "Media outside the Assembly" : "Assembly coverage unavailable"} · latest recordings · timing estimates.</p>}
      {!outputs.timing.length && !assembly ? <p>No recordings available in this view.</p> : null}
      {sharedQualification ? <p>{sharedQualification} · all {outside.length} recordings below</p> : null}
      {outside.length ? <ul className="outputs-rows" aria-label="Media timing outside Assembly">{outside.map((entry, index) => <OutsideTiming key={entry.assetId} entry={entry} index={index} sharedQualification={sharedQualification} />)}</ul> : null}
      {outputs.timingTruncated ? <p>Showing timing for the first 100 assets. Additional assets are not shown.</p> : null}
    </div>
  </section>;
}
