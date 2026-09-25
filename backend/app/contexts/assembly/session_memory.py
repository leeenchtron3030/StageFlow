"""Non-durable test repository. Inputs are supplied snapshots, never a runtime fallback."""
from collections.abc import Callable
from dataclasses import replace
from threading import RLock

from app.shared.ids import EntityId

from .contracts import ApprovalState, CommandIdentity, nonnegative, validate_page
from .resolution import build_revision, is_stale, resolve_metadata
from .session_contracts import (
    AssemblyAction,
    AssemblyApprovalDecision,
    AssemblyInputs,
    AssemblyMetadataOverride,
    AssemblyPage,
    AssemblyRevision,
    AssemblyTemplate,
    ExplicitBinding,
    MetadataOverridePage,
    PackagingCandidate,
    SessionAssembly,
    TemplatePage,
)
from .session_repository import AssemblyConflictError, AssemblyNotFoundError


class InMemorySessionAssemblyRepository:
    def __init__(
        self, *, event_ids: frozenset[EntityId], inputs: Callable[[EntityId], AssemblyInputs],
        candidates: Callable[[], tuple[PackagingCandidate, ...]],
    ) -> None:
        self._events = frozenset(event_ids)
        self._inputs = inputs
        self._candidates = candidates
        self._templates: dict[EntityId, AssemblyTemplate] = {}
        self._revisions: dict[EntityId, list[AssemblyRevision]] = {}
        self._decisions: dict[EntityId, list[AssemblyApprovalDecision]] = {}
        self._commands: dict[EntityId, tuple[str, object]] = {}
        self._overrides: dict[EntityId, list[AssemblyMetadataOverride]] = {}
        self._override_commands: dict[EntityId, tuple[str, AssemblyMetadataOverride]] = {}
        self._lock = RLock()

    def _resolved_inputs(self, session_id: EntityId) -> AssemblyInputs:
        inputs = self._inputs(session_id)
        return replace(inputs, metadata=resolve_metadata(
            inputs, self._overrides.get(session_id, ()),
        ))

    def record_metadata_override(
        self, command: CommandIdentity, entry: AssemblyMetadataOverride, expected_sequence: int,
    ) -> AssemblyMetadataOverride:
        with self._lock:
            receipt = self._override_commands.get(command.operation_id)
            if receipt is not None:
                if receipt[0] != command.request_digest:
                    raise AssemblyConflictError("human_command_operation_id_conflict")
                return receipt[1]
            if not self._revisions.get(entry.session_id):
                raise AssemblyNotFoundError("session_assembly_not_found")
            history = self._overrides.get(entry.session_id, [])
            if len(history) != expected_sequence or entry.sequence != expected_sequence + 1:
                raise AssemblyConflictError("metadata_override_sequence_conflict")
            self._overrides[entry.session_id] = [*history, entry]
            self._override_commands[command.operation_id] = (command.request_digest, entry)
            return entry

    def list_metadata_overrides(
        self, event_id: EntityId, session_id: EntityId, *, after: int = 0, limit: int = 50,
    ) -> MetadataOverridePage:
        validate_page(limit)
        nonnegative(after, "after")
        with self._lock:
            if self._inputs(session_id).event_id != event_id:
                raise AssemblyNotFoundError("session_not_in_event")
            if not self._revisions.get(session_id):
                raise AssemblyNotFoundError("session_assembly_not_found")
            history = self._overrides.get(session_id, [])
            selected = [entry for entry in history if entry.sequence > after]
            items = tuple(selected[:limit])
            return MetadataOverridePage(items, len(history),
                                        items[-1].sequence if len(selected) > limit else None)

    def _replay[T](self, command: CommandIdentity, kind: type[T]) -> T | None:
        receipt = self._commands.get(command.operation_id)
        if receipt is None:
            return None
        if receipt[0] != command.request_digest or not isinstance(receipt[1], kind):
            raise AssemblyConflictError("human_command_operation_id_conflict")
        return receipt[1]

    def create_template(
        self, command: CommandIdentity, template: AssemblyTemplate, expected_version: int,
    ) -> AssemblyTemplate:
        with self._lock:
            replay = self._replay(command, AssemblyTemplate)
            if replay is not None:
                return replay
            if template.event_id not in self._events:
                raise AssemblyNotFoundError("event_not_found")
            current = max((t.version for t in self._templates.values()
                           if (t.event_id, t.template_key) ==
                           (template.event_id, template.template_key)), default=0)
            if current != expected_version or template.version != current + 1:
                raise AssemblyConflictError("template_version_conflict")
            self._templates[template.id] = template
            self._commands[command.operation_id] = (command.request_digest, template)
            return template

    def propose(
        self, command: CommandIdentity, *, revision_id: EntityId, session_id: EntityId,
        template_id: EntityId, expected_revision: int, expected_package_revision: int,
        explicit: tuple[ExplicitBinding, ...],
    ) -> AssemblyRevision:
        with self._lock:
            replay = self._replay(command, AssemblyRevision)
            if replay is not None:
                return replay
            inputs = self._resolved_inputs(session_id)
            template = self._templates.get(template_id)
            if template is None or template.event_id != inputs.event_id:
                raise AssemblyNotFoundError("template_not_in_session_event")
            history = self._revisions.get(session_id, [])
            if len(history) != expected_revision:
                raise AssemblyConflictError("assembly_revision_conflict")
            if inputs.package_revision != expected_package_revision:
                raise AssemblyConflictError("package_revision_conflict")
            revision = build_revision(command, revision_id, len(history) + 1,
                                      history[-1].id if history else None, template, inputs,
                                      self._candidates(), explicit)
            self._revisions[session_id] = [*history, revision]
            self._commands[command.operation_id] = (command.request_digest, revision)
            return revision

    def decide(
        self, command: CommandIdentity, *, decision_id: EntityId, session_id: EntityId,
        revision_number: int, expected_revision: int, expected_decision_count: int,
        action: AssemblyAction, reason: str,
    ) -> AssemblyApprovalDecision:
        with self._lock:
            replay = self._replay(command, AssemblyApprovalDecision)
            if replay is not None:
                return replay
            inputs = self._resolved_inputs(session_id)
            revisions = self._revisions.get(session_id, [])
            decisions = self._decisions.get(session_id, [])
            decision_count = sum(d.revision_id == revisions[-1].id for d in decisions) if (
                revisions
            ) else 0
            if not revisions or len(revisions) != expected_revision or (
                revision_number != expected_revision or decision_count != expected_decision_count
            ):
                raise AssemblyConflictError("assembly_revision_conflict")
            revision = revisions[-1]
            approved = frozenset(c.revision.id for c in self._candidates()
                                 if c.approval_state == ApprovalState.APPROVED)
            if revision.validation.state != "valid" or is_stale(
                revision, inputs.package_revision, approved, inputs.metadata,
            ):
                raise AssemblyConflictError("assembly_not_approvable")
            decision = AssemblyApprovalDecision(
                decision_id, session_id, revision.id, len(decisions) + 1, command.actor_id,
                command.recorded_at, action, reason,
            )
            self._decisions[session_id] = [*decisions, decision]
            self._commands[command.operation_id] = (command.request_digest, decision)
            return decision

    def list_templates(
        self, event_id: EntityId, *, after: EntityId | None = None, limit: int = 50,
    ) -> TemplatePage:
        validate_page(limit)
        with self._lock:
            all_items = sorted((t for t in self._templates.values() if t.event_id == event_id),
                               key=lambda t: t.id.value)
            selected = [t for t in all_items if after is None or t.id.value > after.value]
            items = tuple(selected[:limit])
            return TemplatePage(items, len(all_items),
                                items[-1].id if len(selected) > limit else None)

    def list_revisions(
        self, event_id: EntityId, session_id: EntityId, *, after: int = 0, limit: int = 50,
    ) -> AssemblyPage:
        validate_page(limit)
        nonnegative(after, "after")
        with self._lock:
            inputs = self._resolved_inputs(session_id)
            if inputs.event_id != event_id:
                raise AssemblyNotFoundError("session_not_in_event")
            history = self._revisions.get(session_id, [])
            selected = [r for r in history if r.revision_number > after]
            approved = frozenset(c.revision.id for c in self._candidates()
                                 if c.approval_state == ApprovalState.APPROVED)
            items: list[SessionAssembly] = []
            for revision in selected[:limit]:
                decisions = [d for d in self._decisions.get(session_id, [])
                             if d.revision_id == revision.id]
                latest = decisions[-1] if decisions else None
                state = ApprovalState.UNREVIEWED if latest is None else (
                    ApprovalState.APPROVED if latest.action == AssemblyAction.APPROVE
                    else ApprovalState.REJECTED
                )
                items.append(SessionAssembly(revision, len(history), is_stale(
                    revision, inputs.package_revision, approved, inputs.metadata,
                ), state, len(decisions), latest))
            return AssemblyPage(tuple(items), len(history),
                                items[-1].revision.revision_number
                                if len(selected) > limit else None)
