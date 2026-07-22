from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest
from local_filesystem_discovery_fixtures import make_adapter
from runtime_fixtures import entity_id

from app.contexts.production.local_filesystem_discovery import (
    LocalFilesystemDiscoveryLimitation,
    LocalFilesystemDiscoveryReasonCode,
    LocalFilesystemTargetScope,
)
from app.contexts.production.media_collection import (
    MediaCandidateDiscoveryOutcome,
    MediaCandidateDiscoveryResult,
)
from app.contexts.production.software_agent_runtime import AgentRuntimeExecutionPermission


def _filenames(result: MediaCandidateDiscoveryResult) -> set[str]:
    return {
        discovered.candidate.primary_resource.original_filename
        for discovered in result.discovered_candidates
    }


def test_exact_directory_entry_bound_is_allowed(tmp_path: Path) -> None:
    for name in ("a.mov", "b.mov", "notes.txt"):
        (tmp_path / name).write_bytes(b"")
    adapter, request = make_adapter(tmp_path, entry_limit=3)

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.DISCOVERED
    assert _filenames(result) == {"a.mov", "b.mov"}
    assert result.metadata["entries_examined"] == 3


def test_oversized_directory_stops_at_bound_plus_one_and_retains_no_subset(
    tmp_path: Path,
) -> None:
    for index in range(20):
        (tmp_path / f"clip-{index:02d}.mov").write_bytes(b"")
    adapter, request = make_adapter(tmp_path, entry_limit=3)

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.BLOCKED
    assert result.discovered_candidates == ()
    assert result.metadata["entries_examined"] == 4
    assert LocalFilesystemDiscoveryReasonCode.DIRECTORY_ENTRY_LIMIT_EXCEEDED.value in result.reasons
    assert (
        LocalFilesystemDiscoveryLimitation.DIRECTORY_ENTRY_BOUND_PREVENTED_DISCOVERY.value
        in result.limitations
    )


def test_candidate_bound_is_applied_after_deterministic_filtering_and_sorting(
    tmp_path: Path,
) -> None:
    for name in ("z.mov", "notes.txt", "B.mov", "a.mov"):
        (tmp_path / name).write_bytes(b"")
    adapter, request = make_adapter(tmp_path)

    result = adapter.discover(replace(request, maximum_candidate_count=2))

    assert result.outcome is MediaCandidateDiscoveryOutcome.PARTIAL
    assert tuple(
        item.candidate.primary_resource.original_filename
        for item in result.discovered_candidates
    ) == ("a.mov", "B.mov")
    assert "z.mov" not in _filenames(result)
    assert LocalFilesystemDiscoveryReasonCode.CANDIDATE_RESULT_LIMIT_REACHED.value in result.reasons
    assert (
        LocalFilesystemDiscoveryLimitation.CANDIDATE_RESULT_BOUND_TRUNCATED_DISCOVERY.value
        in result.limitations
    )


def test_configured_target_symlink_is_blocked_without_following(tmp_path: Path) -> None:
    target = tmp_path / "real.mov"
    target.write_bytes(b"")
    link = tmp_path / "link.mov"
    link.symlink_to(target)
    adapter, request = make_adapter(link, scope=LocalFilesystemTargetScope.SINGLE_FILE)

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.BLOCKED
    assert result.discovered_candidates == ()
    assert LocalFilesystemDiscoveryReasonCode.CONFIGURED_TARGET_IS_SYMLINK.value in result.reasons


def test_child_symlinks_are_skipped_and_never_escape_scope(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-ed0053.mov"
    outside.write_bytes(b"outside")
    (tmp_path / "inside.mov").write_bytes(b"inside")
    (tmp_path / "escape.mov").symlink_to(outside)
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "nested.mov").write_bytes(b"nested")
    (tmp_path / "nested-link").symlink_to(nested, target_is_directory=True)
    adapter, request = make_adapter(tmp_path)

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.PARTIAL
    assert _filenames(result) == {"inside.mov"}
    assert LocalFilesystemDiscoveryReasonCode.SYMLINK_ENTRY_SKIPPED.value in result.reasons
    assert (
        LocalFilesystemDiscoveryLimitation.SYMLINK_ENTRIES_NOT_FOLLOWED.value
        in result.limitations
    )


