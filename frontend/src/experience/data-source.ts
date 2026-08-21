import "server-only";
import { getFixtureWorkspace } from "./fixtures.ts";
import {
  adaptKernelStatus,
  adaptKernelMediaTimingEvidence,
  type KernelMediaStatus,
  type KernelMediaTimingEvidenceHistory,
  kernelUnavailableWorkspace,
  type KernelStatusPayload,
} from "./kernel-adapter.ts";
import type { OperationalWorkspace } from "./model.ts";

export interface WorkspaceRequest {
  scenario?: string;
  includeTimingEvidence?: boolean;
}

const stageflowApiSecretHeader = "x-stageflow-api-secret";

function currentApiSecret(): string | undefined {
  const value = process.env.STAGEFLOW_API_SHARED_SECRET;
  return value && value.length >= 32 ? value : undefined;
}


function configuredMode(): "fixture" | "kernel" {
  const configured = process.env.STAGEFLOW_UI_DATA_MODE;
  if (configured === "fixture" || configured === "kernel") return configured;
  return process.env.NODE_ENV === "development" ? "fixture" : "kernel";
}

export async function loadWorkspace(
  request: WorkspaceRequest = {},
): Promise<OperationalWorkspace> {
  if (configuredMode() === "fixture") return getFixtureWorkspace(request.scenario);

  const observedAt = new Date().toISOString();
  const url =
    process.env.STAGEFLOW_KERNEL_STATUS_URL ??
    "http://127.0.0.1:8000/api/v1/kernel/status";
  try {
    const apiSecret = currentApiSecret();
    if (!apiSecret) throw new Error("stageflow_api_authentication_unavailable");
    const headers = {
      Accept: "application/json",
      [stageflowApiSecretHeader]: apiSecret,
    };
    const response = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(2_500),
      headers,
    });
    const payload = (await response.json()) as KernelStatusPayload;
    if (!response.ok && response.status !== 503) {
      return kernelUnavailableWorkspace(observedAt, `Kernel returned HTTP ${response.status}`);
    }
    const workspace = adaptKernelStatus(payload, observedAt);
    if (!request.includeTimingEvidence) return workspace;
    const media = (payload.recent_media ?? []).filter(
      (item): item is KernelMediaStatus & { asset_id: string } => Boolean(item.asset_id),
    ).slice(0, 8);
    const apiBase =
      process.env.STAGEFLOW_MTE_API_BASE_URL ??
      new URL("../", url).toString().replace(/\/$/, "");
    try {
      const histories = await Promise.all(
        media.map(async (item) => {
          const response = await fetch(
            `${apiBase}/media-assets/${encodeURIComponent(item.asset_id)}/timing-evidence`,
            {
              cache: "no-store",
              signal: AbortSignal.timeout(2_500),
              headers,
            },
          );
          if (!response.ok) throw new Error(`MTE returned HTTP ${response.status}`);
          return {
            item,
            history: (await response.json()) as KernelMediaTimingEvidenceHistory,
          };
        }),
      );
      workspace.mediaTimingEvidence = histories.flatMap(({ item, history }) =>
        adaptKernelMediaTimingEvidence(history, item, payload.stages),
      );
      workspace.mediaTimingEvidenceStatus = "available";
    } catch {
      workspace.mediaTimingEvidence = [];
      workspace.mediaTimingEvidenceStatus = "unavailable";
    }
    return workspace;
  } catch {
    return kernelUnavailableWorkspace(observedAt);
  }
}
