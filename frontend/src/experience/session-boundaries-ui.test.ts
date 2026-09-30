import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { boundaryLabels as labels } from "./ui-labels.ts";
import type { BoundaryProposal } from "./session-boundaries-api.ts";
import { getFixtureWorkspace } from "./fixtures.ts";
import { eventId, stageId, suggestionId as id, suggestionFixture as suggestion, suggestionDataFixture as data, titlesFixture as titles } from "./session-suggestions-fixtures.ts";
import { sessionId, startProposal as start, endProposal as end, currentStart, currentEnd, boundaryDecision, boundaryKernelFixture, boundaryHistoryDecision, realizedSessionFixture } from "./session-boundaries-fixtures.ts";
import { adaptKernelStatus } from "./kernel-adapter.ts";

type Props = Record<string, unknown>;
type Node = React.ReactElement<Props>;
const require = createRequire(import.meta.url);
function compile(path: string, imports: Record<string, unknown> = {}, env: Record<string, string> = {}) {
  const source = readFileSync(new URL(path, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS } });
  const exports: Record<string, (props: never) => Node> = {};
  runInNewContext(compiled.outputText, { exports, process: { env }, require: (name: string) => imports[name] ?? require(name) });
  return exports;
}
const nodes = (value: unknown): Node[] => Array.isArray(value) ? value.flatMap(nodes) : React.isValidElement<Props>(value) ? [value, ...nodes(value.props.children), ...nodes(value.props.decisionForm)] : [];
function harness(proposals: BoundaryProposal[] | undefined = [start], authorized = true, launchContext = "synthetic", history = false) {
  const slots: unknown[] = []; let cursor = 0, refreshes = 0, refreshPending = false;
  const exports = compile("../components/session-boundaries.tsx", {
    react: {
      useState(value: unknown) { const i = cursor++; if (!(i in slots)) slots[i] = value; return [slots[i], (next: unknown) => { slots[i] = next; }]; },
      useRef(value: unknown) { const i = cursor++; return slots[i] ??= { current: value }; },
      useSyncExternalStore() { return "UTC"; },
      useTransition() { return [refreshPending, (work: () => void) => { refreshPending = true; work(); }]; },
    },
    "next/navigation": { useRouter: () => ({ refresh() { refreshes++; } }) },
  });
  const render = () => { cursor = 0; return exports[history ? "BoundaryDecisionHistory" : "SessionBoundaries"]({ eventId, sessionId, proposals: history ? undefined : proposals, currentStart, currentEnd, authorized, launchContext } as never); };
  const find = (predicate: (n: Node) => boolean) => { const n = nodes(render()).find(predicate); assert.ok(n); return n; };
  const button = (label: string) => find((n) => n.type === "button" && n.props.children === label);
  const click = (label: string) => { const n = button(label); assert.ok(!n.props.disabled, `${label} disabled`); return (n.props.onClick as () => void)(); };
  const submit = () => (find((n) => n.type === "form").props.onSubmit as (e: unknown) => void)({ preventDefault() {} });
  const change = (value: string) => (find((n) => n.type === "select").props.onChange as (e: unknown) => void)({ target: { value } });
  return { render, find, button, click, submit, change, html: () => renderToStaticMarkup(render()), refreshes: () => refreshes, finishRefresh: () => { refreshPending = false; }, setProposals: (value?: BoundaryProposal[]) => { proposals = value; } };
}
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

test("none renders nothing; one and both edges summarize before times, actions and collapsed evidence", () => {
  assert.equal(harness([]).html(), "");
  for (const proposals of [[start], [end], [start, end]]) {
    const html = harness(proposals).html(), visible = html.replace(/<details\b[\s\S]*?<\/details>/g, "");
    assert.equal((html.match(/class="suggestion-row"/g) ?? []).length, proposals.length);
    if (proposals.includes(start)) { assert.match(visible, /Start could be 1 min 20 s later — at a still-image changeover/); assert.match(visible, /10:00:00 → 10:01:20/); }
    if (proposals.includes(end)) { assert.match(visible, /End could be 45 s earlier — at a recording gap/); assert.match(visible, /11:00:00 → 10:59:15/); }
    assert.doesNotMatch(visible, /Sep 29|\+1 min 20 s|−45 s|Current \d|Suggested \d/);
    assert.ok(html.indexOf("could be") < html.indexOf('aria-label="current'));
    assert.doesNotMatch(html, /<details[^>]*\bopen\b/);
    for (const internal of [start.proposal_id, start.proposer_id, start.evidence_ids[0], start.policy_id, "advisory_only"]) assert.ok(!visible.includes(internal));
    assert.match(html, /Recorder start and length are unverified/);
  }
});

