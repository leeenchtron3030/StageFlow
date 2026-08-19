import assert from "node:assert/strict";
import test from "node:test";

import { getFixtureWorkspace } from "./fixtures.ts";
import {
  adaptKernelStatus,
  adaptKernelMediaTimingEvidence,
  kernelUnavailableWorkspace,
  type KernelStatusPayload,
} from "./kernel-adapter.ts";
import {
  authorityActionsEnabled,
  formatActivityState,
  formatPackageState,
  isSessionProminent,
  workspaceAttentionLevel,
} from "./presentation.ts";

test("quiet Event renders no unnecessary Producer Attention", () => {
  const workspace = getFixtureWorkspace("quiet");

  assert.equal(workspace.attention.length, 0);
  assert.equal(workspaceAttentionLevel(workspace), undefined);
  assert.deepEqual(workspace.stages.map((stage) => stage.key), ["main", "studio", "workshop"]);
});

test("unresolved turnover is Review and explains preservation", () => {
  const workspace = getFixtureWorkspace("turnover");

  assert.equal(workspaceAttentionLevel(workspace), "review");
  assert.equal(workspace.stages[0].media.unresolved, 17);
  assert.equal(workspace.stages[0].attentionLevel, "review");
  assert.match(workspace.attention[0].safeContinuation, /Media is preserved/);
  assert.doesNotMatch(workspace.attention[0].title, /error|failure/i);
});

test("normal file stabilization remains visually quiet", () => {
  const workspace = getFixtureWorkspace("growing");

  assert.equal(workspace.stages[1].media.stabilizing, 1);
  assert.equal(workspace.stages[1].attentionLevel, undefined);
  assert.equal(workspace.attention.length, 0);
});

test("Presentation End and Package Assembling remain distinct", () => {
  const workspace = getFixtureWorkspace("assembling");
  const session = workspace.stages[0].currentSession;

  assert.ok(session);
  assert.equal(formatActivityState(session), "Presentation ended");
  assert.equal(formatPackageState(session), "Assembling");
});

test("completed Sessions leave active Stage prominence", () => {
  const workspace = getFixtureWorkspace("completed");
  const completed = workspace.sessions.find((session) => session.packageState === "complete");

  assert.ok(completed);
  assert.equal(isSessionProminent(completed), false);
  assert.equal(workspace.stages[0].currentSession, undefined);
  assert.equal(workspace.stages[0].previousSession?.id, completed.id);
});

test("source loss is Intervention while cloud loss communicates local continuation", () => {
  const sourceLoss = getFixtureWorkspace("source-unavailable");
  const cloudLoss = getFixtureWorkspace("cloud-unavailable");

  assert.equal(workspaceAttentionLevel(sourceLoss), "intervention");
  assert.match(sourceLoss.attention[0].safeContinuation, /preserved/i);
  assert.equal(workspaceAttentionLevel(cloudLoss), undefined);
  assert.match(
    cloudLoss.infrastructure.find((item) => item.id === "internet")?.impact ?? "",
    /Local Session control and media preservation continue/,
  );
});

test("fixture mode is explicit and never enables authority actions", () => {
  const workspace = getFixtureWorkspace("run-004");

  assert.equal(workspace.dataSource.kind, "fixture");
  assert.equal(workspace.dataSource.state, "development_fixture");
  assert.equal(workspace.dataSource.statusLabel, "DEVELOPMENT FIXTURE");
  assert.equal(workspace.dataSource.authoritative, false);
  assert.match(workspace.dataSource.label, /Development fixture/);
  assert.equal(authorityActionsEnabled(workspace), false);
});

test("Run 003 fixture preserves media without inventing Session authority", () => {
  const workspace = getFixtureWorkspace("run-003");

  assert.equal(workspace.sessions.length, 0);
  assert.equal(workspace.stages[0].media.registered, 35);
  assert.equal(workspace.stages[0].media.unresolved, 35);
  assert.match(workspace.attention[0].safeContinuation, /did not invent Session authority/);
});

