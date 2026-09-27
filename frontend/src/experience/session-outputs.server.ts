import "server-only";
import { readCapability } from "./capability-proxy.server.ts";
import { getFixtureSessionOutputs } from "./session-outputs-fixtures.ts";
import { readSessionOutputs } from "./session-outputs.ts";
import type { OperationalWorkspace } from "./model.ts";

export async function loadSessionOutputs(workspace: OperationalWorkspace, sessionId: string) {
  if (workspace.dataSource.kind === "fixture") return getFixtureSessionOutputs();
  return readSessionOutputs(workspace.event.id ?? "", sessionId,
    workspace.mediaAssets.filter((asset) => asset.sessionId === sessionId && asset.assetId).map((asset) => asset.assetId!), {
      assembly: (path) => readCapability("assembly", path),
      rendering: (path) => readCapability("rendering", path),
      timing: (path) => readCapability("media-timing", path),
    });
}
