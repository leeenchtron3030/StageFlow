import type {
  AttentionLevel,
  MediaSummaryView,
  OperationalWorkspace,
  SessionView,
  StageView,
} from "./model.ts";

const attentionOrder: Record<AttentionLevel, number> = {
  information: 1,
  review: 2,
  intervention: 3,
};

export function formatMediaSummary(media: MediaSummaryView): string {
  const parts = [`${media.associated} associated`];
  if (media.stabilizing > 0) parts.push(`${media.stabilizing} stabilizing`);
  if (media.unresolved > 0) parts.push(`${media.unresolved} unresolved`);
  if (media.conflicting > 0) parts.push(`${media.conflicting} conflicting`);
  return parts.join(" · ");
}

export function formatActivityState(session?: SessionView): string {
  if (!session) return "No realized Session";
  if (session.activityState === "presentation_active") return "Presentation active";
  if (session.activityState === "presentation_ended") return "Presentation ended";
  return "Expected";
}

export function formatPackageState(session?: SessionView): string {
  if (!session) return "No package";
  const labels: Record<SessionView["packageState"], string> = {
    assembling: "Assembling",
    ready_for_review: "Ready for review",
    in_review: "In review",
    correction_required: "Review required",
    complete: "Complete",
  };
  return labels[session.packageState];
}

export function workspaceAttentionLevel(
  workspace: OperationalWorkspace,
): AttentionLevel | undefined {
  return workspace.attention.reduce<AttentionLevel | undefined>((current, item) => {
    if (!current || attentionOrder[item.level] > attentionOrder[current]) return item.level;
    return current;
  }, undefined);
}

export function stageOperationalLabel(stage: StageView): string {
  if (stage.attentionLevel === "intervention") return "Intervention";
  if (stage.attentionLevel === "review") return "Review required";
  if (stage.currentSession?.activityState === "presentation_active") return "Live";
  if (stage.currentSession?.activityState === "presentation_ended") return "Assembling";
  return "Standing by";
}

export function isSessionProminent(session: SessionView): boolean {
  return !(
    session.activityState === "presentation_ended" && session.packageState === "complete"
  );
}

export function authorityActionsEnabled(workspace: OperationalWorkspace): boolean {
  void workspace;
  // The current HTTP boundary is intentionally read-only. UI readiness must never
  // manufacture command authority that the backend does not expose.
  return false;
}

export function relativeTimeLabel(value?: string): string {
  if (!value) return "No media observed";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return "Time unavailable";
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(parsed));
}
