import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as actions from "./editorial-actions.ts";
import * as api from "./editorial-api.ts";
import * as presentation from "./editorial-presentation.ts";
import * as normalization from "./editorial-normalization.ts";
import * as fixtures from "./editorial-fixtures.ts";

const require = createRequire(import.meta.url);
type Props = Record<string, unknown>;
type Element = React.ReactElement<Props>;
function nodes(value: unknown): Element[] {
  if (Array.isArray(value)) return value.flatMap(nodes);
  return React.isValidElement<Props>(value) ? [value, ...nodes(value.props.children)] : [];
}
function plain(value: unknown): string {
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (Array.isArray(value)) return value.map(plain).join("");
  return React.isValidElement<Props>(value) ? plain(value.props.children) : "";
}
const settle = () => new Promise<void>((resolve) => setImmediate(resolve));
function context(): actions.EditorialAuthority { return { eventId: fixtures.editorialFixtureEvent, fixture: false, authoritative: true, launchContext: "synthetic-launch", operatorAvailable: true }; }
const surfaceProps = () => ({ context: context(), eventName: "Synthetic Event", sessions: fixtures.editorialFixtureSessions, initialQueue: fixtures.fixtureQueue() });

/** Exercise actual handlers with deterministic hooks. Native dialog provides focus trap. */
function harness(component: string, initial: Props, options: { fetcher?: typeof fetch; client?: ReturnType<typeof api.editorialApi>; file?: string } = {}) {
  const slots: unknown[] = [], effects: Array<() => void> = [];
  let cursor = 0, tree: Element, shows = 0, focuses = 0;
  const nativeDialog = { open: false, showModal() { this.open = true; shows++; }, close() { this.open = false; } };
  const trigger = { isConnected: true, focus() { focuses++; } };
  const exports: Record<string, (props: Props) => Element> = {};
  const file = options.file ?? "editorial-review-surface.tsx";
  const source = readFileSync(new URL(`../components/${file}`, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS } });
  const imports: Record<string, unknown> = {
    react: {
      useState(initial: unknown) { const index = cursor++; if (!(index in slots)) slots[index] = initial; return [slots[index], (value: unknown) => { slots[index] = typeof value === "function" ? value(slots[index]) : value; }]; },
      useRef(initial: unknown) { const index = cursor++; return slots[index] ??= { current: initial }; },
      useEffect(effect: () => void | (() => void), dependencies: unknown[]) {
        const index = cursor++, previous = slots[index] as { dependencies: unknown[]; cleanup?: () => void } | undefined;
        if (!previous || dependencies.some((value, i) => value !== previous.dependencies[i])) effects.push(() => {
          previous?.cleanup?.();
          slots[index] = { dependencies, cleanup: effect() };
        });
      },
    },
    "../experience/editorial-actions.ts": actions,
    "../experience/editorial-api.ts": { ...api, editorialApi: () => options.client ?? api.editorialApi() },
    "../experience/editorial-presentation.ts": presentation,
    "../experience/editorial-normalization.ts": normalization,
    "../experience/editorial-fixtures.ts": fixtures,
  };
  runInNewContext(compiled.outputText, { exports, document: { activeElement: trigger }, fetch: options.fetcher ?? (async () => { assert.fail("unexpected command"); }), require: (name: string) => imports[name] ?? require(name) });
  const ui = {
    props: initial,
    render() { cursor = 0; tree = exports[component](ui.props); for (const node of nodes(tree)) { const ref = node.props.ref as { current: unknown } | undefined; if (ref) ref.current = node.type === "dialog" ? nativeDialog : trigger; } effects.splice(0).forEach((effect) => effect()); return tree; },
    find(type: string, label?: string) { const node = nodes(tree).find((n) => n.type === type && (label === undefined || n.props.id === label || plain(n.props.children) === label)); assert.ok(node, `${type} ${label ?? ""}`); return node.props; },
    child(name: string) { const node = nodes(tree).find((n) => typeof n.type === "function" && n.type.name === name); assert.ok(node, name); return node.props; },
    click(label: string) { const handler = ui.find("button", label).onClick as () => unknown; const result = handler(); ui.render(); return result; },
    change(type: string, label: string, value: string) { (ui.find(type, label).onChange as (event: unknown) => void)({ target: { value } }); ui.render(); },
    submit(index = 0) { const form = nodes(tree).filter((n) => n.type === "form")[index]; assert.ok(form); (form.props.onSubmit as (event: unknown) => void)({ preventDefault() {} }); ui.render(); },
    // Static rendering child functions uses the same hook shim; preserve the harness cursor.
    html() { const saved = cursor; const html = renderToStaticMarkup(tree); cursor = saved; return html; },
    stats: () => ({ shows, focuses, open: nativeDialog.open }),
  };
  ui.render(); return ui;
}

