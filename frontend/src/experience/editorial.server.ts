import "server-only";
import { editorialApi } from "./editorial-api.ts";
import { readCapability } from "./capability-proxy.server.ts";
import { fixtureQueue } from "./editorial-fixtures.ts";
import type { OperationalWorkspace } from "./model.ts";
import type { ReadBudget } from "./read-budget.ts";

export async function loadEditorialQueue(workspace: OperationalWorkspace, budget: ReadBudget) {
  if (workspace.dataSource.kind === "fixture") return fixtureQueue();
  try {
    const queue = await budget.read(() => editorialApi((path) => readCapability("editorial", path)).queue(workspace.event.id ?? ""));
    if (queue.event_id !== workspace.event.id || queue.items.some((i) => i.event_id !== workspace.event.id)) return null;
    return queue;
  } catch { return null; }
}
