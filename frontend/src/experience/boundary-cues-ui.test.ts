import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { cueCurrentFixture, cueNoneFixture, cueCompositionFixture as current, cueCheckpointFixture } from "./boundary-cues-fixtures.ts";
import { boundaryCueLabels as labels } from "./ui-labels.ts";
import type { BoundaryCueData } from "./boundary-cues-api.ts";

type Props = Record<string, unknown>;
type Node = React.ReactElement<Props>;
function harness(data: BoundaryCueData | undefined = cueCurrentFixture, authorized = true, launchContext: string | undefined = "synthetic") {
  const require = createRequire(import.meta.url);
  const source = readFileSync(new URL("../components/event-boundary-cues.tsx", import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS } });
  const slots: unknown[] = []; let cursor = 0, refreshes = 0;
  const exports: { EventBoundaryCues?: (props: object) => Node } = {};
  const imports: Record<string, unknown> = {
    react: {
      useState(value: unknown) { const index = cursor++; if (!(index in slots)) slots[index] = value; return [slots[index], (next: unknown) => { slots[index] = next; }]; },
      useRef(value: unknown) { const index = cursor++; return slots[index] ??= { current: value }; },
      useSyncExternalStore(_subscribe: unknown, snapshot: () => string) { return snapshot(); },
    },
    "next/navigation": { useRouter: () => ({ refresh() { refreshes++; } }) },
  };
  runInNewContext(compiled.outputText, { exports, require: (name: string) => imports[name] ?? require(name) });
  const render = () => { cursor = 0; return exports.EventBoundaryCues!({ data, authorized, eventId: current.event_id, launchContext }); };
  const nodes = (value: unknown): Node[] => Array.isArray(value) ? value.flatMap(nodes) : React.isValidElement<Props>(value) ? [value, ...nodes(value.props.children)] : [];
  const find = (predicate: (n: Node) => boolean) => { const node = nodes(render()).find(predicate); assert.ok(node); return node; };
  const button = (label: string) => find((n) => n.type === "button" && n.props.children === label);
  const click = (label: string) => { const node = button(label); assert.ok(!node.props.disabled); (node.props.onClick as () => void)(); };
  const change = (id: string, value: string) => (find((n) => n.props.id === id).props.onChange as (e: unknown) => void)({ target: { value } });
  const submit = () => (find((n) => n.type === "form").props.onSubmit as (e: unknown) => void)({ preventDefault() {} });
  const action = (label: string) => (find((n) => n.props["aria-label"] === label).props.onClick as () => void)();
  const toggle = (name: string) => {
    const label = find((n) => n.type === "label" && Array.isArray(n.props.children) && n.props.children.includes(name));
    (nodes(label).find((n) => n.type === "input")!.props.onChange as () => void)();
  };
  return { render, nodes, find, button, click, change, submit, action, toggle, html: () => renderToStaticMarkup(render()), refreshes: () => refreshes };
}

test("none/current fixtures render summary first with collapsed provenance and readable names", () => {
  assert.match(harness(cueNoneFixture).html(), /Not set up — suggestions run without cue phrases/);
  const html = harness().html();
  assert.match(html, /Conference stage · 3 groups · 2 start \/ 2 end phrases · Composed/);
  assert.ok(html.indexOf("2 start / 2 end") < html.indexOf("<details"));
  assert.doesNotMatch(html, /<details[^>]*\bopen\b/);
  assert.match(html, /Version 1/); assert.match(html, /Operator ID/); assert.match(html, /Profile key/);
  assert.ok(html.includes(current.composed_by)); assert.ok(html.includes(current.catalog_id));
  const visible = html.slice(0, html.indexOf("<details"));
  for (const internal of [current.composed_by, current.catalog_id, current.command_id, current.catalog_digest]) assert.ok(!visible.includes(internal));
});

test("unauthorized or missing launch is read-only; catalog mismatch disables editing honestly", () => {
  for (const h of [harness(cueCurrentFixture, false), harness(cueCurrentFixture, true, "")]) {
    assert.equal(h.button(labels.edit).props.disabled, true); assert.match(h.html(), /Editing requires a live Event/);
    assert.equal(h.nodes(h.render()).filter((n) => n.type === "form").length, 0);
  }
  const h = harness({ ...cueCurrentFixture, current: { ...current, catalog_version: 2 } });
  assert.equal(h.button(labels.edit).props.disabled, true); assert.match(h.html(), /phrase counts are unavailable/);
});

