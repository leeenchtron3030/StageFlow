import { OperationalShell } from "@/components/operational-shell";
import { StageOperationalView } from "@/components/operational-views";
import { loadWorkspace } from "@/experience/data-source.ts";

export const dynamic = "force-dynamic";

export default async function StagePage({ params, searchParams }: { params: Promise<{ stageKey: string }>; searchParams: Promise<{ scenario?: string | string[] }> }) {
  const [route, query] = await Promise.all([params, searchParams]);
  const workspace = await loadWorkspace({ scenario: typeof query.scenario === "string" ? query.scenario : undefined, includeTimingEvidence: true });
  const stage = workspace.stages.find((item) => item.key === decodeURIComponent(route.stageKey));
  return <OperationalShell activePath="/" workspace={workspace}><StageOperationalView stage={stage} workspace={workspace} /></OperationalShell>;
}
