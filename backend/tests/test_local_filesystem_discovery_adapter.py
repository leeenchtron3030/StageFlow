from __future__ import annotations

import builtins
from dataclasses import fields, replace
from pathlib import Path

import pytest
from local_filesystem_discovery_fixtures import (
    ADAPTER_ID,
    REQUESTED_AT,
    make_adapter,
    make_policy,
)

from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetLocationScheme,
    CompletedMediaAssetRuntimeProfile,
)
from app.contexts.production.local_filesystem_discovery import (
    LocalFilesystemDiscoveryLimitation,
    LocalFilesystemDiscoveryReasonCode,
    LocalFilesystemTargetScope,
)
from app.contexts.production.media_collection import (
    MediaCandidateDiscoveryOutcome,
    MediaCandidateDiscoveryResult,
)
from app.contexts.production.runtime import RuntimeSourceLocationScheme


def candidate_filenames(result: MediaCandidateDiscoveryResult) -> tuple[str, ...]:
    return tuple(
        discovered.candidate.primary_resource.original_filename
        for discovered in result.discovered_candidates
    )


def test_single_file_discovery_maps_canonical_candidate_without_content_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "segment001.MOV"
    source.write_bytes(b"media-content-must-not-be-read")
    before = source.stat()
    adapter, request = make_adapter(source, scope=LocalFilesystemTargetScope.SINGLE_FILE)
    def fail_open(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("content opened")

    monkeypatch.setattr(builtins, "open", fail_open)
    monkeypatch.setattr(Path, "open", fail_open)

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.DISCOVERED
    assert candidate_filenames(result) == ("segment001.MOV",)
    discovered = result.discovered_candidates[0]
    candidate = discovered.candidate
    resource = candidate.primary_resource
    assert result.port_id == ADAPTER_ID
    assert candidate.first_observed_at == REQUESTED_AT
    assert discovered.discovered_at == REQUESTED_AT
    assert result.started_at == REQUESTED_AT
    assert result.completed_at == REQUESTED_AT
    assert candidate.source_runtime_id == request.runtime_id
    assert candidate.runtime_profile is CompletedMediaAssetRuntimeProfile.AGENT
    assert candidate.source_host_id == adapter.configuration.target_bindings[0].source_host_id
    assert candidate.adapter_id == ADAPTER_ID
    assert (
        candidate.context.stage_id
        == adapter.configuration.target_bindings[0].configured_stage_id
    )
    assert (
        candidate.context.recording_block_id
        == adapter.configuration.target_bindings[0].configured_recording_block_id
    )
    assert (
        resource.source_location.location_scheme
        is CompletedMediaAssetLocationScheme.LOCAL_FILESYSTEM
    )
    assert resource.source_location.location_value == str(source)
    assert resource.original_filename == source.name
    assert resource.media_type_hint == "video/quicktime"
    assert resource.container_type_hint == "quicktime"
    assert not {
        "checksum",
        "completion",
        "duration",
        "file_size_bytes",
        "filesystem_modified_at",
        "readiness",
        "session_id",
    } & {
        field.name
        for field in (*fields(type(candidate)), *fields(type(resource)))
    }
    after = source.stat()
    assert (after.st_mode, after.st_size, after.st_mtime_ns) == (
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
    )


def test_shallow_directory_filters_explicitly_and_never_recurses(tmp_path: Path) -> None:
    (tmp_path / "b.MOV").write_bytes(b"b")
    (tmp_path / "a.mp4").write_bytes(b"a")
    (tmp_path / "notes.txt").write_text("notes")
    (tmp_path / ".hidden.mov").write_bytes(b"hidden")
    (tmp_path / "unfinished.mov.partial").write_bytes(b"partial")
    nested = tmp_path / "archive"
    nested.mkdir()
    (nested / "c.mp4").write_bytes(b"nested")
    adapter, request = make_adapter(tmp_path)

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.PARTIAL
    assert set(candidate_filenames(result)) == {"a.mp4", "b.MOV"}
    assert "c.mp4" not in candidate_filenames(result)
    assert LocalFilesystemDiscoveryReasonCode.NESTED_DIRECTORY_IGNORED.value in result.reasons
    assert LocalFilesystemDiscoveryReasonCode.HIDDEN_ENTRY_EXCLUDED.value in result.reasons
    assert LocalFilesystemDiscoveryReasonCode.EXTENSION_NOT_ELIGIBLE.value in result.reasons
    assert LocalFilesystemDiscoveryReasonCode.EXPLICIT_EXCLUSION_MATCHED.value in result.reasons
    assert (
        LocalFilesystemDiscoveryLimitation.NESTED_DIRECTORIES_NOT_TRAVERSED.value
        in result.limitations
    )


def test_empty_or_ineligible_scope_returns_no_candidates(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("notes")
    (tmp_path / "nested").mkdir()
    adapter, request = make_adapter(tmp_path)

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.NO_CANDIDATES
    assert result.discovered_candidates == ()
    assert LocalFilesystemDiscoveryReasonCode.NO_ELIGIBLE_CANDIDATES.value in result.reasons


@pytest.mark.parametrize("filename", ["recording_active.mov", "recent.mov"])
def test_active_looking_and_recent_files_remain_candidates_only(
    tmp_path: Path,
    filename: str,
) -> None:
    source = tmp_path / filename
    source.write_bytes(b"")
    adapter, request = make_adapter(tmp_path)

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.DISCOVERED
    candidate = result.discovered_candidates[0].candidate
    assert candidate.primary_resource.original_filename == filename
    assert not hasattr(candidate.primary_resource, "file_size_bytes")
    assert not hasattr(candidate, "completion")
    assert not hasattr(candidate, "readiness")
    assert (
        LocalFilesystemDiscoveryReasonCode.NO_COMPLETION_ASSESSMENT_PERFORMED.value
        in result.reasons
    )
    assert (
        LocalFilesystemDiscoveryReasonCode.NO_READINESS_ASSESSMENT_PERFORMED.value
        in result.reasons
    )


def test_explicit_hidden_include_and_deliberate_allow_all(tmp_path: Path) -> None:
    (tmp_path / ".capture.bin").write_bytes(b"")
    adapter, request = make_adapter(
        tmp_path,
        policy=make_policy(allowed=(), include_hidden=True, permit_all=True),
    )

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.DISCOVERED
    assert candidate_filenames(result) == (".capture.bin",)


def test_mounted_volume_uses_same_candidate_semantics(tmp_path: Path) -> None:
    source = tmp_path / "capture.mov"
    source.write_bytes(b"")
    adapter, request = make_adapter(
        source,
        scope=LocalFilesystemTargetScope.SINGLE_FILE,
        scheme=RuntimeSourceLocationScheme.MOUNTED_VOLUME,
    )

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.DISCOVERED
    resource = result.discovered_candidates[0].candidate.primary_resource
    assert (
        resource.source_location.location_scheme
        is CompletedMediaAssetLocationScheme.MOUNTED_VOLUME
    )
    assert LocalFilesystemDiscoveryReasonCode.MOUNTED_VOLUME_TARGET_ACCEPTED.value in result.reasons


def test_unsupported_network_scheme_does_not_touch_filesystem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, request = make_adapter(
        tmp_path,
        scheme=RuntimeSourceLocationScheme.NETWORK_SHARE,
    )
    def fail_lstat(_path: object) -> None:
        raise AssertionError("filesystem touched")

    monkeypatch.setattr(
        "app.contexts.production.local_filesystem_discovery.local_filesystem_candidate_discovery_adapter.os.lstat",
        fail_lstat,
    )

    result = adapter.discover(request)

    assert result.outcome is MediaCandidateDiscoveryOutcome.UNSUPPORTED
    assert result.discovered_candidates == ()
    assert LocalFilesystemDiscoveryReasonCode.UNSUPPORTED_SOURCE_SCHEME.value in result.reasons


def test_missing_target_and_target_type_mismatch_are_typed(tmp_path: Path) -> None:
    missing = tmp_path / "missing.mov"
    adapter, request = make_adapter(missing, scope=LocalFilesystemTargetScope.SINGLE_FILE)
    missing_result = adapter.discover(request)
    assert missing_result.outcome is MediaCandidateDiscoveryOutcome.BLOCKED
    assert LocalFilesystemDiscoveryReasonCode.TARGET_MISSING.value in missing_result.reasons

    directory_adapter, directory_request = make_adapter(
        tmp_path,
        scope=LocalFilesystemTargetScope.SINGLE_FILE,
    )
    mismatch = directory_adapter.discover(directory_request)
    assert mismatch.outcome is MediaCandidateDiscoveryOutcome.BLOCKED
    assert LocalFilesystemDiscoveryReasonCode.TARGET_TYPE_MISMATCH.value in mismatch.reasons


def test_request_timestamp_is_authoritative_and_repeat_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "capture.mov").write_bytes(b"changing bytes are out of scope")
    adapter, request = make_adapter(tmp_path)

    first = adapter.discover(request)
    second = adapter.discover(request)

    assert first == second
    assert first.started_at == first.completed_at == request.requested_at
    assert first.discovered_candidates[0].discovered_at == request.requested_at
    assert first.discovered_candidates[0].candidate.first_observed_at == request.requested_at
    assert (
        LocalFilesystemDiscoveryLimitation.DISCOVERY_TIMESTAMP_REQUEST_ANCHORED.value
        in first.limitations
    )


def test_target_reference_substitution_is_blocked_before_filesystem_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, request = make_adapter(tmp_path)
    substituted = replace(request, target_reference=str(tmp_path / "other"))
    def fail_lstat(_path: object) -> None:
        raise AssertionError("filesystem touched")

    monkeypatch.setattr(
        "app.contexts.production.local_filesystem_discovery.local_filesystem_candidate_discovery_adapter.os.lstat",
        fail_lstat,
    )

    result = adapter.discover(substituted)

    assert result.outcome is MediaCandidateDiscoveryOutcome.BLOCKED
    assert LocalFilesystemDiscoveryReasonCode.TARGET_PATH_MISMATCH.value in result.reasons
