import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { suggestionLabels as labels } from "./ui-labels.ts";
import { localInput } from "./session-suggestions.ts";
import { type SuggestionData } from "./session-suggestions-api.ts";
import { getFixtureWorkspace } from "./fixtures.ts";
import { eventId, stageId, suggestionId as id, suggestionFixture as s, runFixture as run, offsetFixture as offset, suggestionDataFixture as data, suggestionNoneFixture as none, titlesFixture as titles, queueFixture } from "./session-suggestions-fixtures.ts";

type Props = Record<string, unknown>;
type Node = React.ReactElement<Props>;
const require = createRequire(import.meta.url);
function compile(file: string, imports: Record<string, unknown>) {
  const source = readFileSync(new URL(`../components/${file}.tsx`, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS } });
  const exports: Record<string, (props: never) => Node> = {};
  runInNewContext(compiled.outputText, { exports, require: (name: string) => imports[name] ?? require(name) });
  return exports;
}
function harness(value: SuggestionData | null = data, authorized = true, launchContext = "synthetic", hasPlannedTalks = true) {
  const slots: unknown[] = []; let cursor = 0, refreshes = 0;
  const exports = compile("stage-suggestions", {
    react: {
      useState(value: unknown) { const i = cursor++; if (!(i in slots)) slots[i] = value; return [slots[i], (next: unknown) => { slots[i] = next; }]; },
      useRef(value: unknown) { const i = cursor++; return slots[i] ??= { current: value }; },
      useSyncExternalStore() { return "UTC"; },
    },
    "next/navigation": { useRouter: () => ({ refresh() { refreshes++; } }) },
  });
  const render = () => { cursor = 0; return exports.StageSuggestions({ eventId, stageId, data: value ?? undefined, titles, authorized, launchContext, hasPlannedTalks } as never); };
  const nodes = (value: unknown): Node[] => Array.isArray(value) ? value.flatMap(nodes) : React.isValidElement<Props>(value) ? [value, ...nodes(value.props.children), ...nodes(value.props.decisionForm)] : [];
  const find = (predicate: (n: Node) => boolean) => { const n = nodes(render()).find(predicate); assert.ok(n); return n; };
  const button = (label: string) => find((n) => n.type === "button" && n.props.children === label);
  const click = (label: string) => { const n = button(label); assert.ok(!n.props.disabled, `${label} is disabled`); return (n.props.onClick as () => void)(); };
  const change = (id: string, value: string) => (find((n) => n.props.id === id).props.onChange as (e: unknown) => void)({ target: { value } });
  const submit = () => (find((n) => n.type === "form").props.onSubmit as (e: unknown) => void)({ preventDefault() {} });
  return { render, find, nodes, button, click, change, submit, html: () => renderToStaticMarkup(render()), refreshes: () => refreshes, rerender: (next: SuggestionData) => { value = next; } };
}
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
function decision(body: Record<string, unknown>, reject = false) {
  return { command_id: body.command_id, suggestion_id: s.suggestion_id, actor_id: id(4), decided_at: run.created_at, kind: reject ? "rejected" : "confirmed", reason: body.reason ?? null, session_id: reject ? null : id(40), used_start: reject ? null : body.start ?? s.suggested_start, used_end: reject ? null : body.end ?? s.suggested_end };
}

test("none, open, weak, overlap, fallback, unscheduled, decided and hidden superseded render compactly with Details", () => {
  assert.match(harness(none).html(), /No suggestions yet/);
  const mixed: SuggestionData = { ...data, suggestions: [
    { ...s, suggestion_id: id(15), suggested_start: "2026-09-29T12:00:00Z", suggested_end: "2026-09-29T13:00:00Z", strength: "weak", overlap: true, start_edge_kind: "schedule", schedule_offset_source: "producer" },
    s, { ...s, suggestion_id: id(16), strength: "weak", expectation_id: null, expectation_revision: null, start_plan_offset_seconds: null, end_plan_offset_seconds: null, schedule_offset_source: "none" },
    { ...s, suggestion_id: id(17), status: "confirmed" }, { ...s, suggestion_id: id(18), status: "rejected" }, { ...s, suggestion_id: id(19), status: "superseded" },
  ] };
  const h = harness(mixed), html = h.html();
  assert.match(html, /3 suggested · 2 need a closer look/); assert.match(html, /Decided · 2/); assert.match(html, /1 superseded suggestion hidden/);
  assert.match(html, /Unscheduled activity/); assert.match(html, /\+12 min/); assert.match(html, /60 min/);
  for (const label of [labels.weak, labels.overlap, labels.fallback, labels.producer]) assert.ok(html.includes(label));
  assert.doesNotMatch(html, /<details[^>]*\bopen\b/);
  assert.ok(html.indexOf("3 suggested") < html.indexOf("Talk 1"));
  const visible = html.replace(/<details\b[\s\S]*?<\/details>/g, "");
  for (const internal of [s.suggestion_id, s.run_id, s.timing_references[0].id, "freeze"]) assert.ok(!visible.includes(internal));
  assert.equal((html.match(/class="suggestion-row"/g) ?? []).length, 5);
  assert.equal((harness().html().match(/class="cue-badge"/g) ?? []).length, 0);
  assert.match(html, /silence supports/); assert.match(html, /cue phrases support/); assert.match(html, /Nothing becomes a Session until you confirm/);
});

