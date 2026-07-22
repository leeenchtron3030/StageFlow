from __future__ import annotations

import ast
import inspect
from dataclasses import fields
from pathlib import Path

from local_filesystem_discovery_fixtures import make_adapter
from media_collection_fixtures import (
    COORDINATOR_ID,
    RecordingAgentStatePort,
    RecordingObservationPorts,
    make_cycle_request,
)
from software_agent_runtime_fixtures import make_running_agent

from app.contexts.production.local_filesystem_discovery import (
    LocalFilesystemCandidateDiscoveryAdapter,
)
from app.contexts.production.media_collection import (
    MediaCandidateCollectionCoordinator,
    MediaCandidateDiscoveryPort,
    MediaCollectionCycleOutcome,
    MediaCollectionDependencies,
)
from app.contexts.production.runtime import RuntimeProfile

BACKEND_ROOT = Path(__file__).parents[1]
PACKAGE_ROOT = (
    BACKEND_ROOT / "app" / "contexts" / "production" / "local_filesystem_discovery"
)


def _python_sources() -> tuple[tuple[Path, str], ...]:
    return tuple((path, path.read_text()) for path in sorted(PACKAGE_ROOT.glob("*.py")))


def test_exactly_one_concrete_ed0052_discovery_port_implementation_exists() -> None:
    implementations: list[str] = []
    for _, source in _python_sources():
        tree = ast.parse(source)
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            base_names = {
                base.id
                for base in node.bases
                if isinstance(base, ast.Name)
            }
            if "MediaCandidateDiscoveryPort" in base_names:
                implementations.append(node.name)

    assert implementations == ["LocalFilesystemCandidateDiscoveryAdapter"]
    assert issubclass(LocalFilesystemCandidateDiscoveryAdapter, MediaCandidateDiscoveryPort)
    assert not inspect.isabstract(LocalFilesystemCandidateDiscoveryAdapter)
    assert LocalFilesystemCandidateDiscoveryAdapter.discover.__name__ == "discover"


def test_adapter_through_real_ed0052_coordinator_keeps_observation_owned_by_ports(
    tmp_path: Path,
) -> None:
    (tmp_path / "capture.mov").write_bytes(b"")
    adapter, _ = make_adapter(tmp_path, profile=RuntimeProfile.AGENT)
    agent, _ = make_running_agent(runtime=adapter.runtime, profile=RuntimeProfile.AGENT)
    agent_port = RecordingAgentStatePort([agent.snapshot])
    observations = RecordingObservationPorts()
    coordinator = MediaCandidateCollectionCoordinator(
        coordinator_id=COORDINATOR_ID,
        runtime=adapter.runtime,
        dependencies=MediaCollectionDependencies(
            agent_execution_state_port=agent_port,
            media_candidate_discovery_port=adapter,
            resource_snapshot_collection_port=observations,
            finalization_observation_collection_port=observations,
            write_state_observation_collection_port=observations,
            read_access_observation_collection_port=observations,
            resource_presence_observation_collection_port=observations,
        ),
    )

    result = coordinator.run_cycle(make_cycle_request())

    assert result.outcome is MediaCollectionCycleOutcome.COMPLETED
    assert len(result.newly_discovered_candidate_ids) == 1
    assert result.total_observation_calls_attempted == 5
    assert len(observations.calls) == 5


def test_adapter_has_only_immutable_configuration_and_no_candidate_history(tmp_path: Path) -> None:
    adapter, _ = make_adapter(tmp_path)

    assert {field.name for field in fields(adapter)} == {
        "runtime",
        "configuration",
        "_bindings_by_target",
    }
    assert not {
        "candidate_history",
        "cycle_history",
        "directory_snapshot",
        "operation_index",
        "previous_candidates",
        "retry_state",
    } & set(vars(type(adapter)))


def test_package_has_no_forbidden_architecture_imports_or_domain_dependencies() -> None:
    forbidden_modules = {
        "asyncio",
        "hashlib",
        "multiprocessing",
        "queue",
        "requests",
        "socket",
        "sqlalchemy",
        "subprocess",
        "threading",
        "time",
    }
    forbidden_domains = {
        "ai",
        "evidence",
        "observation",
        "operational_state",
        "operational_state_acceptance",
        "operational_state_repository",
        "production_event",
        "repository",
        "session",
    }
    imports: set[str] = set()
    for _, source in _python_sources():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.add(node.module)

    assert not any(
        imported == forbidden or imported.startswith(f"{forbidden}.")
        for imported in imports
        for forbidden in forbidden_modules
    )
    assert not any(
        imported == forbidden
        or imported.endswith(f".{forbidden}")
        or f".{forbidden}." in imported
        for imported in imports
        for forbidden in forbidden_domains
    )


def test_package_has_no_watcher_polling_recursion_content_or_wall_clock_calls() -> None:
    forbidden_called_names = {
        "checksum",
        "connect",
        "enqueue",
        "evaluate_readiness",
        "glob",
        "mount",
        "now",
        "open",
        "poll",
        "probe",
        "read",
        "rglob",
        "sleep",
        "start",
        "time",
        "today",
        "transfer",
        "utcnow",
        "walk",
        "watch",
    }
    called_names: set[str] = set()
    loops: list[ast.While] = []
    for _, source in _python_sources():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called_names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    called_names.add(node.func.attr)
            elif isinstance(node, ast.While):
                loops.append(node)

    assert not forbidden_called_names & called_names
    assert loops == []
    assert "scandir" in called_names
    assert "lstat" in called_names


def test_package_contains_no_api_worker_service_persistence_or_frontend_artifacts() -> None:
    names = {path.name for path in PACKAGE_ROOT.iterdir() if path.is_file()}

    assert names == {
        "README.md",
        "__init__.py",
        "local_filesystem_candidate_discovery_adapter.py",
        "local_filesystem_discovery_contracts.py",
        "local_filesystem_discovery_reason.py",
        "local_filesystem_validation.py",
    }
    source = "\n".join(value for _, value in _python_sources())
    assert all(
        token not in source
        for token in (
            "CompletedMediaAsset(",
            "ProductionEvent(",
            "AssetReadinessEvaluation(",
            "AssetResourceSnapshot(",
            "FastAPI(",
            "APIRouter(",
        )
    )
