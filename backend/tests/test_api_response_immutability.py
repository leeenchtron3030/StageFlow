from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.api.v1.demo import WorkProjectionResponse
from app.api.v1.kernel_status import MediaStatusResponse


def test_work_projection_counts_are_immutable_and_serialize_as_an_object() -> None:
    response = WorkProjectionResponse(
        counts={"pending": 1},
        oldest_eligible_at=None,
        active_lease_count=0,
        attention_codes=(),
    )

    with pytest.raises(TypeError):
        response.counts["pending"] = 2  # type: ignore[index]

    assert response.model_dump(mode="json")["counts"] == {"pending": 1}


def test_media_association_references_are_recursively_immutable() -> None:
    now = datetime(2026, 8, 21, tzinfo=UTC)
    response = MediaStatusResponse(
        candidate_id="candidate",
        proposed_asset_id="proposed",
        asset_id=None,
        stage_id="stage",
        source_binding_key="source",
        registration_state="discovered",
        discovered_at=now,
        last_observed_at=now,
        association_status=None,
        association_authority=None,
        session_id=None,
        epistemic_kinds=(),
        media_started_at=None,
        media_ended_at=None,
        diagnostic_codes=(),
        association_reason_codes=(),
        association_evidence_ids=(),
        association_policy_id=None,
        association_policy_version=None,
        association_input_references=(
            {"record_type": "session", "details": {"revision": 1}},
        ),
        association_actor_id=None,
        association_decided_at=None,
    )

    reference = response.association_input_references[0]
    with pytest.raises(TypeError):
        reference["record_type"] = "asset"  # type: ignore[index]
    with pytest.raises(TypeError):
        reference["details"]["revision"] = 2  # type: ignore[index]

    assert response.model_dump(mode="json")["association_input_references"] == [
        {"record_type": "session", "details": {"revision": 1}}
    ]