test("apply opens a consequence confirmation; cancel sends nothing; confirm sends once and locks until refresh", async () => {
  const original = globalThis.fetch; const bodies: string[] = [];
  globalThis.fetch = async (url, init) => { assert.match(String(url), /\/apply$/); bodies.push(String(init?.body)); return Response.json(boundaryDecision(JSON.parse(String(init?.body)))); };
  try {
    const h = harness(); h.click(labels.apply); assert.equal(bodies.length, 0);
    assert.match(h.html(), /Change the Session&#x27;s start\?/);
    const confirmation = renderToStaticMarkup(h.find((n) => n.type === "form"));
    assert.match(confirmation, /aria-label="current 10:00:00, suggested 10:01:20">10:00:00 → 10:01:20/);
    assert.doesNotMatch(confirmation, /Sep 29|Current|Suggested|\+1 min/);
    h.click(labels.cancel); assert.equal(bodies.length, 0); assert.ok(!nodes(h.render()).some((n) => n.type === "form"));
    h.click(labels.apply); h.submit(); h.submit(); await tick();
    assert.equal(bodies.length, 1); assert.deepEqual(Object.keys(JSON.parse(bodies[0])).sort(), ["authority_kind", "command_id"]);
    assert.equal(h.refreshes(), 1); assert.equal(h.button(labels.apply).props.disabled, true);
    h.setProposals([]); assert.equal(h.html(), "");
  } finally { globalThis.fetch = original; }
});

test("dismiss confirms unchanged time, uses optional bounded picker and omits an unselected reason", async () => {
  const original = globalThis.fetch; const bodies: Record<string, unknown>[] = [];
  globalThis.fetch = async (url, init) => { assert.match(String(url), /\/dismiss$/); const body = JSON.parse(String(init?.body)); bodies.push(body); return Response.json(boundaryDecision(body, true)); };
  try {
    for (const reason of ["", labels.dismissReasons[0]]) {
      const h = harness(); h.click(labels.dismiss); assert.equal(bodies.length, reason ? 1 : 0);
      assert.match(h.html(), /time will stay unchanged/);
      assert.deepEqual(nodes(h.render()).filter((n) => n.type === "option").map((n) => n.props.children), ["No reason", ...labels.dismissReasons]);
      h.change(reason); h.submit(); await tick(); assert.equal(bodies.at(-1)?.reason, reason || undefined);
      assert.equal(h.refreshes(), 1); h.setProposals([]); assert.equal(h.html(), "");
    }
  } finally { globalThis.fetch = original; }
});

test("deterministic refusals offer only Refresh and unlock other actions only after refresh completes", async () => {
  const original = globalThis.fetch;
  try {
    for (const kind of ["apply", "dismiss"] as const) for (const [status, detail, message] of [[409, "boundary_proposal_stale", labels.stale], [409, "boundary_proposal_decided", labels.decided], [409, "other", labels.conflict], [422, "", labels.invalid], [404, "", labels.missing], [413, "", labels.invalid], [401, "", labels.readOnly], [403, "", labels.readOnly]] as const) {
      const bodies: string[] = [];
      globalThis.fetch = async (_url, init) => { bodies.push(String(init?.body)); return bodies.length === 1 ? Response.json({ detail }, { status }) : Response.json(boundaryDecision(JSON.parse(String(init?.body)), kind === "dismiss")); };
      const h = harness(); h.click(labels[kind]); h.submit(); await tick();
      assert.equal(bodies.length, 1); assert.ok(h.html().includes(message));
      assert.doesNotMatch(h.html(), /Retry same command|<form/);
      assert.equal(h.button(labels.apply).props.disabled, true); assert.equal(h.button(labels.dismiss).props.disabled, true);
      assert.equal(h.button(labels.refresh).props.disabled, false);
      h.click(labels.refresh); assert.equal(h.refreshes(), 1); assert.equal(bodies.length, 1);
      assert.equal(h.button(labels.apply).props.disabled, true); assert.equal(h.button(labels.dismiss).props.disabled, true);
      h.finishRefresh(); // Same data/key: refresh must still unlock a refused command.
      assert.equal(h.button(labels.apply).props.disabled, false); assert.equal(h.button(labels.dismiss).props.disabled, false);
      h.click(kind === "apply" ? labels.dismiss : labels.apply);
      assert.ok(nodes(h.render()).some((n) => n.type === "form"));
    }
  } finally { globalThis.fetch = original; }
});

test("transport, 5xx and unknown outcomes keep byte-identical retries and lock other actions", async () => {
  const original = globalThis.fetch;
  try {
    for (const kind of ["apply", "dismiss"] as const) for (const failure of ["transport", "malformed", "mismatch", 500, 503, 408] as const) {
      const bodies: string[] = [];
      globalThis.fetch = async (_url, init) => {
        bodies.push(String(init?.body));
        if (bodies.length === 1) {
          if (failure === "transport") throw new Error("offline");
          if (failure === "malformed") return new Response("broken");
          if (failure === "mismatch") return Response.json(boundaryDecision({ command_id: id(99) }, kind === "dismiss"));
          return Response.json({}, { status: failure });
        }
        return Response.json(boundaryDecision(JSON.parse(String(init?.body)), kind === "dismiss"));
      };
      const h = harness(); h.click(labels[kind]); h.submit(); await tick();
      assert.equal(h.button(labels.refresh).props.disabled, true);
      assert.equal(h.button(labels.apply).props.disabled, true); assert.equal(h.button(labels.dismiss).props.disabled, true);
      h.click(labels.retry); await tick(); assert.equal(bodies.length, 2); assert.equal(bodies[0], bodies[1]); assert.equal(h.refreshes(), 1);
    }
  } finally { globalThis.fetch = original; }
});

test("missing producer authority keeps suggestions readable and disables mutations; unavailable differs from none", () => {
  for (const h of [harness([start], false), harness([start], true, "")]) {
    assert.equal(h.button(labels.apply).props.disabled, true); assert.equal(h.button(labels.dismiss).props.disabled, true);
    assert.match(h.html(), /authorized producer connection/); assert.match(h.html(), /still-image changeover/);
  }
  const h = harness(); h.setProposals(undefined); assert.match(h.html(), /Boundary suggestions are unavailable/);
  h.click(labels.refresh); assert.equal(h.refreshes(), 1);
});

test("history labels both edges without Kernel proposals, pages on demand and retries failed reads", async () => {
  const original = globalThis.fetch; let calls = 0;
  globalThis.fetch = async (url) => {
    calls++;
    if (calls === 1) return Response.json({}, { status: 503 });
    assert.match(String(url), /boundary-proposals\/history\?limit=50/);
    if (calls === 3) assert.match(String(url), new RegExp(`&after=${id(50)}$`));
    return Response.json({ items: [boundaryHistoryDecision({ command_id: id(calls === 2 ? 50 : 51), ...(calls === 3 ? { reason: "Not enough evidence" } : {}) }, calls === 3 ? end : start, calls === 3)], limit: 50, next_after: calls === 2 ? id(50) : null });
  };
  try {
    const h = harness([], true, "synthetic", true); assert.equal(calls, 0);
    const load = h.button(labels.loadHistory).props.onClick as () => void;
    load(); load(); await tick(); assert.equal(calls, 1); assert.match(h.html(), /history is unavailable/);
    h.click(labels.loadHistory); await tick(); assert.match(h.html(), /Start applied · 14:05 · by producer/);
    h.click(labels.moreHistory); await tick(); assert.match(h.html(), /End dismissed · 14:05 · Not enough evidence/);
    const visible = h.html().replace(/<details\b[\s\S]*?<\/details>/g, "");
    for (const internal of [id(4), id(50), id(51), start.proposal_id, end.proposal_id]) {
      assert.ok(h.html().includes(internal)); assert.ok(!visible.includes(internal));
    }
    assert.doesNotMatch(h.html(), /<pre>|<details[^>]*\bopen\b/);
    assert.doesNotMatch(h.html(), /Load more decisions/);
  } finally { globalThis.fetch = original; }
});

test("Already Sessions is collapsed, links current times, and owns badges; Decided rows never do", () => {
  const { StageSuggestions } = compile("../components/stage-suggestions.tsx", { "next/navigation": { useRouter: () => ({ refresh() {} }) } });
  const decided = { ...suggestion, status: "confirmed", suggestion_id: id(60) };
  const html = renderToStaticMarkup(React.createElement(StageSuggestions as React.ComponentType<Props>, { eventId, stageId, data: { ...data, suggestions: [suggestion, decided, { ...decided, suggestion_id: id(61), status: "rejected" }] }, titles, hasPlannedTalks: true, authorized: false, realizedSessions: [realizedSessionFixture], boundaryBadges: { sessions: { [sessionId]: 1 }, incomplete: true } }));
  assert.equal((html.match(/>Boundary suggestion<\/span>/g) ?? []).length, 1);
  assert.ok(html.includes(`href="/sessions/${sessionId}#suggested-boundaries"`));
  assert.match(html, /Some boundary suggestions could not be checked/);
  assert.match(html, / · 1 boundary suggestion<\/strong>/);
  const realized = html.slice(html.indexOf("Already Sessions · 1"), html.indexOf("Decided ·"));
  assert.match(realized, /Talk 1/); assert.match(realized, /10:00–11:00/); assert.doesNotMatch(realized, /2026|10:00:00/); // owner polish: same format as suggestion rows
  assert.equal((realized.match(/Sep 29/g) ?? []).length, 1);
  assert.doesNotMatch(html, /<details[^>]*\bopen\b/);
  assert.doesNotMatch(html.slice(html.indexOf("Decided ·")), /Boundary suggestion/);
});

test("Session view places suggestions with timing before Outputs/evidence and history inside collapsed Details", () => {
  const imports: Record<string, unknown> = {
    "next/link": ({ children, ...props }: Props) => React.createElement("a", props, children as React.ReactNode),
    "@/experience/presentation.ts": require("./presentation.ts"), "@/experience/program-provider.ts": require("./program-provider.ts"),
    "./session-timing-evidence": { SessionTimingEvidence: () => React.createElement("section", { id: "long-timing-evidence" }) },
    "./demo-session-workspace": { DemoSessionWorkspace: () => null }, "./demo-program-refresh-control": { DemoProgramRefreshControl: () => null },
    "./demo-start-session-control": { DemoStartSessionControl: () => null }, "./mission-control": { WorkspaceTitle: () => null, AttentionPanel: () => null },
  };
  const { SessionOperationalView } = compile("../components/operational-views.tsx", imports);
  const workspace = getFixtureWorkspace("turnover");
  const html = renderToStaticMarkup(SessionOperationalView({ workspace, session: workspace.sessions[0], boundaries: React.createElement("section", { id: "suggested-boundaries" }), outputs: React.createElement("section", { id: "outputs" }), boundaryHistory: React.createElement("div", null, "Boundary decision history") } as never));
  assert.ok(html.indexOf("Session start") < html.indexOf('id="suggested-boundaries"'));
  assert.ok(html.indexOf('id="suggested-boundaries"') < html.indexOf('id="outputs"'));
  assert.ok(html.indexOf('id="suggested-boundaries"') < html.indexOf('id="long-timing-evidence"'));
  assert.match(html, /<details><summary>Details<\/summary>(?:(?!<\/details>)[\s\S])*Boundary decision history/);
});

test("Session page scopes reads, gates authority, preserves unchanged retry keys, refreshes changed keys and handles outage", async () => {
  const workspace = getFixtureWorkspace("turnover");
  workspace.event.id = eventId; workspace.sessions[0] = { ...workspace.sessions[0], id: sessionId, authoritativeStart: currentStart, authoritativeEnd: currentEnd };
  workspace.dataSource = { ...workspace.dataSource, kind: "kernel", state: "live_connected", authoritative: true };
  let proposals = [start], fail = false, calls = 0, disposed = 0, outputCalls = 0;
  let heldRead: Promise<void> | undefined;
  const env = { STAGEFLOW_DEMO_OPERATOR_ID: id(4), STAGEFLOW_DEMO_LAUNCH_CONTEXT: "synthetic" };
  const imports = {
    "@/components/operational-shell": { OperationalShell: "shell" }, "@/components/operational-views": { SessionOperationalView: "view" },
    "@/components/session-outputs-panel": { SessionOutputsPanel: "outputs" }, "@/components/session-output-actions": { SessionOutputActions: "actions" },
    "@/components/session-boundaries": { SessionBoundaries: "boundaries", BoundaryDecisionHistory: "history" },
    "@/experience/session-outputs.server.ts": { loadSessionOutputs: async () => { outputCalls++; return undefined; } },
    "@/experience/data-source.ts": { loadWorkspace: async () => workspace },
    "@/experience/session-boundaries-api.ts": require("./session-boundaries-api.ts"),
    "@/experience/capability-proxy.server.ts": { readCapability: async (capability: string, path: string) => { calls++; assert.equal(capability, "session-suggestions"); assert.equal(path, `events/${eventId}/sessions/${sessionId}/boundary-proposals`); if (heldRead) await heldRead; if (fail) throw new Error(); return { items: proposals }; } },
    "@/experience/read-budget.ts": { createReadBudget: () => ({ read: (read: () => Promise<unknown>) => read(), dispose() { disposed++; } }) },
  };
  const page = compile("../../app/sessions/[sessionId]/page.tsx", imports, env);
  const render = async (session = sessionId) => (await page.default({ params: Promise.resolve({ sessionId: session }), searchParams: Promise.resolve({}) } as never)).props.children as Node;
  const first = (await render()).props.boundaries as Node;
  assert.equal(first.props.authorized, true); assert.equal(first.props.currentStart, currentStart);
  let release: () => void = () => undefined;
  heldRead = new Promise<void>((resolve) => { release = resolve; });
  const priorOutputs = outputCalls, pending = render();
  await tick(); assert.equal(outputCalls, priorOutputs + 1, "Outputs must start while proposals are stalled");
  release(); await pending; heldRead = undefined;
  assert.equal(((await render()).props.boundaries as Node).key, first.key);
  delete (env as Partial<typeof env>).STAGEFLOW_DEMO_OPERATOR_ID;
  assert.equal(((await render()).props.boundaries as Node).props.authorized, false);
  proposals = [end]; assert.notEqual(((await render()).props.boundaries as Node).key, first.key);
  proposals = []; assert.deepEqual(((await render()).props.boundaries as Node).props.proposals, []);
  assert.ok((await render()).props.boundaryHistory);
  fail = true; assert.equal(((await render()).props.boundaries as Node).props.proposals, undefined);
  const before = calls; workspace.dataSource.state = "live_unavailable";
  assert.equal(((await render()).props.boundaries as Node).props.authorized, false); assert.equal(calls, before);
  workspace.dataSource.kind = "fixture"; assert.equal((await render()).props.boundaries, null);
  assert.equal((await render("missing")).props.boundaries, null); assert.equal(disposed, 11);
});

test("Stage page keeps realized Sessions and badges after a new run excludes their suggestions, even on run-read failure", async () => {
  const workspace = adaptKernelStatus(boundaryKernelFixture(), currentStart);
  let proposals = [start], reads = 0, disposed = 0, failRun = false;
  const imports = {
    "@/components/operational-shell": { OperationalShell: "shell" }, "@/components/operational-views": { StageOperationalView: "view" },
    "@/components/stage-suggestions": { StageSuggestions: "suggestions" },
    "@/experience/data-source.ts": { loadWorkspace: async () => workspace },
    "@/experience/session-suggestions-api.ts": { suggestionsApi: () => ({ load: async () => { if (failRun) throw new Error(); return { ...data, suggestions: [] }; } }) },
    "@/experience/session-boundaries-api.ts": require("./session-boundaries-api.ts"),
    "@/experience/capability-proxy.server.ts": { readCapability: async (capability: string, path: string) => { reads++; assert.equal(capability, "session-suggestions"); assert.equal(path, `events/${eventId}/sessions/${sessionId}/boundary-proposals`); return { items: proposals }; } },
    "@/experience/read-budget.ts": { createReadBudget: () => ({ read: (read: () => Promise<unknown>) => read(), dispose() { disposed++; } }) },
  };
  const page = compile("../../app/stages/[stageKey]/page.tsx", imports);
  const render = async () => ((await page.default({ params: Promise.resolve({ stageKey: "main" }), searchParams: Promise.resolve({}) } as never)).props.children as Node).props.suggestions as Node;
  const initial = await render();
  assert.deepEqual(initial.props.boundaryBadges, { sessions: { [sessionId]: 1 }, incomplete: false });
  assert.equal((initial.props.realizedSessions as unknown[]).length, 1);
  failRun = true;
  assert.deepEqual((await render()).props.boundaryBadges, { sessions: { [sessionId]: 1 }, incomplete: false });
  proposals = []; assert.deepEqual((await render()).props.boundaryBadges, { sessions: {}, incomplete: false });
  assert.equal(reads, 3); workspace.dataSource.state = "live_unavailable";
  assert.equal((await render()).props.boundaryBadges, undefined); assert.equal(reads, 3); assert.equal(disposed, 4);
});