test("a Stage with zero planned talks prompts for its schedule before any counts, even with zero skips", () => {
  for (const value of [none, { ...none, run: { ...run, blocks: [] } }]) {
    const html = harness(value, true, "synthetic", false).html();
    assert.match(html, /<strong>Add the schedule first/);
    assert.doesNotMatch(html, /No suggestions yet/);
  }
  assert.match(harness({ ...data, suggestions: [{ ...s, strength: "weak" }] }, true, "synthetic", false).html(), /Add the schedule first · 1 suggested · 1 needs a closer look/);
});

test("every skip and hidden suggestion count uses singular and plural wording", () => {
  for (const count of [1, 2]) {
    const html = harness({ ...data, run: { ...run, skips: { no_timing_evidence: count, no_segmentation: count, clock_implausible: count, no_coverage: count, no_planned_time: count, already_realized: 0 } }, suggestions: Array.from({ length: count }, (_, i) => ({ ...s, suggestion_id: id(70 + i), status: "superseded" })) }).html();
    const expected = count === 1 ? ["recording without timing evidence", "recording without changeover evidence", "recording with an implausible clock", "planned talk without enough recording coverage", "scheduled talk missing planned times", "superseded suggestion hidden"] : ["recordings without timing evidence", "recordings without changeover evidence", "recordings with implausible clocks", "planned talks without enough recording coverage", "scheduled talks missing planned times", "superseded suggestions hidden"];
    for (const phrase of expected) assert.ok(html.includes(`${count} ${phrase}`), phrase);
  }
});

test("suggest again requires an existing run, including when an offset was published first", () => {
  for (const value of [none, { ...none, offset }]) {
    const h = harness(value);
    assert.equal(h.button(labels.suggest).props.disabled, false);
    assert.doesNotMatch(h.html(), />Suggest again<|Suggest again to apply it/);
  }
  assert.equal(harness(data).button(labels.again).props.disabled, false);
});

test("rows, confirm and reject dialogs, and Decided share compact local ranges", () => {
  for (const [end, expected] of [["2026-09-29T10:28:00Z", "Sep 29, 10:12–10:28"], ["2026-09-30T00:16:00Z", "Sep 29, 10:12–Sep 30, 00:16"]]) {
    const value = { ...data, suggestions: [{ ...s, suggested_end: end }] };
    const h = harness(value);
    assert.ok(h.html().includes(`<span>${expected}</span>`));
    for (const action of [labels.confirm, labels.reject]) {
      h.click(action); assert.ok(h.html().includes(`<p>${expected}</p>`)); h.click(labels.cancel);
    }
    const html = harness({ ...value, suggestions: [{ ...value.suggestions[0], status: "confirmed" }] }).html();
    assert.match(html, /Decided · 1/); assert.ok(html.includes(`<span>${expected}</span>`));
  }
});

