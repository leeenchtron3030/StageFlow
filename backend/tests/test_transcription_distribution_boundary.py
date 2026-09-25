"""Guard ED-0075's optional local-transcription installation boundary."""

import re
import tomllib
from pathlib import Path


def test_transcription_remains_a_non_default_dependency_group() -> None:
    with (Path(__file__).resolve().parents[1] / "pyproject.toml").open("rb") as manifest:
        project = tomllib.load(manifest)

    groups = project["dependency-groups"]
    assert "transcription" in groups
    default_groups = project.get("tool", {}).get("uv", {}).get("default-groups", ["dev"])
    assert default_groups != "all", "ED-0075 excludes transcription from default groups"
    assert "transcription" not in default_groups

    # Follow included groups so a default group cannot indirectly enable transcription.
    pending = list(default_groups)
    visited: set[str] = set()
    default_requirements = list(project["project"]["dependencies"])
    while pending:
        group = pending.pop()
        assert group != "transcription", "A default group includes transcription"
        if group in visited:
            continue
        visited.add(group)
        for requirement in groups[group]:
            if isinstance(requirement, str):
                default_requirements.append(requirement)
            else:
                pending.append(requirement["include-group"])

    # Check package identities, independent of pins, extras, markers, or name spelling.
    # Include PyAV itself so directly promoting the transitive exposure also fails.
    excluded = {"transcription", "ctranslate2", "faster-whisper", "av"}
    for requirement in default_requirements:
        match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement)
        assert match is not None
        name = re.sub(r"[-_.]+", "-", match.group()).lower()
        assert name not in excluded, f"ED-0075 excludes {name} from default dependencies"
