import { z } from "zod";
import { demoAuthorityHeaders } from "./demo-launch-context.ts";

export const idSchema = z.uuid();
export const timestampSchema = z.iso.datetime({ offset: true });
export const countSchema = z.number().int().nonnegative();
export const revisionSchema = z.number().int().positive();
export const qualificationSchema = z.enum(["unqualified", "qualified", "rejected", "expired"]);
export const operationStateSchema = z.enum(["pending", "eligible", "leased", "running", "retry_wait", "deferred", "blocked", "succeeded", "terminal_failed", "cancel_requested", "cancelled"]);
export const hashSchema = z.string().regex(/^[0-9a-f]{64}$/);
export const pageFields = { limit: revisionSchema.max(100), next_after: idSchema.nullable() };
export const numberedPageFields = { limit: revisionSchema.max(100), next_after: countSchema.nullable(), items_truncated: z.boolean() };
export type ApiRead = (path: string) => Promise<unknown>;
export class CapabilityReadError extends Error {
  readonly status: number;
  readonly detail?: string;
  constructor(status: number, detail?: string) { super(`outputs_http_${status}`); this.status = status; this.detail = detail; }
  static async fromResponse(response: Response) {
    const payload: unknown = await response.json().catch(() => undefined);
    const detail = payload && typeof payload === "object" && "detail" in payload && typeof payload.detail === "string" ? payload.detail : undefined;
    return new CapabilityReadError(response.status, detail);
  }
}

/** Browser transport: only same-origin capability routes; no secret or backend URL. */
export function capabilityRead(capability: "assembly" | "rendering" | "editorial" | "media-timing" | "session-suggestions" | "producer"): ApiRead {
  return async (path) => {
    const response = await fetch(`/api/stageflow/${capability}/${path}`, { cache: "no-store", redirect: "error" });
    if (!response.ok) throw await CapabilityReadError.fromResponse(response);
    return response.json();
  };
}

export async function capabilityCommand<T>(capability: "assembly" | "rendering" | "editorial", path: string, body: Record<string, unknown>, launchContext: string, schema: z.ZodType<T>): Promise<T> {
  const response = await fetch(`/api/stageflow/${capability}/${path}`, {
    method: "POST", cache: "no-store", redirect: "error",
    headers: demoAuthorityHeaders(launchContext), body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`outputs_http_${response.status}`);
  return schema.parse(await response.json());
}

export function query(values: Record<string, string | number | undefined>): string {
  const result = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) if (value !== undefined) result.set(key, String(value));
  return result.toString();
}
