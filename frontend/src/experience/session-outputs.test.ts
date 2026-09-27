import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as presentation from "./session-outputs.ts";
import { loadSessionOutputs } from "./session-outputs.server.ts";
import { getFixtureWorkspace } from "./fixtures.ts";
import { createReadBudget } from "./read-budget.ts";
import { loadWorkspace } from "./data-source.ts";
import type { MediaTimingEvidenceView } from "./model.ts";
import type { KernelStatusPayload } from "./kernel-adapter.ts";
import type { DemoSessionWorkspace as DemoWorkspace } from "./demo-api.ts";
import { fixtureAssembly, fixtureId, fixtureRenderedOutput, fixtureRenderOperation, fixtureTiming, getFixtureSessionOutputs } from "./session-outputs-fixtures.ts";
const require = createRequire(import.meta.url);
const source = readFileSync(new URL("../components/session-outputs-panel.tsx", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS } });
const exports: { SessionOutputsPanel?: React.ComponentType<{ outputs: presentation.SessionOutputs }> } = {};
runInNewContext(compiled.outputText, { exports, require: (id: string) => id === "../experience/session-outputs.ts" ? presentation : require(id) });
const render = (outputs: presentation.SessionOutputs) => renderToStaticMarkup(React.createElement(exports.SessionOutputsPanel!, { outputs }));
const page = { items: [], next_after: null, limit: 100 };
const eventId = fixtureId(3), sessionId = fixtureId(2);
const revisions = (items = [fixtureAssembly()]) => ({ ...page, event_id: eventId, session_id: sessionId, items, total_count: items.length, items_truncated: false });

test("render tables preserve stable state groups, sort output instants, and disclose identities only in details", () => {
  const outputs = getFixtureSessionOutputs();
  const states = ["terminal_failed", "running", "succeeded", "pending", "cancelled", "leased", "succeeded"] as const;
  const operations = states.map((state, index) => ({ ...fixtureRenderOperation(), state, operation_id: fixtureId(100 + index), assembly_revision_id: index === 0 ? fixtureId(1) : fixtureId(4) }));
  outputs.operations = { state: "available", value: { items: operations, truncated: true } };
  const items = [
    { ...presentation.outputSummary(fixtureRenderedOutput()), output_id: fixtureId(200), produced_at: "2026-09-27T12:00:00Z" },
    { ...presentation.outputSummary(fixtureRenderedOutput()), output_id: fixtureId(201), produced_at: "2026-09-27T07:00:00-07:00", assembly_revision_id: fixtureId(99) },
    { ...presentation.outputSummary(fixtureRenderedOutput()), output_id: fixtureId(202), produced_at: "2026-09-27T13:00:00Z", assembly_revision_id: fixtureId(1) },
  ];
  outputs.outputs = { state: "available", value: { items, truncated: true } };
  outputs.knownRevisions = [{ revisionId: fixtureId(4), number: 1 }];
  const before = JSON.stringify(outputs);
  const html = render(outputs);
  const operationTable = html.match(/<table[^>]*aria-label="Render operations">.*?<\/table>/)![0];
  const outputTable = html.match(/<table[^>]*aria-label="Rendered Outputs">.*?<\/table>/)![0];
  assert.deepEqual([...operationTable.matchAll(/<th scope="row">([^<]+)<\/th>/g)].map((m) => m[1]), ["Rendering...", "Rendering...", "Rendering...", "Done", "Done", "Failed", "Cancelled"]);
  assert.ok(operationTable.indexOf(fixtureId(102)) < operationTable.indexOf(fixtureId(106)));
  assert.ok(outputTable.indexOf(fixtureId(201)) < outputTable.indexOf(fixtureId(202)));
  assert.ok(outputTable.indexOf(fixtureId(202)) < outputTable.indexOf(fixtureId(200)));
  assert.match(outputTable, /Revision 1/); assert.match(outputTable, /Revision 2/); assert.match(outputTable, /earlier revision/);
  assert.match(operationTable, /Revision 1/); assert.match(operationTable, /Revision 2/);
  assert.match(outputTable, /60.000 seconds · 1799 frames/);
  assert.match(outputTable, /<time dateTime="2026-09-27T07:00:00-07:00"/);
  for (const table of [operationTable, outputTable]) {
    const visible = table.replace(/<details>.*?<\/details>/g, "");
    assert.doesNotMatch(visible, /10000000-|aaaaaaaaaaaa|h264-nvenc/);
    assert.doesNotMatch(table, /<details[^>]*\bopen/);
  }
  assert.match(outputTable, /<details>.*SHA-256 prefix:.*aaaaaaaaaaaa/);
  assert.match(html, /Newest produced time first among the outputs shown/);
  assert.match(html, /operation times are unavailable/);
  assert.doesNotMatch(operationTable, /Produced time|newest|dateTime/);
  assert.equal(JSON.stringify(outputs), before);
});

test("current revision summary prioritizes in-flight over success over failure and chooses newest matching output", () => {
  const revisionId = fixtureId(1);
  const operation = { ...fixtureRenderOperation(), assembly_revision_id: revisionId };
  const summary = (items: typeof operation[], outputs: presentation.SessionOutputs["outputs"] = { state: "unavailable" }) =>
    presentation.currentRenderSummary(revisionId, { state: "available", value: { items, truncated: true } }, outputs);
  const failed = { ...operation, state: "terminal_failed" as const, reason_code: "encoder_unavailable" };
  for (const state of ["pending", "leased", "running"] as const) assert.equal(summary([failed, operation, { ...operation, state }]), "Rendering...");
  const output = { ...presentation.outputSummary(fixtureRenderedOutput()), assembly_revision_id: revisionId };
  assert.equal(summary([failed, operation], { state: "available", value: { items: [
    { ...output, produced_at: "2026-09-27T12:00:00Z" },
    { ...output, produced_at: "2026-09-27T07:00:00-07:00", duration_microseconds: 90_000_000 },
    { ...output, produced_at: "2026-09-28T12:00:00Z", assembly_revision_id: fixtureId(99), duration_microseconds: 1 },
  ], truncated: true } }), "Done · 90.000 seconds");
  assert.equal(summary([failed, operation]), "Done");
  assert.equal(summary([failed]), "Failed · encoder_unavailable");
  assert.equal(summary([fixtureRenderOperation()]), undefined);
  assert.equal(summary([]), undefined);
  assert.equal(presentation.currentRenderSummary(revisionId, { state: "unavailable" }), undefined);
});