test("queue paging replaces bounded rows, preserves failed-page position and explicit refresh", async () => {
  const reads: string[] = [];
  let fail = false;
  const client = api.editorialApi(async (path) => { reads.push(path); if (fail) throw new Error(); return fixtures.fixtureQueue(path.includes("cursor=") ? "fixture-page-2" : undefined); });
  const ui = harness("EditorialReviewSurface", surfaceProps(), { client });
  assert.equal(reads.length, 0);
  assert.equal(ui.find("button", "Previous page").disabled, true);
  await ui.click("Next page"); ui.render();
  assert.match(ui.html(), /Page 2/); assert.match(ui.html(), /2 suggested · 1 outside Session/);
  assert.equal(ui.find("button", "Next page").disabled, true);
  fail = true; await ui.click("Previous page"); ui.render();
  assert.match(ui.html(), /Page 2/); assert.match(ui.html(), /rows may be stale/);
  fail = false; await ui.click("Previous page"); ui.render();
  assert.match(ui.html(), /Page 1/); assert.equal(ui.find("button", "Previous page").disabled, true);
});
test("candidate markup uses phrase-only transcript, text flags and collapsed full provenance", () => {
  const ui = harness("EditorialReviewSurface", surfaceProps());
  const html = ui.html();
  assert.match(html, /00:18:52 · 8 s/);
  assert.match(html, />Marked</); assert.match(html, />Suggested ·/); assert.match(html, /recorder time \(unverified\)/);
  assert.equal((html.match(/silver lantern/g) ?? []).length, 1);
  for (const text of ["phrase list version", "transcript revision", "timing revision", "timing evidence id", "first word id", "last word id"]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /<details open|<details[^>]*open=/);
});
test("selected review controls sit in their candidate row and receive keyboard focus", () => {
  const ui = harness("EditorialReviewSurface", surfaceProps());
  ui.click(presentation.candidateLabel(fixtures.fixtureCandidate()));
  const rows = nodes(ui.render()).filter((node) => node.type === "li");
  assert.ok(nodes(rows[0]).some((node) => typeof node.type === "function" && node.type.name === "ReviewForm"));
  assert.ok(rows.slice(1).every((row) => !nodes(row).some((node) => typeof node.type === "function" && node.type.name === "ReviewForm")));
  const form = harness("ReviewForm", ui.child("ReviewForm"));
  assert.equal(form.find("select", "editorial-action").autoFocus, true);
});
test("real review form validates reason/range and dispatches each action only on submit", () => {
  const intents: actions.EditorialIntent[] = [], consequences: string[] = [];
  const ui = harness("ReviewForm", { candidate: fixtures.fixtureCandidate(), title: "Synthetic opening", disabled: false, begin: (intent: actions.EditorialIntent, consequence: string) => { intents.push(intent); consequences.push(consequence); } });
  ui.submit(); assert.equal(intents.length, 0);
  ui.change("textarea", "editorial-reason", "Synthetic reason");
  assert.equal(ui.find("button", "Approve & create clip").disabled, true);
  ui.change("input", "editorial-end", "1123.123456");
  assert.equal(ui.find("button", "Approve & create clip").disabled, false);
  ui.submit(); assert.equal(intents.length, 1);
  assert.equal((intents[0] as { end: number }).end, 1123123456);
  assert.match(consequences[0], /^Create an Editorial Clip/);
  for (const action of ["reject", "revise_range", "defer"] as const) { ui.change("select", "editorial-action", action); ui.submit(); assert.equal((intents.at(-1) as { action: string }).action, action); }
  assert.match(consequences[2], /moment location stays unchanged/);
  ui.props.disabled = true; ui.render(); ui.submit(); assert.equal(intents.length, 4);
});
test("confirmation is consequence-labelled, cancels/Esc restore focus, duplicate confirms issue one command", async () => {
  const bodies: Record<string, unknown>[] = [];
  const ui = harness("EditorialReviewSurface", surfaceProps(), {
    fetcher: async (_url, init) => { bodies.push(JSON.parse(String(init?.body))); return Response.json({ detail: "synthetic_rejection" }, { status: 422 }); },
  });
  const begin = ui.child("PhraseTools").begin as (intent: actions.EditorialIntent, consequence: string) => void;
  const intent: actions.EditorialIntent = { kind: "publish", key: "highlights", name: "Synthetic", version: 2, text: "silver lantern" };
  begin(intent, "Publish immutable version 2."); ui.render();
  assert.equal(bodies.length, 0); assert.equal(ui.stats().open, true);
  assert.equal(ui.find("dialog")["aria-labelledby"], "editorial-consequence");
  assert.equal(ui.find("button", "Cancel").autoFocus, true);
  let cancelled = false;
  (ui.find("dialog").onCancel as (event: unknown) => void)({ preventDefault() { cancelled = true; } }); ui.render();
  assert.ok(cancelled); assert.equal(ui.stats().open, false); assert.ok(ui.stats().focuses > 0);
  begin(intent, "Publish immutable version 2."); ui.render(); ui.submit(); ui.submit(); await settle(); ui.render();
  assert.equal(bodies.length, 1); assert.equal(bodies[0].confirmed, "confirmed");
  assert.match(ui.html(), /synthetic_rejection/); assert.doesNotMatch(ui.html(), /Retry same command/);
});
test("changed authority invalidates an open confirmation", () => {
  const ui = harness("EditorialReviewSurface", surfaceProps());
  (ui.child("PhraseTools").begin as (i: actions.EditorialIntent, c: string) => void)({ kind: "publish", key: "highlights", name: "Synthetic", version: 2, text: "silver lantern" }, "Publish version 2."); ui.render();
  ui.props.context = { ...context(), launchContext: "changed-launch" }; ui.render();
  assert.equal(ui.find("button", "Confirm action").disabled, true);
  ui.submit(); assert.match(ui.html(), /State changed/);
});
test("network failure retains same-ID retry and blocks other actions until resolved", async () => {
  const bodies: string[] = [];
  const ui = harness("EditorialReviewSurface", surfaceProps(), { fetcher: async (_url, init) => { bodies.push(String(init?.body)); if (bodies.length === 1) throw new TypeError(); return Response.json(fixtures.fixturePhraseLists().items[0]); }, client: api.editorialApi(async () => fixtures.fixtureQueue()) });
  (ui.child("PhraseTools").begin as (i: actions.EditorialIntent, c: string) => void)({ kind: "publish", key: "highlights", name: "Synthetic", version: 2, text: "silver lantern" }, "Publish version 2."); ui.render(); ui.submit(); await settle(); ui.render();
  assert.equal(bodies.length, 1); assert.equal(ui.find("button", "Refresh queue").disabled, true);
  assert.equal(ui.child("PhraseTools").disabled, true);
  await ui.click("Retry same command"); await settle(); ui.render();
  assert.equal(bodies.length, 2); assert.equal(bodies[0], bodies[1]); assert.match(ui.html(), /version 1 published/);
});
test("409 refreshes page without replay; failed refresh disables review", async () => {
  let calls = 0, reads = 0;
  const ui = harness("EditorialReviewSurface", surfaceProps(), { fetcher: async () => { calls++; return Response.json({ detail: "candidate_revision_conflict" }, { status: 409 }); }, client: api.editorialApi(async () => { reads++; throw new Error(); }) });
  (ui.child("PhraseTools").begin as (i: actions.EditorialIntent, c: string) => void)({ kind: "review", candidate: fixtures.fixtureCandidate(1), action: "defer", reason: "Synthetic" }, "Defer candidate."); ui.render(); ui.submit(); await settle(); ui.render();
  assert.equal(calls, 1); assert.equal(reads, 1); assert.equal(ui.child("PhraseTools").disabled, true);
  assert.match(ui.html(), /candidate_revision_conflict/); assert.match(ui.html(), /rows may be stale/);
  assert.doesNotMatch(ui.html(), /Retry same command/);
});
test("phrase preview rejection gates publish and keyed version pages gate derivation", async () => {
  const intents: actions.EditorialIntent[] = [], paths: string[] = [];
  const ui = harness("PhraseTools", { context: context(), sessions: fixtures.editorialFixtureSessions, disabled: false, refresh: 0, begin: (intent: actions.EditorialIntent) => intents.push(intent) }, { client: api.editorialApi(async (path) => { paths.push(path); return fixtures.fixturePhraseLists(); }) });
  ui.change("input", "phrase-name", "Synthetic list");
  ui.change("textarea", "phrase-text", "Straße\nSTRASSE");
  assert.equal(ui.find("button", "Publish version").disabled, true); ui.submit(1); assert.equal(intents.length, 0);
  assert.match(ui.html(), /Duplicate token sequence/);
  ui.change("textarea", "phrase-text", "silver lantern"); ui.submit(1); assert.equal(intents[0].kind, "publish");
  ui.submit(0); await settle(); ui.render(); assert.match(paths[0], /key=highlights&after=0&limit=100/);
  const phrase = fixtures.fixturePhraseLists().items[0];
  ui.change("select", "derivation-session", fixtures.editorialFixtureSessions[0].id);
  ui.change("select", "derivation-phrases", `${phrase.phrase_list_id}:${phrase.version}`);
  assert.equal(ui.find("button", "Run derivation").disabled, false); ui.submit(2); assert.equal(intents[1].kind, "derive");
  assert.equal((intents[1] as { version: number }).version, 1);
  ui.change("input", "phrase-key", "different-key"); assert.equal(ui.find("button", "Run derivation").disabled, true); ui.submit(2); assert.equal(intents.length, 2);
  ui.change("input", "phrase-key", "highlights"); ui.props.refresh = 1; ui.render(); assert.equal(ui.find("button", "Run derivation").disabled, true);
});
test("fixture has the same queue/paging/forms and never issues commands", async () => {
  const props = surfaceProps(); props.context.fixture = true;
  const ui = harness("EditorialReviewSurface", props);
  assert.match(ui.html(), /Development fixture · commands disabled/);
  assert.equal(ui.child("PhraseTools").disabled, true);
  await ui.click("Next page"); ui.render(); assert.match(ui.html(), /Page 2/);
  (ui.child("PhraseTools").begin as (i: actions.EditorialIntent, c: string) => void)({ kind: "publish", key: "x", name: "Synthetic", version: 1, text: "silver lantern" }, "Publish."); ui.render(); assert.equal(ui.stats().open, false);
});
test("moments summary replaces 31 tiles with counts, five initial rows and collapsed remainder", () => {
  const items = Array.from({ length: 31 }, (_, i) => fixtures.fixtureCandidate(i));
  const ui = harness("MomentsSummary", { moments: { session_id: items[0].session_id, candidate_count: 35, items, items_truncated: true } }, { file: "session-moments.tsx" });
  const html = ui.html();
  assert.match(html, /16 marked · 15 suggested · 30 awaiting review · 1 deferred · 31 of 35 shown/);
  assert.match(html, /26 more moments/); assert.match(html, /href="\/editorial"/);
  assert.doesNotMatch(html, /<article|Producer Mark Moment|<details open/);
  assert.equal((html.split("</table>")[0].match(/<tr>/g) ?? []).length, 6);
});
test("unchanged ranged review form omits adjustments; editing either value sends the range", () => {
  const candidate = fixtures.fixtureCandidate(1), commands: actions.EditorialCommand[] = [];
  const ui = harness("ReviewForm", { candidate, disabled: false, begin: (intent: actions.EditorialIntent) => commands.push(actions.prepareEditorialCommand(context(), intent, true)!) });
  ui.change("textarea", "editorial-reason", "Synthetic reason"); ui.submit();
  assert.equal("adjusted_timeline_start_microseconds" in commands[0].body, false);
  assert.equal("adjusted_timeline_end_microseconds" in commands[0].body, false);
  ui.change("input", "editorial-start", String(candidate.timeline_start_microseconds / 1_000_000 + 1)); ui.submit();
  assert.equal(commands[1].body.adjusted_timeline_start_microseconds, candidate.timeline_start_microseconds + 1_000_000);
  assert.equal(commands[1].body.adjusted_timeline_end_microseconds, candidate.timeline_end_microseconds);
  ui.change("input", "editorial-end", String(candidate.timeline_end_microseconds! / 1_000_000 + 2)); ui.submit();
  assert.equal(commands[2].body.adjusted_timeline_end_microseconds, candidate.timeline_end_microseconds! + 2_000_000);
});
for (const state of ["unreviewed", "deferred", "revision_requested", "approved", "rejected"] as const) test(`review default fits ${state} state`, () => {
  const candidate = { ...fixtures.fixtureCandidate(1), review_state: state };
  const consequences: string[] = [];
  const ui = harness("ReviewForm", { candidate, disabled: false, begin: (_intent: actions.EditorialIntent, consequence: string) => consequences.push(consequence) });
  const explicit = state === "approved" || state === "rejected";
  assert.equal(ui.find("select", "editorial-action").value, explicit ? "" : "approve_and_create_clip");
  assert.equal(nodes(ui.render()).filter((node) => node.type === "button" && node.props.type === "submit").length, 1);
  ui.change("textarea", "editorial-reason", "Synthetic reason"); ui.submit();
  assert.equal(consequences.length, explicit ? 0 : 1);
  if (explicit) {
    assert.equal(ui.find("button", "Choose a review action").disabled, true);
    ui.change("select", "editorial-action", "approve_and_create_clip");
    ui.submit(); assert.equal(consequences.length, 1);
  }
  assert.match(consequences[0], state === "approved" ? /^Create another Editorial Clip/ : /^Create an Editorial Clip/);
  if (state === "approved") assert.equal(ui.find("button", "Approve & create another clip").disabled, false);
});
function momentsFixture(state = "unreviewed") {
  const candidate = fixtures.fixtureCandidate(1);
  return { session_id: candidate.session_id, candidate_count: 1, latest_candidate_activity_at: null, generation_state: "healthy", location_conflict_count: 0, items: [{ ...candidate, review_state: state }], items_truncated: false, limit: 100 };
}
function momentsHarness() {
  const requests: { resolve: (value: unknown) => void; reject: (reason: Error) => void }[] = [];
  const ui = harness("SessionMoments", { sessionId: fixtures.fixtureCandidate(1).session_id, refreshToken: "initial" }, {
    file: "session-moments.tsx", client: api.editorialApi(() => new Promise((resolve, reject) => requests.push({ resolve, reject }))),
  });
  return { ui, requests };
}
test("background moments refresh keeps the table and has no refresh status; stable identity does not reread", async () => {
  const { ui, requests } = momentsHarness();
  assert.match(ui.html(), /Loading Editorial moments/);
  requests[0].resolve(momentsFixture()); await settle(); ui.render();
  const before = ui.html();
  ui.render(); assert.equal(requests.length, 1);
  ui.props.refreshToken = "new-identity"; ui.render();
  assert.equal(requests.length, 2); assert.equal(ui.html(), before);
  assert.doesNotMatch(ui.html(), /Refreshing|Loading/);
  requests[1].resolve(momentsFixture("approved")); await settle(); ui.render();
  assert.match(ui.html(), /1 approved/); assert.doesNotMatch(ui.html(), /Refreshing|stale since/);
});
test("transient refresh failure keeps last good moments and a stable stale-since note until recovery", async () => {
  const { ui, requests } = momentsHarness();
  requests[0].resolve(momentsFixture()); await settle(); ui.render();
  ui.props.refreshToken = "new-identity"; ui.render();
  requests[1].reject(new Error()); await settle(); ui.render();
  assert.match(ui.html(), /1 awaiting review/); assert.match(ui.html(), /<table/);
  assert.match(ui.html(), /<small role="status">Editorial moments stale since \d{2}:\d{2}:\d{2}<\/small>/);
  assert.doesNotMatch(ui.html(), /unavailable|Refreshing/);
  const stale = plain(ui.find("small").children);
  ui.props.refreshToken = "another-identity"; ui.render();
  requests[2].reject(new Error()); await settle(); ui.render();
  assert.equal(plain(ui.find("small").children), stale);
  ui.click("Reload moments");
  assert.match(ui.html(), /Refreshing Editorial moments/); assert.match(ui.html(), /1 awaiting review/);
  requests[3].resolve(momentsFixture("approved")); await settle(); ui.render();
  assert.match(ui.html(), /1 approved/); assert.doesNotMatch(ui.html(), /stale since|Refreshing/);
});
test("explicit reload alone shows refresh status and reads review-only changes", async () => {
  const { ui, requests } = momentsHarness();
  requests[0].resolve(momentsFixture()); await settle(); ui.render();
  ui.click("Reload moments");
  assert.equal(requests.length, 2); assert.match(ui.html(), /Refreshing Editorial moments/);
  assert.match(ui.html(), /<table/); assert.equal(ui.find("button", "Reload moments").disabled, true);
  requests[1].resolve(momentsFixture("approved")); await settle(); ui.render();
  assert.match(ui.html(), /1 approved/); assert.doesNotMatch(ui.html(), /Refreshing/);
  assert.equal(ui.find("button", "Reload moments").disabled, false);
});
test("initial moments failure offers reload; obsolete requests cannot replace the current Session", async () => {
  const { ui, requests } = momentsHarness();
  requests[0].reject(new Error()); await settle(); ui.render();
  assert.match(ui.html(), /Editorial moments unavailable/);
  ui.click("Reload moments");
  const sessionId = "00000000-0000-4000-8000-000000000099";
  ui.props.sessionId = sessionId; ui.render();
  requests[1].resolve(momentsFixture()); await settle(); ui.render();
  assert.match(ui.html(), /Loading Editorial moments/); assert.doesNotMatch(ui.html(), /<table/);
  requests[2].resolve({ ...momentsFixture(), session_id: sessionId, items: [{ ...fixtures.fixtureCandidate(1), session_id: sessionId }] });
  await settle(); ui.render(); assert.match(ui.html(), /1 awaiting review/);
});
test("phrase textarea publishes around blank lines but rejects punctuation-only and duplicate lines", () => {
  const commands: actions.EditorialCommand[] = [];
  const ui = harness("PhraseTools", { context: context(), sessions: fixtures.editorialFixtureSessions, disabled: false, refresh: 0, begin: (intent: actions.EditorialIntent) => commands.push(actions.prepareEditorialCommand(context(), intent, true)!) });
  ui.change("input", "phrase-name", "Synthetic list");
  ui.change("textarea", "phrase-text", "\n silver lantern \n\n Blue moon\n\n");
  assert.equal(ui.find("button", "Publish version").disabled, false); ui.submit(1);
  assert.deepEqual(commands[0].body.phrases, ["silver lantern", "Blue moon"]);
  for (const text of ["silver lantern\n\n!!!\n", "silver lantern\n\nSILVER LANTERN\n", "\n \n"]) {
    ui.change("textarea", "phrase-text", text);
    assert.equal(ui.find("button", "Publish version").disabled, true); ui.submit(1);
  }
  assert.equal(commands.length, 1);
});
test("derivation result renders one summary line with nonzero skips and identifiers only in details", async () => {
  const candidate = fixtures.fixtureCandidate(1), provenance = candidate.provenance!;
  const run = { run_id: provenance.run_id, session_id: candidate.session_id, phrase_list_id: provenance.phrase_list_id, phrase_list_version: 1, created_by: candidate.actor_id, created_at: candidate.created_at, input_asset_count: 4, candidate_ids: [candidate.candidate_moment_id], skip_counts: { no_transcript: 0, no_timing_evidence: 2, outside_session: 1, limit_reached: 0 } };
  const ui = harness("EditorialReviewSurface", surfaceProps(), { fetcher: async () => Response.json(run), client: api.editorialApi(async () => fixtures.fixtureQueue()) });
  (ui.child("PhraseTools").begin as (i: actions.EditorialIntent, c: string) => void)({ kind: "derive", sessionId: candidate.session_id, phraseListId: provenance.phrase_list_id, version: 1 }, "Create advisory candidates.");
  ui.render(); ui.submit(); await settle();
  ui.render();
  const tools = harness("PhraseTools", ui.child("PhraseTools"));
  const tree = tools.render();
  const summary = nodes(tree).filter((node) => node.type === "p" && plain(node.props.children).includes("skipped:"));
  assert.equal(summary.length, 1); assert.equal(summary[0].props.role, "status");
  assert.equal(plain(summary[0].props.children), "1 moment · 2 skipped: no timing evidence · 1 skipped: outside session");
  const result = nodes(tree).find((node) => node.type === "div" && Array.isArray(node.props.children) && node.props.children.includes(summary[0]));
  assert.ok(result);
  const html = renderToStaticMarkup(result);
  assert.doesNotMatch(html, /0 skipped|<br|<details[^>]*open/);
  const details = html.slice(html.indexOf("<details>")), visible = html.slice(0, html.indexOf("<details>"));
  for (const id of [run.run_id, run.phrase_list_id, ...run.candidate_ids]) {
    assert.ok(details.includes(id)); assert.ok(!visible.includes(id));
  }
  assert.match(details, /<summary>Details<\/summary>/);
});


