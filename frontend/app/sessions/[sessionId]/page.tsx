import type { SessionOutputs } from "@/experience/session-outputs.ts";
import { SessionOutputsPanel } from "@/components/session-outputs-panel";
import { SessionOutputActions } from "@/components/session-output-actions";
import { loadSessionOutputs, loadRenderSetting } from "@/experience/session-outputs.server.ts";
import { OperationalShell } from "@/components/operational-shell";
import { SessionOperationalView } from "@/components/operational-views";
import { loadWorkspace } from "@/experience/data-source.ts";
import { createReadBudget } from "@/experience/read-budget.ts";
import { SessionBoundaries, BoundaryDecisionHistory } from "@/components/session-boundaries";
import { boundariesApi } from "@/experience/session-boundaries-api.ts";
import { readCapability } from "@/experience/capability-proxy.server.ts";
import { createHash } from "node:crypto";

export const dynamic = "force-dynamic";

export default async function SessionPage({ params, searchParams }: { params: Promise<{ sessionId: string }>; searchParams: Promise<{ scenario?: string | string[] }> }) {
  const [route, query] = await Promise.all([params, searchParams]);
  const budget = createReadBudget();
  try {
    const workspace = await loadWorkspace({ scenario: typeof query.scenario === "string" ? query.scenario : undefined, includeTimingEvidence: true, readBudget: budget });
    const session = workspace.sessions.find((item) => item.id === decodeURIComponent(route.sessionId));
    const connected = workspace.dataSource.kind !== "fixture" && workspace.dataSource.authoritative && workspace.dataSource.state === "live_connected";
    // Start alongside Outputs so a slow proposal read cannot consume its entire deadline first.
    const proposalsRead = connected && session && workspace.event.id ? boundariesApi((path) => budget.read(() => readCapability("session-suggestions", path))).open(workspace.event.id, session.id).catch(() => undefined) : Promise.resolve(undefined);
    const outputs: SessionOutputs | undefined = session ? await loadSessionOutputs(workspace, session.id, budget) : undefined;
    if (outputs && !outputs.fixture) {
      try {
        const setting = await loadRenderSetting(workspace.event.id ?? "", budget);
        outputs.renderSetting = { state: "available", value: setting.current };
      } catch { outputs.renderSetting = { state: "unavailable" }; }
    }
    const demoActorId = process.env.STAGEFLOW_DEMO_OPERATOR_ID;
    const demoLaunchContext = process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT;
    const actions = outputs && session ? <SessionOutputActions context={{
      eventId: workspace.event.id ?? "", sessionId: session.id, packageRevision: session.packageRevision,
      launchContext: demoLaunchContext, operatorAvailable: Boolean(demoActorId),
      authoritative: workspace.dataSource.authoritative && workspace.dataSource.state === "live_connected",
      fixture: outputs.fixture, assembly: outputs.assembly,
      operations: outputs.operations, outputs: outputs.outputs, renderSetting: outputs.renderSetting,
    }} /> : null;
    const proposals = await proposalsRead;
    const boundaryKey = createHash("sha256").update(JSON.stringify([session?.id, session?.sessionRevision, proposals])).digest("hex");
    const serverTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const boundaries = session && workspace.dataSource.kind !== "fixture" ? <SessionBoundaries key={boundaryKey} eventId={workspace.event.id ?? ""} proposals={proposals} currentStart={session.authoritativeStart} currentEnd={session.authoritativeEnd} authorized={connected && Boolean(demoActorId)} launchContext={demoLaunchContext} serverTimeZone={serverTimeZone} /> : null;
    const boundaryHistory = session && connected && workspace.event.id ? <BoundaryDecisionHistory key={boundaryKey} eventId={workspace.event.id} sessionId={session.id} serverTimeZone={serverTimeZone} /> : null;
    return <OperationalShell activePath="/sessions" workspace={workspace}><SessionOperationalView demoActorId={demoActorId} demoLaunchContext={demoLaunchContext} session={session} workspace={workspace} boundaries={boundaries} boundaryHistory={boundaryHistory} outputs={outputs ? <SessionOutputsPanel outputs={outputs} actions={actions} /> : null} /></OperationalShell>;
  } finally { budget.dispose(); }
}
