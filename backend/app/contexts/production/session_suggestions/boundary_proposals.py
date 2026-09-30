"""Advisory refinements and explicit human decisions; Kernel retains authority."""
from uuid import NAMESPACE_URL, uuid5

from app.contexts.production.event_mode_kernel.contracts import (
    EpistemicKind,
    Session,
    SessionBoundaryProposal,
)
from app.shared.human_commands import human_command_digest
from app.shared.ids import EntityId
from app.shared.time import Clock

from .contracts import (
    POLICY_V3,
    BoundaryProposalDecision,
    BoundaryProposalDecisionHistoryItem,
    BoundaryProposalDecisionKind,
    Candidate,
    EdgeKind,
    SuggestionConflictError,
)
from .repository import SuggestionRepository, SuggestionTransaction

SYSTEM_PROPOSER_ID = EntityId(str(uuid5(
    NAMESPACE_URL, "stageflow:session-suggestion:boundary-proposer")))


def produce_boundary_proposals(tx: SuggestionTransaction, session: Session,
                               candidate: Candidate) -> int:
    evidence = tuple(sorted({*candidate.segmentation_ids,
                             *(r.id for r in candidate.timing_references)},
                            key=lambda i: i.value))
    if not evidence:
        return 0
    latest = {p.boundary_kind: p for p in tx.latest_nonstale_boundary_proposals(session.id)}
    count = 0
    for edge in ("start", "end"):
        current = getattr(session, "authoritative_" + edge)
        boundary = getattr(candidate.span, edge)
        kind = getattr(candidate, edge + "_edge_kind")
        # An active Session has no current end to compare against.
        if (current is None or kind == EdgeKind.SCHEDULE
                or abs((boundary - current).total_seconds()) < 30):
            continue
        prior = latest.get(edge)
        if (prior is not None and prior.boundary_at == boundary
                and prior.policy_version == POLICY_V3.version):
            continue
        reason = ("cue_supported" if getattr(candidate, edge + "_cue_support") else {
            EdgeKind.FREEZE: "changeover_edge", EdgeKind.GAP: "recording_gap",
            EdgeKind.COVERAGE: "recording_boundary",
        }[kind])
        tx.kernel.propose_session_boundary(
            session_id=session.id, boundary_kind=edge, boundary_at=boundary,
            epistemic_kind=EpistemicKind.DERIVED, proposer_id=SYSTEM_PROPOSER_ID,
            evidence_ids=evidence, policy_id=POLICY_V3.id, policy_version=POLICY_V3.version,
            reason=reason,
        )
        count += 1
    return count


class BoundaryProposalService:
    def __init__(self, repository: SuggestionRepository, clock: Clock) -> None:
        self.repository, self.clock = repository, clock

    def open(self, event_id: EntityId, session_id: EntityId
             ) -> tuple[SessionBoundaryProposal, ...]:
        with self.repository.transaction(self.clock) as tx:
            tx.boundary_session(event_id, session_id)
            return tx.open_boundary_proposals(session_id)

    def history(self, event_id: EntityId, session_id: EntityId, *,
                after: EntityId | None = None, limit: int = 50
                ) -> tuple[tuple[BoundaryProposalDecisionHistoryItem, ...], EntityId | None]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("invalid boundary decision page limit")
        with self.repository.transaction(self.clock) as tx:
            tx.boundary_session(event_id, session_id)
            values = tx.boundary_decision_history(session_id, after, limit + 1)
            return values[:limit], values[limit - 1].command_id if len(values) > limit else None

    def apply(self, *, event_id: EntityId, session_id: EntityId, proposal_id: EntityId,
              command_id: EntityId, actor_id: EntityId,
              authority_kind: str = "human") -> BoundaryProposalDecision:
        return self._decide(event_id, session_id, proposal_id, command_id, actor_id,
                            BoundaryProposalDecisionKind.APPLIED, None, authority_kind)

    def dismiss(self, *, event_id: EntityId, session_id: EntityId, proposal_id: EntityId,
                command_id: EntityId, actor_id: EntityId, reason: str | None = None,
                authority_kind: str = "human") -> BoundaryProposalDecision:
        if reason is not None:
            if not 1 <= len(reason.strip()) <= 500 or "\x00" in reason:
                raise ValueError("boundary proposal reason out of bounds")
            reason = reason.strip()
        return self._decide(event_id, session_id, proposal_id, command_id, actor_id,
                            BoundaryProposalDecisionKind.DISMISSED, reason, authority_kind)

    def _decide(self, event_id: EntityId, session_id: EntityId, proposal_id: EntityId,
                command_id: EntityId, actor_id: EntityId, kind: BoundaryProposalDecisionKind,
                reason: str | None, authority_kind: str) -> BoundaryProposalDecision:
        from .service import kernel_operation_id

        if authority_kind != "human":
            raise ValueError("boundary_proposal_requires_human")
        digest = human_command_digest({
            "event_id": event_id.value, "session_id": session_id.value,
            "proposal_id": proposal_id.value, "command_id": command_id.value,
            "actor_id": actor_id.value, "kind": kind.value, "reason": reason,
        })
        with self.repository.transaction(self.clock) as tx:
            replay = tx.replay_boundary_decision(command_id, digest)
            if replay is not None:
                return replay
            tx.lock_event(event_id)
            tx.boundary_session(event_id, session_id, lock=True)
            proposal = tx.boundary_proposal(session_id, proposal_id)
            if tx.boundary_decided(proposal_id):
                raise SuggestionConflictError("boundary_proposal_decided")
            if tx.boundary_stale(proposal):
                raise SuggestionConflictError("boundary_proposal_stale")
            if kind == BoundaryProposalDecisionKind.APPLIED:
                tx.kernel.correct_session_boundary(
                    operation_id=kernel_operation_id(command_id, "apply-boundary"),
                    session_id=session_id, boundary_kind=proposal.boundary_kind,
                    boundary_at=proposal.boundary_at, actor_id=actor_id,
                    reason="session_boundary_proposal_applied",
                )
            decision = BoundaryProposalDecision(proposal_id, session_id, kind, command_id,
                                                 digest, actor_id, self.clock.now(), reason)
            # Same borrowed transaction as confirm: a failed final write rolls back
            # the Kernel correction, and retries retain deterministic operation identity.
            tx.save_boundary_decision(decision)
            return decision
