"""Fixed-target qualification harness for the Devcon AV enrichment write path.

The default mode is read-only. Live mode is deliberately restricted to one upstream
test session and is not a StageFlow runtime integration or publication adapter.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, cast

import httpx

API_BASE_URL = "https://api.devcon.org"
TEST_EVENT_ID = "test-devcon-8"
TEST_SESSION_ID = "a-dacc-vision-for-decentralized-ai"
TEST_FIELD = "sources_youtubeId"
TEST_MARKER = "jNQXAC9IVRw"
TARGET_CONFIRMATION = f"{TEST_EVENT_ID}/{TEST_SESSION_ID}"
API_KEY_ENV = "STAGEFLOW_DEVCON_AV_API_KEY"
GITHUB_COMMITS_URL = "https://api.github.com/repos/efdevcon/monorepo/commits"
GITHUB_SESSION_PATH = (
    f"devcon-api/data/sessions/{TEST_EVENT_ID}/{TEST_SESSION_ID}.json"
)
DEFAULT_PERSISTENCE_TIMEOUT_SECONDS = 90.0
PERSISTENCE_POLL_SECONDS = 5.0

Mode = Literal["dry_run", "live"]
Outcome = Literal["preflight_pass", "pass", "fail"]
ValueState = Literal["empty", "nonempty", "unknown"]


class SmokeError(RuntimeError):
    """A typed qualification failure whose code contains no provider data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SessionState:
    event_id: str
    youtube_id: str


@dataclass(frozen=True, slots=True)
class CommitBaseline:
    shas: frozenset[str]


@dataclass(frozen=True, slots=True)
class CommitEvidence:
    new_skip_deploy_commits: int
    timed_out: bool


@dataclass(frozen=True, slots=True)
class SmokeReport:
    schema: str
    observed_at: str
    mode: Mode
    outcome: Outcome
    target_event: str
    target_session: str
    target_field: str
    preflight_event_verified: bool
    original_value_state: ValueState
    marker_put_status: int | None
    marker_observed: bool
    restore_attempted: bool
    restore_put_status: int | None
    restore_observed: bool
    new_skip_deploy_commits: int
    persistence_verified: bool
    manual_intervention_required: bool
    failure_codes: tuple[str, ...]


class DevconAvApi(Protocol):
    def get_test_session(self) -> SessionState: ...

    def put_test_youtube_id(self, value: str) -> int: ...


class CommitVerifier(Protocol):
    def capture_baseline(self) -> CommitBaseline: ...

    def wait_for_new_commits(
        self, baseline: CommitBaseline, *, expected: int
    ) -> CommitEvidence: ...


class HttpDevconAvApi:
    """Qualification-only HTTP boundary with sanitized failures."""

    def __init__(self, client: httpx.Client, api_key: str | None) -> None:
        self._client = client
        self._api_key = api_key

    def get_test_session(self) -> SessionState:
        try:
            response = self._client.get(f"{API_BASE_URL}/sessions/{TEST_SESSION_ID}")
        except httpx.HTTPError as exc:
            raise SmokeError("session_read_failed") from exc
        if response.status_code != 200:
            raise SmokeError("session_read_failed")
        try:
            payload_value = response.json()
        except ValueError as exc:
            raise SmokeError("session_response_invalid") from exc
        if not isinstance(payload_value, dict):
            raise SmokeError("session_response_invalid")
        payload = cast(dict[str, object], payload_value)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise SmokeError("session_response_invalid")
        typed_data = cast(dict[str, object], data)
        event_id = typed_data.get("eventId")
        raw_youtube_id = typed_data.get(TEST_FIELD)
        if not isinstance(event_id, str):
            raise SmokeError("session_response_invalid")
        if raw_youtube_id is None:
            youtube_id = ""
        elif isinstance(raw_youtube_id, str):
            youtube_id = raw_youtube_id
        else:
            raise SmokeError("session_response_invalid")
        return SessionState(event_id=event_id, youtube_id=youtube_id)

    def put_test_youtube_id(self, value: str) -> int:
        if not self._api_key:
            raise SmokeError("credential_missing")
        try:
            response = self._client.put(
                f"{API_BASE_URL}/sessions/sources/{TEST_SESSION_ID}",
                headers={"x-api-key": self._api_key, "Content-Type": "application/json"},
                json={TEST_FIELD: value},
            )
        except httpx.HTTPError as exc:
            raise SmokeError("write_request_failed") from exc
        return response.status_code


