import assert from "node:assert/strict";
import { test } from "node:test";
import { nextOutputAction, outputActionDisabled, outputConfirmation, prepareOutputCommand, sendOutputCommand, type OutputActionContext } from "./output-actions.ts";
import { fixtureAssembly, fixtureId as id } from "./session-outputs-fixtures.ts";
import { demoLaunchContextHeader } from "./demo-launch-context.ts";

const context = (): OutputActionContext => ({ eventId: id(3), sessionId: id(2), packageRevision: 1, launchContext: "synthetic-launch-context", operatorAvailable: true, authoritative: true, fixture: false, assembly: { state: "available", value: fixtureAssembly() } });
const cryptoSource = { randomUUID: () => id(99), getRandomValues: (bytes: Uint8Array) => bytes };
test("proposal body uses expected Assembly and package revisions, chosen template and UUID v4", () => {
  const ctx = context(); ctx.assembly = { state: "available", value: null };
  const command = prepareOutputCommand(ctx, "propose", true, { templateId: id(5), cryptoSource })!;
  assert.equal(command.path, `/api/stageflow/assembly/sessions/${id(2)}/revisions`);
  assert.deepEqual(command.body, { operation_id: id(99), confirmed: "confirmed", template_id: id(5), expected_revision: 0, expected_package_revision: 1 });
  assert.ok(Object.isFrozen(command)); assert.ok(Object.isFrozen(command.body));
  const item = fixtureAssembly(); item.stale = true; ctx.assembly = { state: "available", value: item }; ctx.packageRevision = 2;
  const next = prepareOutputCommand(ctx, "propose", true, { templateId: id(5), cryptoSource })!;
  assert.equal(next.body.expected_revision, 2); assert.equal(next.body.expected_package_revision, 2);
  const random = prepareOutputCommand(ctx, "propose", true, { templateId: id(5) })!;
  assert.match(String(random.body.operation_id), /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/);
});
for (const action of ["approve", "reject"] as const) test(`${action} requires confirmation and reason and sends exact concurrency body`, () => {
  const ctx = context();
  for (const reason of [undefined, "", "  ", "a".repeat(501)]) assert.equal(prepareOutputCommand(ctx, action, true, { reason }), undefined);
  assert.equal(prepareOutputCommand(ctx, action, false, { reason: "Checked" }), undefined);
  const command = prepareOutputCommand(ctx, action, true, { reason: " Checked ", cryptoSource })!;
  assert.equal(command.path, `/api/stageflow/assembly/sessions/${id(2)}/approvals`);
  assert.deepEqual(command.body, { operation_id: id(99), confirmed: "confirmed", revision_number: 2, expected_revision: 2, expected_decision_count: 0, action, reason: "Checked" });
});
test("render requires approval and sends explicit default v2 with command_id", () => {
  const ctx = context(), item = fixtureAssembly();
  assert.equal(prepareOutputCommand(ctx, "render", true), undefined);
  item.approval_state = "approved"; ctx.assembly = { state: "available", value: item };
  const command = prepareOutputCommand(ctx, "render", true, { cryptoSource })!;
  assert.equal(command.path, "/api/stageflow/rendering/requests");
  assert.deepEqual(command.body, { command_id: id(99), confirmed: "confirmed", assembly_revision_id: id(1), profile_id: "h264-nvenc-1080p-video", profile_version: "2", authority_kind: "human" });
  assert.equal(prepareOutputCommand(ctx, "render", false), undefined);
  item.stale = true; assert.equal(prepareOutputCommand(ctx, "render", true), undefined);
});
test("proposal selection and confirmation gate UUID creation", () => {
  const ctx = context(); ctx.assembly = { state: "available", value: null };
  const never = { ...cryptoSource, randomUUID: () => { assert.fail("must not generate a command before confirmation"); } };
  assert.equal(prepareOutputCommand(ctx, "propose", false, { templateId: id(5), cryptoSource: never }), undefined);
  assert.equal(prepareOutputCommand(ctx, "propose", true, { cryptoSource: never }), undefined);
  assert.equal(prepareOutputCommand(ctx, "propose", true, { templateId: "invalid", cryptoSource: never }), undefined);
});
test("confirmations lead with consequences and explicitly name ordering exceptions and bound packaging", () => {
  for (const action of ["approve", "reject", "render"] as const) {
    const text = outputConfirmation(action, fixtureAssembly(), 1);
    assert.match(text.split("\n")[0], action === "render" ? /^Queue a video-only render.*revision 2.*profile v2/ : new RegExp(`^${action === "approve" ? "Approve" : "Reject"} Assembly revision 2.*frozen member order and bound packaging`));
    assert.match(text, /registration_time fallback: member positions 3/);
    assert.match(text, /Unqualified timing evidence.*member positions 2.*advisory only/);
    assert.match(text, /Bound packaging: opening/);
  }
  const proposal = outputConfirmation("propose", null, 4, "Event opening");
  assert.match(proposal.split("\n")[0], /^Freeze.*package revision 4.*Event opening/);
  assert.match(proposal, /registration_time.*unqualified timing evidence/);
});
test("one primary action follows state; rejected revisions cannot render", () => {
  assert.equal(nextOutputAction(null), "propose");
  const item = fixtureAssembly(); assert.equal(nextOutputAction(item), "approve");
  item.approval_state = "approved"; assert.equal(nextOutputAction(item), "render");
  item.stale = true; assert.equal(nextOutputAction(item), "propose");
  item.stale = false; item.revision.validation.state = "invalid"; assert.equal(nextOutputAction(item), "propose");
  item.revision.validation.state = "valid"; item.approval_state = "rejected";
  const ctx = context(); ctx.assembly = { state: "available", value: item };
  assert.match(outputActionDisabled(ctx, "render")!, /not approved/);
  assert.equal(nextOutputAction(item), "propose");
  assert.equal(outputActionDisabled(ctx, "propose"), undefined);
  item.approval_state = "revoked";
  assert.equal(nextOutputAction(item), "propose");
  assert.equal(outputActionDisabled(ctx, "propose"), undefined);
});
test("launch, operator, fixture, unavailable, historical, scope, stale and reviewed states are disabled with reasons", () => {
  const patches: Partial<OutputActionContext>[] = [{ launchContext: undefined }, { operatorAvailable: false }, { authoritative: false }, { fixture: true }, { assembly: { state: "unavailable" } }, { sessionId: id(9) }, { packageRevision: 0 }];
  for (const patch of patches) {
    const ctx = { ...context(), ...patch };
    assert.ok(outputActionDisabled(ctx, "approve"));
    assert.equal(prepareOutputCommand(ctx, "approve", true, { reason: "Checked" }), undefined);
  }
  for (const change of [(item: ReturnType<typeof fixtureAssembly>) => { item.stale = true; }, (item: ReturnType<typeof fixtureAssembly>) => { item.current_revision_number = 3; }, (item: ReturnType<typeof fixtureAssembly>) => { item.approval_state = "approved"; }, (item: ReturnType<typeof fixtureAssembly>) => { item.revision.package_revision = 9; }]) {
    const ctx = context(), item = fixtureAssembly(); change(item); ctx.assembly = { state: "available", value: item };
    assert.ok(outputActionDisabled(ctx, "approve"));
  }
});
test("network failure permits explicit same-command retry; no automatic request or ID replacement", async () => {
  const command = prepareOutputCommand(context(), "approve", true, { reason: "Checked", cryptoSource })!;
  const bodies: string[] = []; let refreshed = 0;
  const fetcher: typeof fetch = async (url, init) => {
    assert.equal(url, command.path); assert.equal(new Headers(init?.headers).get(demoLaunchContextHeader), "synthetic-launch-context");
    assert.equal(new Headers(init?.headers).has("x-stageflow-api-secret"), false);
    bodies.push(String(init?.body)); if (bodies.length === 1) throw new TypeError("synthetic network failure");
    return Response.json({ decision_id: id(8) });
  };
  const first = await sendOutputCommand(command, fetcher, () => refreshed++);
  assert.equal(first.kind, "network_failure"); assert.equal(bodies.length, 1); assert.equal(refreshed, 0);
  const retry = await sendOutputCommand(command, fetcher, () => refreshed++);
  assert.equal(retry.kind, "succeeded"); assert.equal(retry.identifier, id(8)); assert.equal(refreshed, 1);
  assert.equal(bodies[0], bodies[1]);
});
for (const status of [409, 422, 500, 503]) test(`HTTP ${status} is never retried; conflict refreshes and shows bounded code`, async () => {
  const command = prepareOutputCommand(context(), "reject", true, { reason: "Checked" })!;
  let calls = 0, refreshes = 0;
  const result = await sendOutputCommand(command, async () => { calls++; return Response.json({ detail: "assembly_revision_conflict" }, { status }); }, () => refreshes++);
  assert.equal(calls, 1); assert.equal(refreshes, status === 409 ? 1 : 0);
  assert.equal(result.kind, status === 409 ? "conflict" : status < 500 ? "rejected" : "failed");
  assert.match(result.message, /assembly_revision_conflict/);
});
test("unbounded HTTP error text is not displayed; malformed success is refreshed without retry", async () => {
  const command = prepareOutputCommand(context(), "approve", true, { reason: "Checked" })!;
  const result = await sendOutputCommand(command, async () => Response.json({ detail: "private operator free text" }, { status: 409 }), () => {});
  assert.match(result.message, /http_409/); assert.doesNotMatch(result.message, /private/);
  let refreshes = 0;
  assert.equal((await sendOutputCommand(command, async () => new Response("not JSON"), () => refreshes++)).kind, "failed");
  assert.equal(refreshes, 1);
});
