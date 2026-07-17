from __future__ import annotations

import ast
import inspect
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import get_type_hints

from app.contexts.production.runtime import (
    RuntimeAssetAssemblyPlan,
    RuntimeAvailability,
    RuntimeCapability,
    RuntimeCapabilitySet,
    RuntimeCollectionPlan,
    RuntimeCollectionTarget,
    RuntimeConfiguration,
    RuntimeEventMode,
    RuntimeHealth,
    RuntimeHealthReportingPolicy,
    RuntimeHost,
    RuntimeIdentity,
    RuntimeLimitation,
    RuntimeObservationCapability,
    RuntimeReadinessCapability,
    RuntimeReadinessPolicySelection,
    RuntimeResourceBudget,
    RuntimeResourcePolicy,
    RuntimeSourceCapability,
    RuntimeSummary,
    RuntimeValidationReason,
    RuntimeValidationResult,
    RuntimeVersion,
    StageFlowRuntime,
)

BACKEND_ROOT = Path(__file__).parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
PACKAGE_ROOT = BACKEND_ROOT / "app" / "contexts" / "production" / "runtime"
CONTRACTS = (
    RuntimeAssetAssemblyPlan,
    RuntimeAvailability,
    RuntimeCapability,
    RuntimeCapabilitySet,
    RuntimeCollectionPlan,
    RuntimeCollectionTarget,
    RuntimeConfiguration,
    RuntimeEventMode,
    RuntimeHealth,
    RuntimeHealthReportingPolicy,
    RuntimeHost,
    RuntimeIdentity,
    RuntimeLimitation,
    RuntimeObservationCapability,
    RuntimeReadinessCapability,
    RuntimeReadinessPolicySelection,
    RuntimeResourceBudget,
    RuntimeResourcePolicy,
    RuntimeSourceCapability,
    RuntimeSummary,
    RuntimeValidationReason,
    RuntimeValidationResult,
    RuntimeVersion,
    StageFlowRuntime,
)


def _python_sources() -> tuple[tuple[Path, str], ...]:
    return tuple((path, path.read_text()) for path in sorted(PACKAGE_ROOT.glob("*.py")))


def test_package_contains_only_the_approved_runtime_contract_scope() -> None:
    assert {path.name for path in PACKAGE_ROOT.iterdir() if path.is_file()} == {
        "README.md",
        "__init__.py",
        "runtime_asset_assembly_plan.py",
        "runtime_availability.py",
        "runtime_capability.py",
        "runtime_capability_set.py",
        "runtime_collection_plan.py",
        "runtime_collection_target.py",
        "runtime_configuration.py",
        "runtime_contract_validation.py",
        "runtime_event_mode.py",
        "runtime_health.py",
        "runtime_host.py",
        "runtime_identity.py",
        "runtime_limitation.py",
        "runtime_observation_capability.py",
        "runtime_profile.py",
        "runtime_readiness_capability.py",
        "runtime_readiness_policy_selection.py",
        "runtime_resource_budget.py",
        "runtime_resource_policy.py",
        "runtime_source_capability.py",
        "runtime_summary.py",
        "runtime_validation.py",
        "runtime_version.py",
        "stageflow_runtime.py",
    }


def test_one_stageflow_runtime_contract_and_no_global_instance_exist() -> None:
    class_definitions: list[ast.ClassDef] = []
    global_instances: list[ast.Call] = []

    for _, source in _python_sources():
        tree = ast.parse(source)
        class_definitions.extend(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "StageFlowRuntime"
        )
        for node in tree.body:
            if isinstance(node, ast.Assign | ast.AnnAssign):
                value = node.value
                if (
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and value.func.id == "StageFlowRuntime"
                ):
                    global_instances.append(value)

    assert len(class_definitions) == 1
    assert global_instances == []


def test_runtime_contracts_are_immutable_dataclasses_without_active_methods() -> None:
    assert all(is_dataclass(contract) for contract in CONTRACTS)

    forbidden_method_prefixes = (
        "collect",
        "dispatch",
        "enqueue",
        "execute",
        "mount",
        "poll",
        "probe",
        "run",
        "start",
        "stop",
        "transfer",
        "watch",
    )
    for contract in CONTRACTS:
        assert not any(
            name.startswith(forbidden_method_prefixes)
            for name, _ in inspect.getmembers(contract, inspect.isfunction)
        )


def test_package_imports_no_runtime_infrastructure_or_downstream_domains() -> None:
    forbidden_modules = {
        "asyncio",
        "fastapi",
        "hashlib",
        "io",
        "multiprocessing",
        "os",
        "pathlib",
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
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module is not None
            ):
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