test("Kernel adapter keeps stabilizing quiet and maps unresolved media to Review", () => {
  const payload: KernelStatusPayload = {
    configured: true,
    configuration_supplied: true,
    configuration_valid: true,
    runtime_composed: true,
    runtime_profile: "demo-single-stage",
    event_id: "event-1",
    event_key: "event",
    event_name: "Kernel Event",
    database_available: true,
    ready: true,
    recovering: false,
    reconciliation_status: "completed",
    reconciliation_started_at: "2026-08-12T01:00:00Z",
    reconciliation_completed_at: "2026-08-12T01:00:01Z",
    attention_codes: [],
    stages: [
      {
        stage_id: "stage-1",
        key: "main",
        name: "Main Stage",
        source_available: true,
        session_id: null,
        assembling_sessions: [],
        recent_sessions: [],
        session_activity_state: null,
        session_package_state: null,
        session_package_revision: null,
        session_revision: null,
        session_authoritative_start: null,
        session_authoritative_end: null,
        last_media_arrived_at: "2026-08-12T01:01:00Z",
        discovered: 19,
        stabilizing: 1,
        ready: 0,
        registered: 18,
        associated: 17,
        unresolved: 1,
        conflicting: 0,
        attention_codes: ["media_association_unresolved"],
      },
    ],
    program_expectations: [
      {
        expectation_id: "expectation-1",
        stage_id: "stage-1",
        title: "Durable Event Workflows",
        speakers: ["Ada Producer", "Lin Operator"],
        planned_start: "2026-08-12T02:00:00Z",
        planned_end: "2026-08-12T02:45:00Z",
        revision: 1,
        recorded_at: "2026-08-12T01:00:00Z",
        provider: "devcon",
        external_event_id: "event-8",
        external_session_id: "session-12",
        external_room_id: "stage-1",
        evidence_kind: "external",
      },
    ],
  };

  const workspace = adaptKernelStatus(payload, "2026-08-12T01:02:00Z");

  assert.equal(workspace.dataSource.kind, "kernel");
  assert.equal(workspace.dataSource.state, "live_connected");
  assert.equal(workspace.dataSource.authoritative, true);
  assert.equal(workspace.stages[0].media.stabilizing, 1);
  assert.equal(workspace.attention.length, 1);
  assert.equal(workspace.attention[0].level, "review");
  assert.equal(workspace.stages[0].nextExpectation, "Durable Event Workflows");
  assert.deepEqual(workspace.stages[0].nextExpectationSpeakers, [
    "Ada Producer",
    "Lin Operator",
  ]);
  assert.equal(workspace.stages[0].nextExpectationProvider, "devcon");
  assert.equal(workspace.stages[0].nextExpectationPlannedStart, "2026-08-12T02:00:00Z");
  assert.equal(workspace.stages[0].nextExpectationPlannedEnd, "2026-08-12T02:45:00Z");
  assert.equal(workspace.transcriptState.state, "evidence_available");
  assert.match(workspace.transcriptState.detail, /not authoritative Session Transcript/);
  assert.equal(
    workspace.infrastructure.find((item) => item.id === "workers")?.state,
    "Configured · presence not projected",
  );
  assert.equal(
    workspace.infrastructure.find((item) => item.id === "devcon-read")?.state,
    "1 cached Program Expectations",
  );
  assert.equal(
    workspace.infrastructure.find((item) => item.id === "devcon-write")?.state,
    "Disabled",
  );
  assert.equal(authorityActionsEnabled(workspace), false);
});

test("an intentionally unconfigured backend is setup Information, not database Intervention", () => {
  const workspace = adaptKernelStatus(
    {
      configured: false,
      configuration_supplied: false,
      configuration_valid: null,
      runtime_composed: false,
      event_id: null,
      event_key: null,
      event_name: null,
      database_available: false,
      ready: false,
      recovering: false,
      reconciliation_status: null,
      reconciliation_started_at: null,
      reconciliation_completed_at: null,
      attention_codes: ["kernel_not_configured"],
      stages: [],
    },
    "2026-08-12T01:02:00Z",
  );

  assert.equal(workspace.attention[0].level, "information");
  assert.equal(workspace.attention[0].title, "Kernel not configured");
  assert.equal(workspace.dataSource.state, "live_unconfigured");
  assert.equal(workspace.dataSource.statusLabel, "LIVE — unconfigured");
  assert.equal(workspace.dataSource.authoritative, false);
  assert.equal(workspaceAttentionLevel(workspace), "information");
});

test("a failed Kernel request reports client connection loss without inventing database state", () => {
  const workspace = kernelUnavailableWorkspace(
    "2026-08-12T01:02:00Z",
    "Connection refused",
  );

  assert.equal(workspace.dataSource.authoritative, false);
  assert.equal(workspace.dataSource.state, "live_unavailable");
  assert.equal(workspace.dataSource.statusLabel, "LIVE — unavailable");
  assert.equal(workspace.attention[0].level, "intervention");
  assert.equal(workspace.attention[0].title, "Kernel connection unavailable");
  assert.equal(workspace.infrastructure[0].label, "Kernel status API");
  assert.equal(workspace.infrastructure[0].impact, "Connection refused");
  assert.equal(
    workspace.infrastructure.some((item) => item.label === "PostgreSQL"),
    false,
  );
});

