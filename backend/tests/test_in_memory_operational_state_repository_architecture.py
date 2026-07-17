from __future__ import annotations

import ast
from dataclasses import fields, is_dataclass
from inspect import getmembers, isabstract, isfunction
from pathlib import Path
from typing import Any, cast

from app.contexts.production.operational_state_repository import (
    InMemoryOperationalStateRepository,
    OperationalStateRepository,
)
from app.contexts.production.operational_state_repository.in_memory_repository_state import (
    InMemoryOperationalStateRepositoryState,
)

REPOSITORY_ROOT = Path(__file__).parents[2]
PACKAGE_ROOT = (
    REPOSITORY_ROOT
    / "backend"
    / "app"
    / "contexts"
    / "production"
    / "operational_state_repository"
)


def _implementation_sources() -> tuple[tuple[Path, str], ...]:
    names = (
        "in_memory_operational_state_repository.py",
        "in_memory_repository_state.py",
    )
    return tuple((PACKAGE_ROOT / name, (PACKAGE_ROOT / name).read_text()) for name in names)


def test_exactly_one_concrete_repository_implements_the_ed0046_interface() -> None:
    concrete_subclasses: list[str] = []
    for path in sorted(PACKAGE_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            base_names = {
                base.id
                for base in node.bases
                if isinstance(base, ast.Name)
            }
            if "OperationalStateRepository" in base_names:
                concrete_subclasses.append(node.name)

    assert isabstract(OperationalStateRepository)
    assert not isabstract(InMemoryOperationalStateRepository)
    assert concrete_subclasses == ["InMemoryOperationalStateRepository"]


def test_concrete_repository_exposes_only_the_existing_public_operations() -> None:
    public_methods = {
        name
        for name, value in getmembers(InMemoryOperationalStateRepository)
        if isfunction(value) and not name.startswith("_")
    }

    assert public_methods == {
        "commit_acceptance",
        "get_commit_by_evaluation",
        "get_current_state",
        "get_state",
        "has_committed_evaluation",
        "list_state_history",
    }


def test_internal_state_is_frozen_minimal_and_not_publicly_exported() -> None:
    import app.contexts.production.operational_state_repository as repository_package

    assert is_dataclass(InMemoryOperationalStateRepositoryState)
    assert cast(Any, InMemoryOperationalStateRepositoryState).__dataclass_params__.frozen
    assert {field.name for field in fields(InMemoryOperationalStateRepositoryState)} == {
        "records_by_state_id",
        "current_state_id_by_key",
        "history_ids_by_key",
        "commits_by_evaluation_id",
        "commits_by_acceptance_id",
        "revisions_by_key",
    }
    assert "InMemoryOperationalStateRepositoryState" not in repository_package.__all__
    assert "OperationalStateRepositoryKey" not in repository_package.__all__


def test_implementation_imports_no_persistence_network_or_execution_infrastructure() -> None:
    forbidden_modules = {
        "asyncio",
        "fastapi",
        "httpx",
        "multiprocessing",
        "pathlib",
        "queue",
        "redis",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
    }
    forbidden_domain_modules = {
        "operational_state_acceptance.operational_state_acceptance",
        "recording_transition_policy",
        "session_transition_policy",
        "transition_policy.operational_state_transition_policy",
    }
    imported: set[str] = set()

    for _, source in _implementation_sources():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)

    assert not any(
        name == forbidden or name.startswith(f"{forbidden}.")
        for name in imported
        for forbidden in forbidden_modules
    )
    assert not any(
        name == forbidden or name.endswith(f".{forbidden}")
        for name in imported
        for forbidden in forbidden_domain_modules
    )


def test_implementation_has_no_deployment_asset_runtime_or_production_commands() -> None:
    implementation = "\n".join(source.lower() for _, source in _implementation_sources())
    forbidden_terms = {
        "agent_type",
        "asset_queue",
        "completed_file",
        "deployment_type",
        "file_transfer",
        "media_file",
        "node_type",
        "publish_event",
        "register_runtime",
        "start_recording",
        "stop_recording",
    }

    assert not any(term in implementation for term in forbidden_terms)


def test_documentation_registers_process_local_contract_validation_scope() -> None:
    package_readme = " ".join((PACKAGE_ROOT / "README.md").read_text().lower().split())
    production_readme = (
        REPOSITORY_ROOT
        / "backend"
        / "app"
        / "contexts"
        / "production"
        / "README.md"
    ).read_text().lower()
    manifest = (REPOSITORY_ROOT / "REPOSITORY_MANIFEST.md").read_text()
    directives = (REPOSITORY_ROOT / "ENGINEERING_DIRECTIVES.md").read_text()

    for phrase in (
        "development and contract-validation repository",
        "one process",
        "copy-and-swap",
        "rejected commits",
        "repository instances are isolated",
        "not an asset queue",
        "not production persistence",
    ):
        assert phrase in package_readme
    assert "inmemoryoperationalstaterepository" in production_readme
    assert "in_memory_operational_state_repository.py" in manifest
    assert "ED-0047" in directives