test("badge rows keep Details, Confirm and Reject in one nonwrapping action group", () => {
  const h = harness({ ...data, suggestions: [{ ...s, strength: "weak", overlap: true, start_edge_kind: "schedule", schedule_offset_source: "producer" }] });
  const row = h.find((n) => Boolean(n.props.item));
  const tree = (row.type as (props: Props) => Node)(row.props);
  const actions = h.nodes(tree).find((n) => n.props.className === "suggestion-actions")!;
  assert.deepEqual(h.nodes(actions).filter((n) => n.type === "summary" || n.type === "button").map((n) => n.props.children), [labels.details, labels.confirm, labels.reject]);
  assert.equal(h.nodes(actions).filter((n) => n.props.className === "cue-badge").length, 0);
  const facts = h.nodes(tree).find((n) => n.props.className === "suggestion-facts")!;
  // One open row: its producer offset is the one stated in the summary, so that badge is omitted (owner UX checkpoint).
  assert.equal(h.nodes(facts).filter((n) => n.props.className === "cue-badge").length, 3);
  const css = readFileSync(new URL("../../app/globals.css", import.meta.url), "utf8");
  assert.match(css, /\.suggestion-info\s*\{[^}]*display: flex/);
  assert.match(css, /\.suggestion-actions\s*\{[^}]*flex-wrap: nowrap/);
  assert.match(css, /\.suggestion-line\s*\{[^}]*flex-wrap: wrap/);
});

test("unrelated refresh preserves an uncertain retry and its exact command; successful unchanged refresh unlocks", async () => {
  const original = globalThis.fetch; const bodies: string[] = [];
  try {
    globalThis.fetch = async (_url, init) => { bodies.push(String(init?.body)); return bodies.length === 1 ? Response.json({}, { status: 503 }) : Response.json(decision(JSON.parse(String(init?.body)))); };
    const h = harness(); h.click(labels.confirm); h.submit(); await tick();
    h.rerender(structuredClone(data));
    for (const label of [labels.again, labels.confirmSave, labels.refresh]) assert.equal(h.button(label).props.disabled, true);
    h.click(labels.retry); await tick(); assert.equal(bodies[0], bodies[1]);
    globalThis.fetch = async () => Response.json(run);
    const runPanel = harness(); runPanel.click(labels.again); await tick();
    assert.equal(runPanel.button(labels.again).props.disabled, true);
    runPanel.rerender(structuredClone(data));
    assert.equal(runPanel.button(labels.again).props.disabled, false);
  } finally { globalThis.fetch = original; }
});

test("skips show only nonzero exceptions; missing planned times prompt schedule and offsets disclose block differences", () => {
  const h = harness({ ...data, run: { ...run, blocks: [], skips: { no_timing_evidence: 2, no_segmentation: 0, clock_implausible: 1, no_coverage: 3, no_planned_time: 4, already_realized: 0 } } }, true, "synthetic", false);
  assert.match(h.html(), /Add the schedule first/); assert.match(h.html(), /2 recordings without timing evidence/); assert.match(h.html(), /1 recording with an implausible clock/); assert.doesNotMatch(h.html(), /0 recordings without changeover evidence/);
  assert.match(harness({ ...data, run: { ...run, blocks: [...run.blocks, { ...run.blocks[0], ordinal: 1, schedule_offset_source: "producer", schedule_offset_seconds: 600 }] } }).html(), /from Sep 29, 10:00: running about 12.*from Sep 29, 10:00: running about 10/);
});

test("authorization gates every mutation while keeping evidence readable; unavailable data offers refresh", () => {
  for (const h of [harness(data, false), harness(data, true, "")]) {
    for (const label of [labels.again, labels.confirm, labels.reject, labels.editOffset]) assert.equal(h.button(label).props.disabled, true);
    assert.match(h.html(), /authorized producer connection/); assert.match(h.html(), /Talk 1/);
  }
  const h = harness(null); assert.equal(h.button(labels.suggest).props.disabled, true); assert.match(h.html(), /Suggestions are unavailable/); h.click(labels.refresh); assert.equal(h.refreshes(), 1);
});

test("confirm requires a separate form, sends no adjustment by default, prevents duplicate submissions and refreshes", async () => {
  const original = globalThis.fetch, bodies: Record<string, unknown>[] = [];
  globalThis.fetch = async (_url, init) => { const body = JSON.parse(String(init?.body)); bodies.push(body); return Response.json(decision(body)); };
  try {
    const h = harness(); h.click(labels.confirm); assert.equal(bodies.length, 0); assert.match(h.html(), /Create one Session with these times/);
    assert.ok(h.nodes(h.find((n) => n.props.item === s)).some((n) => n.type === "form"));
    assert.match(h.html(), /Sep 29, 10:12/); h.submit(); h.submit(); await tick();
    assert.equal(bodies.length, 1); assert.deepEqual(Object.keys(bodies[0]).sort(), ["authority_kind", "command_id"]); assert.equal(h.refreshes(), 1);
    assert.equal(h.button(labels.again).props.disabled, true);
  } finally { globalThis.fetch = original; }
});

