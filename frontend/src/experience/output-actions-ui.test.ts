import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as commands from "./output-actions.ts";
import { fixtureAssembly, fixtureId as id } from "./session-outputs-fixtures.ts";

const require = createRequire(import.meta.url);
const source = readFileSync(new URL("../components/session-output-actions.tsx", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS } });
const context = (): commands.OutputActionContext => ({ eventId: id(3), sessionId: id(2), packageRevision: 1, launchContext: "synthetic-launch", operatorAvailable: true, authoritative: true, fixture: false, assembly: { state: "available", value: fixtureAssembly() } });
type Props = Record<string, unknown>;
type Node = React.ReactElement<Props>;
function nodes(value: unknown): Node[] {
  if (Array.isArray(value)) return value.flatMap(nodes);
  return React.isValidElement<Props>(value) ? [value, ...nodes(value.props.children)] : [];
}
const settle = () => new Promise<void>((resolve) => setImmediate(resolve));

/** Invoke real event handlers with deterministic hook state; native dialog owns focus trapping. */
function harness(initial: commands.OutputActionContext, fetcher: typeof fetch) {
  const slots: unknown[] = [], effects: Array<() => void> = [];
  let cursor = 0, tree: Node, refreshes = 0, focuses = 0, shows = 0, reads = 0;
  const nativeDialog = { open: false, showModal() { this.open = true; shows++; }, close() { this.open = false; } };
  const exports: { SessionOutputActions?: (props: { context: commands.OutputActionContext }) => Node } = {};
  const imports: Record<string, unknown> = {
    react: {
      useState(initial: unknown) {
        const index = cursor++; if (!(index in slots)) slots[index] = initial;
        return [slots[index], (value: unknown) => { slots[index] = typeof value === "function" ? value(slots[index]) : value; }];
      },
      useRef(initial: unknown) { const index = cursor++; return slots[index] ??= { current: initial }; },
      useEffect(effect: () => void, dependencies: unknown[]) {
        const index = cursor++, previous = slots[index] as unknown[] | undefined;
        if (!previous || dependencies.some((value, i) => value !== previous[i])) effects.push(effect);
        slots[index] = dependencies;
      },
      useTransition: () => [false, (work: () => void) => work()],
    },
    "next/navigation": { useRouter: () => ({ refresh() { refreshes++; } }) },
    "../experience/output-actions.ts": commands,
    "../experience/assembly-api.ts": { assemblyApi: () => ({ templates: async (eventId: string) => {
      reads++; assert.equal(eventId, id(3));
      return { event_id: id(3), items: [{ template_id: id(5), event_id: id(3), name: "Event template", version: 2 }], total_count: 1, next_after: null };
    } }) },
  };
  runInNewContext(compiled.outputText, { exports, fetch: fetcher, require: (name: string) => imports[name] ?? require(name) });
  const api = {
    context: initial,
    render() {
      cursor = 0; tree = exports.SessionOutputActions!({ context: api.context });
      for (const node of nodes(tree)) {
        const ref = node.props.ref as { current: unknown } | undefined;
        if (ref) ref.current = node.type === "dialog" ? nativeDialog : { focus() { focuses++; } };
      }
      effects.splice(0).forEach((effect) => effect());
      return tree;
    },
    find(type: string, text?: string) {
      const node = nodes(tree).find((node) => node.type === type && (text === undefined || node.props.children === text || node.props.id === text));
      assert.ok(node, `${type} ${text ?? ""}`); return node.props;
    },
    click(text: string) { (api.find("button", text).onClick as () => void)(); api.render(); },
    change(type: string, id: string, value: string) { (api.find(type, id).onChange as (event: unknown) => void)({ target: { value } }); api.render(); },
    submit() { (api.find("form").onSubmit as (event: unknown) => void)({ preventDefault() {} }); api.render(); },
    stats: () => ({ refreshes, focuses, shows, reads, open: nativeDialog.open }),
    html: () => renderToStaticMarkup(tree),
  };
  api.render(); return api;
}

