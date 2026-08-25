from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, Protocol, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from app.api.v1.demo import router
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.editorial import (
    DeclareEditorialMoment,
    EditorialCandidateMoment,
    EditorialGenerationState,
    EditorialMomentConflictError,
    EditorialMomentService,
    EditorialMomentStorageUnavailableError,
    EditorialSessionCandidateProjection,
)
from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
)
from app.contexts.transcription_evidence import (
    NormalizedTranscriptResult,
    TranscriptEvidenceRevision,
    TranscriptEvidenceStatus,
    TranscriptExecutionProvenance,
    TranscriptSegment,
    TranscriptWord,
)
from app.core.config.deployment import EffectiveKernelConfiguration, RuntimeProfile
from app.shared.ids import EntityId
from app.shared.time import FixedClock

NOW = datetime(2026, 8, 18, 14, 0, tzinfo=UTC)
ACTOR = "81000000-0000-0000-0000-000000000001"


class SyncHttpClient(Protocol):
    def get(self, url: str) -> Response: ...

    def post(self, url: str, *, json: object) -> Response: ...


class InMemoryMoments:
    def __init__(self, kernel_repository: InMemoryEventModeKernelRepository) -> None:
        self.kernel_repository = kernel_repository
        self.by_operation: dict[EntityId, tuple[str, EditorialCandidateMoment]] = {}

    def declare(self, command: DeclareEditorialMoment) -> EditorialCandidateMoment:
        replay = self.by_operation.get(command.operation_id)
        if replay is not None:
            digest, moment = replay
            if digest != command.request_digest:
                raise EditorialMomentConflictError("human_command_operation_id_conflict")
            return moment
        session = self.kernel_repository.get_session(command.session_id)
        assert session is not None
        if session.revision != command.expected_session_revision:
            raise EditorialMomentConflictError("session_revision_conflict")
        moment = EditorialCandidateMoment(
            id=command.candidate_moment_id,
            session_id=command.session_id,
            expected_session_revision=command.expected_session_revision,
            timeline_start_microseconds=command.timeline_start_microseconds,
            timeline_end_microseconds=command.timeline_end_microseconds,
            session_authoritative_start=session.authoritative_start,
            session_authoritative_end=session.authoritative_end,
            actor_id=command.actor_id,
            operation_id=command.operation_id,
            note=command.note,
            declared_at=command.declared_at,
        )
        self.by_operation[command.operation_id] = (command.request_digest, moment)
        return moment

    def list_for_session(
        self, session_id: EntityId, *, limit: int = 100
    ) -> tuple[EditorialCandidateMoment, ...]:
        return tuple(
            moment
            for _, moment in self.by_operation.values()
            if moment.session_id == session_id
        )[:limit]

    def projection_for_session(
        self, session_id: EntityId
    ) -> EditorialSessionCandidateProjection:
        moments = self.list_for_session(session_id)
        return EditorialSessionCandidateProjection(
            session_id=session_id,
            candidate_count=len(moments),
            latest_candidate_activity_at=(
                None if not moments else max(item.declared_at for item in moments)
            ),
            generation_state=EditorialGenerationState.HEALTHY,
        )

    def projections_for_sessions(
        self, session_ids: tuple[EntityId, ...]
    ) -> tuple[EditorialSessionCandidateProjection, ...]:
        return tuple(self.projection_for_session(item) for item in session_ids)

    def revalidate_session_locations(
        self, session_id: EntityId, *, evaluated_at: datetime
    ) -> tuple[EditorialCandidateMoment, ...]:
        del evaluated_at
        return self.list_for_session(session_id)