def test_symlinked_ancestor_is_blocked_as_scope_escape(tmp_path: Path) -> None:
    real_directory = tmp_path / "real"
    real_directory.mkdir()
    (real_directory / "capture.mov").write_bytes(b"")
    linked_directory = tmp_path / "linked"
    linked_directory.symlink_to(real_directory, target_is_directory=True)
    configured = linked_directory / "capture.mov"
    adapter, request = make_adapter(
        configured,
        scope=LocalFilesystemTargetScope.SINGLE_FILE,
    )

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.BLOCKED
    assert result.discovered_candidates == ()
    assert (
        LocalFilesystemDiscoveryReasonCode.PATH_VIOLATES_CONFIGURED_SCOPE.value
        in result.reasons
    )


def test_entry_disappearance_returns_remaining_candidates_as_partial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vanished = tmp_path / "a.mov"
    remaining = tmp_path / "b.mov"
    vanished.write_bytes(b"")
    remaining.write_bytes(b"")
    adapter, request = make_adapter(tmp_path)
    real_lstat = os.lstat

    def lstat_with_race(path: str | bytes) -> os.stat_result:
        if os.fspath(path) == str(vanished):
            raise FileNotFoundError
        return real_lstat(path)

    monkeypatch.setattr(
        "app.contexts.production.local_filesystem_discovery.local_filesystem_candidate_discovery_adapter.os.lstat",
        lstat_with_race,
    )

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.PARTIAL
    assert _filenames(result) == {"b.mov"}
    assert (
        LocalFilesystemDiscoveryReasonCode.ENTRY_DISAPPEARED_DURING_DISCOVERY.value
        in result.reasons
    )
    assert LocalFilesystemDiscoveryLimitation.ENTRIES_BECAME_UNAVAILABLE.value in result.limitations


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO creation is not portable")
def test_special_filesystem_objects_never_become_candidates(tmp_path: Path) -> None:
    (tmp_path / "capture.mov").write_bytes(b"")
    os.mkfifo(tmp_path / "device-looking.mov")
    adapter, request = make_adapter(tmp_path)

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.PARTIAL
    assert _filenames(result) == {"capture.mov"}
    assert LocalFilesystemDiscoveryReasonCode.SPECIAL_ENTRY_SKIPPED.value in result.reasons


def test_per_entry_inspection_failure_is_sanitized_and_partial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inaccessible = tmp_path / "a.mov"
    remaining = tmp_path / "b.mov"
    inaccessible.write_bytes(b"")
    remaining.write_bytes(b"")
    adapter, request = make_adapter(tmp_path)
    real_lstat = os.lstat

    def lstat_with_failure(path: str | bytes) -> os.stat_result:
        if os.fspath(path) == str(inaccessible):
            raise PermissionError("/sensitive/user/path: secret operating-system detail")
        return real_lstat(path)

    monkeypatch.setattr(
        "app.contexts.production.local_filesystem_discovery.local_filesystem_candidate_discovery_adapter.os.lstat",
        lstat_with_failure,
    )

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.PARTIAL
    assert _filenames(result) == {"b.mov"}
    assert LocalFilesystemDiscoveryReasonCode.ENTRY_INSPECTION_FAILED.value in result.reasons
    assert "/sensitive" not in repr(result)
    assert "secret operating-system detail" not in repr(result)