test("uniform unknown duration is stated once; differing member values retain columns", () => {
  const outputs = getFixtureSessionOutputs();
  outputs.timing = outputs.timing.map((entry) => ({ ...entry, result: { state: "unavailable" } }));
  let html = render(outputs);
  assert.equal((html.match(/Duration unknown/g) ?? []).length, 1);
  assert.match(html, /Duration unknown \(all members\)/);
  assert.doesNotMatch(html, /<th scope="col">Duration<\/th>/);
  assert.match(html, /<th scope="col">Start<\/th>/);
  outputs.timing[1].result = { state: "available", value: fixtureTiming() };
  html = render(outputs);
  assert.match(html, /<th scope="col">Duration<\/th>/);
  assert.match(html, /<td>1:00<\/td>/);
  assert.match(html, /<td>Duration unknown<\/td>/);
});

const packagingAsset = (n = 70) => ({ packaging_asset_id: fixtureId(n), event_id: eventId, stage_id: null, name: "Event opening", role: "opening_bumper", created_at: "2026-09-27T12:00:00Z" });
const packagingAssets = (assets = [packagingAsset()]) => ({ ...page, event_id: eventId, items: assets.map((asset) => ({ asset, current_revision_number: 2, decision_count: 1 })), total_count: assets.length, items_truncated: false });
const packagingRevisions = (assetId = fixtureId(70)) => ({
  ...page, event_id: eventId, packaging_asset_id: assetId, total_count: 1, items_truncated: false,
  items: [{ revision: { revision_id: fixtureId(7), packaging_asset_id: assetId, revision_number: 1,
    content: { kind: "external_content", content_key: "never-expose-content", sha256: "f".repeat(64), byte_size: 1, media_type: "video/mp4" },
    measured_duration_microseconds: null, effective_from: null, effective_until: null, created_at: "2026-09-27T12:00:00Z",
  }, approval_state: "approved", decision_count: 0, latest_decision: null }],
});
const baseReads = { assembly: async () => revisions(), rendering: async () => page, timing: async (path: string) => ({ asset_id: path.split("/")[1], evidence: null }) };

test("slot names and roles resolve by frozen packaging revision, with only safe labels retained", async () => {
  const paths: string[] = [];
  const outputs = await presentation.readSessionOutputs(eventId, sessionId, [], { ...baseReads,
    packaging: async (path) => { paths.push(path); return path.includes("/revisions") ? packagingRevisions() : packagingAssets(); },
  });
  assert.deepEqual(paths, [`events/${eventId}/packaging-assets?limit=100`, `events/${eventId}/packaging-assets/${fixtureId(70)}/revisions?after=0&limit=100`]);
  assert.deepEqual(outputs.packaging, [{ revisionId: fixtureId(7), name: "Event opening", role: "opening_bumper" }]);
  assert.deepEqual(outputs.knownRevisions, [{ revisionId: fixtureId(1), number: 2 }]);
  const html = render(outputs);
  const bindings = html.match(/<ul[^>]*aria-label="Assembly slot bindings">.*?<\/ul>/)![0];
  assert.match(html, /Layout: Intro \(Event opening\)/);
  assert.match(html, /<details><summary>Details<\/summary><ul aria-label="Assembly slot bindings">/);
  assert.doesNotMatch(html.replace(/<details[^>]*>.*?<\/details>/g, ""), /10000000-/);
  assert.ok(bindings.includes(fixtureId(7)));
  assert.doesNotMatch(JSON.stringify(outputs), /never-expose-content|ffffffffffff/);
});

test("missing, failed, truncated and wrong-scope packaging reads keep the ID in details with unavailable wording", async () => {
  const wrongRevision = packagingRevisions(); wrongRevision.items[0].revision.packaging_asset_id = fixtureId(99);
  const readers = [
    async () => { throw new Error("unavailable"); },
    async () => ({ ...packagingAssets([]), items_truncated: true, next_after: fixtureId(90), total_count: 110 }),
    async () => ({ ...packagingAssets(), event_id: fixtureId(90) }),
    async (path: string) => path.includes("/revisions") ? { ...packagingRevisions(), event_id: fixtureId(90) } : packagingAssets(),
    async (path: string) => path.includes("/revisions") ? { ...packagingRevisions(), packaging_asset_id: fixtureId(90) } : packagingAssets(),
    async (path: string) => path.includes("/revisions") ? wrongRevision : packagingAssets(),
    async (path: string) => path.includes("/revisions") ? { ...packagingRevisions(), items: [], items_truncated: true, next_after: 100, total_count: 101 } : packagingAssets(),
  ];
  for (const packaging of readers) {
    const result = await presentation.readSessionOutputs(eventId, sessionId, [], { ...baseReads, packaging });
    assert.deepEqual(result.packaging, []);
    assert.equal(result.assembly.state, "available");
    assert.match(render(result), /Packaging asset unavailable/);
    assert.match(render(result), new RegExp(`<details><summary>Details</summary>.*${fixtureId(7)}`));
  }
});

test("packaging shares the deadline, limits revision reads to eight concurrent and preserves other sections", async () => {
  const budget = createReadBudget(40);
  let calls = 0;
  try {
    const result = await presentation.readSessionOutputs(eventId, sessionId, [], { ...baseReads,
      packaging: async (path) => {
        if (!path.includes("/revisions")) return packagingAssets(Array.from({ length: 100 }, (_, index) => packagingAsset(100 + index)));
        calls++; return new Promise(() => {});
      },
    }, budget);
    assert.equal(calls, 8); assert.deepEqual(result.packaging, []);
    assert.equal(result.assembly.state, "available"); assert.equal(result.outputs.state, "available");
    assert.ok(result.timing.every((entry) => entry.result.state === "available"));
    assert.equal(budget.signal.aborted, true);
  } finally { budget.dispose(); }
});

function compileComponent(file: string, imports: Record<string, unknown>) {
  const source = readFileSync(new URL(file, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS } });
  const exports: Record<string, React.ElementType> = {};
  runInNewContext(compiled.outputText, { exports, require: (id: string) => imports[id] ?? require(id) });
  return exports;
}
const { SessionTimingEvidence } = compileComponent("../components/session-timing-evidence.tsx", { "../experience/session-outputs.ts": presentation });
const renderEvidence = (evidence: MediaTimingEvidenceView[], status = "available") => renderToStaticMarkup(React.createElement(SessionTimingEvidence, { evidence, status }));