test("editor shows categories, source and honest evidence badges, role disclosures and custom role choices", () => {
  const h = harness(cueCheckpointFixture); h.click(labels.edit);
  assert.match(h.html(), /<legend>Stage<\/legend>/); assert.match(h.html(), /<legend>Studio<\/legend>/);
  assert.match(h.html(), /2 default \/ 1 optional phrases/);
  for (const value of ["Between sessions", "Inside a session", "saved, not used for boundaries", labels.measured, labels.scripts, labels.warning, "Opening greetings", "Closing thanks"]) assert.ok(h.html().includes(value));
  assert.doesNotMatch(h.html(), /M 2\/2|R \[1\]/);
  assert.deepEqual(h.nodes(h.find((n) => n.props.id === "cue-custom-role")).filter((n) => n.type === "option").map((n) => n.props.value), ["start", "end", "changeover"]);
  assert.equal(h.nodes(h.render()).filter((n) => n.type === "input" && n.props.type === "checkbox" && n.props.checked).length, 3);
});

test("group picker puts selected groups first and folds other categories and regional add-ons into More groups", () => {
  const h = harness(cueCheckpointFixture); h.click(labels.edit);
  const selected = h.find((n) => n.props.className === "cue-groups cue-selected-groups");
  const more = h.find((n) => n.props.className === "cue-more-groups");
  assert.equal(more.props.open, undefined);
  const checkboxes = (n: Node) => h.nodes(n).filter((child) => child.props.type === "checkbox");
  assert.equal(checkboxes(selected).length, 3); assert.ok(checkboxes(selected).every((n) => n.props.checked));
  assert.equal(checkboxes(more).length, 4); assert.ok(checkboxes(more).every((n) => !n.props.checked));
  assert.deepEqual(h.nodes(more).filter((n) => n.type === "legend").map((n) => n.props.children), ["Stage", "Studio", "Regional add-ons (never pre-ticked)"]);
  assert.ok(h.html().indexOf("cue-selected-groups") < h.html().indexOf("cue-more-groups"));
  h.toggle("Regional greetings");
  assert.equal(checkboxes(h.find((n) => n.props.className === "cue-groups cue-selected-groups")).length, 4);
});

test("role lists use source headings, one compact row, also-in notes, one legend and exception-only badges", () => {
  const h = harness(); h.click(labels.edit); h.change("cue-custom", "Synthetic custom"); h.click(labels.addCustom);
  const roles = h.nodes(h.render()).filter((n) => n.type === "details" && n.props.className === "cue-role").slice(0, 4);
  assert.deepEqual(h.nodes(roles[1]).filter((n) => n.type === "h4").map((n) => n.props.children), ["Opening greetings"]);
  assert.equal(h.nodes(roles[1]).filter((n) => n.type === "li").length, 1);
  assert.match(renderToStaticMarkup(roles[1]), /also in 1 other groups/);
  assert.doesNotMatch(renderToStaticMarkup(roles[1]), /cue-badge/); // M + R is the measured default.
  assert.deepEqual(h.nodes(roles[0]).filter((n) => n.type === "h4").map((n) => n.props.children), ["Opening greetings", "Custom"]);
  const selectedRows = roles.flatMap((role) => h.nodes(role).filter((n) => n.type === "li"));
  for (const row of selectedRows) {
    assert.equal(row.props.className, "cue-phrase-line");
    assert.equal(h.nodes(row).filter((n) => n.type === "button").length, 1);
  }
  const badges = selectedRows.flatMap((row) => h.nodes(row).filter((n) => n.props.className === "cue-badge"));
  assert.deepEqual(badges.map((n) => n.props.children), [labels.scripts, labels.scripts]);
  assert.equal(h.html().split(labels.measured).length - 1, 1);
  assert.ok(h.html().includes(labels.evidenceLegend));
});