test("decision dialog gates submission, names exceptions, cancels with focus restoration, and submits only on confirmation", async () => {
  let calls = 0;
  const ui = harness(context(), async () => { calls++; return Response.json({ decision_id: id(20) }); });
  assert.equal(calls, 0); assert.equal(ui.stats().open, false);
  ui.click("Approve / Reject");
  assert.equal(ui.stats().shows, 1); assert.equal(ui.stats().open, true);
  assert.equal(ui.find("button", "Confirm approval").disabled, true);
  ui.submit(); assert.equal(calls, 0);
  assert.match(ui.html(), /registration_time fallback: member positions 3/);
  assert.match(ui.html(), /Unqualified timing evidence/); assert.match(ui.html(), /Bound packaging: opening/);
  assert.equal(ui.find("dialog")["aria-labelledby"], "output-confirm-title");
  assert.equal(ui.find("button", "Cancel").autoFocus, true);
  let prevented = false;
  (ui.find("dialog").onCancel as (event: unknown) => void)({ preventDefault() { prevented = true; } }); ui.render();
  assert.equal(prevented, true); assert.equal(ui.stats().open, false); assert.ok(ui.stats().focuses > 0);
  ui.click("Approve / Reject"); ui.change("select", "output-decision", "reject");
  ui.change("textarea", "output-reason", "Checked the synthetic order");
  assert.equal(ui.find("button", "Confirm rejection").disabled, false);
  ui.submit(); ui.submit(); await settle(); ui.render();
  assert.equal(calls, 1); assert.equal(ui.stats().open, false); assert.equal(ui.stats().refreshes, 1);
  assert.match(ui.html(), /Assembly revision rejected/); assert.match(ui.html(), /Result details/); assert.match(ui.html(), new RegExp(id(20)));
});
test("proposal loads Event-scoped templates only when opened, requires selection and carries chosen template", async () => {
  const ctx = context(); ctx.assembly = { state: "available", value: null };
  const bodies: Record<string, unknown>[] = [];
  const ui = harness(ctx, async (_url, init) => { bodies.push(JSON.parse(String(init?.body))); return Response.json({ revision_id: id(21) }); });
  assert.equal(ui.stats().reads, 0); ui.click("Propose revision");
  assert.equal(bodies.length, 0); await settle(); ui.render(); assert.equal(ui.stats().reads, 1);
  assert.equal(ui.find("button", "Confirm proposal").disabled, true);
  ui.change("select", "output-template", id(5)); assert.equal(ui.find("button", "Confirm proposal").disabled, false);
  ui.submit(); await settle(); ui.render();
  assert.equal(bodies.length, 1); assert.equal(bodies[0].template_id, id(5)); assert.equal(bodies[0].expected_revision, 0);
});
test("state changes invalidate an open confirmation; disabled states explain why", () => {
  const ui = harness(context(), async () => { assert.fail("must not submit"); });
  ui.click("Approve / Reject"); ui.change("textarea", "output-reason", "Checked");
  ui.context = { ...ui.context, packageRevision: 2 }; ui.render(); ui.submit();
  assert.match(ui.html(), /State changed. Cancel and review/); assert.equal(ui.find("button", "Confirm approval").disabled, true);
  for (const patch of [{ launchContext: undefined }, { operatorAvailable: false }, { authoritative: false }, { fixture: true }]) {
    const disabled = harness({ ...context(), ...patch }, async () => { assert.fail("disabled control submitted"); });
    assert.equal(disabled.find("button", "Approve / Reject").disabled, true);
    disabled.click("Approve / Reject"); assert.equal(disabled.stats().open, false); assert.match(disabled.html(), /Commands unavailable:/);
  }
});
test("UI conflict refreshes once without retry; network failure offers same-command retry only", async () => {
  for (const conflict of [true, false]) {
    const bodies: string[] = [];
    const ui = harness(context(), async (_url, init) => {
      bodies.push(String(init?.body));
      if (conflict) return Response.json({ detail: "assembly_revision_conflict" }, { status: 409 });
      if (bodies.length === 1) throw new TypeError("network failure");
      return Response.json({ decision_id: id(20) });
    });
    ui.click("Approve / Reject"); ui.change("textarea", "output-reason", "Checked"); ui.submit(); await settle(); ui.render();
    assert.equal(bodies.length, 1);
    if (conflict) { assert.equal(ui.stats().refreshes, 1); assert.match(ui.html(), /assembly_revision_conflict/); assert.doesNotMatch(ui.html(), /Retry same command/); }
    else { assert.equal(ui.stats().refreshes, 0); ui.click("Retry same command"); await settle(); ui.render(); assert.equal(bodies.length, 2); assert.equal(bodies[0], bodies[1]); }
  }
});