test("adjusted confirm validates start before end and transmits timezone-aware instants", async () => {
  const original = globalThis.fetch, bodies: Record<string, unknown>[] = [];
  globalThis.fetch = async (_url, init) => { const body = JSON.parse(String(init?.body)); bodies.push(body); return Response.json(decision(body)); };
  try {
    const h = harness(); h.click(labels.confirm);
    (h.find((n) => n.props.type === "checkbox").props.onChange as (e: unknown) => void)({ target: { checked: true } });
    h.change("suggestion-start", localInput(s.suggested_end)); h.submit(); assert.equal(bodies.length, 0); assert.match(h.html(), /start before the end/);
    h.change("suggestion-start", localInput("2026-09-29T10:15:30Z")); h.change("suggestion-end", localInput("2026-09-29T11:10:45Z")); h.submit(); await tick();
    assert.equal(bodies[0].start, "2026-09-29T10:15:30.000Z"); assert.equal(bodies[0].end, "2026-09-29T11:10:45.000Z");
  } finally { globalThis.fetch = original; }
});

test("409, 422 and 5xx retain the same confirmation command for manual retry; unknown outcome locks editing", async () => {
  const original = globalThis.fetch;
  try {
    for (const status of [409, 422, 503]) {
      const bodies: string[] = [];
      globalThis.fetch = async (_url, init) => { bodies.push(String(init?.body)); return bodies.length === 1 ? Response.json({ detail: "stale_expectation_revision" }, { status }) : Response.json(decision(JSON.parse(String(init?.body)))); };
      const h = harness(); h.click(labels.confirm); h.submit(); await tick();
      assert.equal(h.button(labels.confirmSave).props.disabled, true);
      assert.equal(h.button(labels.refresh).props.disabled, status >= 500);
      h.click(labels.retry); await tick(); assert.equal(bodies.length, 2); assert.equal(bodies[0], bodies[1]); assert.equal(h.refreshes(), 1);
    }
  } finally { globalThis.fetch = original; }
});

test("reject uses the bounded picker and posts only after the producer submits", async () => {
  const original = globalThis.fetch; let body: Record<string, unknown> | undefined;
  globalThis.fetch = async (url, init) => { assert.match(String(url), /\/reject$/); body = JSON.parse(String(init?.body)); return Response.json(decision(body!, true)); };
  try {
    const h = harness(); h.click(labels.reject); assert.equal(body, undefined);
    assert.deepEqual(h.nodes(h.render()).filter((n) => n.type === "option").map((n) => n.props.children), [...labels.rejectionReasons]);
    h.change("suggestion-reason", "Incorrect times"); h.submit(); await tick(); assert.equal(body!.reason, "Incorrect times"); assert.equal(h.refreshes(), 1);
  } finally { globalThis.fetch = original; }
});

test("suggest uses default Event composition and shows readable failures without automatic retries", async () => {
  const original = globalThis.fetch; const bodies: string[] = [];
  globalThis.fetch = async (url, init) => { assert.match(String(url), new RegExp(`stages/${stageId}/runs$`)); bodies.push(String(init?.body)); return bodies.length === 1 ? Response.json({}, { status: 503 }) : Response.json(run); };
  try {
    const h = harness(none); h.click(labels.suggest); await tick(); assert.equal(bodies.length, 1); assert.match(h.html(), /service is unavailable/);
    h.click(labels.retry); await tick(); assert.equal(bodies.length, 2); assert.equal(bodies[0], bodies[1]); assert.deepEqual(JSON.parse(bodies[0]), { authority_kind: "human" }); assert.equal(h.refreshes(), 1);
  } finally { globalThis.fetch = original; }
});

