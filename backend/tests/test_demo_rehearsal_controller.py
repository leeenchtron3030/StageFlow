from __future__ import annotations

import json

import pytest

from app.demo.controller import (
    DemoControllerError,
    build_devcon_publish_candidate,
    execute_devcon_publish,
    preview_devcon_publish,
    resolve_current_session,
    resolve_required_secret,
    summarize_demo_state,
    validate_database_identity,
)
from app.infrastructure.devcon.session_publish import (
    DevconPublishError,
    RemoteDevconSession,
)

SESSION_ID = "6b4c60cc-9008-43db-976d-3fdba826b242"
EXPECTATION_ID = "20000000-0000-0000-0000-000000000001"


def _session(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "session_id": SESSION_ID,
        "activity_state": "presentation_ended",
        "package_state": "complete",
        "package_revision": 2,
        "revision": 4,
        "authoritative_start": "2026-08-19T20:00:00Z",
        "authoritative_end": "2026-08-19T20:30:00Z",
        "program_expectation_id": EXPECTATION_ID,
    }
    value.update(updates)
    return value


def _kernel(*, sessions: list[dict[str, object]] | None = None) -> dict[str, object]:
    session_values = [_session()] if sessions is None else sessions
    return {
        "runtime_profile": "demo-single-stage",
        "ready": True,
        "database_available": True,
        "event_id": "10000000-0000-0000-0000-000000000001",
        "event_key": "stageflow-demo-1",
        "stages": [
            {
                "stage_id": "10000000-0000-0000-0000-000000000002",
                "key": "main",
                "source_available": True,
                "session_id": SESSION_ID if session_values else None,
                "assembling_sessions": session_values,
                "recent_sessions": session_values,
                "discovered": 0,
                "stabilizing": 0,
                "ready": 0,
                "registered": 5,
                "associated": 5,
                "unresolved": 0,
                "conflicting": 0,
            }
        ],
        "program_expectations": [
            {
                "expectation_id": EXPECTATION_ID,
                "external_event_id": "test-devcon-8",
                "external_session_id": "a-dacc-vision-for-decentralized-ai",
            }
        ],
        "recent_media": [
            {
                "asset_id": "30000000-0000-0000-0000-000000000001",
                "media_started_at": "2026-08-19T20:00:00Z",
            }
        ],
    }


def _workspace() -> dict[str, object]:
    return {
        "session_id": SESSION_ID,
        "work": {
            "counts": {"succeeded": 1, "terminal_failed": 1},
            "active_lease_count": 0,
            "attention_codes": [],
        },
        "operations": [
            {
                "operation_id": "40000000-0000-0000-0000-000000000001",
                "status": "succeeded",
                "attempt_count": 1,
                "max_attempts": 3,
                "last_reason_code": None,
            },
            {
                "operation_id": "40000000-0000-0000-0000-000000000002",
                "status": "terminal_failed",
                "attempt_count": 3,
                "max_attempts": 3,
                "last_reason_code": "provider_execution_failed",
            },
        ],
        "operations_truncated": False,
        "transcript_evidence": [
            {
                "evidence_id": "50000000-0000-0000-0000-000000000001",
                "asset_id": "30000000-0000-0000-0000-000000000001",
                "status": "complete",
                "revision": 1,
                "provider_id": "faster-whisper",
                "provider_version": "1.2.1",
                "model_id": "large-v3-turbo",
                "model_version": "model-revision",
                "segments": [
                    {
                        "ordinal": 0,
                        "text": "sensitive transcript sentence",
                    }
                ],
                "segments_truncated": False,
            }
        ],
        "transcript_assets_truncated": False,
        "moments": [{"candidate_moment_id": "moment-1"}],
    }


def test_database_guard_rejects_qualification_and_non_demo_identities() -> None:
    assert validate_database_identity("stageflow_demo") == "stageflow_demo"
    for name in (
        "stageflow_worker_test",
        "stageflow_validation_004",
        "stageflow_qualification",
        "postgres",
    ):
        with pytest.raises(DemoControllerError):
            validate_database_identity(name)


def test_missing_secret_reports_presence_by_name_only() -> None:
    with pytest.raises(
        DemoControllerError,
        match="required_secret_unavailable:STAGEFLOW_DEMO_POSTGRES_DSN",
    ) as caught:
        resolve_required_secret({}, "STAGEFLOW_DEMO_POSTGRES_DSN")

    assert "postgresql://" not in str(caught.value)


def test_session_discovery_handles_none_one_and_ambiguity_safely() -> None:
    assert resolve_current_session(_kernel(sessions=[])) is None
    assert resolve_current_session(_kernel()).session_id == SESSION_ID  # type: ignore[union-attr]

    first = _session(session_id="60000000-0000-0000-0000-000000000001")
    second = _session(session_id="60000000-0000-0000-0000-000000000002")
    ambiguous = _kernel(sessions=[first, second])
    stage = ambiguous["stages"][0]  # type: ignore[index]
    stage["session_id"] = None  # type: ignore[index]
    with pytest.raises(DemoControllerError, match="ambiguous"):
        resolve_current_session(ambiguous)


def test_summary_reports_terminal_failure_and_successful_evidence_without_text() -> None:
    summary = summarize_demo_state(
        _kernel(),
        _workspace(),
        worker_summary={"state": "available", "registered": 1, "available": 1},
    )

    assert summary["operations"] == {
        "counts": {"succeeded": 1, "terminal_failed": 1},
        "terminal_failures": (
            {
                "operation_id": "40000000-0000-0000-0000-000000000002",
                "attempt_count": 3,
                "max_attempts": 3,
                "reason_code": "provider_execution_failed",
            },
        ),
        "truncated": False,
    }
    transcript = summary["transcript_evidence"]
    assert transcript["count"] == 1  # type: ignore[index]
    assert transcript["complete"] == 1  # type: ignore[index]
    serialized = json.dumps(summary)
    assert "sensitive transcript sentence" not in serialized
    assert "transcript_text" not in serialized


