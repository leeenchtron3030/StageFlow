"""Session Suggestions decision storage and projections over immutable Kernel proposals."""
from typing import Any

import psycopg

from app.contexts.production.event_mode_kernel.contracts import (
    EpistemicKind,
    Session,
    SessionBoundaryProposal,
)
from app.contexts.production.event_mode_kernel.service import DurableEventModeKernel
from app.contexts.production.session_suggestions.contracts import (
    BoundaryProposalDecision,
    BoundaryProposalDecisionKind,
    SuggestionConflictError,
    SuggestionNotFoundError,
)
from app.shared.ids import EntityId

# Use the Kernel's existing (proposed_at, ID) order to break timestamp ties.
_STALE = """EXISTS (SELECT 1 FROM stageflow.session_boundary_history h
    WHERE h.session_id=p.session_id AND h.boundary_kind=p.boundary_kind
      AND h.decided_at>p.proposed_at)
    OR EXISTS (SELECT 1 FROM stageflow.session_boundary_proposal n
    WHERE n.session_id=p.session_id AND n.boundary_kind=p.boundary_kind
      AND (n.proposed_at,n.boundary_proposal_id)>(p.proposed_at,p.boundary_proposal_id))"""


class PostgresBoundaryProposalTransaction:
    connection: psycopg.Connection[dict[str, Any]]
    kernel: DurableEventModeKernel

    def boundary_session(self, event_id: EntityId, session_id: EntityId,
                         *, lock: bool = False) -> Session:
        row = self.connection.execute(
            "SELECT * FROM stageflow.session WHERE session_id=%s AND event_id=%s"
            + (" FOR UPDATE" if lock else ""), (session_id.value, event_id.value),
        ).fetchone()
        if row is None:
            raise SuggestionNotFoundError("session_not_found")
        session = self.kernel.repository.get_session(session_id)
        assert session is not None
        return session

    def boundary_proposal(self, session_id: EntityId,
                          proposal_id: EntityId) -> SessionBoundaryProposal:
        row = self.connection.execute(
            """SELECT * FROM stageflow.session_boundary_proposal
               WHERE boundary_proposal_id=%s AND session_id=%s""",
            (proposal_id.value, session_id.value),
        ).fetchone()
        if row is None:
            raise SuggestionNotFoundError("boundary_proposal_not_found")
        return _proposal(row)

    def boundary_decided(self, proposal_id: EntityId) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM stageflow.boundary_proposal_decision WHERE proposal_id=%s",
            (proposal_id.value,),
        ).fetchone() is not None

    def boundary_stale(self, proposal: SessionBoundaryProposal) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM stageflow.session_boundary_proposal p "
            "WHERE p.boundary_proposal_id=%s AND (" + _STALE + ")", (proposal.id.value,),
        ).fetchone() is not None

    def latest_nonstale_boundary_proposals(self, session_id: EntityId
                                           ) -> tuple[SessionBoundaryProposal, ...]:
        """Latest per edge, regardless of decision, unless corrected since proposal."""
        rows = self.connection.execute(
            """SELECT p.* FROM stageflow.session_boundary_proposal p
               WHERE p.session_id=%s AND NOT (""" + _STALE
            + ") ORDER BY p.boundary_kind LIMIT 2", (session_id.value,),
        ).fetchall()
        return tuple(_proposal(r) for r in rows)

    def open_boundary_proposals(self, session_id: EntityId
                                ) -> tuple[SessionBoundaryProposal, ...]:
        rows = self.connection.execute(
            """SELECT p.* FROM stageflow.session_boundary_proposal p
               WHERE p.session_id=%s AND NOT EXISTS (
                   SELECT 1 FROM stageflow.boundary_proposal_decision d
                   WHERE d.proposal_id=p.boundary_proposal_id)
               AND NOT (""" + _STALE + ") ORDER BY p.boundary_kind LIMIT 2", (session_id.value,),
        ).fetchall()
        return tuple(_proposal(r) for r in rows)

    def replay_boundary_decision(self, command_id: EntityId, digest: str
                                 ) -> BoundaryProposalDecision | None:
        self.connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                                ("boundary_proposal_command:" + command_id.value,))
        row = self.connection.execute(
            "SELECT * FROM stageflow.boundary_proposal_decision WHERE command_id=%s",
            (command_id.value,),
        ).fetchone()
        if row is not None and row["request_digest"] != digest:
            raise SuggestionConflictError("boundary_proposal_command_id_conflict")
        return None if row is None else _decision(row)

    def save_boundary_decision(self, value: BoundaryProposalDecision) -> None:
        self.connection.execute(
            """INSERT INTO stageflow.boundary_proposal_decision
               (proposal_id, session_id, kind, command_id, request_digest, actor_id,
                decided_at, reason) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (value.proposal_id.value, value.session_id.value, value.kind.value,
             value.command_id.value, value.request_digest, value.actor_id.value,
             value.decided_at, value.reason),
        )

    def boundary_decision_history(self, session_id: EntityId, after: EntityId | None,
                                  limit: int) -> tuple[BoundaryProposalDecision, ...]:
        rows = self.connection.execute(
            """SELECT * FROM stageflow.boundary_proposal_decision
               WHERE session_id=%s AND (%s::uuid IS NULL OR command_id>%s::uuid)
               ORDER BY command_id LIMIT %s""",
            (session_id.value, None if after is None else after.value,
             None if after is None else after.value, limit),
        ).fetchall()
        return tuple(_decision(r) for r in rows)


def _decision(row: dict[str, Any]) -> BoundaryProposalDecision:
    return BoundaryProposalDecision(
        EntityId(str(row["proposal_id"])), EntityId(str(row["session_id"])),
        BoundaryProposalDecisionKind(row["kind"]), EntityId(str(row["command_id"])),
        row["request_digest"], EntityId(str(row["actor_id"])), row["decided_at"], row["reason"],
    )


def _proposal(row: dict[str, Any]) -> SessionBoundaryProposal:
    return SessionBoundaryProposal(
        id=EntityId(str(row["boundary_proposal_id"])), session_id=EntityId(str(row["session_id"])),
        boundary_kind=row["boundary_kind"], boundary_at=row["boundary_at"],
        epistemic_kind=EpistemicKind(row["epistemic_kind"]),
        proposer_id=EntityId(str(row["proposer_id"])),
        evidence_ids=tuple(EntityId(str(i)) for i in row["evidence_ids"]),
        policy_id=row["policy_id"], policy_version=row["policy_version"],
        reason=row["reason"], proposed_at=row["proposed_at"],
        model_id=row["model_id"], model_version=row["model_version"],
    )
