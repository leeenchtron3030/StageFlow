import { OperationalShell } from "@/components/operational-shell";
import { EventOperationalView } from "@/components/operational-views";
import { loadWorkspace } from "@/experience/data-source.ts";

export const dynamic = "force-dynamic";

export default async function EventPage({ searchParams }: { searchParams: Promise<{ scenario?: string | string[] }> }) {
  const query = await searchParams;
  const workspace = await loadWorkspace({ scenario: typeof query.scenario === "string" ? query.scenario : undefined });
  return <OperationalShell activePath="/event" workspace={workspace}><EventOperationalView workspace={workspace} /></OperationalShell>;
}