test("uniform members have one ordering summary, readable labels and collapsed copyable identity", () => {
  const outputs = getFixtureSessionOutputs();
  const item = fixtureAssembly();
  item.revision.membership = Array.from({ length: 11 }, (_, index) => ({ ...item.revision.membership[1], asset_id: fixtureId(index + 100) }));
  outputs.assembly = { state: "available", value: item };
  outputs.timing = item.revision.membership.map((member) => ({ assetId: member.asset_id, result: { state: "available", value: { ...fixtureTiming(), asset_id: member.asset_id } } }));
  const html = render(outputs);
  assert.match(html, /Ordered by recorder time · Recorder time \(unverified\)/);
  assert.equal((html.match(/Recorder time \(unverified\)/gi) ?? []).length, 1);
  assert.doesNotMatch(html, /class="outputs-qualification"/);
  assert.match(html, /<th scope="row">3<\/th><td><details/);
  assert.match(html, /Start: 12:00:00 \(all members\) · Duration: 1:00 \(all members\)/);
  assert.doesNotMatch(html.replace(/<details[^>]*>.*?<\/details>/g, ""), /Evidence revision/);
  assert.match(html, /<dt>Evidence revision<\/dt><dd>3 · latest 3/);
  assert.equal((html.match(/<th scope="row">\d+<\/th>/g) ?? []).length, 11);
  for (const label of ["Position", "Details"]) assert.ok(html.includes(`<th scope="col">${label}</th>`));
  for (const label of ["Start", "Duration", "Flags"]) assert.ok(!html.includes(`<th scope="col">${label}</th>`));
  assert.match(html, /<summary>Details<\/summary>.*Media ID \(select to copy\).*class="copyable-id" tabindex="0"/);
  assert.match(html, /Start \(date and zone\).*2026-09-27T12:00:00Z/);
  assert.doesNotMatch(html, /<details[^>]*\bopen/);
  assert.match(html, /All recordings shown are in the Assembly/);
  assert.doesNotMatch(html, /aria-label="Media timing outside Assembly"/);
  assert.equal((html.match(new RegExp(fixtureId(102), "g")) ?? []).length, 1);
});

test("only differing ordering or qualification is flagged, and registration is never a media start", () => {
  const outputs = getFixtureSessionOutputs();
  const item = fixtureAssembly();
  const recorder = item.revision.membership[1];
  item.revision.membership = [recorder, { ...recorder, asset_id: fixtureId(80) }, { ...recorder, asset_id: fixtureId(81), order_evidence_qualification: "qualified" }, item.revision.membership[2]];
  outputs.assembly = { state: "available", value: item };
  const html = render(outputs);
  assert.match(html, /Recorder time \(unverified\) \(2 recordings\)/);
  assert.equal((html.match(/class="outputs-qualification"/g) ?? []).length, 2);
  assert.match(html, /Recorder time \(verified\)/);
  assert.match(html, /Arrival time \(no recorder time\)/);
  assert.match(html, /<th scope="row">4<\/th><td>Start unknown<\/td><td>Duration unknown/);
  assert.doesNotMatch(html, /qualification not supplied/);
  assert.equal(presentation.wallClockLabel("2026-09-27T07:48:15-07:00"), "07:48:15");
  assert.equal(presentation.intervalDuration({ started_at: "2026-09-27T07:48:15-07:00", ended_at: "2026-09-27T14:49:15Z" }), "1:00");
});

test("folding preserves latest versus frozen evidence and lists only media outside Assembly", () => {
  const outputs = getFixtureSessionOutputs();
  const latest = fixtureTiming(); latest.evidence!.revision = 4; latest.evidence!.evidence_id = fixtureId(88);
  outputs.timing[1].result = { state: "available", value: latest };
  outputs.timing.push({ assetId: fixtureId(99), result: { state: "unavailable" } });
  const html = render(outputs);
  assert.match(html, /A newer timing estimate exists/);
  assert.match(html, /Latest timing does not replace frozen ordering evidence/);
  const outside = html.split('aria-label="Media timing outside Assembly"')[1];
  assert.ok(outside.includes(fixtureId(99)));
  assert.ok(!outside.includes(fixtureId(11)));
  assert.match(outside, /Media timing unavailable/);
  assert.doesNotMatch(html, /All Session media/);
  outputs.timing.pop(); outputs.timingTruncated = true;
  assert.doesNotMatch(render(outputs), /All Session media/);
  assert.match(render(outputs), /additional media may be outside this view/);
});

test("evidence summary and cards are collapsed, limitations unique, full tool hash only in detail", () => {
  const evidence = getFixtureWorkspace("run-004").mediaTimingEvidence[0];
  const item = { ...evidence, toolLabel: `ffprobe sha256:${"a".repeat(64)}`, limitations: ["One limitation", "One limitation"], observations: [{ kind: "duration", precision: "microseconds", limitations: ["One limitation", "Second limitation"] }] };
  const html = renderEvidence([item]);
  assert.match(html, /1 recent recording · Recorder time \(unverified\)/);
  assert.equal((html.match(/One limitation/g) ?? []).length, 1);
  assert.equal((html.match(/Second limitation/g) ?? []).length, 1);
  assert.equal((html.match(new RegExp("a".repeat(64), "g")) ?? []).length, 1);
  const summaries = html.match(/<summary>[\s\S]*?<\/summary>/g) ?? [];
  assert.equal(summaries.length, 2);
  assert.ok(summaries[1].includes("Estimated start"));
  assert.ok(!summaries[1].includes("a".repeat(64)));
  assert.doesNotMatch(html, /<details[^>]*\bopen/);
  assert.match(renderEvidence([item, { ...item, evidenceId: "other", assetId: "other", qualificationStatus: "qualified" }]), /2 recent recordings · Timing certainty varies/);
  assert.match(renderEvidence([], "unavailable"), /<summary>.*Timing evidence unavailable<\/span><\/summary>/);
  assert.match(renderEvidence([]), /No timing estimates in this view/);
});

