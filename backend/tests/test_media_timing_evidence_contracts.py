from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest
from media_timing_evidence_fixtures import (
    ASSET_ID,
    MANIFEST_ID,
    NOW,
    changed_evidence_request,
    evidence_request,
)

from app.contexts.production.media_timing_evidence import (
    MediaTimingDerivation,
    MediaTimingEvidenceApplication,
    MediaTimingEvidenceConflictError,
    MediaTimingObservation,
    TimingTimezoneKind,
)
from app.contexts.production.media_timing_evidence.repository import (
    InMemoryMediaTimingEvidenceRepository,
)
from app.shared.ids import EntityId


def repository() -> InMemoryMediaTimingEvidenceRepository:
    value = InMemoryMediaTimingEvidenceRepository()
    value.register_asset(ASSET_ID, MANIFEST_ID)
    return value


def test_observed_and_derived_evidence_are_structurally_distinct_and_immutable() -> None:
    request = evidence_request()
    observation = request.result.observations[0]
    derivation = request.result.derivations[0]

    assert observation.epistemic_kind.value == "observed"
    assert derivation.epistemic_kind.value == "derived"
    assert observation.normalized_timestamp == NOW
    assert derivation.input_observation_ids == tuple(
        sorted(
            (item.id for item in request.result.observations),
            key=lambda value: value.value,
        )
    )
    with pytest.raises(FrozenInstanceError):
        observation.kind = "declared"  # type: ignore[misc]


def test_naive_and_sensitive_observations_fail_before_application() -> None:
    with pytest.raises(ValueError, match="Naive timing evidence"):
        MediaTimingObservation(
            id=EntityId.new(),
            kind="embedded_creation_time",
            source_field="format.tags.creation_time",
            original_representation="2026-08-12 18:24:01",
            observed_at=NOW,
            timezone_kind=TimingTimezoneKind.NAIVE_UNQUALIFIED,
            normalized_timestamp=NOW,
        )
    with pytest.raises(ValueError, match="private path or media filename"):
        replace(
            evidence_request().result.observations[0],
            original_representation="C:\\private\\event\\segment.mp4",
        )
    with pytest.raises(ValueError, match="private path or media filename"):
        replace(
            evidence_request().result.observations[0],
            original_representation="C:/private/event/segment-without-extension",
        )
    with pytest.raises(ValueError, match="private path or media filename"):
        replace(
            evidence_request().result.observations[0],
            original_representation="inspection source /srv/events/segment",
        )
    with pytest.raises(ValueError, match="credential"):
        replace(
            evidence_request().result.observations[0],
            original_representation="token=private-value",
        )
    with pytest.raises(ValueError, match="private path or media filename"):
        replace(
            evidence_request().result,
            limitations=("Inspected private-session-name.mp4",),
        )


def test_derivation_requires_complete_local_observation_lineage() -> None:
    request = evidence_request()
    with pytest.raises(ValueError, match="reference observations"):
        replace(
            request.result,
            derivations=(
                MediaTimingDerivation(
                    id=EntityId.new(),
                    rule_id="candidate-interval",
                    rule_version="1.0",
                    input_observation_ids=(EntityId.new(),),
                    candidate_started_at=NOW,
                    candidate_ended_at=NOW + timedelta(seconds=1),
                    derived_at=NOW,
                ),
            ),
        )


def test_exact_replay_returns_original_revision_and_conflicting_replay_fails() -> None:
    application = MediaTimingEvidenceApplication(repository())
    request = evidence_request()

    first = application.apply(request)
    replay = application.apply(request)

    assert replay == first
    assert first.revision == 1
    with pytest.raises(
        MediaTimingEvidenceConflictError,
        match="application_identity_conflict",
    ):
        application.apply(changed_evidence_request(request))


def test_reprocessing_appends_and_preserves_prior_revision() -> None:
    store = repository()
    application = MediaTimingEvidenceApplication(store)
    first = application.apply(evidence_request(operation_number=10))
    second = application.apply(
        evidence_request(
            operation_number=11,
            inspected_at=NOW + timedelta(minutes=5),
            provider_id="alternate-probe",
            profile_revision=2,
        )
    )

    reconstructed = tuple(store.history(ASSET_ID))

    assert [item.revision for item in reconstructed] == [1, 2]
    assert second.predecessor_evidence_id == first.id
    assert reconstructed[0] == first
    assert store.get_active(ASSET_ID) == second
    assert second.result.provenance.provider_id == "alternate-probe"


def test_application_rejects_asset_manifest_identity_mismatch() -> None:
    application = MediaTimingEvidenceApplication(repository())
    request = replace(evidence_request(), manifest_id=EntityId.new())

    with pytest.raises(
        MediaTimingEvidenceConflictError,
        match="asset_manifest_identity_conflict",
    ):
        application.apply(request)


def test_externally_supplied_times_must_be_aware() -> None:
    request = evidence_request()
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(request, applied_at=datetime(2026, 8, 12, 18, 24, 2))
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(
            request.result.observations[0],
            observed_at=datetime(2026, 8, 12, 18, 24, 1),
        )
    assert request.applied_at.tzinfo is UTC
