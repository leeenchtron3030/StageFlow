from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

from media_collection_fixtures import make_coordinator, make_cycle_request

from app.contexts.production.media_collection import (
    MediaCandidateCollectionCoordinator,
    MediaCollectionCycleOutcome,
)
from app.contexts.production.runtime import RuntimeProfile
from app.shared.ids import EntityId

PACKAGE = Path(__file__).parents[1] / "app" / "contexts" / "production" / "media_collection"


def test_runtime_configuration_drift_is_rejected_before_any_port() -> None:
    coordinator, agent, discovery, observations = make_coordinator()
    drifted_runtime = replace(coordinator.runtime, collection_plans=())
    drifted = MediaCandidateCollectionCoordinator(
        coordinator_id=coordinator.snapshot.coordinator_id,
        runtime=drifted_runtime,
        dependencies=coordinator._dependencies,  # type: ignore[attr-defined]
    )

    result = drifted.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.INVALID_CONFIGURATION
    assert agent.calls == []
    assert discovery.calls == []
    assert observations.calls == []


def test_agent_identity_mismatch_rejects_without_media_calls() -> None:
    coordinator, agent, discovery, observations = make_coordinator()
    agent.snapshots[0] = replace(
        agent.snapshots[0],
        runtime_id=EntityId("10000000-0000-0000-0000-999999999999"),
    )

    result = coordinator.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.INVALID_RUNTIME
    assert discovery.calls == []
    assert observations.calls == []
    assert coordinator.snapshot.coordinator_revision == 0


def test_missing_selected_observation_port_is_invalid_dependency() -> None:
    coordinator, agent, discovery, observations = make_coordinator()
    missing = replace(
        coordinator._dependencies,  # type: ignore[attr-defined]
        read_access_observation_collection_port=None,
    )
    invalid = MediaCandidateCollectionCoordinator(
        coordinator_id=coordinator.snapshot.coordinator_id,
        runtime=coordinator.runtime,
        dependencies=missing,
    )

    result = invalid.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.INVALID_DEPENDENCY
    assert agent.calls == []
    assert discovery.calls == []
    assert observations.calls == []


def test_node_profile_is_not_an_agent_execution_path() -> None:
    coordinator, agent, discovery, _ = make_coordinator(profile=RuntimeProfile.NODE)

    result = coordinator.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.INVALID_RUNTIME
    assert agent.calls == []
    assert discovery.calls == []


def test_package_has_exactly_one_concrete_coordinator_and_no_active_process_boundary() -> None:
    coordinator_classes: list[str] = []
    imports: set[str] = set()
    calls: set[str] = set()
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith("Coordinator"):
                coordinator_classes.append(node.name)
            elif isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.add(node.module)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)

    assert coordinator_classes == ["MediaCandidateCollectionCoordinator"]
    assert not any(
        name.startswith(prefix)
        for name in imports
        for prefix in (
            "asyncio",
            "subprocess",
            "socket",
            "pathlib",
            "sqlalchemy",
        )
    )
    assert calls.isdisjoint(
        {
            "Thread",
            "Timer",
            "sleep",
            "open",
            "read_bytes",
            "write_bytes",
            "time",
            "now",
            "utcnow",
        }
    )


def test_package_does_not_import_forbidden_downstream_domain_boundaries() -> None:
    source = "\n".join(path.read_text() for path in PACKAGE.rglob("*.py"))

    assert "operational_state_repository" not in source
    assert "semantic_observation" not in source
    assert "completed_media_asset import CompletedMediaAsset" not in source
    assert "AssetReadinessPolicy" not in source
    assert "ConservativeAssetReadinessPolicy" not in source
    assert "queue" not in source.lower()
    assert "filesystem client" not in source.lower()
