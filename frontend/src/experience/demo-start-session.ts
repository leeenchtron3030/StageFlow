import { createDemoCommandEnvelope } from "./demo-api.ts";
import { demoAuthorityHeaders } from "./demo-launch-context.ts";
import type { UuidCryptoSource } from "../shared/ids/uuid-v4.ts";

const demoApiRoot = "/api/stageflow/demo";

export type DemoStartSessionSelection =
  | {
      kind: "expectation";
      expectationId: string;
      title: string;
    }
  | { kind: "ad_hoc" };

export type DemoStartSessionSubmissionResult =
  | {
      status: "not_submitted";
      reason:
        | "actor_required"
        | "launch_context_required"
        | "selection_required"
        | "confirmation_declined";
    }
  | { status: "submitted"; response: Response };

export async function submitDemoStartSession({
  actorId,
  stageId,
  launchContext,
  selection,
  authoritativeStart,
  confirm,
  fetcher,
  cryptoSource,
}: {
  actorId?: string;
  stageId: string;
  launchContext?: string;
  selection?: DemoStartSessionSelection;
  authoritativeStart: string;
  confirm: (message: string) => boolean;
  fetcher: typeof fetch;
  cryptoSource?: UuidCryptoSource;
}): Promise<DemoStartSessionSubmissionResult> {
  if (!actorId) return { status: "not_submitted", reason: "actor_required" };
  if (!launchContext) {
    return { status: "not_submitted", reason: "launch_context_required" };
  }
  if (!selection) return { status: "not_submitted", reason: "selection_required" };

  const confirmation =
    selection.kind === "expectation"
      ? `Declare an authoritative Session start for “${selection.title}” now?`
      : "Declare an authoritative ad hoc / unscheduled Session start now?";
  if (!confirm(confirmation)) {
    return { status: "not_submitted", reason: "confirmation_declined" };
  }

  const response = await fetcher(`${demoApiRoot}/sessions/start`, {
    method: "POST",
    cache: "no-store",
    headers: demoAuthorityHeaders(launchContext),
    body: JSON.stringify(
      createDemoCommandEnvelope(
        actorId,
        {
          stage_id: stageId,
          authoritative_start: authoritativeStart,
          ...(selection.kind === "expectation"
            ? { program_expectation_id: selection.expectationId }
            : {}),
        },
        cryptoSource,
      ),
    ),
  });
  return { status: "submitted", response };
}