def test_no_session_summary_is_bounded_and_non_authoritative() -> None:
    summary = summarize_demo_state(_kernel(sessions=[]), None)

    assert summary["session"] is None
    assert summary["transcript_evidence"] == {
        "count": 0,
        "complete": 0,
        "items": (),
    }


class FakeDevconAdapter:
    def __init__(self, candidate_text: str = "sensitive transcript sentence") -> None:
        self.candidate_text = candidate_text
        self.get_calls = 0
        self.put_calls: list[dict[str, object]] = []

    def get_session(self, session_id: str) -> RemoteDevconSession:
        self.get_calls += 1
        transcript = None if self.get_calls == 1 else self.candidate_text
        duration = 0 if self.get_calls == 1 else 1800
        return RemoteDevconSession(
            session_id=session_id,
            event_id="test-devcon-8",
            transcript_text=transcript,
            duration_seconds=duration,
        )

    def put_enrichment(self, **values: object) -> None:
        self.put_calls.append(values)


def test_publish_preview_and_execution_require_confirmation_and_verify_twice() -> None:
    candidate = build_devcon_publish_candidate(_kernel(), _workspace())
    preview_adapter = FakeDevconAdapter()
    preview = preview_devcon_publish(
        candidate,
        credential_available=True,
        adapter=preview_adapter,  # type: ignore[arg-type]
    )

    assert preview == {
        "event": "test-devcon-8",
        "target_session": "a-dacc-vision-for-decentralized-ai",
        "fields": ("transcript_text", "duration"),
        "remote_identity_verified": True,
        "package_approved": True,
        "credential_available": True,
        "candidate_digest": candidate.digest,
    }

    denied_adapter = FakeDevconAdapter(candidate.transcript_text)
    with pytest.raises(DemoControllerError, match="human_confirmation_required"):
        execute_devcon_publish(
            candidate,
            expected_digest=candidate.digest,
            confirmed=False,
            api_key="secret-value",
            adapter=denied_adapter,  # type: ignore[arg-type]
        )
    assert denied_adapter.get_calls == 0
    assert denied_adapter.put_calls == []

    adapter = FakeDevconAdapter(candidate.transcript_text)
    result = execute_devcon_publish(
        candidate,
        expected_digest=candidate.digest,
        confirmed=True,
        api_key="secret-value",
        adapter=adapter,  # type: ignore[arg-type]
    )

    assert adapter.get_calls == 3
    assert len(adapter.put_calls) == 1
    assert set(adapter.put_calls[0]) == {
        "session_id",
        "api_key",
        "transcript_text",
        "duration_seconds",
    }
    assert result["read_back_verified"] is True
    assert result["durability_verified"] is True
    assert "secret-value" not in json.dumps(result)
    assert candidate.transcript_text not in json.dumps(result)


def test_rejected_publish_does_not_retry_or_run_read_back() -> None:
    candidate = build_devcon_publish_candidate(_kernel(), _workspace())

    class RejectingDevconAdapter(FakeDevconAdapter):
        def put_enrichment(self, **values: object) -> None:
            self.put_calls.append(values)
            raise DevconPublishError("devcon_publish_rejected:no_body")

    adapter = RejectingDevconAdapter(candidate.transcript_text)
    with pytest.raises(
        DevconPublishError,
        match=r"^devcon_publish_rejected:no_body$",
    ):
        execute_devcon_publish(
            candidate,
            expected_digest=candidate.digest,
            confirmed=True,
            api_key="secret-value",
            adapter=adapter,  # type: ignore[arg-type]
        )

    assert adapter.get_calls == 1
    assert len(adapter.put_calls) == 1


def test_publish_requires_package_approval() -> None:
    kernel = _kernel(sessions=[_session(package_state="ready_for_review")])

    with pytest.raises(DemoControllerError, match="package_not_approved"):
        build_devcon_publish_candidate(kernel, _workspace())


def test_publish_digest_prevents_stale_confirmation() -> None:
    candidate = build_devcon_publish_candidate(_kernel(), _workspace())
    adapter = FakeDevconAdapter(candidate.transcript_text)

    with pytest.raises(DemoControllerError, match="candidate_changed"):
        execute_devcon_publish(
            candidate,
            expected_digest="0" * 64,
            confirmed=True,
            api_key="secret-value",
            adapter=adapter,  # type: ignore[arg-type]
        )

    assert adapter.get_calls == 0
    assert adapter.put_calls == []


def test_summary_never_copies_unknown_workspace_fields() -> None:
    workspace = _workspace()
    workspace["dsn"] = "postgresql://user:password@example.invalid/demo"
    workspace["api_key"] = "secret-value"
    workspace["raw_provider_diagnostic"] = "private path"

    serialized = json.dumps(summarize_demo_state(_kernel(), workspace))

    for forbidden in ("password", "secret-value", "private path", "postgresql://"):
        assert forbidden not in serialized


def test_operation_counts_are_copied_as_bounded_scalar_mapping() -> None:
    workspace = _workspace()
    work = workspace["work"]
    assert isinstance(work, dict)
    work["counts"] = {"terminal_failed": 2}

    summary = summarize_demo_state(_kernel(), workspace)

    operations = summary["operations"]
    assert isinstance(operations, dict)
    assert operations["counts"] == {
        "terminal_failed": 2
    }
