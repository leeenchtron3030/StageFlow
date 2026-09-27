import { OperationalShell } from "@/components/operational-shell";
import { EditorialReviewSurface } from "@/components/editorial-review-surface";
import { loadWorkspace } from "@/experience/data-source.ts";
import { loadEditorialQueue } from "@/experience/editorial.server.ts";
import { createReadBudget } from "@/experience/read-budget.ts";
import { editorialFixtureEvent, editorialFixtureSessions } from "@/experience/editorial-fixtures.ts";
import { idSchema } from "@/experience/outputs-api.ts";

export const dynamic = "force-dynamic";

export default async function EditorialPage({ searchParams }: { searchParams: Promise<{ scenario?: string | string[] }> }) {
  const query = await searchParams;
  const budget = createReadBudget();
  try {
    const workspace = await loadWorkspace({ scenario: typeof query.scenario === "string" ? query.scenario : undefined, readBudget: budget });
    const initialQueue = await loadEditorialQueue(workspace, budget);
    const fixture = workspace.dataSource.kind === "fixture";
    const context = { eventId: fixture ? editorialFixtureEvent : workspace.event.id ?? "", fixture,
      authoritative: workspace.dataSource.authoritative && workspace.dataSource.state === "live_connected",
      operatorAvailable: idSchema.safeParse(process.env.STAGEFLOW_DEMO_OPERATOR_ID).success,
      launchContext: fixture ? undefined : process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT };
    return <OperationalShell activePath="/editorial" workspace={workspace}><EditorialReviewSurface key={context.eventId} context={context} initialQueue={initialQueue} eventName={workspace.event.name} sessions={fixture ? editorialFixtureSessions : workspace.sessions.map((s) => ({ id: s.id, title: s.title }))} /></OperationalShell>;
  } finally { budget.dispose(); }
}