class GitHubCommitVerifier:
    """Read-only verifier for path-scoped upstream durability commits."""

    def __init__(
        self,
        client: httpx.Client,
        *,
        timeout_seconds: float = DEFAULT_PERSISTENCE_TIMEOUT_SECONDS,
        poll_seconds: float = PERSISTENCE_POLL_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout_seconds <= 0 or poll_seconds <= 0:
            raise ValueError("polling bounds must be positive")
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._poll_seconds = poll_seconds
        self._monotonic = monotonic
        self._sleep = sleep

    def _commits(self) -> dict[str, str]:
        try:
            response = self._client.get(
                GITHUB_COMMITS_URL,
                params={"path": GITHUB_SESSION_PATH, "per_page": 20},
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "stageflow-devcon-av-write-qualification",
                },
            )
        except httpx.HTTPError as exc:
            raise SmokeError("commit_evidence_unavailable") from exc
        if response.status_code != 200:
            raise SmokeError("commit_evidence_unavailable")
        try:
            payload_value = response.json()
        except ValueError as exc:
            raise SmokeError("commit_evidence_invalid") from exc
        if not isinstance(payload_value, list):
            raise SmokeError("commit_evidence_invalid")
        payload = cast(list[object], payload_value)
        commits: dict[str, str] = {}
        for item_value in payload:
            if not isinstance(item_value, dict):
                raise SmokeError("commit_evidence_invalid")
            item = cast(dict[str, object], item_value)
            sha = item.get("sha")
            commit = item.get("commit")
            if not isinstance(sha, str) or not isinstance(commit, dict):
                raise SmokeError("commit_evidence_invalid")
            typed_commit = cast(dict[str, object], commit)
            message = typed_commit.get("message")
            if not isinstance(message, str):
                raise SmokeError("commit_evidence_invalid")
            commits[sha] = message
        return commits

    def capture_baseline(self) -> CommitBaseline:
        return CommitBaseline(shas=frozenset(self._commits()))

    def wait_for_new_commits(
        self, baseline: CommitBaseline, *, expected: int
    ) -> CommitEvidence:
        if expected < 1:
            raise ValueError("expected commit count must be positive")
        deadline = self._monotonic() + self._timeout_seconds
        latest_count = 0
        while True:
            commits = self._commits()
            latest_count = sum(
                1
                for sha, message in commits.items()
                if sha not in baseline.shas and "[skip deploy]" in message
            )
            if latest_count >= expected:
                return CommitEvidence(
                    new_skip_deploy_commits=latest_count,
                    timed_out=False,
                )
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                return CommitEvidence(
                    new_skip_deploy_commits=latest_count,
                    timed_out=True,
                )
            self._sleep(min(self._poll_seconds, remaining))


def _value_state(value: str | None) -> ValueState:
    if value is None:
        return "unknown"
    return "empty" if value == "" else "nonempty"


def _report(
    *,
    mode: Mode,
    outcome: Outcome,
    observed_at: datetime,
    preflight_event_verified: bool = False,
    original_value: str | None = None,
    marker_put_status: int | None = None,
    marker_observed: bool = False,
    restore_attempted: bool = False,
    restore_put_status: int | None = None,
    restore_observed: bool = False,
    new_skip_deploy_commits: int = 0,
    persistence_verified: bool = False,
    manual_intervention_required: bool = False,
    failure_codes: Sequence[str] = (),
) -> SmokeReport:
    return SmokeReport(
        schema="stageflow.devcon-av-write-qualification-report.v1",
        observed_at=observed_at.astimezone(UTC).isoformat(),
        mode=mode,
        outcome=outcome,
        target_event=TEST_EVENT_ID,
        target_session=TEST_SESSION_ID,
        target_field=TEST_FIELD,
        preflight_event_verified=preflight_event_verified,
        original_value_state=_value_state(original_value),
        marker_put_status=marker_put_status,
        marker_observed=marker_observed,
        restore_attempted=restore_attempted,
        restore_put_status=restore_put_status,
        restore_observed=restore_observed,
        new_skip_deploy_commits=new_skip_deploy_commits,
        persistence_verified=persistence_verified,
        manual_intervention_required=manual_intervention_required,
        failure_codes=tuple(dict.fromkeys(failure_codes)),
    )


def _preflight(api: DevconAvApi) -> SessionState:
    state = api.get_test_session()
    if state.event_id != TEST_EVENT_ID:
        raise SmokeError("wrong_event")
    if state.youtube_id == TEST_MARKER:
        raise SmokeError("marker_already_present")
    return state


def run_dry_preflight(
    api: DevconAvApi, *, observed_at: datetime | None = None
) -> SmokeReport:
    timestamp = observed_at or datetime.now(UTC)
    try:
        state = _preflight(api)
    except SmokeError as exc:
        return _report(
            mode="dry_run",
            outcome="fail",
            observed_at=timestamp,
            failure_codes=(exc.code,),
        )
    return _report(
        mode="dry_run",
        outcome="preflight_pass",
        observed_at=timestamp,
        preflight_event_verified=True,
        original_value=state.youtube_id,
    )


