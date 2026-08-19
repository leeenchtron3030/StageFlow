import { OperationalShell } from "@/components/operational-shell";
import { StageOperationalView } from "@/components/operational-views";
import { loadWorkspace } from "@/experience/data-source.ts";

export const dynamic = "force-dynamic";

export default async function StagePage({ params, searchParams }: { params: Promise<{ stageKey: string }>; searchParams: Promise<{ scenario?: string | string[] }> }) {
  const [route, query] = await Promise.all([params, searchParams]);
  const workspace = await loadWorkspace({ scenario: typeof query.scenario === "string" ? query.scenario : undefined, includeTimingEvidence: true });
  const stage = workspace.stages.find((item) => item.key === decodeURIComponent(route.stageKey));
  const demoActorId = process.env.STAGEFLOW_DEMO_OPERATOR_ID;
  const demoLaunchContext = process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT;
  return <OperationalShell activePath="/" workspace={workspace}><StageOperationalView demoActorId={demoActorId} demoLaunchContext={demoLaunchContext} stage={stage} workspace={workspace} /></OperationalShell>;
}