test("Session groups keep first-seen order, compact Details, shared certainty and only review exceptions", () => {
  const props = surfaceProps();
  const second = { id: "00000000-0000-4000-8000-000000000099", title: "Synthetic closing Session" };
  props.sessions = [...props.sessions, second];
  const first = props.initialQueue.items[0];
  props.initialQueue.items.splice(1, 0, { ...first, candidate: { ...fixtures.fixtureCandidate(5), session_id: second.id } });
  const before = JSON.stringify(props.initialQueue);
  const ui = harness("EditorialReviewSurface", props);
  const tree = ui.render();
  const groups = nodes(tree).filter((n) => n.type === "section" && n.props.className === "editorial-session");
  assert.equal(groups.length, 2);
  assert.deepEqual(groups.map((g) => plain(nodes(g).find((n) => n.type === "h2")?.props.children)), props.sessions.map((s) => s.title));
  const rows = nodes(groups[0]).filter((n) => n.props.className === "editorial-row");
  assert.equal(rows.length, 3);
  for (const row of rows) {
    assert.ok(nodes(row).some((n) => typeof n.type === "function" && n.type.name === "CandidateDetails"));
    assert.doesNotMatch(plain(row), /Synthetic opening Session|Awaiting review/);
  }
  assert.match(plain(groups[0]), /All suggestions use recorder time \(unverified\)/);
  assert.doesNotMatch(rows.map(plain).join(""), /Recorder time/);
  assert.match(rows.map(plain).join(""), /Deferred/);
  const html = ui.html();
  assert.match(html, /Suggestions need human review. No review or clip approval is automatic/);
  assert.match(html, /<summary>Details<\/summary>.*origin.*declared.*review state.*unreviewed/);
  assert.doesNotMatch(html, /<details[^>]*\bopen/);
  assert.equal(JSON.stringify(props.initialQueue), before);
});

