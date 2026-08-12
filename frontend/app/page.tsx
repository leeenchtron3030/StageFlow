import { MissionControl } from "@/components/mission-control";
import { OperationalShell } from "@/components/operational-shell";
import { loadWorkspace } from "@/experience/data-source.ts";

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
  return (
    <OperationalShell activePath="/" workspace={workspace}>
      <MissionControl workspace={workspace} />
    </OperationalShell>
  );
}
