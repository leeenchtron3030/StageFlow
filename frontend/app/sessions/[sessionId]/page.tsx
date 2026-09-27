import { SessionOutputsPanel } from "@/components/session-outputs-panel";
import { SessionOutputActions } from "@/components/session-output-actions";
import { loadSessionOutputs } from "@/experience/session-outputs.server.ts";
import { OperationalShell } from "@/components/operational-shell";
import { SessionOperationalView } from "@/components/operational-views";
import { loadWorkspace } from "@/experience/data-source.ts";
import { createReadBudget } from "@/experience/read-budget.ts";

export const dynamic = "force-dynamic";

export default async function SessionPage({ params, searchParams }: { params: Promise<{ sessionId: string }>; searchParams: Promise<{ scenario?: string | string[] }> }) {
  const [route, query] = await Promise.all([params, searchParams]);
  const budget = createReadBudget();
  try {
    const workspace = await loadWorkspace({ scenario: typeof query.scenario === "string" ? query.scenario : undefined, includeTimingEvidence: true, readBudget: budget });
    const session = workspace.sessions.find((item) => item.id === decodeURIComponent(route.sessionId));
    const outputs = session ? await loadSessionOutputs(workspace, session.id, budget) : undefined;
    const demoActorId = process.env.STAGEFLOW_DEMO_OPERATOR_ID;
    const demoLaunchContext = process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT;
    const actions = outputs && session ? <SessionOutputActions context={{
      eventId: workspace.event.id ?? "", sessionId: session.id, packageRevision: session.packageRevision,
      launchContext: demoLaunchContext, operatorAvailable: Boolean(demoActorId),
      authoritative: workspace.dataSource.authoritative && workspace.dataSource.state === "live_connected",
      fixture: outputs.fixture, assembly: outputs.assembly,
    }} /> : null;
    return <OperationalShell activePath="/sessions" workspace={workspace}><SessionOperationalView demoActorId={demoActorId} demoLaunchContext={demoLaunchContext} session={session} workspace={workspace} outputs={outputs ? <SessionOutputsPanel outputs={outputs} actions={actions} /> : null} /></OperationalShell>;
  } finally { budget.dispose(); }
}