test("mixed suggestion timing stays on the affected row and never labels a marked moment", () => {
  const props = surfaceProps();
  props.initialQueue.items[2].candidate = fixtures.fixtureCandidate(3);
  const ui = harness("EditorialReviewSurface", props);
  const tree = ui.render();
  assert.doesNotMatch(plain(tree), /All suggestions use/);
  const rows = nodes(tree).filter((n) => n.props.className === "editorial-row");
  assert.doesNotMatch(plain(rows[0]), /Recorder time/);
  assert.match(plain(rows[1]), /Recorder time \(unverified\)/);
  assert.match(plain(rows[2]), /Recorder time \(verified\).*Outside Session|Outside Session.*Recorder time \(verified\)/);
});

test("mm:ss controls preserve fractional microseconds and the existing review command", () => {
  const candidate = { ...fixtures.fixtureCandidate(1), timeline_start_microseconds: 1123123456, timeline_end_microseconds: 1130000249 };
  const commands: actions.EditorialCommand[] = [];
  const ui = harness("ReviewForm", { candidate, disabled: false, begin: (intent: actions.EditorialIntent) => commands.push(actions.prepareEditorialCommand(context(), intent, true)!) });
  assert.equal(ui.find("input", "editorial-start").value, "18:43.123456");
  assert.equal(ui.find("input", "editorial-end").value, "18:50.000249");
  assert.match(ui.html(), /Start — time into Session \(mm:ss\)/);
  ui.change("textarea", "editorial-reason", "Synthetic review"); ui.submit();
  assert.equal("adjusted_timeline_start_microseconds" in commands[0].body, false);
  ui.change("input", "editorial-end", "19:01.000249"); ui.submit();
  assert.equal(commands[1].body.adjusted_timeline_end_microseconds, 1141000249);
  ui.change("input", "editorial-start", "18:60"); ui.submit();
  assert.equal(commands.length, 2);
});

