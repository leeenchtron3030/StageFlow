from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import get_type_hints

from app.contexts.production.completed_media_asset import (
    CompletedMediaAsset,
    CompletedMediaAssetCompletion,
    CompletedMediaAssetContext,
    CompletedMediaAssetIntegrity,
    CompletedMediaAssetManifest,
    CompletedMediaAssetProvenance,
    CompletedMediaAssetReadiness,
    CompletedMediaAssetRelationship,
    CompletedMediaAssetResource,
    CompletedMediaAssetResourceReference,
    CompletedMediaAssetSource,
    CompletedMediaAssetSourceLocation,
    CompletedMediaAssetSummary,
    CompletedMediaAssetTechnicalDescription,
)

REPOSITORY_ROOT = Path(__file__).parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "app" / "contexts" / "production" / "completed_media_asset"
CONTRACTS = (
    CompletedMediaAsset,
    CompletedMediaAssetCompletion,
    CompletedMediaAssetContext,
    CompletedMediaAssetIntegrity,
    CompletedMediaAssetManifest,
    CompletedMediaAssetProvenance,
    CompletedMediaAssetReadiness,
    CompletedMediaAssetRelationship,
    CompletedMediaAssetResource,
    CompletedMediaAssetResourceReference,
    CompletedMediaAssetSource,
    CompletedMediaAssetSourceLocation,
    CompletedMediaAssetSummary,
    CompletedMediaAssetTechnicalDescription,
)


def _python_sources() -> tuple[tuple[Path, str], ...]:
    return tuple((path, path.read_text()) for path in sorted(PACKAGE_ROOT.glob("*.py")))


def test_package_contains_only_the_approved_completed_asset_contract_scope() -> None:
    assert {path.name for path in PACKAGE_ROOT.iterdir() if path.is_file()} == {
        "README.md",
        "__init__.py",
        "completed_media_asset.py",
        "completed_media_asset_completion.py",
        "completed_media_asset_context.py",
        "completed_media_asset_integrity.py",
        "completed_media_asset_kind.py",
        "completed_media_asset_manifest.py",
        "completed_media_asset_provenance.py",
        "completed_media_asset_readiness.py",
        "completed_media_asset_relationship.py",
        "completed_media_asset_resource.py",
        "completed_media_asset_source.py",
        "completed_media_asset_summary.py",
        "completed_media_asset_technical_description.py",
        "completed_media_asset_validation.py",
    }


def test_contracts_import_no_runtime_infrastructure_or_downstream_domains() -> None:
    forbidden_modules = {
        "asyncio",
        "fastapi",
        "hashlib",
        "io",
        "multiprocessing",
        "pathlib",
        "queue",
        "requests",
        "socket",
        "sqlalchemy",
        "subprocess",
        "threading",
    }
    forbidden_domains = {
        "evidence",
        "observation",
        "operational_state",
        "operational_state_acceptance",
        "operational_state_repository",
        "production_event",
        "transition_policy",
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


def test_contract_code_has_no_monitoring_transfer_processing_or_control_behavior() -> None:
    forbidden_functions = {
        "calculate_checksum",
        "copy",
        "dispatch",
        "emit_event",
        "enqueue",
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
    defined_functions: set[str] = set()
    called_names: set[str] = set()

    for _, source in _python_sources():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                defined_functions.add(node.name)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called_names.add(node.func.id)

    assert not forbidden_functions & defined_functions
    assert not {"open", "exec", "eval"} & called_names


def test_contracts_do_not_read_an_implicit_wall_clock() -> None:
    forbidden_attributes = {"now", "utcnow", "today", "time", "monotonic", "perf_counter"}
    calls: set[str] = set()

    for _, source in _python_sources():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    assert not forbidden_attributes & calls


def test_public_contract_shape_has_no_session_workflow_or_scoring_state() -> None:
    forbidden_fields = {
        "ai_status",
        "confidence",
        "editorial_status",
        "operational_state",
        "probability",
        "publication_status",
        "queue_position",
        "score",
        "session_id",
        "transfer_status",
    }

    assert all(is_dataclass(contract) for contract in CONTRACTS)
    contract_fields = {
        field.name
        for contract in CONTRACTS
        for field in fields(contract)
    }
    assert not forbidden_fields & contract_fields


def test_public_annotations_are_serialization_ready_and_have_no_active_objects() -> None:
    forbidden_annotation_fragments = {
        "BinaryIO",
        "Callable",
        "FileIO",
        "IOBase",
        "Lock",
        "Path",
        "RuntimeService",
        "Socket",
        "StreamReader",
    }

    for contract in CONTRACTS:
        annotations = get_type_hints(contract)
        rendered = " ".join(str(annotation) for annotation in annotations.values())
        assert not any(fragment in rendered for fragment in forbidden_annotation_fragments)


def test_summary_contract_cannot_expose_source_location_or_credentials() -> None:
    summary_fields = {field.name for field in fields(CompletedMediaAssetSummary)}

    assert not {
        "source_location",
        "location_value",
        "credentials",
        "access_token",
        "password",
    } & summary_fields


def test_documentation_preserves_mission_and_future_boundaries() -> None:
    readme = " ".join((PACKAGE_ROOT / "README.md").read_text().split()).lower()

    for phrase in (
        "production recording application owns recording",
        "production recording and livestream workloads always take priority",
        "actively written",
        "entire recording or session does not need to be complete",
        "filenames and paths are descriptive",
        "agent does not mean lower trust",
        "node does not mean higher trust",
        "does not detect file stability",
        "does not create production events",
        "never stored in the operational state repository",
        "should stop before transfer or queueing",
    ):
        assert phrase in readme


def test_completed_asset_scope_is_registered_in_repository_documents() -> None:
    manifest = (REPOSITORY_ROOT.parent / "REPOSITORY_MANIFEST.md").read_text()
    directives = (REPOSITORY_ROOT.parent / "ENGINEERING_DIRECTIVES.md").read_text()
    production = (REPOSITORY_ROOT / "app" / "contexts" / "production" / "README.md").read_text()
    tests = (REPOSITORY_ROOT / "tests" / "README.md").read_text()

    assert "completed_media_asset/" in manifest
    assert "ED-0048" in directives
    assert "Completed Media Asset" in production
    assert "ED-0048" in tests
