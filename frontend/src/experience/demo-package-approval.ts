import { createDemoCommandEnvelope } from "./demo-api.ts";
import { demoAuthorityHeaders } from "./demo-launch-context.ts";
import type { UuidCryptoSource } from "../shared/ids/uuid-v4.ts";

const demoApiRoot = "/api/stageflow/demo";

export interface DemoPackageApprovalSummary {
  sessionTitle: string;
  packageRevision: number;
  mediaAssociated: number;
  mediaUnresolved: number;
  mediaConflicting: number;
  transcriptionSucceeded: number;
  transcriptionFailed: number;
  transcriptEvidenceCount: number;
  declaredMomentCount: number;
}

export type DemoPackageApprovalResult =
  | {
      status: "not_submitted";
      reason:
        | "actor_required"
        | "launch_context_required"
        | "authority_state_required"
        | "confirmation_declined";
    }
  | { status: "submitted"; response: Response };

export function packageApprovalConfirmation(
  summary: DemoPackageApprovalSummary,
): string {
  return [
    `Approve package revision ${summary.packageRevision}? This records an attributable human acceptance of this exact Session package revision.`,
    "",
    `Session: ${summary.sessionTitle}`,
    `Media: associated ${summary.mediaAssociated}, unresolved ${summary.mediaUnresolved}, conflicting ${summary.mediaConflicting}`,
    `Transcription: succeeded ${summary.transcriptionSucceeded}, failed ${summary.transcriptionFailed}`,
    `Transcript Evidence: ${summary.transcriptEvidenceCount}`,
    `Declared Moments: ${summary.declaredMomentCount}`,
  ].join("\n");
}

export async function submitDemoPackageApproval({
  actorId,
  launchContext,
  sessionId,
  activityState,
  packageState,
  summary,
  confirm,
  fetcher,
  cryptoSource,
}: {
  actorId?: string;
  launchContext?: string;
  sessionId: string;
  activityState: string;
  packageState: string;
  summary: DemoPackageApprovalSummary;
  confirm: (message: string) => boolean;
  fetcher: typeof fetch;
  cryptoSource?: UuidCryptoSource;
}): Promise<DemoPackageApprovalResult> {
  if (!actorId) return { status: "not_submitted", reason: "actor_required" };
  if (!launchContext) {
    return { status: "not_submitted", reason: "launch_context_required" };
  }
  if (
    activityState !== "presentation_ended" ||
    packageState !== "ready_for_review"
  ) {
    return { status: "not_submitted", reason: "authority_state_required" };
  }
  if (!confirm(packageApprovalConfirmation(summary))) {
    return { status: "not_submitted", reason: "confirmation_declined" };
  }

  const response = await fetcher(`${demoApiRoot}/sessions/approve-package`, {
    method: "POST",
    cache: "no-store",
    headers: demoAuthorityHeaders(launchContext),
    body: JSON.stringify(
      createDemoCommandEnvelope(
        actorId,
        {
          session_id: sessionId,
          package_revision: summary.packageRevision,
        },
        cryptoSource,
      ),
    ),
  });
  return { status: "submitted", response };
}