test("Session structure puts Outputs immediately after lifecycle and membership, before evidence", () => {
  const empty = () => null;
  const { SessionOperationalView } = compileComponent("../components/operational-views.tsx", {
    "next/link": { default: empty },
    "@/experience/program-provider.ts": { programProviderDisplayName: () => "Schedule" },
    "@/experience/presentation.ts": { formatActivityState: () => "Active", formatPackageState: () => "Assembling", authorityActionsEnabled: () => false },
    "./session-timing-evidence": { SessionTimingEvidence },
    "./demo-session-workspace": { DemoSessionWorkspace: empty },
    "./demo-program-refresh-control": { DemoProgramRefreshControl: empty },
    "./demo-start-session-control": { DemoStartSessionControl: empty },
    "./mission-control": { AttentionPanel: empty, WorkspaceTitle: empty },
  });
  const workspace = getFixtureWorkspace("quiet");
  const html = renderToStaticMarkup(React.createElement(SessionOperationalView, { workspace, session: workspace.sessions[0], outputs: React.createElement(exports.SessionOutputsPanel!, { outputs: getFixtureSessionOutputs() }) }));
  assert.ok(html.indexOf("Operational lifecycle") < html.indexOf("Recordings"));
  assert.match(html, /<\/section><\/div><section class="detail-panel outputs-panel"/);
  assert.ok(html.indexOf("Outputs") < html.indexOf("Timing estimates"));
});

test("member flags show differing evidence revision and frozen/latest status only", () => {
  const outputs = getFixtureSessionOutputs();
  const item = fixtureAssembly();
  item.revision.membership = Array.from({ length: 4 }, (_, index) => ({ ...item.revision.membership[1], asset_id: fixtureId(index + 100) }));
  outputs.assembly = { state: "available", value: item };
  outputs.timing = item.revision.membership.map((member) => ({ assetId: member.asset_id, result: { state: "available", value: { ...fixtureTiming(), asset_id: member.asset_id } } }));
  // Same revision number, different identity: it must not be called frozen and latest.
  const latest = fixtureTiming(); latest.evidence!.evidence_id = fixtureId(88);
  outputs.timing[2].result = { state: "available", value: latest };
  outputs.timing[3].result = { state: "unavailable" };
  const html = render(outputs);
  assert.doesNotMatch(html.replace(/<details[^>]*>.*?<\/details>/g, ""), /Evidence revision/);
  assert.match(html, /Ordered by recorder time/);
  const flags = [...html.matchAll(/<td class="member-flags">(.*?)<\/td>/g)].map((match) => match[1]);
  assert.deepEqual(flags.slice(0, 2), ["", ""]);
  assert.match(flags[2], /A newer timing estimate exists/);
  assert.match(flags[3], /Media timing unavailable/);
});

test("bounded timing sample counts unique recent assets without inventing a Session total", () => {
  const item = getFixtureWorkspace("run-004").mediaTimingEvidence[0];
  const evidence = Array.from({ length: 8 }, (_, index) => ({ ...item, assetId: fixtureId(100 + index), evidenceId: fixtureId(200 + index) }));
  evidence.push({ ...evidence[0], evidenceId: fixtureId(300), revision: 2 });
  const summary = renderEvidence(evidence).match(/<summary>(.*?)<\/summary>/)![1];
  assert.match(summary, /8 recent recordings/);
  assert.doesNotMatch(summary, /9 recent|of \d+|12 assets/);
});

function demoWorkspaceFixture(): DemoWorkspace {
  return {
    session_id: sessionId, activity_state: "presentation_active", package_state: "assembling", package_revision: 1, revision: 1,
    label: "Transcription Evidence", authority_notice: "Evidence only",
    work: { counts: {}, oldest_eligible_at: null, active_lease_count: 0, attention_codes: [] },
    operations: [], operations_truncated: false, operation_limit: 100,
    transcript_assets_truncated: false, transcript_asset_limit: 20, moments: [],
    transcript_evidence: Array.from({ length: 11 }, (_, index) => ({
      evidence_id: fixtureId(index + 100), operation_id: fixtureId(index + 200), asset_id: fixtureId(index + 300), revision: 1,
      status: "complete", language: "en", provider_id: "synthetic", provider_version: "1", model_id: "synthetic", model_version: "1",
      produced_at: "2026-09-27T12:00:00Z", applied_at: "2026-09-27T12:00:00Z", limitations: [], partial_reason: null, failure_reason: null,
      segments_truncated: false, segment_limit: 100,
      segments: [{ segment_id: fixtureId(index + 400), ordinal: 0, text: Array(index === 0 ? 146 : 140).fill("synthetic").join(" "),
        asset_start_microseconds: 0, asset_end_microseconds: 60_000_000, speaker_label: null, speaker_evidence_kind: null,
        confidence: null, confidence_semantics: null, limitations: [], words: [], words_truncated: false, word_limit: 100 }],
    })),
  };
}

function renderDemo(workspace?: DemoWorkspace, loading = false) {
  const states = [workspace, loading, undefined, undefined];
  const { DemoSessionWorkspace } = compileComponent("../components/demo-session-workspace.tsx", {
    react: { ...React, useState: () => [states.shift(), () => undefined] },
    "next/navigation": { useRouter: () => ({ refresh() {} }) },
    "./session-moments": { SessionMoments: () => null },
    "@/experience/demo-api.ts": {}, "@/experience/demo-launch-context.ts": {}, "@/experience/demo-package-approval.ts": {},
  });
  return renderToStaticMarkup(React.createElement(DemoSessionWorkspace, {
    sessionId, sessionTitle: "Synthetic Session", enabled: true, initialActivityState: "presentation_active", initialPackageState: "assembling",
    initialRevision: 1, initialPackageRevision: 1, mediaAssociated: 11, mediaUnresolved: 0, mediaConflicting: 0,
  }));
}

test("transcript summary and every asset use closed native disclosures with segments inside", () => {
  const html = renderDemo(demoWorkspaceFixture());
  assert.match(html, /<details class="transcription-disclosure"><summary><strong>Automatic transcript: may contain errors<\/strong> · 11 complete · 1,546 words<\/summary>/);
  assert.equal((html.match(/<details class="transcription-evidence-card">/g) ?? []).length, 11);
  assert.match(html, /<details class="transcription-evidence-card"><summary>Asset .*?<\/summary>.*?class="transcript-segments"/);
  assert.doesNotMatch(html, /<details[^>]*\bopen/);
  // Authority controls remain outside the evidence disclosure.
  for (const label of ["End Presentation", "Process Media Now", "Package Ready", "Approve Package", "Mark Moment"]) {
    assert.ok(html.indexOf(label) < html.indexOf('<details class="transcription-disclosure">'));
  }
});