test("default Studio noisy phrases display the mid-talk exception", () => {
  const h = harness(cueCheckpointFixture); h.click(labels.edit); h.toggle("Studio: wraps"); h.toggle("Studio: slate and takes");
  for (const text of ["moving on", "rolling", "speed", "action", "cut", "reset"]) {
    const row = h.find((n) => n.type === "li" && h.nodes(n).some((child) => child.props["aria-label"] === `${labels.remove}: ${text}`));
    assert.ok(h.nodes(row).some((n) => n.props.className === "cue-badge" && n.props.children === labels.warning));
  }
});

test("Removed and Add back preserve removal across ticks and publish only backend choices", async () => {
  const original = globalThis.fetch; let body: Record<string, unknown> | undefined;
  globalThis.fetch = async (_url, init) => { body = JSON.parse(String(init?.body)); return Response.json({ ...current, command_id: body!.command_id }); };
  try {
    const h = harness(cueCheckpointFixture); h.click(labels.edit);
    h.action(`${labels.remove}: Our shared phrase`);
    let removed = h.find((n) => n.props.className === "cue-role cue-removed");
    assert.equal(removed.props.open, undefined); assert.match(renderToStaticMarkup(removed), /Removed · 1/);
    assert.equal(h.nodes(removed).filter((n) => n.type === "li").length, 1);
    h.toggle("Extra greetings"); assert.match(h.html(), /1 removed phrase stays removed/);
    assert.equal(h.nodes(h.render()).filter((n) => n.props["aria-label"] === `${labels.remove}: Our shared phrase`).length, 0);
    h.action(`${labels.addBack}: Our shared phrase`);
    assert.doesNotMatch(h.html(), /removed phrases stay removed/);
    removed = h.find((n) => n.props.className === "cue-role cue-removed");
    assert.match(renderToStaticMarkup(removed), /Removed · 0/);
    assert.match(h.html(), /also in 2 other groups/);
    h.submit(); h.submit(); await new Promise((resolve) => setTimeout(resolve, 0));
    assert.ok(body); assert.deepEqual(body.exclude, []);
    assert.deepEqual(body.group_keys, ["openings", "closings", "inside", "extra"]);
    assert.deepEqual(Object.keys(body).sort(), ["authority_kind", "catalog_version", "command_id", "custom_phrases", "exclude", "group_keys", "include", "profile_key"]);
  } finally { globalThis.fetch = original; }
});

