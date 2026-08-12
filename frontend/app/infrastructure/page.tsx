import { OperationalShell } from "@/components/operational-shell";
import { InfrastructureOperationalView } from "@/components/operational-views";
import { loadWorkspace } from "@/experience/data-source.ts";

export const dynamic = "force-dynamic";

export default async function InfrastructurePage({ searchParams }: { searchParams: Promise<{ scenario?: string | string[] }> }) {
  const query = await searchParams;
  const workspace = await loadWorkspace({ scenario: typeof query.scenario === "string" ? query.scenario : undefined });
  return <OperationalShell activePath="/infrastructure" workspace={workspace}><InfrastructureOperationalView workspace={workspace} /></OperationalShell>;
}