test("offset editor adds, validates, removes, clears and confirms; saving never invokes a run", async () => {
  const original = globalThis.fetch; const bodies: Record<string, unknown>[] = [];
  globalThis.fetch = async (url, init) => { assert.match(String(url), /schedule-offset$/); const body = JSON.parse(String(init?.body)); bodies.push(body); return Response.json({ ...offset, command_id: body.command_id, entries: body.entries }); };
  try {
    const h = harness(); h.click(labels.editOffset); h.click(labels.addOffset); h.submit(); assert.match(h.html(), /up to 20 entries/); assert.equal(bodies.length, 0);
    h.change("offset-from-0", localInput("2026-09-29T10:00:00Z")); h.change("offset-minutes-0", "12"); h.submit(); assert.equal(bodies.length, 0); assert.match(h.html(), /Publish these offsets for future suggestion runs/);
    h.click("Back"); h.click(labels.addOffset); h.click(labels.removeOffset); h.click(labels.clearOffset); h.submit(); assert.match(h.html(), /Clear the producer override/);
    h.submit(); await tick(); assert.deepEqual(bodies[0].entries, []); assert.equal(bodies.length, 1); assert.equal(h.refreshes(), 1);
    const updated = harness({ ...data, offset }); assert.ok(updated.button(labels.again)); assert.match(updated.html(), /from Sep 29, 09:00, \+10 min/);
    assert.match(updated.html(), /Suggest again to apply it/);
  } finally { globalThis.fetch = original; }
});

test("offset history stays collapsed and pages explicitly with recoverable read failure", async () => {
  const original = globalThis.fetch; let calls = 0;
  globalThis.fetch = async (url) => { calls++; if (calls === 1) return Response.json({}, { status: 503 }); assert.match(String(url), /schedule-offset\/history\?after=0&limit=50/); return Response.json({ items: [offset], next_after: null, limit: 50 }); };
  try {
    const h = harness(); h.click(labels.moreHistory); await tick(); assert.match(h.html(), /Offset history is unavailable/);
    h.click(labels.moreHistory); await tick(); assert.match(h.html(), /Version 1/); assert.doesNotMatch(h.html(), /Load more versions/); assert.doesNotMatch(h.html(), /<details[^>]*\bopen\b/);
  } finally { globalThis.fetch = original; }
});

test("Mission Control emits one linked summary per matching Stage, uses suggestion counts and nothing when none", () => {
  const { SuggestionQueueLines } = compile("suggestion-queue-lines", { "next/link": ({ children, ...props }: Props) => React.createElement("a", props, children as React.ReactNode) });
  const stages = [{ id: stageId, key: "stage A", name: "Stage A" }];
  const html = (items: unknown) => renderToStaticMarkup(SuggestionQueueLines({ items, stages } as never));
  assert.equal(html([]), "");
  assert.match(html([queueFixture, queueFixture]), /Stage A<\/a><span>9 suggestions to review \(2 need a closer look\)/);
  assert.equal((html([queueFixture, queueFixture]).match(/<a /g) ?? []).length, 1);
  assert.match(html([queueFixture]), /href="\/stages\/stage%20A#suggested-presentations"/);
  assert.doesNotMatch(html([queueFixture]), /9 presentations/);
  assert.equal(html([{ ...queueFixture, decision_type: "assembly_approval_pending" }]), "");
  assert.match(html([{ ...queueFixture, reason_codes: ["open_count:1", "weak_count:0"] }]), /1 suggestion to review<\/span>/);
  assert.match(html([{ ...queueFixture, reason_codes: ["open_count:1", "weak_count:1"] }]), /1 suggestion to review \(1 needs a closer look\)/);
  assert.equal(html([{ ...queueFixture, reason_codes: ["open_count:0", "weak_count:0"] }]), "");
  assert.match(html([queueFixture]), /<section class="suggestion-queue-lines" aria-label="Suggestions to review"><h2>Suggestions to review<\/h2><ul><li><a class="text-link"/);
  assert.match(html(undefined), /counts are unavailable/);
});

