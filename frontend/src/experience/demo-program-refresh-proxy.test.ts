import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { NextRequest } from "next/server.js";

import { POST } from "../../app/api/stageflow/demo/[...path]/route.ts";
import { demoProtectedHeaders } from "./demo-launch-context.ts";

const originalFetch = globalThis.fetch;
const originalBackend = process.env.STAGEFLOW_DEMO_API_BASE_URL;
const originalLaunchContext = process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT;
const originalConsoleInfo = console.info;
const launchContext = "current-launch-context-0123456789abcdef";

function context() {
  return { params: Promise.resolve({ path: ["program", "refresh"] }) };
}

afterEach(() => {
  globalThis.fetch = originalFetch;
  console.info = originalConsoleInfo;
  if (originalBackend === undefined) delete process.env.STAGEFLOW_DEMO_API_BASE_URL;
  else process.env.STAGEFLOW_DEMO_API_BASE_URL = originalBackend;
  if (originalLaunchContext === undefined) delete process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT;
  else process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT = originalLaunchContext;
});

test("current launch can refresh Program through the loopback proxy without a Devcon write", async () => {
  process.env.STAGEFLOW_DEMO_API_BASE_URL = "http://127.0.0.1:8123/api/v1/demo";
  process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT = launchContext;
  const logs: string[] = [];
  let upstream: { method?: string; body?: BodyInit | null; url: string } | undefined;
  console.info = (message?: unknown) => logs.push(String(message));
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    upstream = { method: init?.method, body: init?.body, url: input.toString() };
    return Response.json({ provider: "devcon", observed: 4, withdrawn: 1 });
  }) as typeof fetch;

  const response = await POST(
    new NextRequest("http://stageflow.demo/api/stageflow/demo/program/refresh", {
      method: "POST",
      headers: {
        ...demoProtectedHeaders(launchContext),
        origin: "http://stageflow.demo",
        "sec-fetch-site": "same-origin",
      },
    }),
    context(),
  );

  assert.equal(response.status, 200);
  assert.equal(upstream?.url, "http://127.0.0.1:8123/api/v1/demo/program/refresh");
  assert.equal(upstream?.method, "POST");
  assert.equal(upstream?.body, "");
  assert.doesNotMatch(upstream?.url ?? "", /sessions\/sources|publish/i);
  assert.equal(logs.length, 1);
  assert.match(logs[0], /^stageflow_demo_program_refresh_request=/);
  assert.doesNotMatch(logs[0], new RegExp(launchContext));
});

test("stale or absent launch context cannot reach the refresh backend", async (t) => {
  process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT = launchContext;
  console.info = () => undefined;
  for (const presented of ["prior-launch-context-0123456789abcdef", undefined]) {
    await t.test(presented ? "stale" : "absent", async () => {
      let forwarded = false;
      globalThis.fetch = (async () => {
        forwarded = true;
        return Response.json({});
      }) as typeof fetch;
      const headers: Record<string, string> = {
        origin: "http://stageflow.demo",
        "sec-fetch-site": "same-origin",
      };
      if (presented) Object.assign(headers, demoProtectedHeaders(presented));
      const response = await POST(
        new NextRequest("http://stageflow.demo/api/stageflow/demo/program/refresh", {
          method: "POST",
          headers,
        }),
        context(),
      );
      assert.equal(response.status, 403);
      assert.equal(forwarded, false);
    });
  }
});
