from __future__ import annotations

import ast
import inspect
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import get_type_hints

from app.contexts.production.asset_readiness import (
    AssetFinalizationObservation,
    AssetReadAccessObservation,
    AssetReadinessEvaluation,
    AssetReadinessEvaluationRequest,
    AssetReadinessObservationBundle,
    AssetReadinessPolicy,
    AssetReadinessPolicyParameters,
    AssetReadinessReason,
    AssetReadinessSummary,
    AssetResourcePresenceObservation,
    AssetResourceSnapshot,
    AssetStabilityWindow,
    AssetWriteStateObservation,
    ConservativeAssetReadinessPolicy,
    MediaAssetCandidate,
    MediaAssetCandidateResource,
)

BACKEND_ROOT = Path(__file__).parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
PACKAGE_ROOT = BACKEND_ROOT / "app" / "contexts" / "production" / "asset_readiness"
CONTRACTS = (
    MediaAssetCandidate,
    MediaAssetCandidateResource,
    AssetResourceSnapshot,
    AssetFinalizationObservation,
    AssetWriteStateObservation,
    AssetReadAccessObservation,
    AssetResourcePresenceObservation,
    AssetReadinessObservationBundle,
    AssetReadinessPolicyParameters,
    AssetStabilityWindow,
    AssetReadinessEvaluationRequest,
    AssetReadinessReason,
    AssetReadinessEvaluation,
    AssetReadinessSummary,
)


def _python_sources() -> tuple[tuple[Path, str], ...]:
    return tuple((path, path.read_text()) for path in sorted(PACKAGE_ROOT.glob("*.py")))


def test_package_contains_only_the_approved_asset_readiness_scope() -> None:
    assert {path.name for path in PACKAGE_ROOT.iterdir() if path.is_file()} == {
        "README.md",
        "__init__.py",
        "asset_finalization_observation.py",
        "asset_read_access_observation.py",
        "asset_readiness_evaluation.py",
        "asset_readiness_evaluation_request.py",
        "asset_readiness_observation_bundle.py",
        "asset_readiness_outcome.py",
        "asset_readiness_policy.py",
        "asset_readiness_policy_parameters.py",
        "asset_readiness_reason.py",
        "asset_readiness_summary.py",
        "asset_readiness_validation.py",
        "asset_resource_presence_observation.py",
        "asset_resource_snapshot.py",
        "asset_stability_window.py",
        "asset_write_state_observation.py",
        "conservative_asset_readiness_policy.py",
        "media_asset_candidate.py",
        "media_asset_candidate_resource.py",
    }


def test_one_abstract_and_exactly_one_concrete_readiness_policy_exist() -> None:
    assert inspect.isabstract(AssetReadinessPolicy)
    assert not inspect.isabstract(ConservativeAssetReadinessPolicy)
    assert AssetReadinessPolicy.__subclasses__() == [ConservativeAssetReadinessPolicy]


def test_contracts_and_policy_are_dataclasses_with_no_mutating_methods() -> None:
    assert all(is_dataclass(contract) for contract in CONTRACTS)
    assert is_dataclass(ConservativeAssetReadinessPolicy)

    mutating_method_prefixes = ("add_", "clear", "delete", "remove", "set_", "update")
    for contract in (*CONTRACTS, ConservativeAssetReadinessPolicy):
        assert not any(
            name.startswith(mutating_method_prefixes)
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
        "evidence",
        "observation",
        "operational_state",
        "operational_state_acceptance",
        "operational_state_repository",
        "production_event",
        "runtime",
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


def test_package_has_no_monitoring_file_access_transfer_or_control_behavior() -> None:
    forbidden_functions = {
        "calculate_checksum",
        "copy",
        "decode",
        "dispatch",
        "emit_event",
        "enqueue",
        "ingest",
        "mount",
        "open",
        "poll",
        "probe",
        "read",
        "sleep",
        "start_recording",
        "stop_recording",
        "transfer",
        "watch",
    }
    forbidden_calls = {
        "open",
        "exec",
        "eval",
        "sleep",
        "system",
    }
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


def test_package_reads_no_implicit_wall_clock() -> None:
    forbidden_attributes = {
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


def test_public_contract_shape_has_no_session_scoring_transfer_or_active_objects() -> None:
    forbidden_fields = {
        "confidence",
        "file_handle",
        "operational_state",
        "probability",
        "queue_position",
        "score",
        "session_id",
        "stream",
        "transfer_status",
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
        "Socket",
        "StreamReader",
    }

    for contract in CONTRACTS:
        rendered = " ".join(
            str(annotation) for annotation in get_type_hints(contract).values()
        )
        assert not any(fragment in rendered for fragment in forbidden_fragments)


def test_summary_cannot_expose_sensitive_source_location_or_private_metadata() -> None:
    summary_fields = {field.name for field in fields(AssetReadinessSummary)}

    assert not {
        "access_token",
        "credentials",
        "location_value",
        "metadata",
        "password",
        "source_location",
    } & summary_fields


def test_policy_reuses_ed0048_completion_and_readiness_contracts_without_asset_builder() -> None:
    source = (PACKAGE_ROOT / "conservative_asset_readiness_policy.py").read_text()

    assert "CompletedMediaAssetCompletion" in source
    assert "CompletedMediaAssetReadiness" in source
    assert "CompletedMediaAsset(" not in source
    assert "CompletedMediaAssetResource(" not in source


def test_documentation_preserves_mission_detection_and_future_runtime_boundaries() -> None:
    readme = " ".join((PACKAGE_ROOT / "README.md").read_text().split()).lower()

    for phrase in (
        "evaluates supplied objective resource-state observations",
        "does not collect those observations",
        "production recording application owns recording",
        "production recording and livestream workloads always take priority",
        "size stability alone does not establish completion",
        "strong finalization and stability-derived completion are distinct routes",
        "completion, safe-to-read readiness, and integrity remain separate facts",
        "agent does not mean lower trust",
        "node does not mean higher trust",
        "never stored in the operational state repository",
        "should stop before transfer or queueing",
    ):
        assert phrase in readme


def test_asset_readiness_scope_is_registered_in_repository_documents() -> None:
    manifest = (REPOSITORY_ROOT / "REPOSITORY_MANIFEST.md").read_text()
    directives = (REPOSITORY_ROOT / "ENGINEERING_DIRECTIVES.md").read_text()
    production = (BACKEND_ROOT / "app" / "contexts" / "production" / "README.md").read_text()
    tests = (BACKEND_ROOT / "tests" / "README.md").read_text()

    assert "asset_readiness/" in manifest
    assert "ED-0049" in directives
    assert "Asset Stability and Readiness" in production
    assert "ED-0049" in tests
