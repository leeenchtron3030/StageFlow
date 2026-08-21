import assert from "node:assert/strict";
import test from "node:test";

import type { UuidCryptoSource } from "../shared/ids/uuid-v4.ts";
import { demoLaunchContextHeader } from "./demo-launch-context.ts";
import {
  packageApprovalConfirmation,
  submitDemoPackageApproval,
  type DemoPackageApprovalSummary,
} from "./demo-package-approval.ts";

const actorId = "61000000-0000-4000-8000-000000000001";
const sessionId = "62000000-0000-4000-8000-000000000001";
const operationId = "63000000-0000-4000-8000-000000000001";
const launchContext = "current-launch-context-0123456789abcdef";
const summary: DemoPackageApprovalSummary = {
  sessionTitle: "A d/acc vision for decentralized AI",
  packageRevision: 1,
  mediaAssociated: 1,
  mediaUnresolved: 2,
  mediaConflicting: 3,
  transcriptionSucceeded: 4,
  transcriptionFailed: 5,
  transcriptEvidenceCount: 6,
  declaredMomentCount: 7,
};
const cryptoSource: UuidCryptoSource = {
  randomUUID: () => operationId,
  getRandomValues: (array) => array,
};

test("approval confirmation summarizes the exact package decision", () => {
  const confirmation = packageApprovalConfirmation(summary);

  assert.match(
    confirmation,
    /^Approve package revision 1\? This records an attributable human acceptance/,
  );
  for (const expected of [
    "Session: A d/acc vision for decentralized AI",
    "Media: associated 1, unresolved 2, conflicting 3",
    "Transcription: succeeded 4, failed 5",
    "Transcript Evidence: 6",
    "Declared Moments: 7",
  ]) {
    assert.ok(confirmation.includes(expected));
  }
});

test("confirmed ready-for-review approval submits exact revision through Demo proxy only", async () => {
  const confirmations: string[] = [];
  let request: { init?: RequestInit; url: string } | undefined;
  const result = await submitDemoPackageApproval({
    actorId,
    launchContext,
    sessionId,
    activityState: "presentation_ended",
    packageState: "ready_for_review",
    summary,
    confirm(message) {
      confirmations.push(message);
      return true;
    },
    fetcher: (async (input: RequestInfo | URL, init?: RequestInit) => {
      request = { init, url: input.toString() };
      return Response.json({ package_state: "complete" });
    }) as typeof fetch,
    cryptoSource,
  });

  assert.equal(result.status, "submitted");
  assert.deepEqual(confirmations, [packageApprovalConfirmation(summary)]);
  assert.equal(request?.url, "/api/stageflow/demo/sessions/approve-package");
  assert.equal(request?.init?.method, "POST");
  assert.doesNotMatch(request?.url ?? "", /devcon/i);
  const headers = new Headers(request?.init?.headers);
  assert.equal(headers.get(demoLaunchContextHeader), launchContext);
  const body = JSON.parse(String(request?.init?.body)) as Record<string, unknown>;
  assert.equal(body.session_id, sessionId);
  assert.equal(body.package_revision, 1);
  assert.equal(body.operation_id, operationId);
  assert.equal(body.actor_id, actorId);
  assert.equal(body.confirmed, "confirmed");
});

test("declined confirmation sends no authority POST", async () => {
  let posts = 0;
  const result = await submitDemoPackageApproval({
    actorId,
    launchContext,
    sessionId,
    activityState: "presentation_ended",
    packageState: "ready_for_review",
    summary,
    confirm: () => false,
    fetcher: (async () => {
      posts += 1;
      return Response.json({});
    }) as typeof fetch,
    cryptoSource,
  });

  assert.deepEqual(result, {
    status: "not_submitted",
    reason: "confirmation_declined",
  });
  assert.equal(posts, 0);
});

test("missing authority prerequisites and non-reviewable state send no POST", async (t) => {
  for (const [name, values, reason] of [
    [
      "actor",
      { actorId: undefined, launchContext, activityState: "presentation_ended", packageState: "ready_for_review" },
      "actor_required",
    ],
    [
      "launch context",
      { actorId, launchContext: undefined, activityState: "presentation_ended", packageState: "ready_for_review" },
      "launch_context_required",
    ],
    [
      "active presentation",
      { actorId, launchContext, activityState: "presentation_active", packageState: "ready_for_review" },
      "authority_state_required",
    ],
    [
      "assembling package",
      { actorId, launchContext, activityState: "presentation_ended", packageState: "assembling" },
      "authority_state_required",
    ],
  ] as const) {
    await t.test(name, async () => {
      let posts = 0;
      const result = await submitDemoPackageApproval({
        ...values,
        sessionId,
        summary,
        confirm: () => true,
        fetcher: (async () => {
          posts += 1;
          return Response.json({});
        }) as typeof fetch,
        cryptoSource,
      });
      assert.deepEqual(result, { status: "not_submitted", reason });
      assert.equal(posts, 0);
    });
  }
});