test("transcript summary discloses partial, failed, empty, loading and bounded evidence", () => {
  const workspace = demoWorkspaceFixture();
  workspace.transcript_evidence[0].status = "partial";
  workspace.transcript_evidence[1].status = "failed";
  for (const boundedBy of ["assets", "segments"] as const) {
    workspace.transcript_assets_truncated = boundedBy === "assets";
    workspace.transcript_evidence[0].segments_truncated = boundedBy === "segments";
    assert.match(renderDemo(workspace), /1 partial · 1 failed · 9 complete · 1,546 words shown · more available/);
  }
  workspace.transcript_evidence = [];
  assert.match(renderDemo(workspace), /<summary><strong>Automatic transcript: may contain errors<\/strong> · No automatic transcript yet<\/summary>/);
  assert.match(renderDemo(), /<summary><strong>Automatic transcript: may contain errors<\/strong> · Evidence unavailable<\/summary>/);
  assert.match(renderDemo(undefined, true), /<summary><strong>Automatic transcript: may contain errors<\/strong> · Refreshing evidence<\/summary>/);
});

test("operation states are summarized and only non-succeeded operations retain tiles", () => {
  const workspace = demoWorkspaceFixture();
  const operation = { operation_id: fixtureId(500), asset_id: "succeeded-asset", status: "succeeded", attempt_count: 1, max_attempts: 3, last_reason_code: null, created_at: "2026-09-27T12:00:00Z", updated_at: "2026-09-27T12:00:00Z" };
  workspace.operations = Array.from({ length: 11 }, (_, index) => ({ ...operation, operation_id: fixtureId(500 + index) }));
  let html = renderDemo(workspace);
  assert.match(html, /<span>Operations<\/span><strong>11 succeeded<\/strong>/);
  assert.doesNotMatch(html, /class="demo-operation-list"|Asset succeede/);
  workspace.operations.push(...["queued", "running", "retry_scheduled", "terminal_failed", "cancelled"].map((status, index) => ({ ...operation, status, asset_id: `${status}-asset`, operation_id: fixtureId(600 + index), last_reason_code: "synthetic_reason" })));
  workspace.operations_truncated = true;
  html = renderDemo(workspace);
  assert.match(html, /11 succeeded · 1 queued · 1 running · 1 retry scheduled · 1 terminal failed · 1 cancelled/);
  const grid = html.split('aria-label="Transcription operations">')[1].split('</div>')[0];
  assert.equal((grid.match(/<article>/g) ?? []).length, 5);
  assert.doesNotMatch(grid, /succeeded|succeede/);
  assert.match(grid, /Attempt 1 \/ 3/);
  assert.match(grid, /synthetic reason/);
  assert.match(html, /Latest 100 Event operations/);
  workspace.operations = [];
  assert.match(renderDemo(workspace), /<span>Operations<\/span><strong>No operations<\/strong>/);
});

test("shared deadline retains completed sections and stops queued timing reads after eight stalls", async () => {
  const budget = createReadBudget(30);
  let count = 0;
  try {
    const result = await presentation.readSessionOutputs(eventId, sessionId, Array.from({ length: 100 }, (_, index) => fixtureId(index + 100)), {
      assembly: async () => revisions([]), rendering: async () => page,
      timing: () => { count++; return new Promise(() => {}); },
    }, budget);
    assert.equal(count, 8);
    assert.equal(result.timing.length, 100);
    assert.ok(result.timing.every((entry) => entry.result.state === "unavailable"));
    assert.equal(result.assembly.state, "available");
    assert.equal(result.operations.state, "available");
    assert.equal(budget.signal.aborted, true);
  } finally { budget.dispose(); }
});

test("a stalled render read does not block timing; Assembly pagination shares the deadline", async () => {
  for (const stallAssembly of [false, true]) {
    const budget = createReadBudget(30);
    let timingReads = 0, assemblyReads = 0;
    try {
      const result = await presentation.readSessionOutputs(eventId, sessionId, [fixtureId(11)], {
        assembly: async () => {
          assemblyReads++;
          if (!stallAssembly) return revisions([]);
          if (assemblyReads === 1) return revisions([{ ...fixtureAssembly(), current_revision_number: 101 }]);
          return new Promise(() => {});
        },
        rendering: async (path) => path.startsWith("outputs") ? page : new Promise(() => {}),
        timing: async () => { timingReads++; return fixtureTiming(); },
      }, budget);
      assert.equal(result.operations.state, "unavailable");
      assert.equal(result.outputs.state, "available");
      assert.equal(result.assembly.state, stallAssembly ? "unavailable" : "available");
      assert.equal(timingReads, stallAssembly ? 0 : 1);
      assert.equal(result.timing[0].result.state, stallAssembly ? "unavailable" : "available");
    } finally { budget.dispose(); }
  }
});

test("workspace response bodies and subsequent reads obey the same overall deadline", async () => {
  const originalFetch = globalThis.fetch;
  const originalMode = process.env.STAGEFLOW_UI_DATA_MODE;
  const originalSecret = process.env.STAGEFLOW_API_SHARED_SECRET;
  process.env.STAGEFLOW_UI_DATA_MODE = "kernel";
  process.env.STAGEFLOW_API_SHARED_SECRET = "synthetic-budget-test-secret-0123456789";
  const budget = createReadBudget(30);
  globalThis.fetch = async () => ({ ok: true, json: () => new Promise(() => {}) }) as Response;
  try {
    const workspace = await loadWorkspace({ includeTimingEvidence: true, readBudget: budget });
    assert.equal(workspace.dataSource.kind, "kernel");
    assert.equal(workspace.event.ready, false);
    let calls = 0;
    const reads = async () => { calls++; return page; };
    const outputs = await presentation.readSessionOutputs(eventId, sessionId, [], { assembly: reads, rendering: reads, timing: reads }, budget);
    assert.equal(calls, 0);
    assert.equal(outputs.assembly.state, "unavailable");
  } finally {
    budget.dispose(); globalThis.fetch = originalFetch;
    if (originalMode === undefined) delete process.env.STAGEFLOW_UI_DATA_MODE; else process.env.STAGEFLOW_UI_DATA_MODE = originalMode;
    if (originalSecret === undefined) delete process.env.STAGEFLOW_API_SHARED_SECRET; else process.env.STAGEFLOW_API_SHARED_SECRET = originalSecret;
  }
});

