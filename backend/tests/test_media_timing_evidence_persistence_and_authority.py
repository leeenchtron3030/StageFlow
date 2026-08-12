from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import psycopg
import pytest
from media_timing_evidence_fixtures import ASSET_ID, MANIFEST_ID, NOW, evidence_request

from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.production.event_mode_kernel import (
    AssociationStatus,
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
    MediaCandidate,
    MediaRegistrationState,
    RegisteredMediaAsset,
    StartSessionRequest,
)
from app.contexts.production.media_timing_evidence import (
    MediaTimingEvidenceApplication,
)
from app.contexts.production.media_timing_evidence.repository import (
    InMemoryMediaTimingEvidenceRepository,
)
from app.infrastructure.postgres import (
    PostgresMediaTimingEvidenceRepository,
    PostgresMigrationRunner,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock


def _kernel_with_authority() -> tuple[
    InMemoryEventModeKernelRepository,
    EntityId,
    EntityId,
]:
    repository = InMemoryEventModeKernelRepository()
    kernel = DurableEventModeKernel(repository=repository, clock=FixedClock(NOW))
    bootstrapped = kernel.bootstrap(
        EventStageBootstrapRequest(
            operation_id=EntityId.new(),
            event_key="mte-authority-test",
            event_name="MTE authority test",
            stages=(
                StageBootstrapDefinition(
                    key="main",
                    name="Main Stage",
                    source_bindings={"recorder": "C:/synthetic"},
                ),
            ),
            actor_id=EntityId.new(),
            requested_at=NOW,
        )
    )
    assert bootstrapped.event is not None
    stage = bootstrapped.stages[0]
    session = kernel.start_session(
        StartSessionRequest(
            operation_id=EntityId.new(),
            event_id=bootstrapped.event.id,
            stage_id=stage.id,
            actor_id=EntityId.new(),
            authoritative_start=NOW - timedelta(minutes=2),
            requested_at=NOW - timedelta(minutes=2),
        )
    )
    candidate = MediaCandidate(
        id=EntityId.new(),
        proposed_asset_id=ASSET_ID,
        stage_id=stage.id,
        source_binding_key="recorder",
        source_reference="synthetic-reference",
        discovered_at=NOW - timedelta(minutes=1),
        last_observed_at=NOW,
        state=MediaRegistrationState.DISCOVERED,
        revision=1,
    )
    kernel.register_candidate(candidate)
    kernel.record_readiness(
        candidate_id=candidate.id,
        ready=True,
        evaluated_at=NOW,
        policy_id="conservative-v1",
        evidence_ids=(),
    )
    asset = RegisteredMediaAsset(
        id=ASSET_ID,
        candidate_id=candidate.id,
        manifest_id=MANIFEST_ID,
        stage_id=stage.id,
        source_binding_key="recorder",
        registered_at=NOW,
    )
    kernel.register_completed_asset(asset)
    return repository, session.id, asset.id


def test_mte_application_does_not_mutate_session_association_or_package_authority() -> None:
    kernel_repository, session_id, asset_id = _kernel_with_authority()
    before_session = kernel_repository.get_session(session_id)
    before_association = kernel_repository.get_association(asset_id)
    before_asset = kernel_repository.get_asset(asset_id)
    assert before_association is not None
    assert before_association.status is AssociationStatus.ASSOCIATED

    evidence_repository = InMemoryMediaTimingEvidenceRepository()
    evidence_repository.register_asset(ASSET_ID, MANIFEST_ID)
    applied = MediaTimingEvidenceApplication(evidence_repository).apply(
        evidence_request()
    )

    assert applied.result.derivations[0].epistemic_kind.value == "derived"
    assert kernel_repository.get_session(session_id) == before_session
    assert kernel_repository.get_association(asset_id) == before_association
    assert kernel_repository.get_asset(asset_id) == before_asset


def test_migration_is_additive_typed_and_reversible() -> None:
    sql = Path(__file__).parents[1] / "app" / "infrastructure" / "postgres" / "sql"
    forward = (sql / "0006_media_timing_evidence_forward.sql").read_text(encoding="utf-8")
    reverse = (sql / "0006_media_timing_evidence_reverse.sql").read_text(encoding="utf-8")

    assert "REFERENCES stageflow.completed_media_asset_registry(asset_id)" in forward
    assert "epistemic_kind = 'observed'" in forward
    assert "epistemic_kind = 'derived'" in forward
    assert "timestamptz" in forward
    assert "media_timing_evidence_application" in forward
    assert "session" not in forward.casefold().replace("schema_migration", "")
    assert "DROP TABLE IF EXISTS stageflow.media_timing_evidence" in reverse
    assert "completed_media_asset_registry" not in reverse


_POSTGRES_DSN = os.getenv("STAGEFLOW_TEST_POSTGRES_DSN")


@pytest.mark.skipif(
    not _POSTGRES_DSN,
    reason="STAGEFLOW_TEST_POSTGRES_DSN is required for real MTE migration checks.",
)
def test_real_postgres_mte_restart_replay_revision_and_reversal() -> None:
    assert _POSTGRES_DSN is not None
    runner = PostgresMigrationRunner(_POSTGRES_DSN)
    runner.apply_event_mode_kernel_v1()
    suffix = EntityId.new().value
    event_id = EntityId.new()
    stage_id = EntityId.new()
    candidate_id = EntityId.new()
    asset_id = EntityId.new()
    manifest_id = EntityId.new()
    with psycopg.connect(_POSTGRES_DSN) as connection:
        connection.execute(
            """
            INSERT INTO stageflow.business_event (
                event_id, event_key, name, revision, created_at, updated_at
            ) VALUES (%s, %s, %s, 1, %s, %s)
            """,
            (event_id.value, f"mte-{suffix}", "MTE test", NOW, NOW),
        )
        connection.execute(
            """
            INSERT INTO stageflow.stage (
                stage_id, event_id, stage_key, name, revision, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, 1, %s, %s)
            """,
            (stage_id.value, event_id.value, f"stage-{suffix}", "Stage", NOW, NOW),
        )
        connection.execute(
            """
            INSERT INTO stageflow.stage_source_binding (
                source_binding_key, stage_id, source_reference, revision, updated_at
            ) VALUES (%s, %s, %s, 1, %s)
            """,
            (f"source-{suffix}", stage_id.value, "sanitized-reference", NOW),
        )
        connection.execute(
            """
            INSERT INTO stageflow.media_candidate (
                candidate_id, proposed_asset_id, stage_id, source_binding_key,
                source_reference, discovered_at, last_observed_at,
                registration_state, revision
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'registered', 1)
            """,
            (
                candidate_id.value,
                asset_id.value,
                stage_id.value,
                f"source-{suffix}",
                "sanitized-reference",
                NOW,
                NOW,
            ),
        )
        connection.execute(
            """
            INSERT INTO stageflow.completed_media_asset_registry (
                asset_id, candidate_id, manifest_id, stage_id,
                source_binding_key, registered_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                asset_id.value,
                candidate_id.value,
                manifest_id.value,
                stage_id.value,
                f"source-{suffix}",
                NOW,
            ),
        )

    first_request = evidence_request()
    first_request = first_request.__class__(
        operation_id=EntityId.new(),
        asset_id=asset_id,
        manifest_id=manifest_id,
        manifest_version=first_request.manifest_version,
        applied_at=first_request.applied_at,
        result=first_request.result,
    )
    first_repository = PostgresMediaTimingEvidenceRepository(_POSTGRES_DSN)
    first = MediaTimingEvidenceApplication(first_repository).apply(first_request)
    second_base = evidence_request(
        operation_number=11,
        inspected_at=NOW + timedelta(minutes=5),
        provider_id="alternate-probe",
        profile_revision=2,
    )
    second_request = second_base.__class__(
        operation_id=EntityId.new(),
        asset_id=asset_id,
        manifest_id=manifest_id,
        manifest_version=second_base.manifest_version,
        applied_at=second_base.applied_at,
        result=second_base.result,
    )
    second = MediaTimingEvidenceApplication(first_repository).apply(second_request)
    reconstructed = PostgresMediaTimingEvidenceRepository(_POSTGRES_DSN)
    replay = MediaTimingEvidenceApplication(reconstructed).apply(first_request)

    assert replay == first
    assert second.revision == 2
    assert second.predecessor_evidence_id == first.id
    assert reconstructed.get_active(asset_id) == second
    assert reconstructed.history(asset_id) == (first, second)

    runner.reverse_media_timing_evidence_v1()
    with psycopg.connect(_POSTGRES_DSN) as connection:
        asset_count = connection.execute(
            "SELECT count(*) FROM stageflow.completed_media_asset_registry WHERE asset_id = %s",
            (asset_id.value,),
        ).fetchone()
        migration_count = connection.execute(
            "SELECT count(*) FROM stageflow.schema_migration WHERE version = %s",
            ("0006_media_timing_evidence",),
        ).fetchone()
    assert asset_count == (1,)
    assert migration_count == (0,)
    runner.apply_media_timing_evidence_v1()