def _client() -> tuple[SyncHttpClient, str, KernelComponents]:
    repository = InMemoryEventModeKernelRepository()
    kernel = DurableEventModeKernel(repository=repository, clock=FixedClock(NOW))
    bootstrapped = kernel.bootstrap(
        EventStageBootstrapRequest(
            operation_id=EntityId("81000000-0000-0000-0000-000000000002"),
            event_key="demo-api",
            event_name="Demo API",
            stages=(
                StageBootstrapDefinition(
                    key="main",
                    name="Main",
                    source_bindings={"vmix": "C:/demo/media"},
                ),
            ),
            actor_id=EntityId(ACTOR),
            requested_at=NOW,
        )
    )
    assert bootstrapped.event is not None
    deployment = SimpleNamespace(
        runtime_profile=RuntimeProfile.DEMO_SINGLE_STAGE,
        deployment_id="demo-api-deployment",
        event=SimpleNamespace(key="demo-api"),
    )
    configuration = cast(
        EffectiveKernelConfiguration,
        cast(
            Any,
            SimpleNamespace(
                deployment=deployment,
                postgres_dsn="secret-dsn-not-response",
            ),
        ),
    )
    components = KernelComponents(
        configuration=configuration,
        repository=repository,
        kernel=kernel,
        editorial_moments=EditorialMomentService(
            InMemoryMoments(repository),
            FixedClock(NOW),
        ),
    )
    app = FastAPI()
    app.include_router(router)
    app.state.kernel = components
    client = cast(SyncHttpClient, TestClient(app))
    return client, bootstrapped.stages[0].id.value, components


def _confirmed(operation: int) -> dict[str, str]:
    return {
        "operation_id": f"81000000-0000-0000-0000-{operation:012d}",
        "actor_id": ACTOR,
        "confirmed": "confirmed",
    }


def test_demo_authority_controls_are_confirmed_and_observable() -> None:
    client, stage_id, _ = _client()
    missing_confirmation = client.post(
        "/demo/sessions/start",
        json={
            "operation_id": "81000000-0000-0000-0000-000000000010",
            "actor_id": ACTOR,
            "stage_id": stage_id,
            "authoritative_start": NOW.isoformat(),
        },
    )
    assert missing_confirmation.status_code == 422

    start = client.post(
        "/demo/sessions/start",
        json={
            **_confirmed(11),
            "stage_id": stage_id,
            "authoritative_start": NOW.isoformat(),
        },
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]
    assert start.json()["activity_state"] == "presentation_active"

    end = client.post(
        "/demo/sessions/end-presentation",
        json={
            **_confirmed(12),
            "session_id": session_id,
            "boundary_at": NOW.isoformat(),
            "reason": "producer ended presentation",
        },
    )
    assert end.status_code == 200
    assert end.json()["activity_state"] == "presentation_ended"

    package = client.post(
        "/demo/sessions/package-ready",
        json={
            **_confirmed(13),
            "session_id": session_id,
            "reason": "producer reviewed package",
        },
    )
    assert package.status_code == 200
    assert package.json()["package_state"] == "ready_for_review"

    moment = client.post(
        "/demo/moments/mark",
        json={
            **_confirmed(14),
            "session_id": session_id,
            "expected_session_revision": package.json()["revision"],
            "timeline_start_microseconds": 0,
            "note": "opening",
        },
    )
    assert moment.status_code == 200
    assert moment.json()["origin"] == "declared"
    assert moment.json()["reason_code"] == "human_mark_moment"

    listed = client.get(f"/demo/sessions/{session_id}/moments")
    assert listed.status_code == 200
    assert [item["candidate_moment_id"] for item in listed.json()] == [
        moment.json()["candidate_moment_id"]
    ]


