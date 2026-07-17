from __future__ import annotations

import ast
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[1]
PACKAGE_ROOT = (
    REPOSITORY_ROOT
    / "app"
    / "contexts"
    / "production"
    / "operational_state_repository"
)


def _contract_python_sources() -> tuple[tuple[Path, str], ...]:
    return tuple(
        (path, path.read_text())
        for path in sorted(PACKAGE_ROOT.glob("*.py"))
        if not path.name.startswith("in_memory_")
    )


def test_repository_package_retains_all_contract_files_without_persistent_storage() -> None:
    filenames = {path.name for path in PACKAGE_ROOT.iterdir()}
    required = {
        "README.md",
        "__init__.py",
        "operational_state_repository.py",
        "operational_state_repository_commit_outcome.py",
        "operational_state_repository_commit_reason.py",
        "operational_state_repository_commit_request.py",
        "operational_state_repository_commit_result.py",
        "operational_state_repository_error.py",
        "operational_state_repository_history.py",
        "operational_state_repository_query_result.py",
        "operational_state_repository_record.py",
    }
    forbidden_fragments = {
        "database",
        "sqlite",
        "sql",
        "redis",
        "filesystem",
        "worker",
        "queue",
        "api",
    }

    assert required <= filenames
    assert not any(fragment in name for name in filenames for fragment in forbidden_fragments)


def test_repository_contract_code_has_no_infrastructure_or_execution_imports() -> None:
    forbidden_modules = {
        "asyncio",
        "fastapi",
        "multiprocessing",
        "pathlib",
        "queue",
        "redis",
        "sqlalchemy",
        "sqlite3",
        "subprocess",
        "threading",
    }
    forbidden_domain_modules = {
        "recording_transition_policy",
        "session_transition_policy",
        "transition_policy",
        "operational_state_acceptance.operational_state_acceptance",
    }
    imported: set[str] = set()

    for _, source in _contract_python_sources():
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


def test_no_concrete_repository_subclass_or_runtime_behavior_is_hidden_in_contract_files() -> None:
    concrete_subclasses: list[str] = []
    forbidden_methods = {
        "connect",
        "create_table",
        "delete",
        "dispatch",
        "execute",
        "flush",
        "publish",
        "retry",
        "run_worker",
        "save_file",
        "send",
        "start_recording",
        "stop_recording",
    }
    methods: set[str] = set()

    for _, source in _contract_python_sources():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                base_names = {
                    base.id
                    for base in node.bases
                    if isinstance(base, ast.Name)
                }
                if "OperationalStateRepository" in base_names:
                    concrete_subclasses.append(node.name)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                methods.add(node.name)

    assert concrete_subclasses == []
    assert not forbidden_methods & methods


def test_repository_documentation_preserves_atomicity_and_mission_boundaries() -> None:
    readme = (PACKAGE_ROOT / "README.md").read_text()
    normalized_readme = " ".join(readme.split())

    for phrase in (
        "at most one current record",
        "No partial-success result shape exists",
        "stale commit never overwrites newer state",
        "one Transition Evaluation ID and one acceptance ID",
        "never mutates the caller's `OperationalState`",
        "oldest committed state to newest",
        "timezone-aware",
        "not a media boundary",
        "does not control physical reality",
        "not production persistence",
    ):
        assert phrase.lower() in normalized_readme.lower()


def test_repository_is_registered_as_backend_only_contract_scope() -> None:
    manifest = (REPOSITORY_ROOT.parent / "REPOSITORY_MANIFEST.md").read_text()
    directives = (REPOSITORY_ROOT.parent / "ENGINEERING_DIRECTIVES.md").read_text()
    production = (REPOSITORY_ROOT / "app" / "contexts" / "production" / "README.md").read_text()

    assert "operational_state_repository/" in manifest
    assert "ED-0046" in directives
    assert "Operational State Repository" in production
    assert "not production persistence" in production
