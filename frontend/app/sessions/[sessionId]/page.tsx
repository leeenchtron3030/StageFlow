import { SessionOutputsPanel } from "@/components/session-outputs-panel";
import { loadSessionOutputs } from "@/experience/session-outputs.server.ts";
import { OperationalShell } from "@/components/operational-shell";
import { SessionOperationalView } from "@/components/operational-views";
import { loadWorkspace } from "@/experience/data-source.ts";

export const dynamic = "force-dynamic";

export default async function SessionPage({ params, searchParams }: { params: Promise<{ sessionId: string }>; searchParams: Promise<{ scenario?: string | string[] }> }) {
  const [route, query] = await Promise.all([params, searchParams]);
  const workspace = await loadWorkspace({ scenario: typeof query.scenario === "string" ? query.scenario : undefined, includeTimingEvidence: true });
  const session = workspace.sessions.find((item) => item.id === decodeURIComponent(route.sessionId));
  const outputs = session ? await loadSessionOutputs(workspace, session.id) : undefined;
  const demoActorId = process.env.STAGEFLOW_DEMO_OPERATOR_ID;
  const demoLaunchContext = process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT;
  return <OperationalShell activePath="/sessions" workspace={workspace}><SessionOperationalView demoActorId={demoActorId} demoLaunchContext={demoLaunchContext} session={session} workspace={workspace} />{outputs ? <SessionOutputsPanel outputs={outputs} /> : null}</OperationalShell>;
}
