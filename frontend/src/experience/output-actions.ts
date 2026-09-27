import type { AssemblyItem } from "./assembly-api.ts";
import type { SessionOutputs } from "./session-outputs.ts";
import { demoAuthorityHeaders } from "./demo-launch-context.ts";
import { generateUuidV4, type UuidCryptoSource } from "../shared/ids/uuid-v4.ts";
import { idSchema } from "./outputs-api.ts";

export type OutputAction = "propose" | "approve" | "reject" | "render";
export interface OutputActionContext {
  eventId: string;
  sessionId: string;
  packageRevision: number;
  launchContext?: string;
  operatorAvailable: boolean;
  authoritative: boolean;
  fixture: boolean;
  assembly: SessionOutputs["assembly"];
  operations?: SessionOutputs["operations"];
  outputs?: SessionOutputs["outputs"];
}
export function nextOutputAction(item: AssemblyItem | null): OutputAction {
  if (!item || item.stale || item.revision.validation.state !== "valid") return "propose";
  if (item.approval_state === "unreviewed") return "approve";
  // A rejected or revoked revision is not usable: the next step is a new proposal.
  if (item.approval_state === "rejected" || item.approval_state === "revoked") return "propose";
  return "render";
}
export function outputActionDisabled(context: OutputActionContext, action: OutputAction): string | undefined {
  if (context.fixture || !context.authoritative) return "Commands unavailable: live authoritative Session state is required.";
  if (!context.launchContext) return "Commands unavailable: current launcher context is unavailable.";
  if (!context.operatorAvailable) return "Commands unavailable: operator identity is not configured.";
  if (context.assembly.state !== "available") return "Commands unavailable: refresh Assembly state first.";
  if (!idSchema.safeParse(context.sessionId).success || !idSchema.safeParse(context.eventId).success || !Number.isSafeInteger(context.packageRevision) || context.packageRevision < 1) return "Commands unavailable: Session identity or package revision is unavailable.";
  const item = context.assembly.value;
  if (item && (item.revision.session_id !== context.sessionId || item.revision.event_id !== context.eventId || item.current_revision_number !== item.revision.revision_number)) return "Commands unavailable: refresh the current Assembly revision.";
  if (action === "propose") return nextOutputAction(item) === "propose" ? undefined : "A current valid revision already exists.";
  if (!item || item.stale || item.revision.package_revision !== context.packageRevision || item.revision.validation.state !== "valid") return "A current valid, non-stale revision is required.";
  if (action === "render") return item.approval_state === "approved" ? undefined : "Render unavailable: this revision is not approved.";
  return item.approval_state === "unreviewed" ? undefined : "This revision has already been reviewed.";
}

export function outputConfirmation(action: OutputAction, item: AssemblyItem | null, packageRevision: number, templateName?: string): string {
  const number = item?.revision.revision_number;
  const consequence = action === "propose"
    ? `Freeze a new Assembly proposal from package revision ${packageRevision} using ${templateName ?? "the selected Event template"}.`
    : action === "render" ? `Queue a video-only render of approved Assembly revision ${number} using profile v2.`
    : `${action === "approve" ? "Approve" : "Reject"} Assembly revision ${number}, including its frozen member order and bound packaging.`;
  if (action === "propose") return `${consequence}\nMember order and bound packaging will be frozen using the selected Event template. Members may use registration_time fallback or unqualified timing evidence; review the resulting revision before approval.`;
  const members = item?.revision.membership ?? [];
  const fallback = members.flatMap((m, i) => m.order_source === "registration_time" ? [i + 1] : []);
  const unqualified = members.flatMap((m, i) => m.order_source === "timing_evidence" && m.order_evidence_qualification !== "qualified" ? [i + 1] : []);
  const packaging = item?.revision.bindings.filter((b) => b.outcome === "bound") ?? [];
  return [consequence,
    fallback.length ? `registration_time fallback: member positions ${fallback.join(", ")}; registration is not captured-content time.` : "",
    unqualified.length ? `Unqualified timing evidence (not qualified): member positions ${unqualified.join(", ")}; advisory only.` : "",
    `Bound packaging: ${packaging.length ? packaging.map((b) => b.slot_key).join(", ") : "none"}.`,
  ].filter(Boolean).join("\n");
}

