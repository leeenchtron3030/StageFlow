from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from local_filesystem_discovery_fixtures import make_adapter

from app.contexts.production.completed_media_asset import (
    CompletedMediaAssetRuntimeProfile,
)
from app.contexts.production.local_filesystem_discovery import (
    LocalFilesystemDiscoveryLimitation,
    LocalFilesystemIdentityStrength,
    LocalFilesystemSourceIdentity,
)
from app.contexts.production.media_collection import MediaCandidateDiscoveryResult
from app.contexts.production.runtime import RuntimeProfile
from app.shared.ids import EntityId


def _ids(
    result: MediaCandidateDiscoveryResult,
) -> tuple[EntityId, EntityId, EntityId, EntityId]:
    discovered = result.discovered_candidates[0]
    candidate = discovered.candidate
    return (
        candidate.primary_resource.id,
        candidate.id,
        candidate.proposed_asset_id,
        discovered.discovery_id,
    )


def test_stable_filesystem_identity_produces_deterministic_scoped_ids(tmp_path: Path) -> None:
    source = tmp_path / "capture.mov"
    source.write_bytes(b"")
    adapter, request = make_adapter(tmp_path)

    first = adapter.discover(request)
    second = adapter.discover(request)

    assert _ids(first) == _ids(second)
    discovered = first.discovered_candidates[0]
    assert discovered.metadata["identity_strength"] == "stable_object_identity"
    assert discovered.candidate.primary_resource.metadata["identity_strength"] == (
        "stable_object_identity"
    )
    assert "device:" not in repr(discovered)
    assert "object:" not in repr(discovered)


def test_request_identity_changes_only_discovery_record_identity(tmp_path: Path) -> None:
    (tmp_path / "capture.mov").write_bytes(b"")
    adapter, request = make_adapter(tmp_path)
    replay_shape = replace(
        request,
        discovery_request_id=EntityId("20000000-0000-0000-0000-000000000001"),
        collection_cycle_id=EntityId("20000000-0000-0000-0000-000000000002"),
    )

    original_ids = _ids(adapter.discover(request))
    changed_ids = _ids(adapter.discover(replay_shape))

    assert original_ids[:3] == changed_ids[:3]
    assert original_ids[3] != changed_ids[3]


def test_profile_is_provenance_not_identity_or_trust_tier(tmp_path: Path) -> None:
    (tmp_path / "capture.mov").write_bytes(b"")
    (tmp_path / "secondary.mov").write_bytes(b"")
    agent_adapter, agent_request = make_adapter(tmp_path, profile=RuntimeProfile.AGENT)
    node_adapter, node_request = make_adapter(tmp_path, profile=RuntimeProfile.NODE)
    development_adapter, development_request = make_adapter(
        tmp_path,
        profile=RuntimeProfile.DEVELOPMENT,
    )

    agent_result = agent_adapter.discover(agent_request)
    node_result = node_adapter.discover(node_request)
    development_result = development_adapter.discover(development_request)

    assert _ids(agent_result) == _ids(node_result) == _ids(development_result)
    assert agent_result.outcome == node_result.outcome == development_result.outcome
    assert tuple(
        discovered.candidate.primary_resource.original_filename
        for discovered in agent_result.discovered_candidates
    ) == tuple(
        discovered.candidate.primary_resource.original_filename
        for discovered in node_result.discovered_candidates
    ) == tuple(
        discovered.candidate.primary_resource.original_filename
        for discovered in development_result.discovered_candidates
    )
    assert {
        agent_result.discovered_candidates[0].candidate.runtime_profile,
        node_result.discovered_candidates[0].candidate.runtime_profile,
        development_result.discovered_candidates[0].candidate.runtime_profile,
    } == {
        CompletedMediaAssetRuntimeProfile.AGENT,
        CompletedMediaAssetRuntimeProfile.NODE,
        CompletedMediaAssetRuntimeProfile.DEVELOPMENT,
    }
    assert all(
        "runtime_profile" not in result.discovered_candidates[0].candidate.metadata
        for result in (agent_result, node_result, development_result)
    )


def test_location_scoped_fallback_is_deterministic_and_first_class(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "capture.mov"
    source.write_bytes(b"")
    adapter, request = make_adapter(tmp_path)

    def fallback(location: str, _entry_stat: object) -> LocalFilesystemSourceIdentity:
        return LocalFilesystemSourceIdentity(
            strength=LocalFilesystemIdentityStrength.LOCATION_SCOPED_IDENTITY,
            normalized_source_location=location,
        )

    monkeypatch.setattr(
        "app.contexts.production.local_filesystem_discovery.local_filesystem_candidate_discovery_adapter._source_identity",
        fallback,
    )

    first = adapter.discover(request)
    second = adapter.discover(request)

    assert _ids(first) == _ids(second)
    assert (
        LocalFilesystemDiscoveryLimitation.STABLE_FILESYSTEM_IDENTITY_UNAVAILABLE.value
        in first.limitations
    )
    assert (
        LocalFilesystemDiscoveryLimitation.LOCATION_SCOPED_CANDIDATE_IDENTITY_USED.value
        in first.discovered_candidates[0].source_limitations
    )


def test_changed_stable_object_token_changes_resource_candidate_and_asset_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "capture.mov"
    source.write_bytes(b"")
    adapter, request = make_adapter(tmp_path)
    token = {"value": "opaque-generation-a"}

    def identity(location: str, _entry_stat: object) -> LocalFilesystemSourceIdentity:
        return LocalFilesystemSourceIdentity(
            strength=LocalFilesystemIdentityStrength.STABLE_OBJECT_IDENTITY,
            normalized_source_location=location,
            stable_object_token=token["value"],
        )

    monkeypatch.setattr(
        "app.contexts.production.local_filesystem_discovery.local_filesystem_candidate_discovery_adapter._source_identity",
        identity,
    )
    first = _ids(adapter.discover(request))
    token["value"] = "opaque-generation-b"
    second = _ids(adapter.discover(request))

    assert first[:3] != second[:3]


def test_candidate_order_does_not_change_identity(tmp_path: Path) -> None:
    for name in ("b.mov", "a.mov"):
        (tmp_path / name).write_bytes(b"")
    adapter, request = make_adapter(tmp_path)
    first = adapter.discover(request)
    by_name = {
        item.candidate.primary_resource.original_filename: item.candidate.id
        for item in first.discovered_candidates
    }
    (tmp_path / "0-not-eligible.txt").write_text("ignored")
    second = adapter.discover(request)
    second_by_name = {
        item.candidate.primary_resource.original_filename: item.candidate.id
        for item in second.discovered_candidates
    }

    assert by_name == second_by_name


def test_concurrent_explicit_calls_share_no_mutable_discovery_state(tmp_path: Path) -> None:
    for name in ("a.mov", "b.mov"):
        (tmp_path / name).write_bytes(b"")
    adapter, request = make_adapter(tmp_path)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = tuple(executor.map(adapter.discover, (request,) * 12))

    assert all(result == results[0] for result in results)
    assert len(results[0].discovered_candidates) == 2
