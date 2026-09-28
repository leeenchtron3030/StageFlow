import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { fixtureId as id } from "./session-outputs-fixtures.ts";
import { renderingApi, type RenderPreset, type RenderSettingHistory } from "./rendering-api.ts";
import { prepareQualityCommand, sendQualityCommand, videoChoices } from "./render-quality.ts";
import { renderQualityLabel, renderQualityLabels as labels, renderSettingProvenance } from "./ui-labels.ts";

const preset: RenderPreset = { profile_id: "h264-nvenc-1080p-video", profile_version: "3", width: 1920, height: 1080, video_bit_rate: 8000000, video_min: 6000000, video_max: 12000000, video_step: 500000, audio_bit_rate: 192000, audio_choices: [128000, 160000, 192000, 256000], default: true };
const history: RenderSettingHistory = { current: { event_id: id(3), version: null, profile_id: preset.profile_id, profile_version: "3", video_bit_rate: null, audio_bit_rate: null, effective_video_bit_rate: 8000000, effective_audio_bit_rate: 192000, selected_by: null, selected_at: null, command_id: null }, history: [] };

test("quality summary, bounded choices, normalization, and typed scope checks", async () => {
  assert.equal(renderQualityLabel(history.current), "1080p Standard · video 8 Mbit/s · audio 192 kbit/s");
  assert.equal(renderSettingProvenance(history.current), "Default");
  assert.deepEqual(videoChoices(preset), [6000000, 6500000, 7000000, 7500000, 8000000, 8500000, 9000000, 9500000, 10000000, 10500000, 11000000, 11500000, 12000000]);
  const command = prepareQualityCommand(history, preset, 8000000, 192000);
  assert.equal(command.video_bit_rate, null); assert.equal(command.audio_bit_rate, null);
  assert.equal(command.expected_version, null); assert.ok(Object.isFrozen(command));
  assert.throws(() => prepareQualityCommand(history, preset, 8000001, 192000));
  assert.throws(() => prepareQualityCommand(history, preset, 8000000, 193000));
  assert.deepEqual(await renderingApi(async () => history).setting(id(3)), history);
  await assert.rejects(renderingApi(async () => history).setting(id(4)), /scope_mismatch/);
});

test("quality commands preserve exact retry, stale refusal, and returned identity", async () => {
  const command = prepareQualityCommand(history, preset, 6500000, 128000);
  const bodies: string[] = [];
  const fetcher: typeof fetch = async (_url, init) => { bodies.push(String(init?.body)); throw new Error("synthetic"); };
  assert.equal((await sendQualityCommand(id(3), command, "synthetic", fetcher)).retry, true);
  await sendQualityCommand(id(3), command, "synthetic", fetcher);
  assert.equal(bodies[0], bodies[1]);
  const stale = await sendQualityCommand(id(3), command, "synthetic", async () => Response.json({ detail: "render_setting_changed" }, { status: 409 }));
  assert.equal(stale.retry, false); assert.equal(stale.message, labels.changed);
  const success = await sendQualityCommand(id(3), command, "synthetic", async () => Response.json({ ...history.current, version: 1, command_id: command.command_id }));
  assert.equal(success.message, labels.saved);
});

test("Event section shows summary first, offers bounded controls, confirms consequence first and collapses history", () => {
  const require = createRequire(import.meta.url);
  const source = readFileSync(new URL("../components/event-render-quality.tsx", import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS } });
  const slots: unknown[] = []; let cursor = 0;
  type Props = Record<string, unknown>;
  type Node = React.ReactElement<Props>;
  const exports: { EventRenderQuality?: (props: object) => Node } = {};
  const imports: Record<string, unknown> = {
    react: {
      useState(value: unknown) { const index = cursor++; if (!(index in slots)) slots[index] = value; return [slots[index], (next: unknown) => { slots[index] = next; }]; },
      useRef(value: unknown) { const index = cursor++; return slots[index] ??= { current: value }; },
    },
    "next/navigation": { useRouter: () => ({ refresh() {} }) },
  };
  runInNewContext(compiled.outputText, { exports, require: (name: string) => imports[name] ?? require(name) });
  const chosen = { ...history.current, version: 2, selected_by: id(9), selected_at: "2026-09-27T00:00:00Z", command_id: id(8) };
  const props = { history: { current: chosen, history: [chosen, { ...chosen, version: 1 }] }, presets: [preset], authorized: true, launchContext: "synthetic" };
  const render = () => { cursor = 0; return exports.EventRenderQuality!(props); };
  const nodes = (value: unknown): Node[] => Array.isArray(value) ? value.flatMap(nodes) : React.isValidElement<Props>(value) ? [value, ...nodes(value.props.children)] : [];
  let tree = render();
  let html = renderToStaticMarkup(tree);
  assert.match(html, /1080p Standard/); assert.match(html, /Chosen by/);
  assert.match(html, /<details><summary>Previous settings/); assert.doesNotMatch(html, /<details open/);
  const change = nodes(tree).find((node) => node.type === "button" && node.props.children === labels.change)!;
  (change.props.onClick as () => void)(); tree = render();
  const selects = nodes(tree).filter((node) => node.type === "select");
  assert.equal(selects.length, 3);
  assert.deepEqual(nodes(selects[1]).filter((node) => node.type === "option").map((node) => node.props.value), videoChoices(preset));
  assert.deepEqual(nodes(selects[2]).filter((node) => node.type === "option").map((node) => node.props.value), preset.audio_choices);
  (nodes(tree).find((node) => node.type === "form")!.props.onSubmit as (event: unknown) => void)({ preventDefault() {} });
  tree = render(); html = renderToStaticMarkup(tree);
  assert.match(html, /<form><p>Applies to renders requested from now on\. Existing outputs keep their quality\.<\/p>/);
  assert.match(html, /Confirm quality/);
});
