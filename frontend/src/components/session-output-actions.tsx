"use client";

import { uiLabels, renderQualityLabel, renderQualityLabels, renderQualityComparison } from "../experience/ui-labels.ts";
import { useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { assemblyApi, type assemblyTemplatesSchema } from "../experience/assembly-api.ts";
import type { z } from "zod";
import { currentRenderSummary, newestOutputs } from "../experience/session-outputs.ts";
import { nextOutputAction, outputActionDisabled, outputConfirmation, prepareOutputCommand, sendOutputCommand, type OutputAction, type OutputActionContext, type OutputCommandResult, type PreparedOutputCommand } from "../experience/output-actions.ts";

type Templates = z.infer<typeof assemblyTemplatesSchema>;
export function SessionOutputActions({ context }: { context: OutputActionContext }) {
  const router = useRouter();
  const [refreshing, startTransition] = useTransition();
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [action, setAction] = useState<OutputAction>("propose");
  const [reason, setReason] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [templates, setTemplates] = useState<Templates>();
  const [templateMessage, setTemplateMessage] = useState("");
  const [result, setResult] = useState<OutputCommandResult>();
  const [retry, setRetry] = useState<PreparedOutputCommand>();
  const [openedState, setOpenedState] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const actionState = useRef<HTMLSpanElement>(null);
  const submitting = useRef(false);
  const item = context.assembly.state === "available" ? context.assembly.value : null;
  const primary = nextOutputAction(item);
  const renderSummary = primary === "render" && item
    ? currentRenderSummary(item.revision.revision_id, context.operations, context.outputs) : undefined;
  const quality = context.renderSetting?.state === "available" ? context.renderSetting.value : undefined;
  const latest = context.outputs?.state === "available" ? newestOutputs(context.outputs.value.items)[0] : undefined;
  const qualityMismatch = Boolean(quality && latest && renderQualityLabel(quality) !== renderQualityLabel(latest));
  const disabled = outputActionDisabled(context, primary);
  const stateKey = JSON.stringify(context);
  const changed = openedState !== stateKey;
  const template = templates?.items.find((entry) => entry.template_id === templateId);
  const confirmation = outputConfirmation(action, item, context.packageRevision, template?.name, quality ? renderQualityLabel(quality) : undefined);
  const formDisabled = !open || busy || refreshing || changed || Boolean(outputActionDisabled(context, action)) ||
    (action === "propose" ? !template : (action === "approve" || action === "reject") && (!reason.trim() || reason.trim().length > 500));

  useEffect(() => {
    if (open) dialog.current?.showModal();
    else if (dialog.current?.open) {
      dialog.current.close();
      (trigger.current?.disabled ? actionState.current : trigger.current)?.focus();
    }
  }, [open]);

  async function loadTemplates(after?: string) {
    setBusy(true);
    setTemplateMessage("Loading Event templates…");
    try {
      const page = await assemblyApi().templates(context.eventId, after);
      if (page.event_id !== context.eventId || page.items.some((entry) => entry.event_id !== context.eventId)) throw new Error();
      setTemplates((previous) => after && previous ? { ...page, items: [...previous.items, ...page.items] } : page);
      setTemplateMessage(page.total_count === 0 ? "No Event templates available." : "");
    } catch { setTemplateMessage("Event templates unavailable. Try loading again."); }
    finally { setBusy(false); }
  }
  function begin() {
    if (disabled || busy || refreshing || retry) return;
    setAction(primary); setReason(""); setTemplateId(""); setTemplates(undefined);
    setOpenedState(stateKey); setOpen(true);
    if (primary === "propose") void loadTemplates();
  }
  async function execute(command: PreparedOutputCommand) {
    if (submitting.current) return;
    submitting.current = true; setBusy(true); setResult(undefined);
    try {
      const outcome = await sendOutputCommand(command, fetch, () => startTransition(() => router.refresh()));
      setResult(outcome);
      setRetry(outcome.kind === "network_failure" ? command : undefined);
    } finally { submitting.current = false; setBusy(false); }
  }
  function confirm() {
    if (formDisabled) return;
    const command = prepareOutputCommand(context, action, true, { reason, templateId });
    if (!command) return;
    setOpen(false);
    void execute(command);
  }
  return <div className="output-actions">
    {renderSummary ? <strong role="status">{renderSummary}</strong> : null}
    <button ref={trigger} className={renderSummary || qualityMismatch ? "output-secondary-action" : undefined} type="button" onClick={begin} disabled={Boolean(disabled) || busy || refreshing || Boolean(retry)} aria-describedby={primary === "render" && qualityMismatch ? "output-action-state render-quality-reason" : "output-action-state"}>
      {primary === "propose" ? "Propose Assembly" : primary === "approve" ? "Approve / Reject" : qualityMismatch ? renderQualityLabels.again : renderSummary ? "Request another render" : "Request render"}
    </button>
    {primary === "render" && qualityMismatch && quality && latest ? <span id="render-quality-reason">{renderQualityComparison(renderQualityLabel(latest), renderQualityLabel(quality))}</span> : null}
    <span ref={actionState} tabIndex={-1} id="output-action-state">{busy ? "Working…" : refreshing ? "Refreshing current state…" : disabled ?? (retry ? "Resolve the pending command before another action." : "")}</span>
    {result ? <div className="output-command-result">
      <p role="status">{result.message}</p>
      {result.identifier ? <details><summary>Result details</summary><code className="copyable-id" tabIndex={0}>{result.identifier}</code></details> : null}
    </div> : null}
    {retry ? <button type="button" disabled={busy || refreshing || !context.launchContext || context.launchContext !== retry.launchContext} onClick={() => void execute(retry)}>Retry same command</button> : null}
    <dialog ref={dialog} className="output-confirmation" aria-labelledby="output-consequence" onCancel={(event) => { event.preventDefault(); setOpen(false); }} onClose={() => { setOpen(false); (trigger.current?.disabled ? actionState.current : trigger.current)?.focus(); }}>
      <form onSubmit={(event) => { event.preventDefault(); confirm(); }}>
        <p id="output-consequence">{confirmation.split("\n")[0]}</p>
        {confirmation.split("\n").slice(1).map((line) => <p key={line}>{line}</p>)}
        {action === "propose" ? <>
          <label htmlFor="output-template">Event template</label>
          <select id="output-template" value={templateId} onChange={(event) => setTemplateId(event.target.value)} required disabled={busy}>
            <option value="">Choose a template</option>
            {templates?.items.map((entry) => <option key={entry.template_id} value={entry.template_id}>{entry.name} · version {entry.version}</option>)}
          </select>
          {templateMessage ? <p role="status">{templateMessage}</p> : null}
          {!templates && !busy ? <button type="button" onClick={() => void loadTemplates()}>Load templates</button> : null}
          {templates?.next_after ? <button type="button" disabled={busy} onClick={() => void loadTemplates(templates.next_after!)}>Load more templates</button> : null}
        </> : null}
        {action === "approve" || action === "reject" ? <>
          <label htmlFor="output-decision">Decision</label>
          <select id="output-decision" value={action} onChange={(event) => setAction(event.target.value as "approve" | "reject")}><option value="approve">Approve</option><option value="reject">Reject</option></select>
          <label htmlFor="output-reason">Reason (required)</label>
          <textarea id="output-reason" value={reason} onChange={(event) => setReason(event.target.value)} required maxLength={500} />
        </> : null}
        {action === "propose" ? <details><summary>{uiLabels.details}</summary><p>Package revision {context.packageRevision} · Expected Assembly revision {item?.current_revision_number ?? 0}</p><p>Template ID: <code>{templateId || "Not selected"}</code></p></details> : null}
        {item && action !== "propose" ? <details><summary>{uiLabels.details}</summary><p>Assembly revision {item.revision.revision_number} · Package revision {item.revision.package_revision}</p><ul>{item.revision.bindings.filter((b) => b.outcome === "bound").map((b) => <li key={b.slot_key}>{b.slot_key}: <code>{b.packaging_revision_id}</code></li>)}</ul></details> : null}
        {changed ? <p>State changed. Cancel and review the current revision.</p> : null}
        <div className="output-dialog-actions">
          <button type="button" autoFocus onClick={() => setOpen(false)}>Cancel</button>
          <button type="submit" disabled={Boolean(formDisabled)}>{action === "approve" ? "Confirm approval" : action === "reject" ? "Confirm rejection" : action === "render" ? "Confirm render" : "Confirm proposal"}</button>
        </div>
      </form>
    </dialog>
  </div>;
}