def run_live_smoke(
    api: DevconAvApi,
    commits: CommitVerifier,
    *,
    observed_at: datetime | None = None,
) -> SmokeReport:
    timestamp = observed_at or datetime.now(UTC)
    failures: list[str] = []
    try:
        before = _preflight(api)
    except SmokeError as exc:
        return _report(
            mode="live",
            outcome="fail",
            observed_at=timestamp,
            failure_codes=(exc.code,),
        )

    try:
        baseline = commits.capture_baseline()
    except SmokeError as exc:
        return _report(
            mode="live",
            outcome="fail",
            observed_at=timestamp,
            preflight_event_verified=True,
            original_value=before.youtube_id,
            failure_codes=(exc.code,),
        )

    marker_status: int | None = None
    marker_observed = False
    restore_attempted = False
    restore_status: int | None = None
    restore_observed = False
    manual_intervention = False
    new_commits = 0
    persistence_verified = False

    try:
        marker_status = api.put_test_youtube_id(TEST_MARKER)
    except SmokeError as exc:
        failures.append(exc.code)

    try:
        after = api.get_test_session()
    except SmokeError:
        failures.append("target_unverifiable")
        manual_intervention = True
        return _report(
            mode="live",
            outcome="fail",
            observed_at=timestamp,
            preflight_event_verified=True,
            original_value=before.youtube_id,
            marker_put_status=marker_status,
            manual_intervention_required=manual_intervention,
            failure_codes=failures,
        )

    if after.event_id != TEST_EVENT_ID:
        failures.append("target_identity_changed")
        manual_intervention = True
    elif after.youtube_id == TEST_MARKER:
        marker_observed = True
        restore_attempted = True
        try:
            restore_status = api.put_test_youtube_id(before.youtube_id)
        except SmokeError:
            failures.append("restore_request_failed")
        try:
            reverted = api.get_test_session()
        except SmokeError:
            failures.append("restore_unverified")
            manual_intervention = True
        else:
            if reverted.event_id != TEST_EVENT_ID:
                failures.append("restore_target_identity_changed")
                manual_intervention = True
            elif reverted.youtube_id == before.youtube_id:
                restore_observed = True
            else:
                failures.append("restore_unverified")
                manual_intervention = True
    elif after.youtube_id == before.youtube_id:
        failures.append("marker_not_observed")
    else:
        failures.append("concurrent_change")
        manual_intervention = True

    if marker_status != 204:
        failures.append("marker_put_not_204")
    if restore_attempted and restore_status != 204:
        failures.append("restore_put_not_204")

    if marker_observed and restore_attempted:
        try:
            evidence = commits.wait_for_new_commits(baseline, expected=2)
        except SmokeError as exc:
            failures.append(exc.code)
        else:
            new_commits = evidence.new_skip_deploy_commits
            persistence_verified = not evidence.timed_out and new_commits >= 2
            if not persistence_verified:
                failures.append("persistence_unverified")

    passed = (
        marker_status == 204
        and marker_observed
        and restore_attempted
        and restore_status == 204
        and restore_observed
        and persistence_verified
        and not failures
    )
    return _report(
        mode="live",
        outcome="pass" if passed else "fail",
        observed_at=timestamp,
        preflight_event_verified=True,
        original_value=before.youtube_id,
        marker_put_status=marker_status,
        marker_observed=marker_observed,
        restore_attempted=restore_attempted,
        restore_put_status=restore_status,
        restore_observed=restore_observed,
        new_skip_deploy_commits=new_commits,
        persistence_verified=persistence_verified,
        manual_intervention_required=manual_intervention,
        failure_codes=failures,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight the fixed Devcon AV test session; live mode performs one "
            "marker write and one restoration write."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="perform the fixed test write and restore; default mode is read-only",
    )
    parser.add_argument(
        "--confirm-target",
        help=f"required with --execute; must equal {TARGET_CONFIRMATION}",
    )
    return parser


def _failure_report(code: str, *, mode: Mode) -> SmokeReport:
    return _report(
        mode=mode,
        outcome="fail",
        observed_at=datetime.now(UTC),
        failure_codes=(code,),
    )


def _print_report(report: SmokeReport) -> None:
    print(json.dumps(asdict(report), indent=2, sort_keys=True, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    execute = cast(bool, args.execute)
    confirmation = cast(str | None, args.confirm_target)
    if not execute and confirmation is not None:
        _print_report(_failure_report("confirmation_without_execute", mode="dry_run"))
        return 2
    if execute and confirmation != TARGET_CONFIRMATION:
        _print_report(_failure_report("target_confirmation_required", mode="live"))
        return 2

    api_key = os.environ.get(API_KEY_ENV, "").strip() if execute else None
    if execute and not api_key:
        _print_report(_failure_report("credential_missing", mode="live"))
        return 2

    timeout = httpx.Timeout(10.0, connect=10.0)
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        api = HttpDevconAvApi(client, api_key)
        if execute:
            verifier = GitHubCommitVerifier(client)
            report = run_live_smoke(api, verifier)
        else:
            report = run_dry_preflight(api)
    _print_report(report)
    return 0 if report.outcome in {"preflight_pass", "pass"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
