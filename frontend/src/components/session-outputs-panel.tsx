import { assemblyConsequence, memberOrderingLabel, memberOrderSummary, intervalDuration, wallClockLabel, qualificationLabel, sortedRenderOperations, newestOutputs, outputDuration, type SessionOutputs } from "../experience/session-outputs.ts";
import type { AssemblyItem, AssemblyMember } from "../experience/assembly-api.ts";

function Unavailable({ section }: { section: string }) {
  return <p role="status">{section} unavailable · Current state cannot be verified. Other Session information remains available. Refresh to try again.</p>;
}
function memberEvidenceLabel(member: AssemblyMember, timing?: SessionOutputs["timing"][number]) {
  const evidence = timing?.result.state === "available" ? timing.result.value.evidence : null;
  const sameEvidence = evidence && member.order_evidence_id === evidence.evidence_id && member.order_evidence_revision === evidence.revision;
  if (evidence) return `${sameEvidence ? `Evidence revision ${evidence.revision} · frozen and latest` : `Latest evidence revision ${evidence.revision}`}${member.order_evidence_revision && !sameEvidence ? ` · Frozen ordering evidence revision ${member.order_evidence_revision}` : ""}`;
  return `${member.order_evidence_revision ? `Frozen ordering evidence revision ${member.order_evidence_revision} · ` : ""}${timing?.result.state === "unavailable" || !timing ? "Media timing unavailable" : "No timing evidence recorded."}`;
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
      {evidenceLabel !== evidenceBaseline ? <span>{evidenceLabel}</span> : null}
    </td> : null}
    <td>
      <details className="diagnostic-details">
        <summary>Member details</summary>
        <dl className="outputs-facts">
          <div><dt>Media ID (select to copy)</dt><dd><code className="copyable-id" tabIndex={0}>{member.asset_id}</code></dd></div>
          <div><dt>Start (date and zone)</dt><dd>{start ?? "Unknown"}</dd></div>
          <div><dt>Start source</dt><dd>{member.media_started_at ? "Media start time" : evidence?.candidate_interval ? "Latest Derived candidate interval · advisory only" : member.order_source === "timing_evidence" && start ? "Frozen timing evidence · advisory only" : "Unknown"}</dd></div>
          <div><dt>Ordering key (wall-clock)</dt><dd>{member.order_key_at ?? "Unavailable"}</dd></div>
          <div><dt>Ordering source</dt><dd><code>{member.order_source}</code></dd></div>
        </dl>
        {evidence && !sameEvidence ? <p>Latest evidence: {qualificationLabel(evidence.qualification)} · advisory only. Latest timing does not replace frozen ordering evidence.</p> : null}
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
  const [evidenceBaseline, evidenceCount] = [...evidenceCounts].sort((a, b) => b[1] - a[1])[0] ?? ["", 0];
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
      <div><dt>Current revision</dt><dd>{revision.revision_number}</dd></div>
      <div><dt>Validation</dt><dd>{revision.validation.state === "valid" ? "Valid" : "Invalid · Review required"}</dd></div>
      <div><dt>Approval</dt><dd>{item.approval_state}</dd></div>
      <div><dt>Staleness</dt><dd>{item.stale ? "Stale · Inputs changed" : "Current · Inputs unchanged"}</dd></div>
      <div><dt>Package revision</dt><dd>{revision.package_revision}</dd></div>
    </dl>
    {revision.validation.issues.length ? <ul aria-label="Assembly validation issue codes">{revision.validation.issues.map((issue, index) => <li key={index}>{issue.code}{issue.subject ? ` · ${issue.subject}` : ""}</li>)}</ul> : <p>No validation issues reported.</p>}
    <h4>Member order</h4>
    <p>Position · wall-clock start · duration. Frozen proposal order. Recorder timing evidence is advisory; registration time is an ordering fallback, not captured-content time.</p>
    {revision.membership.length ? <>
      <p>{order.text} · {evidenceBaseline} ({evidenceCount === revision.membership.length ? "all members" : `${evidenceCount} of ${revision.membership.length} members; exceptions below`}){!columns.start ? ` · Start: ${starts[0]} (all members)` : ""}{!columns.duration ? ` · ${durations[0] === "Duration unknown" ? durations[0] : `Duration: ${durations[0]}`} (all members)` : ""}</p>
      <div className="member-table-scroll">
        <table className="member-table" aria-label="Assembly members in frozen position order">
          <thead><tr><th scope="col">Position</th>{columns.start ? <th scope="col">Start</th> : null}{columns.duration ? <th scope="col">Duration</th> : null}{columns.flags ? <th scope="col">Flags</th> : null}<th scope="col">Details</th></tr></thead>
          <tbody>{revision.membership.map((member, index) => <Member key={member.asset_id} member={member} index={index} timing={timing.find((entry) => entry.assetId === member.asset_id)} baseline={order.baseline} evidenceBaseline={evidenceBaseline} columns={columns} />)}</tbody>
        </table>
      </div>
    </> : null}
    {!revision.membership.length ? <p>No members in this revision.</p> : null}
    <h4>Slot bindings</h4>
    <ul className="outputs-rows" aria-label="Assembly slot bindings">{revision.bindings.map((binding) => {
      const asset = packaging?.find((asset) => asset.revisionId === binding.packaging_revision_id);
      return <li key={binding.slot_key}>
        <strong>{binding.slot_key}</strong><span>{binding.outcome.replaceAll("_", " ")}{binding.packaging_revision_id ? ` · ${asset ? `${asset.name} · ${asset.role.replaceAll("_", " ")}` : "Packaging asset unavailable"}` : ""}</span>
        {binding.packaging_revision_id ? <details><summary>Packaging details</summary><span>Packaging revision ID: <code className="copyable-id" tabIndex={0}>{binding.packaging_revision_id}</code></span></details> : null}
      </li>;
    })}</ul>
    {!revision.bindings.length ? <p>No slot bindings.</p> : null}
  </>;
}
export function SessionOutputsPanel({ outputs, actions }: { outputs: SessionOutputs; actions?: import("react").ReactNode }) {
  const assembly = outputs.assembly.state === "available" ? outputs.assembly.value : null;
  const memberIds = new Set(assembly?.revision.membership.map((member) => member.asset_id));
  const outside = outputs.timing.filter((entry) => !memberIds.has(entry.assetId));
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
          <p>In-flight first, then succeeded, then failed or other states. Order within each group is unchanged; operation times are unavailable.</p>
          <div className="member-table-scroll"><table className="member-table" aria-label="Render operations">
            <thead><tr><th scope="col">State</th><th scope="col">Profile version</th><th scope="col">Assembly revision</th><th scope="col">Details</th></tr></thead>
            <tbody>{sortedRenderOperations(outputs.operations.value.items).map((operation) => <tr key={operation.operation_id}>
              <th scope="row">{operation.state.replaceAll("_", " ")}{operation.reason_code ? ` · ${operation.reason_code}` : ""}</th>
              <td>version {operation.profile_version}</td><td>{revisionLabel(operation.assembly_revision_id)}</td>
              <td><details><summary>Operation details</summary><dl className="outputs-facts">
                <div><dt>Operation ID</dt><dd><code className="copyable-id" tabIndex={0}>{operation.operation_id}</code></dd></div>
                <div><dt>Assembly revision ID</dt><dd><code>{operation.assembly_revision_id}</code></dd></div>
                <div><dt>Profile ID</dt><dd>{operation.profile_id}</dd></div>
                <div><dt>Attempts</dt><dd>{operation.attempt_count}</dd></div>
                {operation.rendered_output_id ? <div><dt>Output ID</dt><dd><code>{operation.rendered_output_id}</code></dd></div> : null}
              </dl></details></td>
            </tr>)}</tbody>
          </table></div>
        </> : null}
        {outputs.operations.value.truncated ? <p>Showing the first 100 render operations. More operations exist.</p> : null}
      </>}
    </div>
    <div className="outputs-section">
      <h3>Rendered Outputs</h3>
      <p>Newest produced time first within this bounded read. Recorded outputs may belong to earlier Assembly revisions.</p>
      {outputs.outputs.state === "unavailable" ? <Unavailable section="Rendered Outputs" /> : <>
        {!outputs.outputs.value.items.length ? <p>No Rendered Outputs reported for this Session.</p> : null}
        {outputs.outputs.value.items.length ? <div className="member-table-scroll"><table className="member-table" aria-label="Rendered Outputs">
          <thead><tr><th scope="col">State</th><th scope="col">Profile version</th><th scope="col">Assembly revision</th><th scope="col">Duration / frames</th><th scope="col">Produced time</th><th scope="col">Details</th></tr></thead>
          <tbody>{newestOutputs(outputs.outputs.value.items).map((output) => <tr key={output.output_id}>
            <th scope="row">Produced</th><td>version {output.profile_version}</td><td>{revisionLabel(output.assembly_revision_id)}</td>
            <td>{outputDuration(output)} · {output.frame_count} frames</td>
            <td><time dateTime={output.produced_at}>{output.produced_at}</time></td>
            <td><details><summary>Output details</summary><dl className="outputs-facts">
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
      {assembly && !outside.length ? <p>{outputs.timingTruncated ? "Assembly members shown above; additional media may be outside this bounded view." : "All Session media in this bounded view is covered by the Assembly."}</p> : <p>{assembly ? "Media outside the Assembly" : "Assembly coverage unavailable"} · bounded recent Session and considered media · advisory only.</p>}
      {!outputs.timing.length && !assembly ? <p>No media assets available in this bounded view.</p> : null}
      {outside.length ? <ul className="outputs-rows" aria-label="Media timing outside Assembly">{outside.map(({ assetId, result }) => <li key={assetId}>
        <strong>Media {assetId}</strong>
        {result.state === "unavailable" ? <Unavailable section="Media timing" /> : result.value.evidence ? <>
          <span className="outputs-qualification">{qualificationLabel(result.value.evidence.qualification)}</span>
          <span>Latest evidence revision {result.value.evidence.revision} · Advisory only</span>
          <span>Derived candidate start (wall-clock): {result.value.evidence.candidate_interval?.started_at ?? "Unavailable"}</span>
          {result.value.evidence.limitations.length ? <span>Limitations: {result.value.evidence.limitations.join(" · ")}</span> : null}
          {result.value.evidence.limitations_truncated ? <span>Additional limitations are not shown.</span> : null}
        </> : <span>No timing evidence recorded.</span>}
      </li>)}</ul> : null}
      {outputs.timingTruncated ? <p>Showing timing for the first 100 assets. Additional assets are not shown.</p> : null}
    </div>
  </section>;
}