def test_end_presentation_surfaces_editorial_revalidation_failure_after_kernel_commit(
    monkeypatch: Any,
) -> None:
    client, stage_id, components = _client()
    start = client.post(
        '/demo/sessions/start',
        json={
            **_confirmed(15),
            'stage_id': stage_id,
            'authoritative_start': NOW.isoformat(),
        },
    )
    session_id = start.json()['session_id']
    assert components.editorial_moments is not None

    def unavailable(
        candidate_session_id: EntityId, *, evaluated_at: datetime
    ) -> tuple[EditorialCandidateMoment, ...]:
        del candidate_session_id, evaluated_at
        raise EditorialMomentStorageUnavailableError('postgresql_unavailable')

    monkeypatch.setattr(
        components.editorial_moments.repository,
        'revalidate_session_locations',
        unavailable,
    )

    response = client.post(
        '/demo/sessions/end-presentation',
        json={
            **_confirmed(16),
            'session_id': session_id,
            'boundary_at': NOW.isoformat(),
            'reason': 'producer ended presentation',
        },
    )

    assert response.status_code == 503
    assert response.json()['detail'] == 'postgresql_unavailable'
    persisted = components.repository.get_session(EntityId(session_id))
    assert persisted is not None
    assert persisted.activity_state.value == 'presentation_ended'


def test_package_approval_requires_reviewable_exact_revision_and_is_idempotent() -> None:
    client, stage_id, _ = _client()
    start = client.post(
        "/demo/sessions/start",
        json={
            **_confirmed(30),
            "stage_id": stage_id,
            "authoritative_start": NOW.isoformat(),
        },
    )
    session_id = start.json()["session_id"]
    approval_operation = 34

    active = client.post(
        "/demo/sessions/approve-package",
        json={
            **_confirmed(approval_operation),
            "session_id": session_id,
            "package_revision": 1,
        },
    )
    assert active.status_code == 409
    assert active.json()["detail"] == "session_presentation_not_ended"

    end = client.post(
        "/demo/sessions/end-presentation",
        json={
            **_confirmed(31),
            "session_id": session_id,
            "boundary_at": NOW.isoformat(),
            "reason": "producer ended presentation",
        },
    )
    assert end.status_code == 200

    assembling = client.post(
        "/demo/sessions/approve-package",
        json={
            **_confirmed(approval_operation),
            "session_id": session_id,
            "package_revision": 1,
        },
    )
    assert assembling.status_code == 409
    assert assembling.json()["detail"] == "package_not_ready_for_completion"

    package = client.post(
        "/demo/sessions/package-ready",
        json={
            **_confirmed(32),
            "session_id": session_id,
            "reason": "producer reviewed package",
        },
    )
    assert package.status_code == 200
    package_revision = package.json()["package_revision"]

    stale_revision = client.post(
        "/demo/sessions/approve-package",
        json={
            **_confirmed(33),
            "session_id": session_id,
            "package_revision": package_revision + 1,
        },
    )
    assert stale_revision.status_code == 409
    assert stale_revision.json()["detail"] == "package_revision_conflict"

    approval_command = {
        **_confirmed(approval_operation),
        "session_id": session_id,
        "package_revision": package_revision,
    }
    approved = client.post("/demo/sessions/approve-package", json=approval_command)
    replay = client.post("/demo/sessions/approve-package", json=approval_command)

    assert approved.status_code == 200
    assert approved.json()["package_state"] == "complete"
    assert approved.json()["package_revision"] == package_revision
    assert replay.status_code == 200
    assert replay.json() == approved.json()

    conflicting_reuse = client.post(
        "/demo/sessions/approve-package",
        json={
            **approval_command,
            "actor_id": "81000000-0000-0000-0000-000000000099",
        },
    )
    assert conflicting_reuse.status_code == 409
    assert conflicting_reuse.json()["detail"] == "human_command_operation_id_conflict"


