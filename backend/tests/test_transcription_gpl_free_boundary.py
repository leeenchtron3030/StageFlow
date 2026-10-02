"""ADR-0036 / ED-0123: default transcription must have no legacy GPL dependency chain."""

import re
import tomllib
from pathlib import Path
from typing import Any, cast

BACKEND = Path(__file__).resolve().parents[1]
ENGINE = {"ctranslate2==4.8.1", "tokenizers==0.23.1", "numpy==2.5.2"}
FORBIDDEN = {"av", "faster-whisper", "onnxruntime", "huggingface-hub", "tqdm"}
# Owner amendment 2026-10-01: tokenizers hard-depends on huggingface-hub (which pulls in
# tqdm). Both are permissive and may be installed, but only through tokenizers, and the
# engine never imports them (clean-process test in test_ctranslate2_whisper_adapter.py).
FORBIDDEN_LOCKED = {"av", "faster-whisper", "onnxruntime"}
TRANSITIVE_ONLY = {"huggingface-hub": {"tokenizers"}, "tqdm": {"huggingface-hub"}}


def requirement_name(value: str) -> str:
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", value)
    assert match is not None
    return re.sub(r"[-_.]+", "-", match.group()).lower()


def declared_names(value: Any) -> set[str]:
    # Inspect every TOML section, including optional/group/uv declarations and overrides.
    if isinstance(value, dict):
        return set[str]().union(
            *(declared_names(item) for item in cast(dict[str, Any], value).values()))
    if isinstance(value, list):
        return set[str]().union(*(declared_names(item) for item in cast(list[Any], value)))
    if isinstance(value, str) and re.match(r"[A-Za-z0-9]", value):
        return {requirement_name(value)}
    return set()


def test_engine_is_default_and_legacy_packages_are_not_declared() -> None:
    with (BACKEND / "pyproject.toml").open("rb") as source:
        project = tomllib.load(source)
    assert ENGINE <= set(project["project"]["dependencies"])
    assert not {"transcription", "transcription-core"} & project["dependency-groups"].keys()
    assert not FORBIDDEN & declared_names(project)


def test_lock_resolution_is_gpl_free() -> None:
    with (BACKEND / "uv.lock").open("rb") as source:
        lock = tomllib.load(source)
    # Conservatively check every locked package across platforms/extras. This includes
    # the entire default + dev resolution and cannot hide a forbidden transitive edge.
    names = {requirement_name(package["name"]) for package in lock["package"]}
    assert not FORBIDDEN_LOCKED & names, "Owner must run uv lock after ED-0123's default switch"
    # Permitted transitive packages may enter only through their expected parent.
    for name, parents in TRANSITIVE_ONLY.items():
        dependents = {
            requirement_name(package["name"]) for package in lock["package"]
            if any(requirement_name(item["name"]) == name
                   for item in package.get("dependencies", []))
        }
        assert dependents <= parents, (name, dependents)
    root = next(package for package in lock["package"] if package["name"] == "stageflow-backend")
    assert {requirement_name(item) for item in ENGINE} <= {
        item["name"] for item in root["dependencies"]
    }
