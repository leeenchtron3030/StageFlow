import assert from "node:assert/strict";
import test from "node:test";

import type { UuidCryptoSource } from "../shared/ids/uuid-v4.ts";
import { demoLaunchContextHeader } from "./demo-launch-context.ts";
import { submitDemoStartSession } from "./demo-start-session.ts";

const actorId = "10000000-0000-4000-8000-000000000001";
const stageId = "20000000-0000-4000-8000-000000000001";
const expectationId = "30000000-0000-4000-8000-000000000001";
const launchContext = "current-launch-context-0123456789abcdef";
const authoritativeStart = "2026-08-19T18:30:00.000Z";

const cryptoSource: UuidCryptoSource = {
  randomUUID: () => "40000000-0000-4000-8000-000000000001",
  getRandomValues: (array) => array,
};

test("selected expectation confirms its title and submits its internal durable ID", async () => {
  const confirmations: string[] = [];
  let request: { init?: RequestInit; url: string } | undefined;
  const fetcher = (async (input: RequestInfo | URL, init?: RequestInit) => {
    request = { init, url: input.toString() };
    return Response.json({ session_id: "50000000-0000-4000-8000-000000000001" });
  }) as typeof fetch;

  const result = await submitDemoStartSession({
    actorId,
    stageId,
    launchContext,
    currentExpectationIds: [expectationId],
    selection: {
      kind: "expectation",
      expectationId,
      title: "A d/acc vision for decentralized AI",
    },
    authoritativeStart,
    confirm(message) {
      confirmations.push(message);
      return true;
    },
    fetcher,
    cryptoSource,
  });

  assert.equal(result.status, "submitted");
  assert.deepEqual(confirmations, [
    "Declare an authoritative Session start for “A d/acc vision for decentralized AI” now?",
  ]);
  assert.equal(request?.url, "/api/stageflow/demo/sessions/start");
  const headers = new Headers(request?.init?.headers);
  assert.equal(headers.get(demoLaunchContextHeader), launchContext);
  const body = JSON.parse(String(request?.init?.body)) as Record<string, unknown>;
  assert.equal(body.program_expectation_id, expectationId);
  assert.equal(body.stage_id, stageId);
  assert.equal(body.authoritative_start, authoritativeStart);
  assert.equal(body.operation_id, "40000000-0000-4000-8000-000000000001");
  assert.equal(Object.hasOwn(body, "external_session_id"), false);
});

test("no selection fails closed without confirmation or authority POST", async () => {
  let confirmations = 0;
  let posts = 0;
  const result = await submitDemoStartSession({
    actorId,
    stageId,
    launchContext,
    currentExpectationIds: [expectationId],
    authoritativeStart,
    confirm() {
      confirmations += 1;
      return true;
    },
    fetcher: (async () => {
      posts += 1;
      return Response.json({});
    }) as typeof fetch,
    cryptoSource,
  });

  assert.deepEqual(result, { status: "not_submitted", reason: "selection_required" });
  assert.equal(confirmations, 0);
  assert.equal(posts, 0);
});

test("explicit ad hoc choice confirms separately and omits expectation identity", async () => {
  const confirmations: string[] = [];
  let body: Record<string, unknown> | undefined;
  const result = await submitDemoStartSession({
    actorId,
    stageId,
    launchContext,
    currentExpectationIds: [expectationId],
    selection: { kind: "ad_hoc" },
    authoritativeStart,
    confirm(message) {
      confirmations.push(message);
      return true;
    },
    fetcher: (async (_input: RequestInfo | URL, init?: RequestInit) => {
      body = JSON.parse(String(init?.body)) as Record<string, unknown>;
      return Response.json({});
    }) as typeof fetch,
    cryptoSource,
  });

  assert.equal(result.status, "submitted");
  assert.deepEqual(confirmations, [
    "Declare an authoritative ad hoc / unscheduled Session start now?",
  ]);
  assert.equal(Object.hasOwn(body ?? {}, "program_expectation_id"), false);
});

test("missing authority prerequisites and declined confirmation never POST", async (t) => {
  for (const [name, values, reason] of [
    ["actor", { actorId: undefined, launchContext }, "actor_required"],
    ["launch context", { actorId, launchContext: undefined }, "launch_context_required"],
  ] as const) {
    await t.test(name, async () => {
      let posts = 0;
      const result = await submitDemoStartSession({
        ...values,
        stageId,
        currentExpectationIds: [expectationId],
        selection: { kind: "ad_hoc" },
        authoritativeStart,
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

  let posts = 0;
  const declined = await submitDemoStartSession({
    actorId,
    stageId,
    launchContext,
    currentExpectationIds: [expectationId],
    selection: { kind: "ad_hoc" },
    authoritativeStart,
    confirm: () => false,
    fetcher: (async () => {
      posts += 1;
      return Response.json({});
    }) as typeof fetch,
    cryptoSource,
  });
  assert.deepEqual(declined, {
    status: "not_submitted",
    reason: "confirmation_declined",
  });
  assert.equal(posts, 0);
});
