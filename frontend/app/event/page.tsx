import { EventRenderQuality } from "@/components/event-render-quality";
import { renderingApi } from "@/experience/rendering-api.ts";
import { readCapability } from "@/experience/capability-proxy.server.ts";
import { createReadBudget } from "@/experience/read-budget.ts";
import { OperationalShell } from "@/components/operational-shell";
import { EventOperationalView } from "@/components/operational-views";
import { loadWorkspace } from "@/experience/data-source.ts";

export const dynamic = "force-dynamic";

export default async function EventPage({ searchParams }: { searchParams: Promise<{ scenario?: string | string[] }> }) {
  const query = await searchParams;
  const budget = createReadBudget();
  try {
    const workspace = await loadWorkspace({ scenario: typeof query.scenario === "string" ? query.scenario : undefined, readBudget: budget });
    const authorized = workspace.dataSource.kind !== "fixture" && workspace.dataSource.authoritative && workspace.dataSource.state === "live_connected";
    const api = renderingApi((path) => budget.read(() => readCapability("rendering", path)));
    const quality = authorized && workspace.event.id ? await Promise.all([api.setting(workspace.event.id), api.presets()]).catch(() => undefined) : undefined;
    return <OperationalShell activePath="/event" workspace={workspace}><EventOperationalView workspace={workspace} /><EventRenderQuality key={`${workspace.event.id}:${quality?.[0].current.version}`} history={quality?.[0]} presets={quality?.[1].items} authorized={authorized && Boolean(process.env.STAGEFLOW_DEMO_OPERATOR_ID)} launchContext={process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT} /></OperationalShell>;
  } finally { budget.dispose(); }
}
