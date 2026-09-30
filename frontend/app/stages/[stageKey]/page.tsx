import { OperationalShell } from "@/components/operational-shell";
import { StageOperationalView } from "@/components/operational-views";
import { loadWorkspace } from "@/experience/data-source.ts";
import { StageSuggestions } from "@/components/stage-suggestions";
import { suggestionsApi } from "@/experience/session-suggestions-api.ts";
import { readCapability } from "@/experience/capability-proxy.server.ts";
import { createReadBudget } from "@/experience/read-budget.ts";
import { createHash } from "node:crypto";

export const dynamic = "force-dynamic";

export default async function StagePage({ params, searchParams }: { params: Promise<{ stageKey: string }>; searchParams: Promise<{ scenario?: string | string[] }> }) {
  const [route, query] = await Promise.all([params, searchParams]);
  const workspace = await loadWorkspace({ scenario: typeof query.scenario === "string" ? query.scenario : undefined, includeTimingEvidence: true });
  const stage = workspace.stages.find((item) => item.key === decodeURIComponent(route.stageKey));
  const demoActorId = process.env.STAGEFLOW_DEMO_OPERATOR_ID;
  const demoLaunchContext = process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT;
  const connected = workspace.dataSource.kind !== "fixture" && workspace.dataSource.authoritative && workspace.dataSource.state === "live_connected";
  const budget = createReadBudget();
  try {
    const data = connected && workspace.event.id && stage ? await suggestionsApi((path) => budget.read(() => readCapability("session-suggestions", path))).load(workspace.event.id, stage.id).catch(() => undefined) : undefined;
    const titles = Object.fromEntries([...(stage?.withdrawnProgramExpectations ?? []), ...(stage?.programExpectations ?? [])].map((p) => [p.id, p.title]));
    // Unrelated refreshes preserve drafts and retry locks; changed suggestion data resets them.
    const readKey = createHash("sha256").update(JSON.stringify([workspace.event.id, stage?.id, data?.run?.run_id, data?.offset?.version, data?.suggestions.map((s) => [s.suggestion_id, s.status]).sort()])).digest("hex");
    const hasPlannedTalks = stage?.programExpectations.some((p) => p.stageId === stage.id && p.plannedStart && p.plannedEnd) ?? false;
    return <OperationalShell activePath="/" workspace={workspace}>
      <StageOperationalView demoActorId={demoActorId} demoLaunchContext={demoLaunchContext} stage={stage} workspace={workspace} suggestions={stage ? <StageSuggestions key={readKey} eventId={workspace.event.id ?? ""} stageId={stage.id} data={data} titles={titles} hasPlannedTalks={hasPlannedTalks} authorized={connected && Boolean(demoActorId)} launchContext={demoLaunchContext} serverTimeZone={Intl.DateTimeFormat().resolvedOptions().timeZone} /> : null} />
    </OperationalShell>;
  } finally { budget.dispose(); }
}
