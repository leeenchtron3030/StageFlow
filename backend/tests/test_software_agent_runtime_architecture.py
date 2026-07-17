from __future__ import annotations

import ast
from pathlib import Path

from app.contexts.production.software_agent_runtime import SoftwareAgentRuntime

PACKAGE = Path(__file__).parents[1] / "app" / "contexts" / "production" / "software_agent_runtime"
ROOT = Path(__file__).parents[2]
PYTHON_FILES = tuple(sorted(PACKAGE.rglob("*.py")))


def _trees() -> tuple[tuple[Path, ast.Module], ...]:
    return tuple((path, ast.parse(path.read_text(encoding="utf-8"))) for path in PYTHON_FILES)


def test_agent_runtime_package_has_exact_focused_source_scope() -> None:
    relative = {path.relative_to(PACKAGE).as_posix() for path in PYTHON_FILES}

    assert relative == {
        "__init__.py",
        "agent_runtime_contract_validation.py",
        "agent_runtime_dependencies.py",
        "agent_runtime_derivation.py",
        "agent_runtime_lifecycle.py",
        "agent_runtime_requests.py",
        "agent_runtime_snapshot.py",
        "ports/__init__.py",
        "ports/lifecycle_event_sink.py",
        "ports/runtime_availability_sink.py",
        "ports/runtime_health_sink.py",
        "software_agent_runtime.py",
    }
    assert (PACKAGE / "README.md").is_file()


def test_software_agent_runtime_is_the_only_concrete_runtime_lifecycle() -> None:
    runtime_classes = [
        node.name
        for _, tree in _trees()
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name.endswith("Runtime")
    ]

    assert runtime_classes == ["SoftwareAgentRuntime"]
    assert SoftwareAgentRuntime.__module__.endswith("software_agent_runtime")


def test_runtime_uses_one_rlock_and_never_starts_background_execution() -> None:
    source = (PACKAGE / "software_agent_runtime.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "RLock" in imports
    assert calls & {"RLock"} == {"RLock"}
    assert not calls & {
        "Thread",
        "create_task",
        "run",
        "sleep",
        "start_new_thread",
    }
    assert (
        not {
            "asyncio",
            "concurrent.futures",
            "multiprocessing",
            "sched",
        }
        & imports
    )


def test_package_has_no_implicit_clock_filesystem_network_process_or_gpu_access() -> None:
    banned_import_roots = {
        "aiohttp",
        "boto3",
        "glob",
        "httpx",
        "os",
        "pathlib",
        "psutil",
        "requests",
        "shutil",
        "socket",
        "subprocess",
        "torch",
        "urllib",
        "watchdog",
    }
    banned_calls = {
        "exec",
        "open",
        "popen",
        "remove",
        "rename",
        "unlink",
    }
    banned_clock_attributes = {"now", "today", "utcnow"}

    for path, tree in _trees():
        imports = {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        imports.update(
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert not banned_import_roots & imports, path
        assert not banned_calls & names, path
        assert not banned_clock_attributes & attributes, path


def test_package_does_not_depend_on_media_reasoning_state_or_repository_layers() -> None:
    forbidden_fragments = {
        "asset_readiness",
        "completed_media_asset",
        "evidence",
        "production_event",
        "observation",
        "operational_state",
        "readiness",
        "repository",
        "session",
    }

    imported_modules = {
        node.module or ""
        for _, tree in _trees()
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported_modules.update(
        alias.name
        for _, tree in _trees()
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert not {
        module
        for module in imported_modules
        if any(fragment in module for fragment in forbidden_fragments)
    }


def test_no_service_cli_scheduler_watcher_polling_or_arbitrary_transition_api_exists() -> None:
    function_names = {
        node.name
        for _, tree in _trees()
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    class_names = {
        node.name.lower()
        for _, tree in _trees()
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    }

    assert (
        not {
            "main",
            "poll",
            "run_forever",
            "schedule",
            "serve",
            "start_daemon",
            "watch",
        }
        & function_names
    )
    assert (
        not {
            "daemon",
            "scheduler",
            "service",
            "watcher",
            "worker",
        }
        & class_names
    )
    assert not {
        "append_transition",
        "insert_transition",
        "set_snapshot",
    } & set(dir(SoftwareAgentRuntime))
    assert not (PACKAGE / "__main__.py").exists()


def test_documentation_states_mission_lifecycle_and_safety_boundaries() -> None:
    package_doc = (PACKAGE / "README.md").read_text(encoding="utf-8").lower()
    production_doc = (PACKAGE.parent / "README.md").read_text(encoding="utf-8").lower()
    runtime_doc = (PACKAGE.parent / "runtime" / "README.md").read_text(encoding="utf-8").lower()

    required = {
        "construction",
        "explicit resume",
        "explicit startup",
        "first executable runtime profile",
        "in-process",
        "notification",
        "production",
        "runtimeconfiguration",
        "stopped instance",
        "validate_runtime",
    }
    assert required <= {phrase for phrase in required if phrase in package_doc}
    assert "not a production event" in package_doc
    assert "no candidate discovery" in package_doc
    assert "software agent runtime" in production_doc
    assert "ed-0051 execution relationship" in runtime_doc


def test_repository_indexes_register_all_ed0051_files_and_tests() -> None:
    manifest = (ROOT / "REPOSITORY_MANIFEST.md").read_text(encoding="utf-8")
    directives = (ROOT / "ENGINEERING_DIRECTIVES.md").read_text(encoding="utf-8")
    tests_doc = (ROOT / "backend" / "tests" / "README.md").read_text(encoding="utf-8")

    for path in (
        *PYTHON_FILES,
        PACKAGE / "README.md",
        *sorted((ROOT / "backend" / "tests").glob("*software_agent_runtime*")),
    ):
        relative = path.relative_to(ROOT).as_posix()
        assert f"`{relative}`" in manifest
    assert "| ED-0051 | Software Agent Runtime Lifecycle |" in directives
    assert "ED-0051 adds `software_agent_runtime_fixtures.py`" in tests_doc