export interface PreparedOutputCommand {
  action: OutputAction;
  path: string;
  body: Readonly<Record<string, unknown>>;
  launchContext: string;
}
/** Called only after the operator confirms. Assembly names its command ID operation_id. */
export function prepareOutputCommand(context: OutputActionContext, action: OutputAction, confirmed: boolean, options: { templateId?: string; reason?: string; cryptoSource?: UuidCryptoSource } = {}): PreparedOutputCommand | undefined {
  if (!confirmed || outputActionDisabled(context, action)) return undefined;
  const item = context.assembly.state === "available" ? context.assembly.value : null;
  const reason = options.reason?.trim();
  if (action === "propose" && !idSchema.safeParse(options.templateId).success) return undefined;
  if ((action === "approve" || action === "reject") && (!reason || reason.length > 500)) return undefined;
  const commandId = generateUuidV4(options.cryptoSource);
  const body = action === "propose" ? { operation_id: commandId, confirmed: "confirmed", template_id: options.templateId!, expected_revision: item?.current_revision_number ?? 0, expected_package_revision: context.packageRevision }
    : action === "render" ? { command_id: commandId, confirmed: "confirmed", assembly_revision_id: item!.revision.revision_id, profile_id: "h264-nvenc-1080p-video", profile_version: "2", authority_kind: "human" }
    : { operation_id: commandId, confirmed: "confirmed", revision_number: item!.revision.revision_number, expected_revision: item!.current_revision_number, expected_decision_count: item!.decision_count, action, reason };
  return Object.freeze({ action, path: action === "render" ? "/api/stageflow/rendering/requests" : `/api/stageflow/assembly/sessions/${context.sessionId}/${action === "propose" ? "revisions" : "approvals"}`, body: Object.freeze(body), launchContext: context.launchContext! });
}

export type OutputCommandResult = { kind: "succeeded" | "rejected" | "conflict" | "failed" | "network_failure"; message: string; identifier?: string };
/** No automatic retries. Only a transport failure permits an explicit retry of this object. */
export async function sendOutputCommand(command: PreparedOutputCommand, fetcher: typeof fetch, refresh: () => void): Promise<OutputCommandResult> {
  let response: Response;
  try {
    response = await fetcher(command.path, { method: "POST", cache: "no-store", redirect: "error", headers: demoAuthorityHeaders(command.launchContext), body: JSON.stringify(command.body) });
  } catch { return { kind: "network_failure", message: "Connection lost; outcome unknown. Retry the same command." }; }
  let payload: Record<string, unknown> = {};
  try { payload = await response.json(); } catch { /* Never retry an HTTP response. */ }
  const detail = payload?.detail;
  const code = typeof detail === "string" && /^[a-z][a-z0-9_]{0,95}$/.test(detail) ? detail : `http_${response.status}`;
  if (response.status === 409) { refresh(); return { kind: "conflict", message: `State changed (${code}); refreshing. Review before acting again.` }; }
  if (!response.ok) return { kind: response.status >= 500 ? "failed" : "rejected", message: `Command not confirmed (${code}).` };
  const identifier = command.action === "render" ? payload?.operation_id : command.action === "propose" ? payload?.revision_id : payload?.decision_id;
  refresh();
  if (!idSchema.safeParse(identifier).success) return { kind: "failed", message: "Command response incomplete; refreshing. Check the current state." };
  return { kind: "succeeded", message: { propose: "Assembly revision proposed.", approve: "Assembly revision approved.", reject: "Assembly revision rejected.", render: "Render requested." }[command.action], identifier: identifier as string };
}