test("derivation failures and successful results share the Run derivation control row", async () => {
  const ui = harness("EditorialReviewSurface", surfaceProps(), { fetcher: async () => Response.json({ detail: "synthetic_failure" }, { status: 422 }) });
  const candidate = fixtures.fixtureCandidate(1);
  (ui.child("PhraseTools").begin as (i: actions.EditorialIntent, c: string) => void)({ kind: "derive", sessionId: candidate.session_id, phraseListId: candidate.provenance!.phrase_list_id, version: 1 }, "Suggest moments.");
  ui.render(); ui.submit(); await settle(); ui.render();
  assert.doesNotMatch(plain(ui.render()), /synthetic_failure/);
  const tools = harness("PhraseTools", ui.child("PhraseTools"));
  const control = nodes(tools.render()).find((n) => n.props.className === "derivation-control");
  assert.ok(control);
  assert.match(plain(control), /Run derivation.*synthetic_failure/);
  assert.ok(nodes(control).some((n) => n.props.role === "status"));
});

test("Session moments expose a real Editorial review anchor and Suggested phrase", () => {
  const ui = harness("MomentsSummary", { moments: { session_id: fixtures.editorialFixtureSessions[0].id, candidate_count: 1, items: [fixtures.fixtureCandidate(1)], items_truncated: false } }, { file: "session-moments.tsx" });
  assert.equal(ui.find("a", "Editorial review").href, "/editorial");
  assert.match(ui.html(), /Suggested.*silver lantern/);
  assert.match(ui.html(), /<summary>Details<\/summary>[\s\S]*origin/);
});