def test_target_permission_failure_is_blocked_and_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, request = make_adapter(tmp_path)
    def deny_target(_path: object) -> None:
        raise PermissionError("/Users/private/path")

    monkeypatch.setattr(
        "app.contexts.production.local_filesystem_discovery.local_filesystem_candidate_discovery_adapter.os.lstat",
        deny_target,
    )

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.BLOCKED
    assert LocalFilesystemDiscoveryReasonCode.TARGET_INACCESSIBLE.value in result.reasons
    assert "/Users/private/path" not in repr(result)


@pytest.mark.parametrize(
    "permission",
    [AgentRuntimeExecutionPermission.NONE, AgentRuntimeExecutionPermission.ESSENTIAL_ONLY],
)
def test_nonpermitted_execution_blocks_before_filesystem_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    permission: AgentRuntimeExecutionPermission,
) -> None:
    adapter, request = make_adapter(tmp_path)
    denied = replace(request, execution_permission=permission)
    def fail_lstat(_path: object) -> None:
        raise AssertionError("filesystem touched")

    monkeypatch.setattr(
        "app.contexts.production.local_filesystem_discovery.local_filesystem_candidate_discovery_adapter.os.lstat",
        fail_lstat,
    )

    result = adapter.discover(denied)

    assert result.outcome is MediaCandidateDiscoveryOutcome.BLOCKED
    assert LocalFilesystemDiscoveryReasonCode.EXECUTION_PERMISSION_DENIED.value in result.reasons


def test_all_request_identity_substitutions_block_before_filesystem_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, request = make_adapter(tmp_path)
    other = entity_id(999999)
    invalid_requests = (
        (
            replace(request, runtime_id=other),
            LocalFilesystemDiscoveryReasonCode.RUNTIME_ID_MISMATCH,
        ),
        (
            replace(request, configuration_id=other),
            LocalFilesystemDiscoveryReasonCode.CONFIGURATION_ID_MISMATCH,
        ),
        (
            replace(request, collection_plan_id=other),
            LocalFilesystemDiscoveryReasonCode.COLLECTION_PLAN_ID_MISMATCH,
        ),
        (
            replace(request, collection_target_id=other),
            LocalFilesystemDiscoveryReasonCode.COLLECTION_TARGET_NOT_CONFIGURED,
        ),
        (
            replace(request, source_capability_id=other),
            LocalFilesystemDiscoveryReasonCode.SOURCE_CAPABILITY_ID_MISMATCH,
        ),
        (
            replace(request, discovery_capability_id=other),
            LocalFilesystemDiscoveryReasonCode.DISCOVERY_CAPABILITY_ID_MISMATCH,
        ),
        (
            replace(request, event_mode_id=other),
            LocalFilesystemDiscoveryReasonCode.EVENT_MODE_ID_MISMATCH,
        ),
        (
            replace(request, resource_policy_id=other),
            LocalFilesystemDiscoveryReasonCode.RESOURCE_POLICY_ID_MISMATCH,
        ),
    )

    def fail_lstat(_path: object) -> None:
        raise AssertionError("filesystem touched")

    monkeypatch.setattr(
        "app.contexts.production.local_filesystem_discovery.local_filesystem_candidate_discovery_adapter.os.lstat",
        fail_lstat,
    )
    for invalid, reason in invalid_requests:
        result = adapter.discover(invalid)
        assert result.outcome is MediaCandidateDiscoveryOutcome.BLOCKED
        assert reason.value in result.reasons


def test_unexpected_filesystem_error_is_failed_without_raw_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, request = make_adapter(tmp_path)
    def fail_lstat(_path: object) -> None:
        raise OSError("token=private")

    monkeypatch.setattr(
        "app.contexts.production.local_filesystem_discovery.local_filesystem_candidate_discovery_adapter.os.lstat",
        fail_lstat,
    )

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.FAILED
    assert (
        LocalFilesystemDiscoveryReasonCode.UNKNOWN_LOCAL_FILESYSTEM_FAILURE.value
        in result.reasons
    )
    assert "token=private" not in repr(result)