test("Stage page resolves the workspace UUID and titles, gates mutations, and preserves keys for unchanged results", async () => {
  const source = readFileSync(new URL("../../app/stages/[stageKey]/page.tsx", import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS } });
  const stage = { id: stageId, key: "stage A", name: "Stage A", programExpectations: [{ id: s.expectation_id, stageId, title: "Talk 1", plannedStart: s.suggested_start, plannedEnd: s.suggested_end }], withdrawnProgramExpectations: [{ id: id(80), title: "Earlier talk", stageId, plannedStart: s.suggested_start, plannedEnd: s.suggested_end }] };
  const workspace = { event: { id: eventId }, stages: [stage], dataSource: { kind: "kernel", state: "live_connected", authoritative: true } };
  const calls: string[][] = []; let disposed = 0;
  let loaded: SuggestionData = data, fail = false;
  const exports: { default?: (props: unknown) => Promise<Node> } = {};
  const imports: Record<string, unknown> = {
    "@/components/operational-shell": { OperationalShell: "shell" }, "@/components/operational-views": { StageOperationalView: "stage-view" },
    "@/components/stage-suggestions": { StageSuggestions: "stage-suggestions" },
    "@/experience/data-source.ts": { loadWorkspace: async () => workspace },
    "@/experience/session-suggestions-api.ts": { suggestionsApi: () => ({ load: async (event: string, stage: string) => { calls.push([event, stage]); if (fail) throw new Error("stage_not_found"); return loaded; } }) },
    "@/experience/capability-proxy.server.ts": { readCapability() { assert.fail("API is stubbed"); } },
    "@/experience/read-budget.ts": { createReadBudget: () => ({ dispose() { disposed++; } }) },
  };
  runInNewContext(compiled.outputText, { exports, process: { env: { STAGEFLOW_DEMO_OPERATOR_ID: id(4), STAGEFLOW_DEMO_LAUNCH_CONTEXT: "synthetic" } }, require: (name: string) => imports[name] ?? require(name) });
  const render = (key = "stage%20A") => exports.default!({ params: Promise.resolve({ stageKey: key }), searchParams: Promise.resolve({}) });
  const panel = (tree: Node) => (tree.props.children as Node).props.suggestions as Node;
  const first = await render(), second = await render();
  assert.deepEqual(calls, [[eventId, stageId], [eventId, stageId]]);
  assert.equal((first.props.children as Node).type, "stage-view"); assert.equal(panel(first).type, "stage-suggestions");
  assert.equal(panel(first).props.stageId, stageId); assert.equal(panel(first).props.authorized, true);
  assert.equal(JSON.stringify(panel(first).props.titles), JSON.stringify({ [id(80)]: "Earlier talk", [s.expectation_id!]: "Talk 1" }));
  assert.equal(panel(first).key, panel(second).key);
  assert.equal(panel(first).props.hasPlannedTalks, true);
  workspace.dataSource.state = "live_unavailable";
  const offline = panel(await render()); assert.equal(offline.props.authorized, false); assert.equal(offline.props.data, undefined); assert.equal(calls.length, 2);
  assert.equal(panel(await render("missing")), null); assert.equal(disposed, 4);
  workspace.dataSource.state = "live_connected";
  fail = true;
  assert.equal(panel(await render()).props.data, undefined);
  fail = false;
  loaded = { ...data, run: { ...run, run_id: id(90) } };
  assert.notEqual(panel(await render()).key, panel(first).key);
  loaded = { ...data, offset };
  assert.notEqual(panel(await render()).key, panel(first).key);
  loaded = { ...data, suggestions: [{ ...s, status: "confirmed" }] };
  assert.notEqual(panel(await render()).key, panel(first).key);
  loaded = { ...data, suggestions: [s, { ...s, suggestion_id: id(90) }] };
  const ordered = panel(await render());
  loaded = { ...loaded, suggestions: [...loaded.suggestions].reverse() };
  assert.equal(panel(await render()).key, ordered.key);
  for (const expectations of [[], [{ ...stage.programExpectations[0], plannedStart: "" }], [{ ...stage.programExpectations[0], plannedEnd: "" }], [{ ...stage.programExpectations[0], stageId: id(99) }]]) {
    stage.programExpectations = expectations;
    assert.equal(panel(await render()).props.hasPlannedTalks, false);
  }
});