test("draft summary and review say Custom after each edit kind; stored provenance uses the same rule", () => {
  const edits = [
    (h: ReturnType<typeof harness>) => h.toggle("Studio takes"),
    (h: ReturnType<typeof harness>) => h.action("Add phrase: Optional welcome (Opening greetings)"),
    (h: ReturnType<typeof harness>) => h.action("Remove phrase: Hello everyone"),
    (h: ReturnType<typeof harness>) => { h.change("cue-custom", "Synthetic custom"); h.click(labels.addCustom); },
  ];
  for (const edit of edits) {
    const h = harness(); h.click(labels.edit); edit(h);
    assert.match(h.html(), /<strong>Custom \(based on Conference stage\)/);
    h.submit(); assert.match(renderToStaticMarkup(h.find((n) => n.type === "form")), /Custom \(based on Conference stage\)/);
  }
  const h = harness(); h.click(labels.edit); h.submit();
  assert.doesNotMatch(h.html(), /Custom \(based on/);
  for (const changes of [{ groups: current.groups.slice(0, 2) }, { include: [{ group_key: "openings", phrase: "Optional welcome" }] },
    { exclude: [{ group_key: "openings", phrase: "Hello everyone" }] }, { custom_phrases: [{ text: "Synthetic custom", role: "start" as const }] }]) {
    assert.match(harness({ ...cueCurrentFixture, current: { ...current, ...changes } }).html(), /<strong>Custom \(based on Conference stage\)/);
  }
});

test("profile switching requires confirmation for edits and can keep or reset them", () => {
  const h = harness(); h.click(labels.edit);
  h.change("cue-custom", "Synthetic custom"); h.click(labels.addCustom);
  h.change("cue-profile", "small"); assert.match(h.html(), /Switching profile resets/);
  assert.equal(h.button(labels.publish).props.disabled, true);
  h.click(labels.keepEditing); assert.match(h.html(), /Synthetic custom/);
  h.change("cue-profile", "small"); h.click(labels.confirmProfile);
  assert.doesNotMatch(h.html(), /Synthetic custom/);
  assert.equal(h.nodes(h.render()).filter((n) => n.type === "input" && n.props.type === "checkbox" && n.props.checked).length, 2);
  h.change("cue-profile", "conference"); assert.doesNotMatch(h.html(), /Switching profile resets/);
  assert.equal(h.nodes(h.render()).filter((n) => n.type === "input" && n.props.type === "checkbox" && n.props.checked).length, 3);
});

test("saved phrase edits require profile-reset confirmation and unadded text blocks publication", () => {
  const h = harness({ ...cueCurrentFixture, current: { ...current, custom_phrases: [{ text: "Saved synthetic phrase", role: "start" }] } });
  h.click(labels.edit); h.change("cue-profile", "small");
  assert.match(h.html(), /Switching profile resets/); h.click(labels.keepEditing);
  h.change("cue-custom", "Unadded phrase");
  assert.equal(h.button(labels.publish).props.disabled, true); assert.ok(h.html().includes(labels.pendingCustom));
  h.change("cue-custom", ""); assert.equal(h.button(labels.publish).props.disabled, false);
});

test("phrase actions update counters and block publishing empty lists", () => {
  const h = harness(); h.click(labels.edit);
  const remove = (text: string) => (h.find((n) => n.props["aria-label"] === `${labels.remove}: ${text}`).props.onClick as () => void)();
  remove("Our shared phrase"); assert.match(h.html(), /Start: 1 \/ 200 · End: 1 \/ 200/);
  remove("Hello everyone"); assert.match(h.html(), /Start: 0 phrases/); assert.equal(h.button(labels.publish).props.disabled, true);
  h.change("cue-custom", "New greeting"); h.click(labels.addCustom); assert.equal(h.button(labels.publish).props.disabled, false);
  const optional = h.find((n) => n.props["aria-label"] === "Add phrase: Optional welcome (Opening greetings)");
  (optional.props.onClick as () => void)(); assert.match(h.html(), /Start: 2 \/ 200 · End: 2 \/ 200/);
});

test("publish requires separate confirmation, sends only then, and refreshes after success", async () => {
  const original = globalThis.fetch; const bodies: Record<string, unknown>[] = [];
  globalThis.fetch = async (_url, init) => {
    const command = JSON.parse(String(init?.body)); bodies.push(command);
    return Response.json({ ...current, command_id: command.command_id, version: 2 });
  };
  try {
    const h = harness(); h.click(labels.edit); h.submit();
    assert.equal(bodies.length, 0); assert.match(h.html(), /Publish these phrases for future suggestion runs/);
    assert.ok(h.button(labels.confirm)); h.click(labels.back); assert.equal(bodies.length, 0);
    h.submit(); h.submit(); h.submit();
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(bodies.length, 1); assert.equal(h.refreshes(), 1); assert.match(h.html(), /Boundary cue phrases published/);
  } finally { globalThis.fetch = original; }
});

test("publication refusal is readable and leaves edits for correction; history paging is explicit", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => Response.json({ detail: { code: "cue_list_too_large", role: "end", count: 205 } }, { status: 422 });
  try {
    const h = harness(); h.click(labels.edit); h.submit(); h.submit();
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.match(h.html(), /End: 205 phrases/); assert.ok(h.button(labels.publish)); assert.equal(h.refreshes(), 0);
    const paged = harness({ ...cueCurrentFixture, history: { items: [current], limit: 50, next_after: 1 } });
    globalThis.fetch = async (url) => {
      assert.match(String(url), /boundary-cues\/history\?after=1&limit=50/);
      return Response.json({ items: [{ ...current, version: 2 }], limit: 50, next_after: null });
    };
    paged.click(labels.moreHistory); await new Promise((resolve) => setTimeout(resolve, 0));
    assert.match(paged.html(), /Version 2/); assert.doesNotMatch(paged.html(), /Load more versions/);
  } finally { globalThis.fetch = original; }
});
