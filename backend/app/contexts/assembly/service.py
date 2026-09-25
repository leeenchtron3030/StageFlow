from datetime import UTC

from app.shared.human_commands import human_command_digest
from app.shared.ids import EntityId
from app.shared.time import Clock
from app.shared.time.validation import normalize_utc_datetime

from .contracts import (
    ApprovalAction,
    CommandIdentity,
    ExternalContent,
    PackagingAsset,
    PackagingAssetApprovalDecision,
    PackagingAssetRevision,
    PackagingAssetRole,
    RevisionContent,
    bounded_text,
    nonnegative,
)
from .repository import PackagingAssetRepository


class PackagingAssetService:
    def __init__(self, repository: PackagingAssetRepository, clock: Clock) -> None:
        self.repository = repository
        self.clock = clock

    def _command(
        self, operation_id: EntityId, actor_id: EntityId, document: dict[str, object],
    ) -> CommandIdentity:
        return CommandIdentity(
            operation_id, actor_id,
            human_command_digest({**document, "actor_id": actor_id.value}),
            normalize_utc_datetime(self.clock.now(), "recorded_at"),
        )

    def register(
        self, *, operation_id: EntityId, actor_id: EntityId, event_id: EntityId,
        name: str, role: PackagingAssetRole, stage_id: EntityId | None = None,
    ) -> PackagingAsset:
        role = PackagingAssetRole(role)
        name = name.strip()
        command = self._command(operation_id, actor_id, {
            "kind": "packaging_asset_registration", "event_id": event_id.value,
            "stage_id": None if stage_id is None else stage_id.value,
            "name": name, "role": role.value,
        })
        return self.repository.register(command, PackagingAsset(
            EntityId.new(), event_id, stage_id, name, role, command.recorded_at,
        ))

    def revise(
        self, *, operation_id: EntityId, actor_id: EntityId, packaging_asset_id: EntityId,
        expected_revision: int, content: RevisionContent,
    ) -> PackagingAssetRevision:
        nonnegative(expected_revision, "expected_revision")
        reference = content.reference
        reference_document: dict[str, object]
        if isinstance(reference, ExternalContent):
            reference_document = {
                "kind": "external_content", "content_key": reference.content_key,
                "sha256": reference.sha256, "byte_size": reference.byte_size,
                "media_type": reference.media_type,
            }
        else:
            reference_document = {
                "kind": "completed_media_asset", "asset_id": reference.asset_id.value,
            }
        command = self._command(operation_id, actor_id, {
            "kind": "packaging_asset_revision", "packaging_asset_id": packaging_asset_id.value,
            "expected_revision": expected_revision, "reference": reference_document,
            "measured_duration_microseconds": content.measured_duration_microseconds,
            "effective_from": (None if content.effective_from is None
                               else content.effective_from.astimezone(UTC).isoformat()),
            "effective_until": (None if content.effective_until is None
                                else content.effective_until.astimezone(UTC).isoformat()),
        })
        return self.repository.revise(command, PackagingAssetRevision(
            EntityId.new(), packaging_asset_id, expected_revision + 1, content, command.recorded_at,
        ), expected_revision=expected_revision)

    def decide(
        self, *, operation_id: EntityId, actor_id: EntityId, packaging_asset_id: EntityId,
        revision_number: int, expected_revision: int, action: ApprovalAction, reason: str,
    ) -> PackagingAssetApprovalDecision:
        nonnegative(expected_revision, "expected_revision")
        nonnegative(revision_number, "revision_number")
        if revision_number == 0:
            raise ValueError("revision_number must be positive")
        action = ApprovalAction(action)
        reason = reason.strip()
        bounded_text(reason, "reason", 500)
        command = self._command(operation_id, actor_id, {
            "kind": "packaging_asset_approval", "packaging_asset_id": packaging_asset_id.value,
            "revision_number": revision_number, "expected_revision": expected_revision,
            "action": action.value, "reason": reason,
        })
        return self.repository.decide(
            command, decision_id=EntityId.new(), packaging_asset_id=packaging_asset_id,
            revision_number=revision_number, expected_revision=expected_revision,
            action=action, reason=reason,
        )