test("stalled evidence degrades its section while keeping the completed Kernel workspace", async () => {
  const originalFetch = globalThis.fetch;
  const originalMode = process.env.STAGEFLOW_UI_DATA_MODE;
  const originalSecret = process.env.STAGEFLOW_API_SHARED_SECRET;
  process.env.STAGEFLOW_UI_DATA_MODE = "kernel";
  process.env.STAGEFLOW_API_SHARED_SECRET = "synthetic-budget-test-secret-0123456789";
  const payload: KernelStatusPayload = {
    configured: true, configuration_supplied: true, configuration_valid: true, runtime_composed: true,
    event_id: eventId, event_key: "synthetic", event_name: "Synthetic Event", database_available: true,
    ready: true, recovering: false, reconciliation_status: "complete", reconciliation_started_at: null,
    reconciliation_completed_at: null, stages: [], attention_codes: [], recent_media: [{
      asset_id: fixtureId(11), candidate_id: fixtureId(50), proposed_asset_id: fixtureId(11), stage_id: fixtureId(51),
      source_binding_key: "synthetic", registration_state: "registered", discovered_at: "2026-09-27T12:00:00Z",
      last_observed_at: "2026-09-27T12:00:00Z", association_status: "unresolved", association_authority: null,
      session_id: null, epistemic_kinds: [], media_started_at: null, media_ended_at: null, diagnostic_codes: [],
      association_reason_codes: [], association_policy_id: null, association_policy_version: null, association_input_references: [],
    }],
  };
  const budget = createReadBudget(30);
  let reads = 0;
  globalThis.fetch = async () => { reads++; return reads === 1 ? Response.json(payload) : new Promise(() => {}); };
  try {
    const workspace = await loadWorkspace({ includeTimingEvidence: true, readBudget: budget });
    assert.equal(reads, 2);
    assert.equal(workspace.event.id, eventId);
    assert.equal(workspace.event.ready, true);
    assert.equal(workspace.mediaTimingEvidenceStatus, "unavailable");
  } finally {
    budget.dispose(); globalThis.fetch = originalFetch;
    if (originalMode === undefined) delete process.env.STAGEFLOW_UI_DATA_MODE; else process.env.STAGEFLOW_UI_DATA_MODE = originalMode;
    if (originalSecret === undefined) delete process.env.STAGEFLOW_API_SHARED_SECRET; else process.env.STAGEFLOW_API_SHARED_SECRET = originalSecret;
  }
});

test("Session page passes one five-second budget through workspace and Outputs loading", async (context) => {
  context.mock.timers.enable({ apis: ["setTimeout"] });
  const budget = createReadBudget();
  context.mock.timers.tick(4_999);
  assert.equal(budget.signal.aborted, false);
  context.mock.timers.tick(1);
  assert.equal(budget.signal.aborted, true);
  budget.dispose();
  const pageSource = readFileSync(new URL("../../app/sessions/[sessionId]/page.tsx", import.meta.url), "utf8");
  const compiledPage = ts.transpileModule(pageSource, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS } });
  const pageExports: { default?: (props: unknown) => Promise<React.ReactElement> } = {};
  let disposed = false, outputRead = false;
  const pageBudget = { ...createReadBudget(), dispose() { disposed = true; } };
  const workspace = getFixtureWorkspace("quiet");
  const empty = () => null;
  const imports: Record<string, unknown> = {
    "@/experience/read-budget.ts": { createReadBudget: () => pageBudget },
    "@/experience/data-source.ts": { loadWorkspace: async (request: { readBudget: unknown }) => { assert.equal(request.readBudget, pageBudget); return workspace; } },
    "@/experience/session-outputs.server.ts": { loadSessionOutputs: async (_workspace: unknown, id: string, receivedBudget: unknown) => { assert.equal(receivedBudget, pageBudget); assert.equal(id, workspace.sessions[0].id); outputRead = true; return getFixtureSessionOutputs(); } },
    "@/components/operational-shell": { OperationalShell: empty },
    "@/components/operational-views": { SessionOperationalView: empty },
    "@/components/session-outputs-panel": { SessionOutputsPanel: empty },
    "@/components/session-output-actions": { SessionOutputActions: empty },
  };
  runInNewContext(compiledPage.outputText, { exports: pageExports, process: { env: {} }, require: (id: string) => imports[id] ?? require(id) });
  await pageExports.default!({ params: Promise.resolve({ sessionId: workspace.sessions[0].id }), searchParams: Promise.resolve({}) });
  assert.equal(outputRead, true);
  assert.equal(disposed, true);
});

