import assert from "node:assert/strict";
import test from "node:test";

import { demoLaunchContextHeader } from "./demo-launch-context.ts";
import { submitDemoProgramRefresh } from "./demo-program-refresh.ts";

const launchContext = "current-launch-context-0123456789abcdef";

test("manual Program refresh is a launch-protected local POST with no body", async () => {
  let request: { input: string; init?: RequestInit } | undefined;
  const result = await submitDemoProgramRefresh({
    launchContext,
    fetcher: (async (input: RequestInfo | URL, init?: RequestInit) => {
      request = { input: input.toString(), init };
      return Response.json({ provider: "devcon", observed: 4 });
    }) as typeof fetch,
  });

  assert.equal(result.status, "submitted");
  assert.equal(request?.input, "/api/stageflow/demo/program/refresh");
  assert.equal(request?.init?.method, "POST");
  assert.equal(request?.init?.body, undefined);
  assert.equal(
    new Headers(request?.init?.headers).get(demoLaunchContextHeader),
    launchContext,
  );
  assert.doesNotMatch(request?.input ?? "", /sessions\/sources|publish/i);
});

test("missing launch context fails closed before any refresh request", async () => {
  let requests = 0;
  const result = await submitDemoProgramRefresh({
    fetcher: (async () => {
      requests += 1;
      return Response.json({});
    }) as typeof fetch,
  });

  assert.deepEqual(result, {
    status: "not_submitted",
    reason: "launch_context_required",
  });
  assert.equal(requests, 0);
});
