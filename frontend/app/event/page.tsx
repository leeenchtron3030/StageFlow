import { EventRenderQuality } from "@/components/event-render-quality";
import { EventBoundaryCues } from "@/components/event-boundary-cues";
import { boundaryCuesApi } from "@/experience/boundary-cues-api.ts";
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
    const cuesApi = boundaryCuesApi((path) => budget.read(() => readCapability("session-suggestions", path)));
    const [quality, cues] = authorized && workspace.event.id ? await Promise.all([
      Promise.all([api.setting(workspace.event.id), api.presets()]).catch(() => undefined),
      cuesApi.load(workspace.event.id).catch(() => undefined),
    ]) : [undefined, undefined];
    const canEdit = authorized && Boolean(process.env.STAGEFLOW_DEMO_OPERATOR_ID);
    return <OperationalShell activePath="/event" workspace={workspace}>
      <EventOperationalView workspace={workspace} />
      <EventRenderQuality key={`${workspace.event.id}:${quality?.[0].current.version}`} history={quality?.[0]} presets={quality?.[1].items} authorized={canEdit} launchContext={process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT} />
      <EventBoundaryCues key={`${workspace.event.id}:${cues?.current?.version}:${cues?.catalog.digest}`} eventId={workspace.event.id ?? ""} data={cues} authorized={canEdit} launchContext={process.env.STAGEFLOW_DEMO_LAUNCH_CONTEXT} serverTimeZone={Intl.DateTimeFormat().resolvedOptions().timeZone} />
    </OperationalShell>;
  } finally { budget.dispose(); }
}