test("real Outputs panel renders frozen position order and all ordering/qualification labels", () => {
  const output = render(getFixtureSessionOutputs());
  for (const label of ["Outputs", "Read-only", "Development fixture", "Not production authority", "Current revision", "Recorder time (unverified)", "media_timing", "timing_evidence", "registration_time", "Arrival time (no recorder time)", "Layout", "Evidence revision", "advisory", "SHA-256 prefix:", "aaaaaaaaaaaa", "60.000 seconds", "1799", "version 2", "2026-09-27T12:00:00Z"]) assert.ok(output.includes(label), label);
  assert.ok(output.indexOf('scope="row">1</th>') < output.indexOf('scope="row">2</th>')); assert.ok(output.indexOf('scope="row">2</th>') < output.indexOf('scope="row">3</th>'));
  assert.match(output, /aria-label="Assembly members in frozen position order"/);
  assert.doesNotMatch(output, /qualification not applicable/);
  assert.doesNotMatch(output, /<button|<video|<audio|synthetic-output|synthetic-manifest|content_key|ffmpeg_sha256/);
});
test("qualified, rejected, expired and absent qualifications remain distinct text", () => {
  const expected = ["Recorder time (unverified)", "Recorder time (verified)", "Recorder time (rejected)", "Recorder time (verification expired)", ""];
  for (const [index, value] of (["unqualified", "qualified", "rejected", "expired", null] as const).entries()) assert.equal(presentation.qualificationLabel(value), expected[index]);
});
test("staleness, issue codes, approval and bounded reads have visible consequences", () => {
  const outputs = getFixtureSessionOutputs();
  if (outputs.assembly.state !== "available" || !outputs.assembly.value || outputs.operations.state !== "available" || outputs.outputs.state !== "available") assert.fail();
  outputs.assembly.value.stale = true;
  outputs.assembly.value.approval_state = "approved";
  outputs.assembly.value.revision.validation = { state: "invalid", issues: [{ code: "unresolved_required_slot", subject: "opening" }] };
  outputs.operations.value.truncated = true; outputs.outputs.value.truncated = true; outputs.timingTruncated = true;
  const html = render(outputs);
  for (const text of ["Out of date: inputs changed", "Prior decisions remain recorded", "unresolved_required_slot", "approved", "More operations exist", "More outputs exist", "Additional assets are not shown"]) assert.ok(html.includes(text), text);
});
test("empty, unavailable and missing evidence are distinct; no fixture fallback", () => {
  const outputs = getFixtureSessionOutputs(); outputs.fixture = false; outputs.assembly = { state: "available", value: null }; outputs.operations = { state: "unavailable" }; outputs.outputs = { state: "available", value: { items: [], truncated: false } };
  const html = render(outputs);
  for (const label of ["No Assembly revision proposed", "Render operations unavailable", "No Rendered Outputs reported", "No timing evidence recorded"]) assert.ok(html.includes(label));
  assert.doesNotMatch(html, /Development fixture/);
});
test("read model jumps to the backend current revision beyond the first page without reordering members", async () => {
  const paths: string[] = [];
  const current = fixtureAssembly(); current.current_revision_number = 101; current.revision.revision_number = 101;
  current.revision.membership.reverse();
  const old = fixtureAssembly(); old.current_revision_number = 101;
  const result = await presentation.readSessionOutputs(eventId, sessionId, [], {
    assembly: async (path) => { paths.push(path); return path.includes("after=100") ? revisions([current]) : { ...revisions([old]), total_count: 101, items_truncated: true, next_after: 2 }; },
    rendering: async (path) => path.startsWith("outputs") ? { ...page, items: [fixtureRenderedOutput()] } : { ...page, items: [fixtureRenderOperation()] },
    timing: async (path) => ({ asset_id: path.split("/")[1], evidence: null }),
  });
  assert.equal(paths.length, 2); assert.ok(paths[1].includes("after=100"));
  assert.equal(result.assembly.state, "available");
  if (result.assembly.state === "available") assert.deepEqual(result.assembly.value?.revision.membership.map((m) => m.asset_id), current.revision.membership.map((m) => m.asset_id));
  assert.equal(result.fixture, false); assert.equal(result.timing.length, 3);
  if (result.outputs.state === "available") { assert.equal(result.outputs.value.items[0].sha256.length, 12); assert.equal("content_key" in result.outputs.value.items[0], false); }
});
test("capability failure does not hide other reads, and mismatched asset evidence is refused", async () => {
  const result = await presentation.readSessionOutputs(eventId, sessionId, [fixtureId(11), fixtureId(12)], {
    assembly: async () => { throw new Error("unavailable"); },
    rendering: async () => page,
    timing: async () => fixtureTiming(),
  });
  assert.equal(result.assembly.state, "unavailable"); assert.equal(result.outputs.state, "available");
  assert.equal(result.timing[0].result.state, "available"); assert.equal(result.timing[1].result.state, "unavailable");
  assert.equal(result.fixture, false);
});
test("current revision races, invalid schemas and cross-Session responses are unavailable", async () => {
  const wrong = fixtureAssembly(); wrong.revision.session_id = fixtureId(90);
  for (const response of [{}, revisions([wrong]), { ...revisions([]), total_count: 3 }, { ...revisions(), session_id: fixtureId(90) }, revisions([{ ...fixtureAssembly(), current_revision_number: 99 }])]) {
    const result = await presentation.readSessionOutputs(eventId, sessionId, [], { assembly: async () => response, rendering: async () => page, timing: async () => { assert.fail(); } });
    assert.equal(result.assembly.state, "unavailable");
  }
});
test("per-asset reads are deduplicated, bounded to 100 and at most eight run together", async () => {
  let active = 0, peak = 0, count = 0;
  const result = await presentation.readSessionOutputs(eventId, sessionId, [...Array.from({ length: 105 }, (_, n) => fixtureId(n + 100)), fixtureId(100)], {
    assembly: async () => revisions([]), rendering: async () => page,
    timing: async (path) => { active++; count++; peak = Math.max(peak, active); await Promise.resolve(); active--; return { asset_id: path.split("/")[1], evidence: null }; },
  });
  assert.equal(count, 100); assert.ok(peak <= 8); assert.equal(result.timingTruncated, true);
});

test("legacy invalid Assembly timing stays visible without inventing a timestamp", () => {
  const outputs = getFixtureSessionOutputs();
  if (outputs.assembly.state !== "available" || !outputs.assembly.value) assert.fail();
  outputs.assembly.value.revision.membership[0].order_key_at = null;
  outputs.assembly.value.revision.membership[0].media_started_at = null;
  const html = render(outputs);
  assert.match(html, /Ordering key \(wall-clock\)<\/dt><dd>Unavailable/);
  assert.doesNotMatch(html, /dateTime="null"/);
});

test("fixture Session loading never calls a backend and keeps the fixture label", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { assert.fail("fixture must not fetch"); };
  try {
    const workspace = getFixtureWorkspace("quiet");
    const result = await loadSessionOutputs(workspace, workspace.sessions[0].id);
    assert.equal(result.fixture, true);
    assert.match(render(result), /Development fixture/);
  } finally { globalThis.fetch = originalFetch; }
});
test("Kernel Session loading uses protected server reads and strips output content references", async () => {
  const originalFetch = globalThis.fetch;
  const originalSecret = process.env.STAGEFLOW_API_SHARED_SECRET;
  const secret = "synthetic-kernel-read-secret-0123456789";
  process.env.STAGEFLOW_API_SHARED_SECRET = secret;
  const seen: string[] = [];
  let packagingRead = false;
  globalThis.fetch = async (input, init) => {
    const url = new URL(String(input));
    assert.equal(url.hostname, "127.0.0.1"); assert.equal(init?.method, "GET");
    assert.equal(new Headers(init?.headers).get("x-stageflow-api-secret"), secret);
    if (url.pathname.endsWith("/packaging-assets")) {
      packagingRead = true;
      return Response.json({ ...page, event_id: eventId, total_count: 0, items_truncated: false });
    }
    seen.push(url.pathname);
    if (url.pathname.endsWith("/revisions")) return Response.json(revisions());
    if (url.pathname.endsWith("/operations")) return Response.json({ ...page, items: [fixtureRenderOperation()] });
    if (url.pathname.endsWith("/outputs")) return Response.json({ ...page, items: [fixtureRenderedOutput()] });
    return Response.json({ asset_id: url.pathname.split("/")[5], evidence: null });
  };
  try {
    const workspace = getFixtureWorkspace("quiet"); workspace.dataSource.kind = "kernel"; workspace.event.id = eventId; workspace.mediaAssets = [];
    const result = await loadSessionOutputs(workspace, sessionId);
    assert.equal(result.fixture, false); assert.equal(result.assembly.state, "available");
    assert.equal(result.operations.state, "available"); assert.equal(result.outputs.state, "available");
    assert.equal(seen.length, 6);
    assert.equal(packagingRead, true);
    for (const item of result.timing) assert.equal(item.result.state, "available");
    const html = render(result);
    assert.doesNotMatch(html, /Development fixture|synthetic-output|synthetic-manifest/);
    assert.doesNotMatch(html, new RegExp(secret));
  } finally {
    globalThis.fetch = originalFetch;
    if (originalSecret === undefined) delete process.env.STAGEFLOW_API_SHARED_SECRET; else process.env.STAGEFLOW_API_SHARED_SECRET = originalSecret;
  }
});


