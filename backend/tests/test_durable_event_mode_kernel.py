from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from app.contexts.events import (
    BootstrapStatus,
    EventStageBootstrapRequest,
    StageBootstrapDefinition,
)
from app.contexts.production.event_mode_kernel.contracts import (
    AssociationAuthority,
    AssociationStatus,
    EpistemicKind,
    MediaCandidate,
    MediaRegistrationState,
    ReconciliationStatus,
    RegisteredMediaAsset,
    SessionPackageState,
    StartSessionRequest,
)
from app.contexts.production.event_mode_kernel.repository import (
    InMemoryEventModeKernelRepository,
    KernelConflictError,
    KernelStorageUnavailableError,
)
from app.contexts.production.event_mode_kernel.service import (
    DurableEventModeKernel,
    StableAssetIngressPublisher,
)
from app.contexts.production.ingress import InMemoryIngressRepository
from app.core.config.deployment import load_kernel_deployment_configuration
from app.infrastructure.postgres import (
    PostgresEventModeKernelRepository,
    PostgresIngressRepository,
    PostgresMigrationRunner,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock

NOW = datetime(2026, 8, 8, 17, 0, tzinfo=UTC)
ACTOR_ID = EntityId("20000000-0000-0000-0000-000000000001")
BOOTSTRAP_OPERATION_ID = EntityId("20000000-0000-0000-0000-000000000002")


def entity_id(number: int) -> EntityId:
    return EntityId(f"20000000-0000-0000-0000-{number:012d}")


def bootstrap_request(
    *,
    operation_id: EntityId = BOOTSTRAP_OPERATION_ID,
    event_name: str = "StageFlow Summit",
    include_second_stage: bool = True,
) -> EventStageBootstrapRequest:
    stages = [
        StageBootstrapDefinition(
            key="main",
            name="Main Stage",
            source_bindings={"main-recorder": "C:/event/main"},
            external_references={"pretalx": "room-main"},
        )
    ]
    if include_second_stage:
        stages.append(
            StageBootstrapDefinition(
                key="studio",
                name="Studio",
                source_bindings={"studio-recorder": "C:/event/studio"},
            )
        )
    return EventStageBootstrapRequest(
        operation_id=operation_id,
        event_key="summit-2026",
        event_name=event_name,
        stages=tuple(stages),
        actor_id=ACTOR_ID,
        requested_at=NOW,
        external_references={"pretalx": "event-42"},
    )


def kernel_with_bootstrap() -> tuple[
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
    EntityId,
    EntityId,
    EntityId,
]:
    repository = InMemoryEventModeKernelRepository()
    kernel = DurableEventModeKernel(repository=repository, clock=FixedClock(NOW))
    result = kernel.bootstrap(bootstrap_request())
    assert result.event is not None
    main = next(stage for stage in result.stages if stage.key == "main")
    studio = next(stage for stage in result.stages if stage.key == "studio")
    return kernel, repository, result.event.id, main.id, studio.id


def make_candidate(
    stage_id: EntityId,
    *,
    number: int,
    source_binding: str = "main-recorder",
) -> MediaCandidate:
    return MediaCandidate(
        id=entity_id(number),
        proposed_asset_id=entity_id(number + 100),
        stage_id=stage_id,
        source_binding_key=source_binding,
        source_reference=f"C:/event/media-{number}.mkv",
        discovered_at=NOW,
        last_observed_at=NOW,
        state=MediaRegistrationState.DISCOVERED,
        revision=1,
    )


def ready_asset(
    kernel: DurableEventModeKernel,
    stage_id: EntityId,
    *,
    number: int,
    media_start: datetime | None = None,
    media_end: datetime | None = None,
    source_binding: str = "main-recorder",
) -> RegisteredMediaAsset:
    candidate = make_candidate(
        stage_id,
        number=number,
        source_binding=source_binding,
    )
    kernel.register_candidate(candidate)
    kernel.record_resource_observation(
        candidate_id=candidate.id,
        observation_kind="resource_snapshot",
        observed_at=NOW,
        facts={"size_bytes": 42, "present": True},
    )
    kernel.record_readiness(
        candidate_id=candidate.id,
        ready=True,
        evaluated_at=NOW,
        policy_id="conservative-v1",
        evidence_ids=(),
    )
    return RegisteredMediaAsset(
        id=candidate.proposed_asset_id,
        candidate_id=candidate.id,
        manifest_id=entity_id(number + 200),
        stage_id=stage_id,
        source_binding_key=source_binding,
        registered_at=NOW,
        media_started_at=media_start,
        media_ended_at=media_end,
    )


def test_versioned_configuration_resolves_secret_and_redacts_it(tmp_path: Path) -> None:
    path = tmp_path / "event.toml"
    path.write_text(
        """
schema_version = "1.0"
deployment_id = "razer-reference"
node_id = "node-razer"
node_role = "node"
event_mode = "event"
network_policy = "local_only"
postgres_dsn_secret_ref = "STAGEFLOW_KERNEL_DSN"

[event]
key = "summit-2026"
name = "StageFlow Summit"

[[event.stages]]
key = "main"
name = "Main Stage"

[[event.stages.sources]]
key = "main-recorder"
path = "C:/event/main"
""".strip(),
        encoding="utf-8",
    )

    effective = load_kernel_deployment_configuration(
        path,
        environment={"STAGEFLOW_KERNEL_DSN": "postgresql://secret-value"},
    )

    assert effective.postgres_dsn == "postgresql://secret-value"
    assert effective.sources == {"main-recorder": "C:/event/main"}
    assert effective.redacted_summary()["postgres_dsn"] == "<redacted>"
    assert effective.field_sources["postgres_dsn"] == (
        "environment:STAGEFLOW_KERNEL_DSN"
    )
    assert "secret-value" not in str(effective.redacted_summary())


def test_configuration_rejects_relative_or_parent_traversing_source_paths(
    tmp_path: Path,
) -> None:
    path = tmp_path / "event.toml"
    path.write_text(
        """
schema_version = "1.0"
deployment_id = "test"
node_id = "test-node"
node_role = "development"
postgres_dsn_secret_ref = "TEST_DSN"
[event]
key = "test-event"
name = "Test Event"
[[event.stages]]
key = "main"
name = "Main"
[[event.stages.sources]]
key = "source"
path = "../recordings"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="absolute"):
        load_kernel_deployment_configuration(
            path,
            environment={"TEST_DSN": "postgresql://test"},
        )


def test_configuration_fails_when_secret_reference_is_unresolved(tmp_path: Path) -> None:
    path = tmp_path / "event.toml"
    path.write_text(
        """
schema_version = "1.0"
deployment_id = "test"
node_id = "test-node"
node_role = "development"
postgres_dsn_secret_ref = "MISSING_DSN"
[event]
key = "test-event"
name = "Test Event"
[[event.stages]]
key = "main"
name = "Main"
[[event.stages.sources]]
key = "source"
path = "C:/event"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unresolved"):
        load_kernel_deployment_configuration(path, environment={})


def test_bootstrap_is_idempotent_and_preserves_internal_identity() -> None:
    repository = InMemoryEventModeKernelRepository()
    first = repository.bootstrap(bootstrap_request())
    replay = repository.bootstrap(bootstrap_request(operation_id=entity_id(3)))
    updated = repository.bootstrap(
        bootstrap_request(operation_id=entity_id(4), event_name="StageFlow Summit 2026")
    )

    assert first.status is BootstrapStatus.CREATED
    assert replay.status is BootstrapStatus.RESOLVED
    assert updated.status is BootstrapStatus.UPDATED
    assert first.event is not None and replay.event is not None and updated.event is not None
    assert first.event.id == replay.event.id == updated.event.id
    assert {stage.key: stage.id for stage in first.stages} == {
        stage.key: stage.id for stage in updated.stages
    }
    assert updated.event.revision == 2


def test_bootstrap_rejects_structural_removal_without_mutating_existing_state() -> None:
    repository = InMemoryEventModeKernelRepository()
    first = repository.bootstrap(bootstrap_request())
    conflict = repository.bootstrap(
        bootstrap_request(operation_id=entity_id(5), include_second_stage=False)
    )

    assert conflict.status is BootstrapStatus.CONFLICT
    assert conflict.reason == "stage_removal_not_permitted"
    assert {stage.key for stage in conflict.stages} == {"main", "studio"}
    assert conflict.event == first.event


def test_human_session_start_supports_expectation_and_ad_hoc_session() -> None:
    kernel, repository, event_id, main_id, studio_id = kernel_with_bootstrap()
    expectation = kernel.record_program_expectation(
        event_id=event_id,
        key="opening",
        title="Opening Keynote",
        stage_id=main_id,
        planned_start=NOW,
        planned_end=NOW + timedelta(minutes=45),
        external_references={"pretalx": "talk-1"},
    )
    started = kernel.start_session(
        StartSessionRequest(
            operation_id=entity_id(20),
            event_id=event_id,
            stage_id=main_id,
            program_expectation_id=expectation.id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW + timedelta(minutes=2),
            requested_at=NOW + timedelta(minutes=2),
        )
    )
    replay = kernel.start_session(
        StartSessionRequest(
            operation_id=entity_id(20),
            event_id=event_id,
            stage_id=main_id,
            program_expectation_id=expectation.id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW + timedelta(minutes=2),
            requested_at=NOW + timedelta(minutes=2),
        )
    )
    ad_hoc = kernel.start_session(
        StartSessionRequest(
            operation_id=entity_id(21),
            event_id=event_id,
            stage_id=studio_id,
            program_expectation_id=None,
            actor_id=ACTOR_ID,
            authoritative_start=NOW + timedelta(minutes=3),
            requested_at=NOW + timedelta(minutes=3),
            title="Ad hoc discussion",
        )
    )

    assert replay.id == started.id
    assert started.program_expectation_id == expectation.id
    assert ad_hoc.program_expectation_id is None
    with pytest.raises(KernelConflictError, match="active_session"):
        repository.start_session(
            StartSessionRequest(
                operation_id=entity_id(22),
                event_id=event_id,
                stage_id=main_id,
                actor_id=ACTOR_ID,
                authoritative_start=NOW + timedelta(minutes=4),
                requested_at=NOW + timedelta(minutes=4),
            )
        )


def test_active_and_compatible_trailing_media_associate_deterministically() -> None:
    kernel, _, event_id, main_id, _ = kernel_with_bootstrap()
    session = kernel.start_session(
        StartSessionRequest(
            operation_id=entity_id(30),
            event_id=event_id,
            stage_id=main_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    active_asset = ready_asset(kernel, main_id, number=40)
    _, active_association, _ = kernel.register_completed_asset(active_asset)
    kernel.correct_session_boundary(
        operation_id=EntityId.new(),
        session_id=session.id,
        boundary_kind="end",
        boundary_at=NOW + timedelta(minutes=45),
        actor_id=ACTOR_ID,
        reason="presentation_and_qa_ended",
    )
    trailing_asset = ready_asset(
        kernel,
        main_id,
        number=41,
        media_start=NOW + timedelta(minutes=44),
        media_end=NOW + timedelta(minutes=47),
    )
    _, trailing_association, _ = kernel.register_completed_asset(trailing_asset)

    assert active_association.status is AssociationStatus.ASSOCIATED
    assert trailing_association.status is AssociationStatus.ASSOCIATED
    assert active_association.session_id == trailing_association.session_id == session.id
    assert trailing_association.authority is AssociationAuthority.DETERMINISTIC


def test_delayed_media_ambiguous_between_previous_and_current_session_is_unresolved() -> None:
    kernel, _, event_id, main_id, _ = kernel_with_bootstrap()
    first = kernel.start_session(
        StartSessionRequest(
            operation_id=entity_id(50),
            event_id=event_id,
            stage_id=main_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    kernel.correct_session_boundary(
        operation_id=EntityId.new(),
        session_id=first.id,
        boundary_kind="end",
        boundary_at=NOW + timedelta(minutes=45),
        actor_id=ACTOR_ID,
        reason="ended",
    )
    second = kernel.start_session(
        StartSessionRequest(
            operation_id=entity_id(51),
            event_id=event_id,
            stage_id=main_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW + timedelta(minutes=50),
            requested_at=NOW + timedelta(minutes=50),
        )
    )
    delayed = ready_asset(
        kernel,
        main_id,
        number=52,
        media_start=NOW + timedelta(minutes=44),
        media_end=NOW + timedelta(minutes=52),
    )
    _, association, _ = kernel.register_completed_asset(delayed)

    assert association.status is AssociationStatus.UNRESOLVED
    assert association.session_id is None
    assert "multiple_eligible_sessions" in association.reason_codes
    assert second.id != first.id


def test_interval_less_turnover_media_is_unresolved_with_truthful_provenance() -> None:
    kernel, _, event_id, main_id, _ = kernel_with_bootstrap()
    first = kernel.start_session(
        StartSessionRequest(
            operation_id=entity_id(53),
            event_id=event_id,
            stage_id=main_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    kernel.correct_session_boundary(
        operation_id=entity_id(54),
        session_id=first.id,
        boundary_kind="end",
        boundary_at=NOW + timedelta(minutes=45),
        actor_id=ACTOR_ID,
        reason="ended",
    )
    second = kernel.start_session(
        StartSessionRequest(
            operation_id=entity_id(57),
            event_id=event_id,
            stage_id=main_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW + timedelta(minutes=50),
            requested_at=NOW + timedelta(minutes=50),
        )
    )

    _, association, _ = kernel.register_completed_asset(
        ready_asset(kernel, main_id, number=58)
    )

    assert association.status is AssociationStatus.UNRESOLVED
    assert association.policy_id == "stageflow.kernel.media-association"
    assert association.policy_version == "1.1.0"
    session_inputs = {
        (value.record_id, value.revision)
        for value in association.input_references
        if value.record_type == "session"
    }
    assert session_inputs == {(first.id.value, 2), (second.id.value, 1)}
    assert association.evidence_ids == ()


def test_trustworthy_turnover_intervals_select_only_the_supported_session() -> None:
    kernel, _, event_id, main_id, _ = kernel_with_bootstrap()
    first = kernel.start_session(
        StartSessionRequest(
            operation_id=entity_id(590),
            event_id=event_id,
            stage_id=main_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    kernel.correct_session_boundary(
        operation_id=entity_id(591),
        session_id=first.id,
        boundary_kind="end",
        boundary_at=NOW + timedelta(minutes=45),
        actor_id=ACTOR_ID,
        reason="ended",
    )
    second = kernel.start_session(
        StartSessionRequest(
            operation_id=entity_id(592),
            event_id=event_id,
            stage_id=main_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW + timedelta(minutes=50),
            requested_at=NOW + timedelta(minutes=50),
        )
    )
    _, previous, _ = kernel.register_completed_asset(
        ready_asset(
            kernel,
            main_id,
            number=593,
            media_start=NOW + timedelta(minutes=44),
            media_end=NOW + timedelta(minutes=45),
        )
    )
    _, current, _ = kernel.register_completed_asset(
        ready_asset(
            kernel,
            main_id,
            number=594,
            media_start=NOW + timedelta(minutes=51),
            media_end=NOW + timedelta(minutes=52),
        )
    )

    assert previous.session_id == first.id
    assert current.session_id == second.id


def test_post_session_media_without_temporal_overlap_remains_unresolved() -> None:
    kernel, _, event_id, main_id, _ = kernel_with_bootstrap()
    session = kernel.start_session(
        StartSessionRequest(
            operation_id=entity_id(55),
            event_id=event_id,
            stage_id=main_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    kernel.correct_session_boundary(
        operation_id=EntityId.new(),
        session_id=session.id,
        boundary_kind="end",
        boundary_at=NOW + timedelta(minutes=45),
        actor_id=ACTOR_ID,
        reason="ended",
    )
    unrelated = ready_asset(
        kernel,
        main_id,
        number=56,
        media_start=NOW + timedelta(minutes=46),
        media_end=NOW + timedelta(minutes=47),
    )

    _, association, _ = kernel.register_completed_asset(unrelated)

    assert association.status is AssociationStatus.UNRESOLVED
    assert association.session_id is None


def test_structural_conflict_preserves_asset_and_human_assignment_is_authoritative() -> None:
    kernel, repository, event_id, main_id, studio_id = kernel_with_bootstrap()
    main_session = kernel.start_session(
        StartSessionRequest(
            operation_id=entity_id(60),
            event_id=event_id,
            stage_id=main_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    asset = ready_asset(
        kernel,
        studio_id,
        number=61,
        source_binding="studio-recorder",
    )
    registered, automatic, _ = kernel.register_completed_asset(asset)
    conflict = kernel.assign_asset(
        operation_id=EntityId.new(),
        asset_id=registered.id,
        session_id=main_session.id,
        actor_id=ACTOR_ID,
        reason="operator_attempted_cross_stage_assignment",
    )

    assert repository.get_asset(registered.id) == registered
    assert automatic.status is AssociationStatus.UNRESOLVED
    assert conflict.status is AssociationStatus.CONFLICT
    assert conflict.authority is AssociationAuthority.HUMAN


def test_candidate_source_binding_must_belong_to_its_stage() -> None:
    kernel, _, _, main_id, _ = kernel_with_bootstrap()

    with pytest.raises(KernelConflictError, match="candidate_source_stage_conflict"):
        kernel.register_candidate(
            make_candidate(
                main_id,
                number=69,
                source_binding="studio-recorder",
            )
        )


def test_completion_requires_human_approval_and_late_media_reopens_revision() -> None:
    kernel, repository, event_id, main_id, _ = kernel_with_bootstrap()
    session = kernel.start_session(
        StartSessionRequest(
            operation_id=entity_id(70),
            event_id=event_id,
            stage_id=main_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    kernel.correct_session_boundary(
        operation_id=EntityId.new(),
        session_id=session.id,
        boundary_kind="end",
        boundary_at=NOW + timedelta(minutes=30),
        actor_id=ACTOR_ID,
        reason="ended",
    )
    kernel.mark_package_ready(session.id)
    completed = kernel.complete_package(
        operation_id=EntityId.new(),
        session_id=session.id,
        actor_id=ACTOR_ID,
        approved=True,
        reason="producer_approved_package",
    )
    late = ready_asset(
        kernel,
        main_id,
        number=71,
        media_start=NOW + timedelta(minutes=29),
        media_end=NOW + timedelta(minutes=32),
    )
    kernel.register_completed_asset(late)
    reopened = repository.get_session(session.id)

    assert completed.package_state is SessionPackageState.COMPLETE
    assert reopened is not None
    assert reopened.package_state is SessionPackageState.CORRECTION_REQUIRED
    assert reopened.package_revision == completed.package_revision + 1


@pytest.mark.parametrize(
    ("source_complete", "target_complete", "expected_source_revision", "expected_target_revision"),
    (
        (False, False, 1, 1),
        (True, False, 2, 1),
        (False, True, 1, 2),
        (True, True, 2, 2),
    ),
)
def test_reassignment_reopens_every_materially_changed_completed_package(
    source_complete: bool,
    target_complete: bool,
    expected_source_revision: int,
    expected_target_revision: int,
) -> None:
    kernel, repository, event_id, main_id, _ = kernel_with_bootstrap()
    source = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId.new(),
            event_id=event_id,
            stage_id=main_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    asset = ready_asset(
        kernel,
        main_id,
        number=720 + int(source_complete) * 10 + int(target_complete),
    )
    _, initial_association, _ = kernel.register_completed_asset(asset)
    assert initial_association.session_id == source.id
    kernel.correct_session_boundary(
        operation_id=EntityId.new(),
        session_id=source.id,
        boundary_kind="end",
        boundary_at=NOW + timedelta(minutes=30),
        actor_id=ACTOR_ID,
        reason="source_ended",
    )
    source_completion_id = None
    if source_complete:
        kernel.mark_package_ready(source.id)
        kernel.complete_package(
            operation_id=EntityId.new(),
            session_id=source.id,
            actor_id=ACTOR_ID,
            approved=True,
            reason="source_approved",
        )
        source_projection = next(
            item
            for item in repository.operational_status(event_id).stages[0].recent_sessions
            if item.session_id == source.id
        )
        source_completion_id = source_projection.completion_decision_id
        assert source_completion_id is not None
        assert repository.list_approved_package_asset_ids(source_completion_id) == (
            asset.id,
        )
    target = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId.new(),
            event_id=event_id,
            stage_id=main_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW + timedelta(minutes=35),
            requested_at=NOW + timedelta(minutes=35),
        )
    )
    if target_complete:
        kernel.mark_package_ready(target.id)
        kernel.complete_package(
            operation_id=EntityId.new(),
            session_id=target.id,
            actor_id=ACTOR_ID,
            approved=True,
            reason="target_approved",
        )

    operation_id = EntityId.new()
    reassigned = kernel.assign_asset(
        operation_id=operation_id,
        asset_id=asset.id,
        session_id=target.id,
        actor_id=ACTOR_ID,
        reason="corrected_membership",
    )
    replay = kernel.assign_asset(
        operation_id=operation_id,
        asset_id=asset.id,
        session_id=target.id,
        actor_id=ACTOR_ID,
        reason="corrected_membership",
    )

    current_source = repository.get_session(source.id)
    current_target = repository.get_session(target.id)
    assert current_source is not None and current_target is not None
    assert replay == reassigned
    assert current_source.package_revision == expected_source_revision
    assert current_target.package_revision == expected_target_revision
    if source_complete:
        assert current_source.package_state is SessionPackageState.CORRECTION_REQUIRED
        assert source_completion_id is not None
        assert repository.list_approved_package_asset_ids(source_completion_id) == (
            asset.id,
        )
    if target_complete:
        assert current_target.package_state is SessionPackageState.CORRECTION_REQUIRED


def test_human_boundary_assignment_and_completion_commands_are_idempotent() -> None:
    kernel, repository, event_id, main_id, _ = kernel_with_bootstrap()
    session = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId.new(),
            event_id=event_id,
            stage_id=main_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    boundary_operation = EntityId.new()
    ended = kernel.correct_session_boundary(
        operation_id=boundary_operation,
        session_id=session.id,
        boundary_kind="end",
        boundary_at=NOW + timedelta(minutes=30),
        actor_id=ACTOR_ID,
        reason="ended",
    )
    boundary_replay = kernel.correct_session_boundary(
        operation_id=boundary_operation,
        session_id=session.id,
        boundary_kind="end",
        boundary_at=NOW + timedelta(minutes=30),
        actor_id=ACTOR_ID,
        reason="ended",
    )
    assert boundary_replay == ended
    with pytest.raises(KernelConflictError, match="human_command_operation_id_conflict"):
        kernel.correct_session_boundary(
            operation_id=boundary_operation,
            session_id=session.id,
            boundary_kind="end",
            boundary_at=NOW + timedelta(minutes=31),
            actor_id=ACTOR_ID,
            reason="ended",
        )

    asset = ready_asset(
        kernel,
        main_id,
        number=760,
        media_start=NOW + timedelta(minutes=1),
        media_end=NOW + timedelta(minutes=2),
    )
    kernel.register_completed_asset(asset)
    assignment_operation = EntityId.new()
    assigned = kernel.assign_asset(
        operation_id=assignment_operation,
        asset_id=asset.id,
        session_id=session.id,
        actor_id=ACTOR_ID,
        reason="confirmed",
    )
    assignment_replay = kernel.assign_asset(
        operation_id=assignment_operation,
        asset_id=asset.id,
        session_id=session.id,
        actor_id=ACTOR_ID,
        reason="confirmed",
    )
    assert assignment_replay == assigned

    kernel.mark_package_ready(session.id)
    completion_operation = EntityId.new()
    completed = kernel.complete_package(
        operation_id=completion_operation,
        session_id=session.id,
        actor_id=ACTOR_ID,
        approved=True,
        reason="approved",
    )
    completion_replay = kernel.complete_package(
        operation_id=completion_operation,
        session_id=session.id,
        actor_id=ACTOR_ID,
        approved=True,
        reason="approved",
    )
    assert completion_replay == completed
    assert repository.get_session(session.id) == completed


def test_operational_session_projection_is_bounded_and_exposes_expectation_context() -> None:
    kernel, repository, event_id, main_id, _ = kernel_with_bootstrap()
    expectation = kernel.record_program_expectation(
        event_id=event_id,
        key="bounded-session",
        title="Bounded Producer Context",
        stage_id=main_id,
        planned_start=NOW,
        planned_end=NOW + timedelta(minutes=30),
    )
    latest = None
    for index in range(22):
        latest = kernel.start_session(
            StartSessionRequest(
                operation_id=EntityId.new(),
                event_id=event_id,
                stage_id=main_id,
                program_expectation_id=(expectation.id if index == 21 else None),
                actor_id=ACTOR_ID,
                authoritative_start=NOW + timedelta(hours=index),
                requested_at=NOW + timedelta(hours=index),
            )
        )
        kernel.correct_session_boundary(
            operation_id=EntityId.new(),
            session_id=latest.id,
            boundary_kind="end",
            boundary_at=NOW + timedelta(hours=index, minutes=30),
            actor_id=ACTOR_ID,
            reason="ended",
        )
    assert latest is not None

    stage = repository.operational_status(event_id).stages[0]

    assert stage.session_limit == 20
    assert len(stage.assembling_sessions) == 20
    assert stage.assembling_sessions_truncated is True
    assert len(stage.recent_sessions) == 20
    assert stage.recent_sessions_truncated is True
    latest_projection = next(
        item for item in stage.recent_sessions if item.session_id == latest.id
    )
    assert latest_projection.program_expectation_id == expectation.id
    assert latest_projection.program_expectation_title == expectation.title
    assert latest_projection.program_expectation_revision == expectation.revision


def test_stable_asset_ingress_replays_one_production_event_identity() -> None:
    ingress = InMemoryIngressRepository()
    publisher = StableAssetIngressPublisher(ingress)
    asset = RegisteredMediaAsset(
        id=entity_id(180),
        candidate_id=entity_id(80),
        manifest_id=entity_id(280),
        stage_id=entity_id(81),
        source_binding_key="main-recorder",
        registered_at=NOW,
    )

    first = publisher.publish(asset, received_at=NOW)
    replay = publisher.publish(asset, received_at=NOW + timedelta(seconds=1))

    assert first == replay


def test_completed_asset_replay_does_not_append_an_association_revision() -> None:
    kernel, repository, event_id, main_id, _ = kernel_with_bootstrap()
    session = kernel.start_session(
        StartSessionRequest(
            operation_id=entity_id(181),
            event_id=event_id,
            stage_id=main_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    asset = ready_asset(kernel, main_id, number=182)

    first_asset, first_association, _ = kernel.register_completed_asset(asset)
    replayed_asset, replayed_association, _ = kernel.register_completed_asset(asset)

    assert replayed_asset == first_asset
    assert replayed_association == first_association
    assert replayed_association.session_id == session.id
    assert repository.get_association(asset.id) is first_association


def test_reconciliation_controls_readiness_and_status_attention() -> None:
    kernel, repository, event_id, main_id, _ = kernel_with_bootstrap()
    running = kernel.begin_reconciliation(event_id=event_id, scope="startup")
    recovering = repository.operational_status(
        event_id,
        source_availability={"main-recorder": False, "studio-recorder": True},
    )
    completed = kernel.finish_reconciliation(
        running, candidates_seen=0, assets_registered=0
    )
    ready = repository.operational_status(
        event_id,
        source_availability={"main-recorder": True, "studio-recorder": True},
    )

    assert recovering.recovering is True
    assert recovering.ready is False
    assert any("source_unavailable" in code for code in recovering.attention_codes)
    assert completed.status is ReconciliationStatus.COMPLETED
    assert ready.ready is True
    assert next(stage for stage in ready.stages if stage.stage_id == main_id).source_available


def test_kernel_migration_is_normalized_typed_and_reversible() -> None:
    sql_directory = Path(__file__).parents[1] / "app" / "infrastructure" / "postgres" / "sql"
    forward = (sql_directory / "0002_event_mode_kernel_forward.sql").read_text(
        encoding="utf-8"
    )
    reverse = (sql_directory / "0002_event_mode_kernel_reverse.sql").read_text(
        encoding="utf-8"
    )
    projections_forward = (
        sql_directory / "0003_kernel_projections_forward.sql"
    ).read_text(encoding="utf-8")
    projections_reverse = (
        sql_directory / "0003_kernel_projections_reverse.sql"
    ).read_text(encoding="utf-8")
    corrections_forward = (
        sql_directory / "0004_kernel_review_corrections_forward.sql"
    ).read_text(encoding="utf-8")
    corrections_reverse = (
        sql_directory / "0004_kernel_review_corrections_reverse.sql"
    ).read_text(encoding="utf-8")

    for table in (
        "business_event",
        "stage",
        "program_expectation",
        "session",
        "session_boundary_history",
        "media_candidate",
        "media_resource_observation",
        "completed_media_asset_registry",
        "media_association_history",
        "session_completion_history",
        "reconciliation_run",
    ):
        assert f"stageflow.{table}" in forward
        assert f"stageflow.{table}" in reverse
    assert "generic_event" not in forward
    assert "event_store" not in forward
    assert "one_active_session_per_stage" in forward
    assert "stageflow.session_boundary_proposal" in projections_forward
    assert "stageflow.session_boundary_proposal" in projections_reverse
    assert "epistemic_kind IN ('observed', 'derived', 'inferred')" in projections_forward
    for table in ("human_command_idempotency", "session_completion_asset"):
        assert f"stageflow.{table}" in corrections_forward
        assert f"stageflow.{table}" in corrections_reverse
    assert "media_association_history_status_ck" in corrections_forward
    assert "media_association_policy_authority_ck" in corrections_forward
    assert "DROP SCHEMA" not in reverse
    assert "DROP SCHEMA" not in corrections_reverse


def test_postgres_unavailability_is_typed_without_memory_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*args: object, **kwargs: object) -> None:
        raise psycopg.OperationalError("offline")

    monkeypatch.setattr(psycopg.Connection, "connect", unavailable)

    with pytest.raises(KernelStorageUnavailableError, match="postgresql_unavailable"):
        PostgresEventModeKernelRepository("postgresql://unavailable").get_event_by_key(
            "summit-2026"
        )


_POSTGRES_DSN = os.getenv("STAGEFLOW_TEST_POSTGRES_DSN")


@pytest.mark.skipif(
    not _POSTGRES_DSN,
    reason="STAGEFLOW_TEST_POSTGRES_DSN is required for real Kernel durability checks.",
)
def test_real_postgres_kernel_reconstruction_and_history() -> None:
    assert _POSTGRES_DSN is not None
    PostgresMigrationRunner(_POSTGRES_DSN).apply_event_mode_kernel_v1()
    suffix = uuid4().hex
    event_key = f"kernel-test-{suffix}"
    source_key = f"source-{suffix}"
    request = EventStageBootstrapRequest(
        operation_id=EntityId.new(),
        event_key=event_key,
        event_name="Kernel Integration Event",
        stages=(
            StageBootstrapDefinition(
                key="main",
                name="Main",
                source_bindings={source_key: f"C:/kernel/{suffix}"},
            ),
        ),
        actor_id=EntityId.new(),
        requested_at=NOW,
    )
    first_repository = PostgresEventModeKernelRepository(_POSTGRES_DSN)
    first = first_repository.bootstrap(request)
    assert first.event is not None
    replay = PostgresEventModeKernelRepository(_POSTGRES_DSN).bootstrap(
        EventStageBootstrapRequest(
            operation_id=EntityId.new(),
            event_key=event_key,
            event_name="Kernel Integration Event",
            stages=request.stages,
            actor_id=request.actor_id,
            requested_at=NOW,
        )
    )
    assert replay.event is not None
    assert replay.event.id == first.event.id
    session = PostgresEventModeKernelRepository(_POSTGRES_DSN).start_session(
        StartSessionRequest(
            operation_id=EntityId.new(),
            event_id=first.event.id,
            stage_id=first.stages[0].id,
            actor_id=request.actor_id,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    reconstructed = PostgresEventModeKernelRepository(_POSTGRES_DSN).get_session(session.id)
    assert reconstructed == session
    durable_kernel = DurableEventModeKernel(
        repository=first_repository,
        clock=FixedClock(NOW),
        asset_ingress_publisher=StableAssetIngressPublisher(
            PostgresIngressRepository(_POSTGRES_DSN)
        ),
    )
    proposal = durable_kernel.propose_session_boundary(
        session_id=session.id,
        boundary_kind="end",
        boundary_at=NOW + timedelta(hours=1),
        epistemic_kind=EpistemicKind.DERIVED,
        proposer_id=EntityId.new(),
        evidence_ids=(EntityId.new(),),
        policy_id="integration-policy",
        policy_version="1.0",
        reason="durability verification",
    )
    asset = ready_asset(
        durable_kernel,
        first.stages[0].id,
        number=900,
        source_binding=source_key,
    )
    registered, association, production_event_id = durable_kernel.register_completed_asset(
        asset
    )
    replayed, replayed_association, replayed_event_id = (
        durable_kernel.register_completed_asset(asset)
    )
    restarted_repository = PostgresEventModeKernelRepository(_POSTGRES_DSN)

    assert replayed == registered
    assert replayed_association == association
    assert replayed_event_id == production_event_id
    assert restarted_repository.get_asset(registered.id) == registered
    assert restarted_repository.get_association(registered.id) == association
    assert association.session_id == session.id
    assert production_event_id is not None
    assert restarted_repository.list_boundary_proposals(session.id) == (proposal,)
    assert restarted_repository.get_session(session.id) == session
    registered_candidate = restarted_repository.get_candidate(registered.candidate_id)
    assert registered_candidate is not None
    replayed_candidate = restarted_repository.register_candidate(
        replace(
            registered_candidate,
            last_observed_at=registered_candidate.last_observed_at
            + timedelta(seconds=1),
            state=MediaRegistrationState.DISCOVERED,
        )
    )
    assert replayed_candidate.state is MediaRegistrationState.REGISTERED

    with psycopg.connect(_POSTGRES_DSN) as connection:
        boundary_count = connection.execute(
            "SELECT count(*) FROM stageflow.session_boundary_history WHERE session_id = %s",
            (session.id.value,),
        ).fetchone()
        assert boundary_count is not None and boundary_count[0] == 1
        ingress_count = connection.execute(
            """
            SELECT count(*) FROM stageflow.production_event_ingress
            WHERE production_event_id = %s
            """,
            (production_event_id.value,),
        ).fetchone()
        assert ingress_count is not None and ingress_count[0] == 1
        association_history_count = connection.execute(
            """
            SELECT count(*) FROM stageflow.media_association_history
            WHERE asset_id = %s
            """,
            (registered.id.value,),
        ).fetchone()
        assert association_history_count is not None
        assert association_history_count[0] == 1
        connection.execute(
            "DELETE FROM stageflow.media_association_history WHERE asset_id = %s",
            (registered.id.value,),
        )
        connection.execute(
            "DELETE FROM stageflow.media_association WHERE asset_id = %s",
            (registered.id.value,),
        )
        connection.execute(
            "DELETE FROM stageflow.completed_media_asset_registry WHERE asset_id = %s",
            (registered.id.value,),
        )
        connection.execute(
            "DELETE FROM stageflow.media_resource_observation WHERE candidate_id = %s",
            (registered.candidate_id.value,),
        )
        connection.execute(
            "DELETE FROM stageflow.media_candidate WHERE candidate_id = %s",
            (registered.candidate_id.value,),
        )
        connection.execute(
            "DELETE FROM stageflow.production_event_ingress WHERE production_event_id = %s",
            (production_event_id.value,),
        )
        connection.execute(
            "DELETE FROM stageflow.session_boundary_proposal WHERE session_id = %s",
            (session.id.value,),
        )
        connection.execute(
            "DELETE FROM stageflow.session_boundary_history WHERE session_id = %s",
            (session.id.value,),
        )
        connection.execute(
            "DELETE FROM stageflow.session_start_operation WHERE session_id = %s",
            (session.id.value,),
        )
        connection.execute(
            "DELETE FROM stageflow.session WHERE session_id = %s",
            (session.id.value,),
        )
        connection.execute(
            "DELETE FROM stageflow.event_stage_bootstrap_operation WHERE event_id = %s",
            (first.event.id.value,),
        )
        connection.execute(
            "DELETE FROM stageflow.stage_source_binding WHERE stage_id = %s",
            (first.stages[0].id.value,),
        )
        connection.execute(
            "DELETE FROM stageflow.stage WHERE event_id = %s",
            (first.event.id.value,),
        )
        connection.execute(
            "DELETE FROM stageflow.business_event WHERE event_id = %s",
            (first.event.id.value,),
        )


@pytest.mark.skipif(
    not _POSTGRES_DSN,
    reason="STAGEFLOW_TEST_POSTGRES_DSN is required for real Kernel correction checks.",
)
def test_real_postgres_reassignment_idempotency_provenance_and_history_constraints() -> None:
    assert _POSTGRES_DSN is not None
    PostgresMigrationRunner(_POSTGRES_DSN).apply_event_mode_kernel_v1()
    suffix = uuid4().hex
    source_key = f"correction-source-{suffix}"
    repository = PostgresEventModeKernelRepository(_POSTGRES_DSN)
    bootstrapped = repository.bootstrap(
        EventStageBootstrapRequest(
            operation_id=EntityId.new(),
            event_key=f"correction-event-{suffix}",
            event_name="Kernel Correction Integration Event",
            stages=(
                StageBootstrapDefinition(
                    key="main",
                    name="Main",
                    source_bindings={source_key: f"C:/correction/{suffix}"},
                ),
            ),
            actor_id=ACTOR_ID,
            requested_at=NOW,
        )
    )
    assert bootstrapped.event is not None
    event_id = bootstrapped.event.id
    stage_id = bootstrapped.stages[0].id
    kernel = DurableEventModeKernel(repository=repository, clock=FixedClock(NOW))
    source = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId.new(),
            event_id=event_id,
            stage_id=stage_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    number = int(uuid4().hex[:9], 16)
    asset = ready_asset(
        kernel,
        stage_id,
        number=number,
        source_binding=source_key,
    )
    _, automatic, _ = kernel.register_completed_asset(asset)
    assert automatic.session_id == source.id
    assert automatic.policy_id == "stageflow.kernel.media-association"
    assert automatic.input_references
    kernel.correct_session_boundary(
        operation_id=EntityId.new(),
        session_id=source.id,
        boundary_kind="end",
        boundary_at=NOW + timedelta(minutes=30),
        actor_id=ACTOR_ID,
        reason="source_ended",
    )
    kernel.mark_package_ready(source.id)
    kernel.complete_package(
        operation_id=EntityId.new(),
        session_id=source.id,
        actor_id=ACTOR_ID,
        approved=True,
        reason="source_approved",
    )
    target = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId.new(),
            event_id=event_id,
            stage_id=stage_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW + timedelta(minutes=35),
            requested_at=NOW + timedelta(minutes=35),
        )
    )
    kernel.mark_package_ready(target.id)
    kernel.complete_package(
        operation_id=EntityId.new(),
        session_id=target.id,
        actor_id=ACTOR_ID,
        approved=True,
        reason="target_approved",
    )
    before = repository.operational_status(event_id).stages[0].recent_sessions
    source_completion = next(
        item.completion_decision_id for item in before if item.session_id == source.id
    )
    target_completion = next(
        item.completion_decision_id for item in before if item.session_id == target.id
    )
    assert source_completion is not None and target_completion is not None
    assert repository.list_approved_package_asset_ids(source_completion) == (asset.id,)
    assert repository.list_approved_package_asset_ids(target_completion) == ()

    operation_id = EntityId.new()
    reassigned = kernel.assign_asset(
        operation_id=operation_id,
        asset_id=asset.id,
        session_id=target.id,
        actor_id=ACTOR_ID,
        reason="corrected_membership",
    )
    replay = kernel.assign_asset(
        operation_id=operation_id,
        asset_id=asset.id,
        session_id=target.id,
        actor_id=ACTOR_ID,
        reason="corrected_membership",
    )
    assert replay == reassigned
    assert PostgresEventModeKernelRepository(_POSTGRES_DSN).get_association(asset.id) == (
        reassigned
    )
    current_source = repository.get_session(source.id)
    current_target = repository.get_session(target.id)
    assert current_source is not None and current_target is not None
    assert current_source.package_state is SessionPackageState.CORRECTION_REQUIRED
    assert current_target.package_state is SessionPackageState.CORRECTION_REQUIRED
    assert current_source.package_revision == 2
    assert current_target.package_revision == 2
    assert repository.list_approved_package_asset_ids(source_completion) == (asset.id,)

    with psycopg.connect(_POSTGRES_DSN) as connection:
        command_count = connection.execute(
            """
            SELECT count(*) FROM stageflow.human_command_idempotency
            WHERE operation_id = %s
            """,
            (operation_id.value,),
        ).fetchone()
        history_count = connection.execute(
            """
            SELECT count(*) FROM stageflow.media_association_history
            WHERE operation_id = %s
            """,
            (operation_id.value,),
        ).fetchone()
        assert command_count is not None and command_count[0] == 1
        assert history_count is not None and history_count[0] == 1

    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(_POSTGRES_DSN) as connection:
            connection.execute(
                """
                INSERT INTO stageflow.media_association_history (
                    association_history_id, asset_id, association_revision,
                    association_status, session_id, authority, reason_codes,
                    evidence_ids, actor_id, decided_at, operation_id,
                    policy_id, policy_version, input_references
                ) VALUES (%s, %s, %s, 'impossible', NULL, 'deterministic',
                          '["invalid"]'::jsonb, '[]'::jsonb, NULL, %s, NULL,
                          'stageflow.kernel.media-association', '1.1.0',
                          '[{"record_type":"registered_media_asset","record_id":"invalid","revision":null}]'::jsonb)
                """,
                (EntityId.new().value, asset.id.value, 99, NOW),
            )

    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(_POSTGRES_DSN) as connection:
            connection.execute(
                """
                INSERT INTO stageflow.media_association_history (
                    association_history_id, asset_id, association_revision,
                    association_status, session_id, authority, reason_codes,
                    evidence_ids, actor_id, decided_at, operation_id,
                    policy_id, policy_version, input_references
                ) VALUES (%s, %s, %s, 'unresolved', NULL, 'deterministic',
                          '["missing_policy"]'::jsonb, '[]'::jsonb, NULL, %s, NULL,
                          NULL, NULL,
                          '[{"record_type":"registered_media_asset","record_id":"invalid","revision":null}]'::jsonb)
                """,
                (EntityId.new().value, asset.id.value, 100, NOW),
            )


@pytest.mark.skipif(
    not _POSTGRES_DSN,
    reason="STAGEFLOW_TEST_POSTGRES_DSN is required for transaction rollback checks.",
)
def test_real_postgres_reassignment_rolls_back_if_history_commit_fails() -> None:
    assert _POSTGRES_DSN is not None
    suffix = uuid4().hex
    source_key = f"rollback-source-{suffix}"
    repository = PostgresEventModeKernelRepository(_POSTGRES_DSN)
    bootstrapped = repository.bootstrap(
        EventStageBootstrapRequest(
            operation_id=EntityId.new(),
            event_key=f"rollback-event-{suffix}",
            event_name="Rollback Event",
            stages=(
                StageBootstrapDefinition(
                    key="main",
                    name="Main",
                    source_bindings={source_key: f"C:/rollback/{suffix}"},
                ),
            ),
            actor_id=ACTOR_ID,
            requested_at=NOW,
        )
    )
    assert bootstrapped.event is not None
    stage_id = bootstrapped.stages[0].id
    kernel = DurableEventModeKernel(repository=repository, clock=FixedClock(NOW))
    source = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId.new(),
            event_id=bootstrapped.event.id,
            stage_id=stage_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW,
            requested_at=NOW,
        )
    )
    number = int(uuid4().hex[:9], 16)
    asset = ready_asset(
        kernel,
        stage_id,
        number=number,
        source_binding=source_key,
    )
    _, current, _ = kernel.register_completed_asset(asset)
    kernel.correct_session_boundary(
        operation_id=EntityId.new(),
        session_id=source.id,
        boundary_kind="end",
        boundary_at=NOW + timedelta(minutes=30),
        actor_id=ACTOR_ID,
        reason="ended",
    )
    kernel.mark_package_ready(source.id)
    completed_source = kernel.complete_package(
        operation_id=EntityId.new(),
        session_id=source.id,
        actor_id=ACTOR_ID,
        approved=True,
        reason="approved",
    )
    target = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId.new(),
            event_id=bootstrapped.event.id,
            stage_id=stage_id,
            actor_id=ACTOR_ID,
            authoritative_start=NOW + timedelta(minutes=35),
            requested_at=NOW + timedelta(minutes=35),
        )
    )
    blocked_revision = current.revision + 1
    with psycopg.connect(_POSTGRES_DSN) as connection:
        connection.execute(
            """
            INSERT INTO stageflow.media_association_history (
                association_history_id, asset_id, association_revision,
                association_status, session_id, authority, reason_codes,
                evidence_ids, actor_id, decided_at, operation_id,
                policy_id, policy_version, input_references
            ) VALUES (%s, %s, %s, 'associated', %s, 'deterministic',
                      '["rollback_probe"]'::jsonb, '[]'::jsonb, NULL, %s, NULL,
                      'stageflow.kernel.media-association', '1.1.0',
                      '[{"record_type":"registered_media_asset","record_id":"rollback-probe","revision":null}]'::jsonb)
            """,
            (
                EntityId.new().value,
                asset.id.value,
                blocked_revision,
                source.id.value,
                NOW,
            ),
        )

    with pytest.raises(psycopg.errors.UniqueViolation):
        kernel.assign_asset(
            operation_id=EntityId.new(),
            asset_id=asset.id,
            session_id=target.id,
            actor_id=ACTOR_ID,
            reason="must_roll_back",
        )

    assert repository.get_association(asset.id) == current
    assert repository.get_session(source.id) == completed_source
    assert repository.get_session(target.id) == target