test("MTE remains advisory drill-down evidence and does not enter Producer Attention", () => {
  const workspace = getFixtureWorkspace("run-004");
  const fixtureEvidence = workspace.mediaTimingEvidence[0];

  assert.equal(fixtureEvidence.qualificationStatus, "unqualified");
  assert.equal(fixtureEvidence.authorizedUse, "advisory_only");
  assert.match(fixtureEvidence.limitations.join(" "), /not authoritative/i);
  assert.equal(
    workspace.attention.some((item) => /timing evidence/i.test(item.title)),
    false,
  );

  const adapted = adaptKernelMediaTimingEvidence(
    {
      asset_id: "asset-1",
      active_revision: 1,
      evidence: [
        {
          evidence_id: "evidence-1",
          revision: 1,
          provider_id: "ffmpeg-probe",
          provider_version: "1.0",
          tool_id: "ffprobe",
          tool_version: "8.0",
          inspected_at: "2026-08-12T18:26:00Z",
          recorder_profile_id: "vmix-reference-profile",
          recorder_profile_revision: 1,
          qualification_status: "unqualified",
          qualification_limitations: ["Calibration has not passed."],
          observations: [
            {
              epistemic_kind: "observed",
              kind: "embedded_creation_time",
              precision: "microsecond",
              limitations: [],
            },
          ],
          derivations: [
            {
              derivation_id: "derivation-1",
              epistemic_kind: "derived",
              rule_id: "creation-time-plus-duration",
              rule_version: "1.0",
              candidate_started_at: "2026-08-12T18:24:01Z",
              candidate_ended_at: "2026-08-12T18:25:01.030Z",
              limitations: ["Advisory only."],
            },
          ],
          limitations: ["No Session authority."],
          authorized_use: "advisory_only",
        },
      ],
    },
    {
      asset_id: "asset-1",
      candidate_id: "candidate-1",
      proposed_asset_id: "asset-1",
      stage_id: "stage-1",
      source_binding_key: "main-recorder",
      registration_state: "registered",
      discovered_at: "2026-08-12T18:23:00Z",
      last_observed_at: "2026-08-12T18:26:00Z",
      association_status: "unresolved",
      association_authority: "deterministic",
      session_id: null,
      epistemic_kinds: ["observed", "derived"],
      media_started_at: null,
      media_ended_at: null,
      diagnostic_codes: ["association_unresolved"],
      association_reason_codes: ["multiple_eligible_sessions"],
      association_policy_id: "stageflow.kernel.media-association",
      association_policy_version: "1.1.0",
      association_input_references: [],
    },
    [
      {
        stage_id: "stage-1",
        key: "main",
        name: "Main Stage",
        source_available: true,
        session_id: null,
        assembling_sessions: [],
        recent_sessions: [],
        session_activity_state: null,
        session_package_state: null,
        session_package_revision: null,
        session_revision: null,
        session_authoritative_start: null,
        session_authoritative_end: null,
        last_media_arrived_at: null,
        discovered: 1,
        stabilizing: 0,
        ready: 0,
        registered: 1,
        associated: 0,
        unresolved: 1,
        conflicting: 0,
        attention_codes: [],
      },
    ],
  );

  assert.equal(adapted[0].stageKey, "main");
  assert.equal(adapted[0].qualificationStatus, "unqualified");
  assert.equal(adapted[0].authorizedUse, "advisory_only");
  assert.match(adapted[0].derivationIdentity ?? "", /derivation-1/);
  assert.equal(adapted[0].observations[0].kind, "embedded_creation_time");
});

test("Run 004 reads as association review with preserved media, not system failure", () => {
  const workspace = getFixtureWorkspace("run-004");
  const stage = workspace.stages[0];

  assert.equal(workspace.event.ready, true);
  assert.equal(stage.media.registered, 49);
  assert.equal(stage.media.associated, 32);
  assert.equal(stage.media.unresolved, 17);
  assert.equal(stage.media.conflicting, 0);
  assert.equal(workspace.attention[0].title, "Media association needs review");
  assert.doesNotMatch(
    `${workspace.attention[0].title} ${workspace.attention[0].impact}`,
    /system failure|media loss/i,
  );
  assert.ok(workspace.mediaAssets.every((item) => item.boundedProjection));
  assert.match(workspace.mediaAssets[0].explanation, /preserved/i);
  assert.equal(workspace.mediaTimingEvidence[0].assetId, workspace.mediaAssets[0].assetId);
  assert.equal(workspace.mediaTimingEvidence[0].authorizedUse, "advisory_only");
});

test("scale fixture covers seven Stages, long identities, no Session, and high Attention", () => {
  const workspace = getFixtureWorkspace("scale");

  assert.equal(workspace.stages.length, 7);
  assert.ok(workspace.stages.some((stage) => stage.name.length > 30));
  assert.ok(workspace.sessions.some((session) => session.title.length > 70));
  assert.ok(workspace.stages.some((stage) => !stage.currentSession));
  assert.ok(workspace.attention.length >= 3);
  assert.equal(workspaceAttentionLevel(workspace), "intervention");
});