// Remove closed disclosures, including nested ones, to test the initial scanning surface.
function collapsedMarkup(html: string): string {
  let depth = 0;
  return html.split(/(<\/?details\b[^>]*>)/).filter((part) => {
    if (part.startsWith("<details")) { depth++; return false; }
    if (part.startsWith("</details")) { depth--; return false; }
    return depth === 0;
  }).join("");
}

test("Outputs use plain labels while internal revisions and states stay in Details", () => {
  const outputs = getFixtureSessionOutputs();
  outputs.packaging = [{ revisionId: fixtureId(7), name: "Event opening", role: "opening_bumper" }];
  const html = render(outputs), visible = collapsedMarkup(html);
  for (const text of ["Up to date", "Awaiting review", "Order locked when proposed", "Ordered by recorder time", "Recorder time (unverified)", "1 recording ordered by arrival time (no recorder time)", "Layout: Intro (Event opening) → Recording", "Done", "1080p (v2)"]) assert.ok(visible.includes(text), text);
  assert.doesNotMatch(visible, /revision \d|unqualified|registration_time|session_media|bounded|wall-clock|advisory/i);
  for (const raw of ["unqualified", "registration_time", "session_media", "Current revision: 2", "succeeded", "opening_bumper"]) assert.ok(html.includes(raw), raw);
  assert.match(html, /Recorder start and length are unverified/);
});

test("navigation and top bar share Editorial review and preserve the event-readiness disclaimer", () => {
  const { OperationalShell } = compileComponent("../components/operational-shell.tsx", {
    "next/link": { __esModule: true, default: ({ children, ...props }: React.PropsWithChildren<{ href: string }>) => React.createElement("a", props, children) },
    "@/experience/fixtures.ts": { scenarioOptions: [] },
    "@/experience/presentation.ts": { workspaceAttentionLevel: () => undefined },
  });
  const workspace = getFixtureWorkspace("quiet");
  workspace.dataSource = { ...workspace.dataSource, kind: "kernel", state: "live_connected", authoritative: true, runtimeProfile: "demo-single-stage", scenarioId: undefined };
  const html = renderToStaticMarkup(React.createElement(OperationalShell, { workspace, activePath: "/editorial" }));
  const visible = collapsedMarkup(html);
  assert.match(visible, /href="\/editorial"[^>]*><span>Editorial review/);
  assert.match(visible, /Test setup · 1 stage · not event-ready/);
  assert.match(visible, /Live · connected/);
  assert.doesNotMatch(visible, /Backend projection|Live Triage/);
  assert.match(html, /<summary>Details<\/summary>.*demo-single-stage/);
});

test("Session lifecycle, recordings and assignment retain diagnostics and preservation meaning", () => {
  const empty = () => null;
  const { SessionOperationalView } = compileComponent("../components/operational-views.tsx", {
    "next/link": { default: empty },
    "@/experience/program-provider.ts": { programProviderDisplayName: () => "Schedule" },
    "@/experience/presentation.ts": { formatActivityState: () => "Active", formatPackageState: () => "Assembling", authorityActionsEnabled: () => false },
    "./session-timing-evidence": { SessionTimingEvidence },
    "./demo-session-workspace": { DemoSessionWorkspace: empty },
    "./demo-program-refresh-control": { DemoProgramRefreshControl: empty },
    "./demo-start-session-control": { DemoStartSessionControl: empty },
    "./mission-control": { AttentionPanel: empty, WorkspaceTitle: empty },
  });
  const workspace = getFixtureWorkspace("run-004");
  const session = { ...workspace.sessions[0], provenance: "declared", media: { ...workspace.sessions[0].media, unresolved: 1 } };
  workspace.mediaAssets = [{ ...workspace.mediaAssets[0], consideredSessionIds: [session.id], associationReasonCodes: ["no_safely_eligible_session"], associationStatus: "unresolved" }];
  const html = renderToStaticMarkup(React.createElement(SessionOperationalView, { workspace, session }));
  const visible = collapsedMarkup(html);
  for (const label of ["Set by producer", "Found", "In this Session", "Still recording", "Needs a decision", "Claimed by two Sessions", "1 recording needs a decision: no Session fits it. Nothing was deleted.", "No Session matches this recording&#x27;s time. Checked:"]) assert.ok(visible.includes(label), label);
  assert.doesNotMatch(visible, /Session revision|Package revision|Aggregate|DECLARED/);
  assert.match(html, /<summary>Details<\/summary>.*Session revision/);
});


test("uniform outside timing is stated once, with raw certainty and full timestamps in Details", () => {
  const outputs = getFixtureSessionOutputs();
  outputs.assembly = { state: "available", value: null };
  outputs.timing = [fixtureId(90), fixtureId(91)].map((assetId) => ({ assetId, result: { state: "available", value: { ...fixtureTiming(), asset_id: assetId } } }));
  const html = render(outputs), visible = collapsedMarkup(html);
  assert.equal((visible.match(/Recorder time \(unverified\)/g) ?? []).length, 1);
  assert.match(visible, /all 2 recordings below/);
  assert.equal((visible.match(/Estimated start:.*?12:00:00/g) ?? []).length, 2);
  assert.doesNotMatch(visible, /Evidence revision|unqualified|10000000-/);
  assert.match(html, /<summary>Details<\/summary>.*Evidence revision 3.*unqualified/);
});