test("Stage suggestions render after current operation and before media evidence; Mission Control strip follows Stages", () => {
  const imports: Record<string, unknown> = {
    "next/link": ({ children, ...props }: Props) => React.createElement("a", props, children as React.ReactNode),
    "@/experience/presentation.ts": require("./presentation.ts"),
    "@/experience/program-provider.ts": require("./program-provider.ts"),
    "./session-timing-evidence": { SessionTimingEvidence: () => null },
    "./demo-session-workspace": { DemoSessionWorkspace: () => null },
    "./demo-program-refresh-control": { DemoProgramRefreshControl: () => null },
    "./demo-start-session-control": { DemoStartSessionControl: () => null },
    "./suggestion-queue-lines": compile("suggestion-queue-lines", { "next/link": ({ children, ...props }: Props) => React.createElement("a", props, children as React.ReactNode) }),
  };
  imports["./mission-control"] = compile("mission-control", imports);
  const { StageOperationalView } = compile("operational-views", imports);
  const workspace = getFixtureWorkspace("turnover");
  workspace.mediaTimingEvidenceStatus = "unavailable";
  const html = renderToStaticMarkup(StageOperationalView({ workspace, stage: workspace.stages[0], suggestions: React.createElement("section", { id: "suggested-presentations" }, "Suggested presentations") } as never));
  assert.ok(html.indexOf("Current operation") < html.indexOf('id="suggested-presentations"'));
  assert.ok(html.indexOf('id="suggested-presentations"') < html.indexOf('id="media-uncertainty-title"'));
  assert.ok(html.indexOf('id="suggested-presentations"') < html.indexOf('id="timing-evidence-title"'));
  const { MissionControl } = imports["./mission-control"] as ReturnType<typeof compile>;
  const mission = renderToStaticMarkup(MissionControl({ workspace, suggestions: [{ ...queueFixture, stage_id: workspace.stages[0].id, action_reference: `stage:${workspace.stages[0].id}:suggestions` }] } as never));
  assert.ok(mission.indexOf('class="stage-matrix"') < mission.indexOf('class="suggestion-queue-lines"'));
  assert.ok(mission.indexOf('class="suggestion-queue-lines"') < mission.indexOf('id="attention-title"'));
});

test("Mission Control page reads the queue only for a connected Event and distinguishes outage from empty", async () => {
  const source = readFileSync(new URL("../../app/page.tsx", import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS } });
  const workspace = { event: { id: eventId }, dataSource: { kind: "kernel", state: "live_connected", authoritative: true } };
  let calls = 0, fail = false;
  const exports: { default?: (props: unknown) => Promise<Node> } = {};
  const imports: Record<string, unknown> = {
    "@/components/operational-shell": { OperationalShell: "shell" }, "@/components/mission-control": { MissionControl: "mission" },
    "@/experience/data-source.ts": { loadWorkspace: async () => workspace },
    "@/experience/session-suggestions-api.ts": { suggestionQueue: async (event: string, read: (path: string) => Promise<unknown>) => { assert.equal(event, eventId); calls++; if (fail) throw new Error(); await read(`events/${event}/work-queue`); return [queueFixture]; } },
    "@/experience/capability-proxy.server.ts": { readCapability: async (capability: string, path: string) => { assert.equal(capability, "producer"); assert.equal(path, `events/${eventId}/work-queue`); } },
    "@/experience/read-budget.ts": { createReadBudget: () => ({ read: (read: () => Promise<unknown>) => read(), dispose() {} }) },
  };
  runInNewContext(compiled.outputText, { exports, require: (name: string) => imports[name] ?? require(name) });
  const render = async () => (await exports.default!({ searchParams: Promise.resolve({}) })).props.children as Node;
  assert.deepEqual((await render()).props.suggestions, [queueFixture]);
  fail = true; assert.equal((await render()).props.suggestions, undefined);
  workspace.dataSource.kind = "fixture"; assert.equal(JSON.stringify((await render()).props.suggestions), "[]"); assert.equal(calls, 2);
});

test("realized talks appear as informational singular/plural summary counts, never skip exceptions", () => {
  for (const count of [0, 1, 2]) {
    const html = harness({ ...data, run: { ...run, skips: { ...run.skips, already_realized: count } } }).html();
    if (count) assert.ok(html.includes(` \u00b7 ${count} already ${count === 1 ? "a Session" : "Sessions"}`));
    else assert.doesNotMatch(html, /already (a Session|Sessions)/);
    const skips = html.match(/<ul class="suggestion-skips">([\s\S]*?)<\/ul>/)?.[1];
    assert.equal(skips, "");
  }
});

test("a run whose remaining talks are all already Sessions reads as no open suggestions, not 'yet'", () => {
  const html = harness({ ...data, suggestions: [], run: { ...run, skips: { ...run.skips, already_realized: 2 } } }).html();
  assert.ok(html.includes("No open suggestions · 2 already Sessions"));
  assert.doesNotMatch(html, /No suggestions yet/);
});
