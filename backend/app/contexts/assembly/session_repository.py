from typing import Protocol

from app.shared.ids import EntityId

from .contracts import CommandIdentity
from .session_contracts import (
    AssemblyAction,
    AssemblyApprovalDecision,
    AssemblyPage,
    AssemblyRevision,
    AssemblyTemplate,
    ExplicitBinding,
    TemplatePage,
)


class AssemblyConflictError(RuntimeError):
    pass


class AssemblyNotFoundError(LookupError):
    pass


class AssemblyStorageUnavailableError(RuntimeError):
    pass


class SessionAssemblyRepository(Protocol):
    def create_template(
        self, command: CommandIdentity, template: AssemblyTemplate, expected_version: int,
    ) -> AssemblyTemplate: ...

    def propose(
        self, command: CommandIdentity, *, revision_id: EntityId, session_id: EntityId,
        template_id: EntityId, expected_revision: int, expected_package_revision: int,
        explicit: tuple[ExplicitBinding, ...],
    ) -> AssemblyRevision: ...

    def decide(
        self, command: CommandIdentity, *, decision_id: EntityId, session_id: EntityId,
        revision_number: int, expected_revision: int, expected_decision_count: int,
        action: AssemblyAction, reason: str,
    ) -> AssemblyApprovalDecision: ...

    def list_templates(
        self, event_id: EntityId, *, after: EntityId | None = None, limit: int = 50,
    ) -> TemplatePage: ...

    def list_revisions(
        self, event_id: EntityId, session_id: EntityId, *, after: int = 0, limit: int = 50,
    ) -> AssemblyPage: ...
