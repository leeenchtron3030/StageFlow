import { demoProtectedHeaders } from "./demo-launch-context.ts";

const demoApiRoot = "/api/stageflow/demo";

export interface ProgramFieldChangeResult {
  field: string;
  previous: string | null;
  current: string | null;
}

export interface ProgramChangeResult {
  kind: "added" | "changed" | "withdrawn" | "restored";
  expectation_id: string;
  expectation_key: string;
  title: string;
  external_session_id: string | null;
  fields: ProgramFieldChangeResult[];
}

export interface ProgramRefreshResult {
  provider: string;
  observed: number;
  added: number;
  changed: number;
  unchanged: number;
  withdrawn: number;
  restored: number;
  synchronized_at: string;
  current_expectation_count: number;
  changes: ProgramChangeResult[];
  changes_truncated: boolean;
  evidence_kind: "external";
  authority_notice: string;
}

export type DemoProgramRefreshSubmission =
  | { status: "not_submitted"; reason: "launch_context_required" }
  | { status: "submitted"; response: Response };

export async function submitDemoProgramRefresh({
  launchContext,
  fetcher,
}: {
  launchContext?: string;
  fetcher: typeof fetch;
}): Promise<DemoProgramRefreshSubmission> {
  if (!launchContext) {
    return { status: "not_submitted", reason: "launch_context_required" };
  }
  const response = await fetcher(`${demoApiRoot}/program/refresh`, {
    method: "POST",
    cache: "no-store",
    headers: demoProtectedHeaders(launchContext),
  });
  return { status: "submitted", response };
}
