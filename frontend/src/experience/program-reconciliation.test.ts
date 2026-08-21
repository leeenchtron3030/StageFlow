import assert from "node:assert/strict";
import test from "node:test";

import { adaptKernelStatus, type KernelStatusPayload } from "./kernel-adapter.ts";
import { submitDemoStartSession } from "./demo-start-session.ts";

const expectationId = "30000000-0000-4000-8000-000000000001";

test("stale withdrawn selection fails closed before confirmation or Session POST", async () => {
  let confirmations = 0;
  let posts = 0;
  const result = await submitDemoStartSession({
    actorId: "10000000-0000-4000-8000-000000000001",
    stageId: "20000000-0000-4000-8000-000000000001",
    launchContext: "current-launch-context-0123456789abcdef",
    selection: {
      kind: "expectation",
      expectationId,
      title: "Withdrawn upstream",
    },
    currentExpectationIds: [],
    authoritativeStart: "2026-08-19T18:30:00.000Z",
    confirm: () => {
      confirmations += 1;
      return true;
    },
    fetcher: (async () => {
      posts += 1;
      return Response.json({});
    }) as typeof fetch,
  });

  assert.deepEqual(result, { status: "not_submitted", reason: "selection_stale" });
  assert.equal(confirmations, 0);
  assert.equal(posts, 0);
});

function expectation(
  number: number,
  plannedStart: string,
  lifecycleState: "current" | "withdrawn" = "current",
) {
  return {
    expectation_id: `30000000-0000-4000-8000-${number.toString().padStart(12, "0")}`,
    stage_id: "20000000-0000-4000-8000-000000000001",
    title: `Program ${number}`,
    speakers: [`Speaker ${number}`],
    planned_start: plannedStart,
    planned_end: "2026-08-19T20:30:00Z",
    revision: lifecycleState === "current" ? 2 : 3,
    recorded_at: "2026-08-19T18:00:00Z",
    provider: "devcon",
    external_event_id: "test-devcon-8",
    external_session_id: `devcon-session-${number}`,
    external_room_id: "stage-1",
    lifecycle_state: lifecycleState,
    synchronization_scope: "devcon:test-devcon-8:stage-1",
    last_observed_at: "2026-08-19T18:00:00Z",
    lifecycle_changed_at: "2026-08-19T18:00:00Z",
    evidence_kind: "external" as const,
  };
}

test("adapter renders four sorted Current items and keeps Withdrawn history separate", () => {
  const payload: KernelStatusPayload = {
    configured: true,
    configuration_supplied: true,
    configuration_valid: true,
    runtime_composed: true,
    runtime_profile: "demo-single-stage",
    event_id: "10000000-0000-4000-8000-000000000001",
    event_key: "program-reconciliation",
    event_name: "Program Reconciliation",
    database_available: true,
    ready: true,
    recovering: false,
    reconciliation_status: "complete",
    reconciliation_started_at: "2026-08-19T18:00:00Z",
    reconciliation_completed_at: "2026-08-19T18:00:00Z",
    stages: [
      {
        stage_id: "20000000-0000-4000-8000-000000000001",
        key: "main",
        name: "Main",
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
        discovered: 0,
        stabilizing: 0,
        ready: 0,
        registered: 0,
        associated: 0,
        unresolved: 0,
        conflicting: 0,
        attention_codes: [],
      },
    ],
    program_expectations: [
      expectation(1, "2026-08-19T20:00:00Z"),
      expectation(2, "2026-08-19T19:00:00Z"),
      expectation(3, "2026-08-19T22:00:00Z"),
      expectation(4, "2026-08-19T21:00:00Z"),
      expectation(5, "2026-08-19T18:30:00Z", "withdrawn"),
    ],
    program_synchronization: {
      provider: "devcon",
      synchronized_at: "2026-08-19T18:00:00Z",
      observed: 4,
      added: 0,
      changed: 1,
      unchanged: 3,
      withdrawn: 1,
      restored: 0,
      current_expectation_count: 4,
      changes: [
        {
          kind: "withdrawn",
          expectation_id: "30000000-0000-4000-8000-000000000005",
          expectation_key: "devcon:test-devcon-8:devcon-session-5",
          title: "Program 5",
          external_session_id: "devcon-session-5",
          fields: [],
        },
      ],
      changes_truncated: false,
    },
    automation: {
      enabled: true,
      state: "running",
      owner: true,
      media_reconciliation_interval_seconds: 5,
      program_refresh_interval_seconds: 120,
      media_cycle_count: 8,
      media_last_attempt_at: "2026-08-19T18:00:55Z",
      media_last_success_at: "2026-08-19T18:00:55Z",
      media_last_failure_code: null,
      media_candidates_seen: 2,
      media_assets_registered: 1,
      transcription_operations_enqueued: 1,
      transcription_enqueue_failures: 0,
      program_refresh_count: 3,
      program_last_attempt_at: "2026-08-19T18:00:00Z",
      program_last_success_at: "2026-08-19T18:00:00Z",
      program_last_failure_code: null,
    },
    attention_codes: [],
  };

  const workspace = adaptKernelStatus(payload, "2026-08-19T18:01:00Z");

  assert.deepEqual(
    workspace.stages[0].programExpectations.map((item) => item.title),
    ["Program 2", "Program 1", "Program 4", "Program 3"],
  );
  assert.deepEqual(
    workspace.stages[0].withdrawnProgramExpectations.map((item) => item.title),
    ["Program 5"],
  );
  assert.equal(workspace.stages[0].nextExpectation, "Program 2");
  assert.equal(workspace.programSynchronization?.withdrawn, 1);
  assert.equal(workspace.programSynchronization?.currentExpectationCount, 4);
  assert.deepEqual(workspace.automation, {
    enabled: true,
    state: "running",
    owner: true,
    mediaReconciliationIntervalSeconds: 5,
    programRefreshIntervalSeconds: 120,
    mediaCycleCount: 8,
    mediaLastAttemptAt: "2026-08-19T18:00:55Z",
    mediaLastSuccessAt: "2026-08-19T18:00:55Z",
    mediaLastFailureCode: undefined,
    mediaCandidatesSeen: 2,
    mediaAssetsRegistered: 1,
    transcriptionOperationsEnqueued: 1,
    transcriptionEnqueueFailures: 0,
    programRefreshCount: 3,
    programLastAttemptAt: "2026-08-19T18:00:00Z",
    programLastSuccessAt: "2026-08-19T18:00:00Z",
    programLastFailureCode: undefined,
  });
});