def test_transcription_evidence_workspace_is_bounded_no_store_and_redacted(
    monkeypatch: Any,
) -> None:
    from app.api.v1 import demo as demo_api

    client, stage_id, components = _client()
    start = client.post(
        "/demo/sessions/start",
        json={
            **_confirmed(20),
            "stage_id": stage_id,
            "authoritative_start": NOW.isoformat(),
        },
    )
    session_id = start.json()["session_id"]
    asset_ids = tuple(
        EntityId(f"81000000-0000-0000-0000-{number:012d}")
        for number in range(21, 26)
    )
    asset_id = asset_ids[0]

    def recent_media(event_id: EntityId, *, limit: int = 100) -> tuple[object, ...]:
        del event_id, limit
        return tuple(
            SimpleNamespace(session_id=EntityId(session_id), asset_id=item)
            for item in asset_ids
        )

    monkeypatch.setattr(components.repository, "list_recent_media", recent_media)
    evidence = TranscriptEvidenceRevision(
        id=EntityId("81000000-0000-0000-0000-000000000022"),
        operation_id=EntityId("81000000-0000-0000-0000-000000000023"),
        work_key="a" * 64,
        result_digest="b" * 64,
        asset_id=asset_id,
        manifest_id=EntityId("81000000-0000-0000-0000-000000000024"),
        manifest_version="1.0",
        revision=1,
        predecessor_evidence_id=None,
        applied_at=NOW,
        result=NormalizedTranscriptResult(
            status=TranscriptEvidenceStatus.COMPLETE,
            provenance=TranscriptExecutionProvenance(
                provider_id="faster-whisper",
                provider_version="1.2.1",
                model_id="large-v3-turbo",
                model_version="demo-model-v1",
                execution_tool_id="ctranslate2",
                execution_tool_version="4.8.1",
                execution_revision="demo-execution-v1",
                produced_at=NOW,
            ),
            language="en",
            segments=(
                TranscriptSegment(
                    id=EntityId("81000000-0000-0000-0000-000000000025"),
                    ordinal=0,
                    text="Welcome to the evidence surface.",
                    asset_start_microseconds=0,
                    asset_end_microseconds=1_000_000,
                    words=(
                        TranscriptWord(
                            id=EntityId("81000000-0000-0000-0000-000000000026"),
                            ordinal=0,
                            text="Welcome",
                            asset_start_microseconds=0,
                            asset_end_microseconds=400_000,
                            confidence=0.91,
                            confidence_semantics="provider_probability",
                        ),
                    ),
                ),
            ),
        ),
    )

    class FakeWorkRepository:
        def __init__(self, dsn: str) -> None:
            assert dsn == "secret-dsn-not-response"

        def status_projection(self, **values: object) -> object:
            return SimpleNamespace(
                counts=(),
                oldest_eligible_at=None,
                active_lease_count=0,
                attention_codes=(),
            )

        def list_operations(self, **values: object) -> tuple[()]:
            return ()

        def list_transcript_evidence_for_asset(
            self, selected_asset_id: EntityId, *, limit: int
        ) -> tuple[TranscriptEvidenceRevision, ...]:
            assert selected_asset_id in asset_ids
            assert limit == 1
            return (replace(evidence, asset_id=selected_asset_id),)

    monkeypatch.setattr(demo_api, "PostgresWorkExecutionRepository", FakeWorkRepository)
    response = client.get(f"/demo/sessions/{session_id}/workspace")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"
    payload = response.json()
    assert payload["label"] == "Transcription Evidence"
    assert "not authoritative Session Transcript" in payload["authority_notice"]
    assert payload["operation_limit"] == 100
    assert payload["operations_truncated"] is False
    assert payload["transcript_asset_limit"] == 4
    assert payload["transcript_assets_truncated"] is True
    assert len(payload["transcript_evidence"]) == 4
    assert payload["transcript_evidence"][0]["segments"][0]["text"] == (
        "Welcome to the evidence surface."
    )
    expanded = client.get(
        f"/demo/sessions/{session_id}/workspace?transcript_asset_limit=5"
    )
    assert expanded.status_code == 200
    expanded_payload = expanded.json()
    assert expanded_payload["transcript_asset_limit"] == 5
    assert expanded_payload["transcript_assets_truncated"] is False
    assert len(expanded_payload["transcript_evidence"]) == 5
    assert client.get(
        f"/demo/sessions/{session_id}/workspace?transcript_asset_limit=101"
    ).status_code == 422
    serialized = json.dumps(payload)
    assert "secret-dsn-not-response" not in serialized
    assert "media_path" not in serialized
    assert "diagnostic" not in serialized
