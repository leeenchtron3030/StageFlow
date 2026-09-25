import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { runInNewContext } from "node:vm";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

import { programProviderDisplayName } from "./program-provider.ts";

const require = createRequire(import.meta.url);
const components = new URL("../components/", import.meta.url);

test("operator-facing components and routes contain no hardcoded provider or event identity", () => {
  // The sole display-name mapping lives in experience/program-provider.ts, outside
  // these operator-facing trees. Cover nested components and route content too.
  for (const root of [components, new URL("../../app/", import.meta.url)]) {
    const directory = fileURLToPath(root);
    for (const entry of readdirSync(directory, { recursive: true, withFileTypes: true })) {
      if (!entry.isFile() || !/\.tsx?$/.test(entry.name)) continue;
      const path = `${entry.parentPath}/${entry.name}`;
      assert.doesNotMatch(
        readFileSync(path, "utf8"),
        /devcon|razer|wenceslas|stageflow demo 1|local_file|local schedule/i,
        `${path} must derive provider/event labels from data`,
      );
    }
  }
  assert.doesNotMatch(readFileSync(new URL("./kernel-adapter.ts", import.meta.url), "utf8"), /devcon|razer|stageflow demo 1/i);
});

test("provider display names preserve unknown identifiers without inventing attribution", () => {
  assert.equal(programProviderDisplayName("local_file"), "Local schedule");
  assert.equal(programProviderDisplayName("devcon"), "Devcon");
  assert.equal(programProviderDisplayName("example_provider"), "example_provider");
  assert.equal(programProviderDisplayName("constructor"), "constructor");
  assert.equal(programProviderDisplayName(undefined), "Provider unknown");
});

// Use the installed TypeScript compiler for TSX and stub only the browser router
// and hook state. Render the real components to verify operator-visible copy.
function renderComponent(name: string, props: Record<string, unknown>, states?: unknown[]) {
  const source = readFileSync(new URL(`${name}.tsx`, components), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
  });
  const exports: Record<string, React.ComponentType<Record<string, unknown>>> = {};
  let stateIndex = 0;
  runInNewContext(compiled.outputText, {
    exports,
    require: (id: string) => {
      if (id === "next/navigation") return { useRouter: () => ({ refresh() {} }) };
      if (id === "react" && states) return { ...React, useState: () => [states[stateIndex++], () => {}] };
      if (id === "@/experience/program-provider.ts") return { programProviderDisplayName };
      if (id.startsWith("@/experience/demo-")) return {};
      return require(id);
    },
  });
  return renderToStaticMarkup(React.createElement(Object.values(exports)[0], props));
}

for (const provider of ["local_file", "example_provider"]) {
  test(`program controls render data-attributed labels for ${provider}`, () => {
    const label = programProviderDisplayName(provider);
    const expectation = {
      id: "example-expectation", title: "Example talk", provider,
      speakers: [], revision: 2, externalSessionId: "example-session",
    };
    const props = {
      enabled: true, currentExpectations: [], withdrawnExpectations: [expectation],
      synchronization: { provider },
    };
    const refresh = renderComponent("demo-program-refresh-control", props);
    assert.match(refresh, new RegExp(`<dd>${label}</dd>`));
    assert.match(refresh, /External session · example-session/);
    const result = renderComponent("demo-program-refresh-control", props, [false, {
      provider, observed: 1, added: 1, changed: 0, withdrawn: 0, restored: 0,
      unchanged: 0, changes: [],
    }, undefined]);
    assert.ok(result.includes(`Program refreshed · ${label} · just now`));
    const start = renderComponent("demo-start-session-control", {
      enabled: true, stageId: "example-stage", hasCurrentSession: false,
      programExpectations: [expectation],
    });
    assert.ok(start.includes(`External · ${label}`));
    assert.match(start, /External session · example-session/);
  });
}
