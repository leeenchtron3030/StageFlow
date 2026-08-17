from __future__ import annotations

import json
from collections import deque
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime

import httpx
import pytest

from tests.qualification.devcon_av_write_smoke import (
    API_KEY_ENV,
    GITHUB_SESSION_PATH,
    TARGET_CONFIRMATION,
    TEST_EVENT_ID,
    TEST_MARKER,
    CommitBaseline,
    CommitEvidence,
    GitHubCommitVerifier,
    HttpDevconAvApi,
    SessionState,
    SmokeError,
    main,
    run_dry_preflight,
    run_live_smoke,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


class FakeApi:
    def __init__(
        self,
        reads: Sequence[SessionState | SmokeError],
        puts: Sequence[int | SmokeError] = (),
    ) -> None:
        self._reads = deque(reads)
        self._puts = deque(puts)
        self.put_values: list[str] = []

    def get_test_session(self) -> SessionState:
        result = self._reads.popleft()
        if isinstance(result, SmokeError):
            raise result
        return result

    def put_test_youtube_id(self, value: str) -> int:
        self.put_values.append(value)
        result = self._puts.popleft()
        if isinstance(result, SmokeError):
            raise result
        return result


class FakeCommits:
    def __init__(
        self,
        evidence: CommitEvidence | None = None,
        *,
        capture_error: SmokeError | None = None,
        wait_error: SmokeError | None = None,
    ) -> None:
        self.evidence = evidence if evidence is not None else CommitEvidence(2, False)
        self.capture_error = capture_error
        self.wait_error = wait_error
        self.expected_counts: list[int] = []

    def capture_baseline(self) -> CommitBaseline:
        if self.capture_error is not None:
            raise self.capture_error
        return CommitBaseline(frozenset({"baseline"}))

    def wait_for_new_commits(
        self, baseline: CommitBaseline, *, expected: int
    ) -> CommitEvidence:
        assert baseline.shas == frozenset({"baseline"})
        self.expected_counts.append(expected)
        if self.wait_error is not None:
            raise self.wait_error
        return self.evidence


def state(youtube_id: str, event_id: str = TEST_EVENT_ID) -> SessionState:
    return SessionState(event_id=event_id, youtube_id=youtube_id)


def test_dry_run_validates_identity_without_writing() -> None:
    api = FakeApi([state("")])

    report = run_dry_preflight(api, observed_at=NOW)

    assert report.outcome == "preflight_pass"
    assert report.preflight_event_verified is True
    assert report.original_value_state == "empty"
    assert api.put_values == []


def test_wrong_event_aborts_before_any_write() -> None:
    api = FakeApi([state("", event_id="devcon-7")])

    report = run_live_smoke(api, FakeCommits(), observed_at=NOW)

    assert report.outcome == "fail"
    assert report.failure_codes == ("wrong_event",)
    assert api.put_values == []


def test_marker_already_present_aborts_before_any_write() -> None:
    api = FakeApi([state(TEST_MARKER)])

    report = run_live_smoke(api, FakeCommits(), observed_at=NOW)

    assert report.failure_codes == ("marker_already_present",)
    assert api.put_values == []


def test_live_pass_requires_write_restore_and_two_commits() -> None:
    original = "original-youtube-id"
    api = FakeApi(
        [state(original), state(TEST_MARKER), state(original)],
        [204, 204],
    )
    commits = FakeCommits()

    report = run_live_smoke(api, commits, observed_at=NOW)

    assert report.outcome == "pass"
    assert report.marker_observed is True
    assert report.restore_observed is True
    assert report.persistence_verified is True
    assert report.new_skip_deploy_commits == 2
    assert api.put_values == [TEST_MARKER, original]
    assert commits.expected_counts == [2]
    assert original not in json.dumps(asdict(report))


def test_non_204_memory_mutation_is_restored_but_never_passes() -> None:
    api = FakeApi(
        [state(""), state(TEST_MARKER), state("")],
        [500, 204],
    )

    report = run_live_smoke(api, FakeCommits(), observed_at=NOW)

    assert report.outcome == "fail"
    assert report.restore_observed is True
    assert "marker_put_not_204" in report.failure_codes
    assert api.put_values == [TEST_MARKER, ""]


def test_unverifiable_target_blocks_blind_restore() -> None:
    api = FakeApi(
        [state(""), SmokeError("session_read_failed")],
        [204],
    )

    report = run_live_smoke(api, FakeCommits(), observed_at=NOW)

    assert report.outcome == "fail"
    assert report.manual_intervention_required is True
    assert report.failure_codes == ("target_unverifiable",)
    assert api.put_values == [TEST_MARKER]


def test_concurrent_third_value_is_not_overwritten() -> None:
    api = FakeApi(
        [state(""), state("another-operator-value")],
        [204],
    )

    report = run_live_smoke(api, FakeCommits(), observed_at=NOW)

    assert report.outcome == "fail"
    assert report.manual_intervention_required is True
    assert "concurrent_change" in report.failure_codes
    assert api.put_values == [TEST_MARKER]


def test_restore_request_failure_can_be_observed_but_not_pass() -> None:
    api = FakeApi(
        [state(""), state(TEST_MARKER), state("")],
        [204, SmokeError("write_request_failed")],
    )

    report = run_live_smoke(api, FakeCommits(), observed_at=NOW)

    assert report.outcome == "fail"
    assert report.restore_observed is True
    assert "restore_request_failed" in report.failure_codes
    assert "restore_put_not_204" in report.failure_codes


def test_missing_durable_commits_is_not_a_pass() -> None:
    api = FakeApi(
        [state(""), state(TEST_MARKER), state("")],
        [204, 204],
    )

    report = run_live_smoke(
        api,
        FakeCommits(CommitEvidence(1, True)),
        observed_at=NOW,
    )

    assert report.outcome == "fail"
    assert report.persistence_verified is False
    assert "persistence_unverified" in report.failure_codes


def test_commit_baseline_failure_occurs_before_write() -> None:
    api = FakeApi([state("")])

    report = run_live_smoke(
        api,
        FakeCommits(capture_error=SmokeError("commit_evidence_unavailable")),
        observed_at=NOW,
    )

    assert report.failure_codes == ("commit_evidence_unavailable",)
    assert api.put_values == []


def test_http_client_uses_header_and_does_not_expose_secret() -> None:
    secret = "never-print-this-api-key"
    seen_header = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_header
        seen_header = request.headers["x-api-key"]
        return httpx.Response(500, json={"error": secret})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        api = HttpDevconAvApi(client, secret)
        status = api.put_test_youtube_id(TEST_MARKER)

    assert status == 500
    assert seen_header == secret


def test_github_verifier_counts_only_new_skip_deploy_commits() -> None:
    responses = deque(
        [
            [{"sha": "old", "commit": {"message": "[skip deploy] old"}}],
            [
                {"sha": "new-1", "commit": {"message": "[skip deploy] write"}},
                {"sha": "new-2", "commit": {"message": "[skip deploy] restore"}},
                {"sha": "other", "commit": {"message": "unrelated"}},
                {"sha": "old", "commit": {"message": "[skip deploy] old"}},
            ],
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["path"] == GITHUB_SESSION_PATH
        return httpx.Response(200, json=responses.popleft())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        verifier = GitHubCommitVerifier(client, timeout_seconds=1, poll_seconds=1)
        baseline = verifier.capture_baseline()
        evidence = verifier.wait_for_new_commits(baseline, expected=2)

    assert evidence == CommitEvidence(2, False)


def test_cli_requires_credential_before_constructing_live_client(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(API_KEY_ENV, raising=False)

    exit_code = main(["--execute", "--confirm-target", TARGET_CONFIRMATION])

    output = capsys.readouterr().out
    assert exit_code == 2
    assert "credential_missing" in output
    assert "x-api-key" not in output


def test_cli_requires_exact_confirmation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(API_KEY_ENV, "not-read-before-confirmation")

    exit_code = main(["--execute", "--confirm-target", "devcon8/real-session"])

    output = capsys.readouterr().out
    assert exit_code == 2
    assert "target_confirmation_required" in output
    assert "not-read-before-confirmation" not in output
