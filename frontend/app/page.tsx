import { MissionControl } from "@/components/mission-control";
import { OperationalShell } from "@/components/operational-shell";
import { loadWorkspace } from "@/experience/data-source.ts";
import { suggestionQueue } from "@/experience/session-suggestions-api.ts";
import { readCapability } from "@/experience/capability-proxy.server.ts";
import { createReadBudget } from "@/experience/read-budget.ts";

export const dynamic = "force-dynamic";

export default async function MissionControlPage({
  searchParams,
}: {
  searchParams: Promise<{ scenario?: string | string[] }>;
}) {
  const query = await searchParams;
  const workspace = await loadWorkspace({
    scenario: typeof query.scenario === "string" ? query.scenario : undefined,
  });
  const budget = createReadBudget();
  try {
    const connected = workspace.dataSource.kind !== "fixture" && workspace.dataSource.authoritative && workspace.dataSource.state === "live_connected";
    const suggestions = connected && workspace.event.id ? await suggestionQueue(workspace.event.id, (path) => budget.read(() => readCapability("producer", path))).catch(() => undefined) : [];
    return (
      <OperationalShell activePath="/" workspace={workspace}>
        <MissionControl workspace={workspace} suggestions={suggestions} />
      </OperationalShell>
    );
  } finally { budget.dispose(); }
}
