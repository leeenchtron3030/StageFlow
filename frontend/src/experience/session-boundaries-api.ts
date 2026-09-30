import { z } from "zod";
import { capabilityRead, idSchema as id, timestampSchema as time, revisionSchema, type ApiRead } from "./outputs-api.ts";
import type { SessionView } from "./model.ts";

export const boundaryProposalSchema = z.object({
  proposal_id: id, session_id: id, boundary_kind: z.enum(["start", "end"]), boundary_at: time,
  epistemic_kind: z.literal("derived"), proposer_id: id, evidence_ids: z.array(id).min(1),
  policy_id: z.string(), policy_version: z.string(), reason: z.enum(["changeover_edge", "recording_gap", "recording_boundary", "cue_supported"]),
  proposed_at: time, authorized_use: z.literal("advisory_only"),
});
export const boundaryDecisionSchema = z.object({
  proposal_id: id, session_id: id, kind: z.enum(["applied", "dismissed"]), command_id: id,
  actor_id: id, decided_at: time, reason: z.string().nullable(),
});
export const boundaryDecisionHistorySchema = boundaryDecisionSchema.extend({ boundary_kind: z.enum(["start", "end"]) });
export type BoundaryDecisionHistory = z.infer<typeof boundaryDecisionHistorySchema>;
export type BoundaryProposal = z.infer<typeof boundaryProposalSchema>;
export type BoundaryDecision = z.infer<typeof boundaryDecisionSchema>;

export function boundariesApi(read: ApiRead = capabilityRead("session-suggestions")) {
  const scope = (event: string, session: string) => `events/${id.parse(event)}/sessions/${id.parse(session)}/boundary-proposals`;
  return {
    async open(event: string, session: string) {
      const { items } = z.object({ items: z.array(boundaryProposalSchema).max(2) }).parse(await read(scope(event, session)));
      if (items.some((p) => p.session_id !== session) || new Set(items.map((p) => p.boundary_kind)).size !== items.length) throw new Error("proposal_scope_or_edge_mismatch");
      return items.sort((a, b) => a.boundary_kind === b.boundary_kind ? 0 : a.boundary_kind === "start" ? -1 : 1);
    },
    async history(event: string, session: string, after?: string) {
      const page = z.object({ items: z.array(boundaryDecisionHistorySchema).max(50), limit: revisionSchema.max(100), next_after: id.nullable() }).parse(
        await read(`${scope(event, session)}/history?limit=50${after ? `&after=${id.parse(after)}` : ""}`));
      if (page.items.some((d) => d.session_id !== session) || new Set(page.items.map((d) => d.command_id)).size !== page.items.length ||
        (page.next_after !== null && (!page.items.length || page.next_after !== page.items.at(-1)?.command_id || (after && page.next_after <= after)))) throw new Error("history_scope_or_cursor_mismatch");
      return page;
    },
  };
}

export type BoundaryBadges = { sessions: Record<string, number>; incomplete: boolean };
export function realizedStageSessions(stageKey: string, sessions: SessionView[]) {
  return [...new Map(sessions.filter((s) => s.stageKey === stageKey && s.programExpectationId).map((s) => [s.id, s])).values()]
    .sort((a, b) => (a.authoritativeStart ?? "").localeCompare(b.authoritativeStart ?? "") || a.id.localeCompare(b.id));
}
/** Read linked Sessions independently of the latest suggestion run. No history or Event-wide scan. */
export async function loadBoundaryBadges(event: string, stageKey: string, sessions: SessionView[], read: ApiRead): Promise<BoundaryBadges> {
  const unique = realizedStageSessions(stageKey, sessions);
  const result: BoundaryBadges = { sessions: {}, incomplete: unique.length > 50 };
  const queue = unique.slice(0, 50);
  const api = boundariesApi(read);
  await Promise.all(Array.from({ length: Math.min(4, queue.length) }, async () => {
    for (let session = queue.shift(); session; session = queue.shift()) {
      try {
        const count = (await api.open(event, session.id)).length;
        if (count) result.sessions[session.id] = count;
      } catch { result.incomplete = true; }
    }
  }));
  return result;
}
