from app.shared.human_commands import human_command_digest
from app.shared.ids import EntityId
from app.shared.time import Clock
from app.shared.time.validation import normalize_utc_datetime

from .contracts import CommandIdentity, bounded_text, nonnegative
from .session_contracts import (
    AssemblyAction,
    AssemblyApprovalDecision,
    AssemblyRevision,
    AssemblySlot,
    AssemblyTemplate,
    ExplicitBinding,
    MetadataField,
    positive,
)
from .session_repository import SessionAssemblyRepository


class SessionAssemblyService:
    def __init__(self, repository: SessionAssemblyRepository, clock: Clock) -> None:
        self.repository = repository
        self.clock = clock

    def _command(
        self, operation_id: EntityId, actor_id: EntityId, document: dict[str, object],
    ) -> CommandIdentity:
        return CommandIdentity(operation_id, actor_id, human_command_digest({
            **document, "actor_id": actor_id.value,
        }), normalize_utc_datetime(self.clock.now(), "recorded_at"))

    def create_template(
        self, *, operation_id: EntityId, actor_id: EntityId, event_id: EntityId,
        template_key: str, expected_version: int, name: str, slots: tuple[AssemblySlot, ...],
        required_metadata: tuple[MetadataField, ...] = (),
    ) -> AssemblyTemplate:
        nonnegative(expected_version, "expected_version")
        template_key, name = template_key.strip(), name.strip()
        required_metadata = tuple(sorted(set(required_metadata)))
        command = self._command(operation_id, actor_id, {
            "kind": "assembly_template", "event_id": event_id.value,
            "template_key": template_key, "expected_version": expected_version, "name": name,
            "slots": [{"key": s.key, "role": s.role.value, "required": s.required} for s in slots],
            "required_metadata": list(required_metadata),
        })
        template = AssemblyTemplate(EntityId.new(), event_id, template_key, expected_version + 1,
                                    name, slots, required_metadata, command.recorded_at)
        return self.repository.create_template(command, template, expected_version)

    def propose(
        self, *, operation_id: EntityId, actor_id: EntityId, session_id: EntityId,
        template_id: EntityId, expected_revision: int, expected_package_revision: int,
        explicit: tuple[ExplicitBinding, ...] = (),
    ) -> AssemblyRevision:
        nonnegative(expected_revision, "expected_revision")
        positive(expected_package_revision, "expected_package_revision")
        positive(expected_revision + 1, "next_revision")
        explicit = tuple(sorted(explicit, key=lambda b: b.slot_key))
        command = self._command(operation_id, actor_id, {
            "kind": "assembly_proposal", "session_id": session_id.value,
            "template_id": template_id.value, "expected_revision": expected_revision,
            "expected_package_revision": expected_package_revision,
            "explicit": [{"slot_key": b.slot_key, "revision_id": b.packaging_revision_id.value}
                         for b in explicit],
        })
        return self.repository.propose(
            command, revision_id=EntityId.new(), session_id=session_id, template_id=template_id,
            expected_revision=expected_revision,
            expected_package_revision=expected_package_revision,
            explicit=explicit,
        )

    def decide(
        self, *, operation_id: EntityId, actor_id: EntityId, session_id: EntityId,
        revision_number: int, expected_revision: int, expected_decision_count: int,
        action: AssemblyAction, reason: str,
    ) -> AssemblyApprovalDecision:
        positive(revision_number, "revision_number")
        positive(expected_revision, "expected_revision")
        nonnegative(expected_decision_count, "expected_decision_count")
        action, reason = AssemblyAction(action), reason.strip()
        bounded_text(reason, "reason", 500)
        command = self._command(operation_id, actor_id, {
            "kind": "assembly_decision", "session_id": session_id.value,
            "revision_number": revision_number, "expected_revision": expected_revision,
            "expected_decision_count": expected_decision_count,
            "action": action.value, "reason": reason,
        })
        return self.repository.decide(
            command, decision_id=EntityId.new(), session_id=session_id,
            revision_number=revision_number, expected_revision=expected_revision,
            expected_decision_count=expected_decision_count, action=action, reason=reason,
        )