def test_package_has_no_collection_monitoring_transfer_or_control_behavior() -> None:
    forbidden_functions = {
        "assemble_asset",
        "calculate_checksum",
        "collect",
        "copy",
        "dispatch",
        "emit_event",
        "enqueue",
        "evaluate_readiness",
        "ingest",
        "mount",
        "open",
        "poll",
        "probe",
        "read",
        "run",
        "start_recording",
        "stop_recording",
        "transfer",
        "watch",
    }
    forbidden_calls = {"eval", "exec", "open", "sleep", "system"}
    defined: set[str] = set()
    called: set[str] = set()

    for _, source in _python_sources():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                defined.add(node.name)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called.add(node.func.id)

    assert not forbidden_functions & defined
    assert not forbidden_calls & called


def test_package_reads_no_wall_clock_or_process_state() -> None:
    forbidden_attributes = {
        "getpid",
        "monotonic",
        "now",
        "perf_counter",
        "sleep",
        "time",
        "today",
        "utcnow",
    }
    calls: set[str] = set()

    for _, source in _python_sources():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    assert not forbidden_attributes & calls


def test_public_contracts_have_no_session_state_or_active_runtime_objects() -> None:
    forbidden_fields = {
        "api_client",
        "background_task",
        "database_connection",
        "evidence",
        "file_handle",
        "network_client",
        "observation",
        "operational_state",
        "queue_position",
        "repository",
        "session_id",
        "transfer_status",
        "worker",
    }
    contract_fields = {
        field.name
        for contract in CONTRACTS
        for field in fields(contract)
    }

    assert not forbidden_fields & contract_fields


def test_public_annotations_are_serialization_ready() -> None:
    forbidden_fragments = {
        "BinaryIO",
        "Callable",
        "FileIO",
        "IOBase",
        "Lock",
        "Path",
        "RuntimeService",
        "Socket",
        "StreamReader",
        "Thread",
    }

    for contract in CONTRACTS:
        rendered = " ".join(
            str(annotation) for annotation in get_type_hints(contract).values()
        )
        assert not any(fragment in rendered for fragment in forbidden_fragments)


def test_runtime_does_not_construct_assets_or_execute_ed0049_policy() -> None:
    source = "\n".join(source for _, source in _python_sources())

    assert "CompletedMediaAsset(" not in source
    assert "CompletedMediaAssetResource(" not in source
    assert "ConservativeAssetReadinessPolicy" not in source
    assert ".evaluate(" not in source
    assert "AssetReadinessPolicyParameters" in source


def test_recorder_control_capability_is_absent_from_contract_and_exports() -> None:
    source = "\n".join(source for _, source in _python_sources()).casefold()

    assert "recorder_control" not in source
    assert "start_recording" not in source
    assert "stop_recording" not in source


def test_runtime_summary_cannot_expose_source_paths_credentials_or_metadata() -> None:
    summary_fields = {field.name for field in fields(RuntimeSummary)}

    assert not {
        "access_token",
        "credentials",
        "metadata",
        "opaque_location_reference",
        "password",
        "source_location",
        "source_path",
    } & summary_fields


def test_documentation_preserves_deployment_neutral_and_execution_boundaries() -> None:
    readme = " ".join((PACKAGE_ROOT / "README.md").read_text().split()).lower()

    for phrase in (
        "one deployment-neutral runtime contract",
        "agent does not mean lower trust",
        "node does not mean higher trust",
        "production recording and livestream workloads always take priority",
        "configuration validity does not mean execution success",
        "does not collect observations",
        "does not evaluate candidate readiness",
        "does not assemble completed media assets",
        "does not control a recorder",
        "does not transfer or queue assets",
        "no session identity",
        "offline-capable event operation",
    ):
        assert phrase in readme


def test_runtime_scope_is_registered_in_repository_documents() -> None:
    manifest = (REPOSITORY_ROOT / "REPOSITORY_MANIFEST.md").read_text()
    directives = (REPOSITORY_ROOT / "ENGINEERING_DIRECTIVES.md").read_text()
    production = (
        BACKEND_ROOT / "app" / "contexts" / "production" / "README.md"
    ).read_text()
    completed_asset = (
        BACKEND_ROOT
        / "app"
        / "contexts"
        / "production"
        / "completed_media_asset"
        / "README.md"
    ).read_text()
    readiness = (
        BACKEND_ROOT
        / "app"
        / "contexts"
        / "production"
        / "asset_readiness"
        / "README.md"
    ).read_text()
    tests = (BACKEND_ROOT / "tests" / "README.md").read_text()

    assert "runtime/" in manifest
    assert "ED-0050" in directives
    assert "StageFlow Runtime" in production
    assert "ED-0050" in completed_asset
    assert "ED-0050" in readiness
    assert "ED-0050" in tests
