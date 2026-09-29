"""The accepted document is content authority; all phrases are generic language."""
import re
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from app.contexts.production.session_suggestions.cue_catalog import (
    BOUNDARY_CUE_CATALOG as CATALOG,
)
from app.contexts.production.session_suggestions.cue_catalog import (
    BoundaryCueCatalog,
    CueGroup,
    CuePhrase,
    CueRole,
    EventProfile,
)

COUNTS = {
    "conference.mc-handoffs": 16, "conference.speaker-openings": 17,
    "conference.speaker-closings": 14, "conference.breaks": 6, "panels": 8,
    "civic.open-close": 9, "civic.agenda": 6, "arena.pa": 7, "arena.anthem": 4,
    "community.anchoring": 10, "press": 6, "interviews": 10, "broadcast": 8,
    "studio.setups": 1, "studio.takes": 92, "studio.wraps": 4, "virtual": 7, "tech.pitch": 8,
    "regional.au-nz": 5, "regional.uk-ie": 4, "regional.south-asia": 3,
}


def test_exact_catalog_content_counts_profiles_and_templates() -> None:
    assert CATALOG.id == "boundary-cue-catalog" and CATALOG.version == 1
    assert CATALOG.digest == "c43f4bc7e95e6ded3578dc5afb4feb452e6c14f52014544dd8e7596536a1aad3"
    assert {g.key: len(g.phrases) for g in CATALOG.groups} == COUNTS
    assert len(CATALOG.groups) == 21
    assert tuple(g.key for g in CATALOG.groups) == tuple(COUNTS)
    assert all(g.version == 1 for g in CATALOG.groups)
    assert tuple(p.key for p in CATALOG.profiles) == (
        "conference", "tech", "panels", "civic", "arena", "community", "press",
        "interviews", "broadcast", "studio", "virtual")
    assert CATALOG.profiles[1].group_keys == CATALOG.profiles[0].group_keys + ("tech.pitch",)
    assert [p.group_keys for p in CATALOG.profiles[2:]] == [
        ("panels", "conference.mc-handoffs", "conference.speaker-closings"),
        ("civic.open-close", "civic.agenda"), ("arena.pa", "arena.anthem"),
        ("community.anchoring", "conference.mc-handoffs", "conference.speaker-closings"),
        ("press",), ("interviews",), ("broadcast",),
        ("studio.setups", "studio.takes", "studio.wraps"), ("virtual",)]
    assert all(not k.startswith("regional.") for p in CATALOG.profiles for k in p.group_keys)
    document = (Path(__file__).parents[2] / "docs/ux/cue-phrase-catalog.md").read_text(
        encoding="utf-8")
    profile_table = document.split("## Event profiles (starter bundles)")[1].split("**Regional")[0]
    names = [line.split("|")[1].strip() for line in profile_table.splitlines()
             if line.startswith("| ")][2:]
    assert [p.name for p in CATALOG.profiles] == names
    # Compare every literal, role, evidence label and default against its source row.
    for group in CATALOG.groups:
        section = document.split(f"(`{group.key}`)", 1)[1]
        section = re.split(r"\n(?:### |\*\*|## )", section, maxsplit=1)[0]
        rows = [tuple(c.strip() for c in line.strip("|").split("|"))
                for line in section.splitlines() if line.startswith("| ")][2:]
        expected: list[tuple[str, str, bool, str]] = []
        words = ("one two three four five six seven eight nine ten eleven twelve thirteen "
                 "fourteen fifteen sixteen seventeen eighteen nineteen twenty").split()
        for text, role, evidence, default in rows:
            if text.startswith("take {n}"):
                text = "take {n}"
            texts = [text] if "{n}" not in text else [
                text.replace("{n}", n) for digit, word in enumerate(words, 1)
                for n in (str(digit), word)]
            expected.extend((t, role, default.startswith("yes"), evidence) for t in texts)
        assert [(p.text, p.role, p.default, p.evidence) for p in group.phrases] == expected
    takes = next(g for g in CATALOG.groups if g.key == "studio.takes")
    for prefix in ("take ", "scene "):
        assert sum(p.text.startswith(prefix) for p in takes.phrases) == 40
    assert "ceremonies.awards" not in COUNTS and "worship" not in COUNTS
    assert all(p.text != "thank you" for g in CATALOG.groups for p in g.phrases)


@pytest.mark.parametrize("text", ["", " ", "!!!", "x" * 101])
def test_catalog_rejects_invalid_phrases(text: str) -> None:
    with pytest.raises(ValueError):
        CuePhrase(text, CueRole.START, True, "R")


def test_catalog_validation_and_recursive_immutability() -> None:
    group, profile = CATALOG.groups[0], CATALOG.profiles[0]
    with pytest.raises(ValueError, match="duplicate group"):
        BoundaryCueCatalog((group, group), ())
    with pytest.raises(ValueError, match="duplicate profile"):
        BoundaryCueCatalog(CATALOG.groups, (profile, profile))
    with pytest.raises(ValueError, match="unknown profile group"):
        BoundaryCueCatalog((group,), (EventProfile("unknown", "Unknown", ("absent",)),))
    with pytest.raises(ValueError, match="duplicate normalized"):
        replace(group, phrases=(group.phrases[0], replace(group.phrases[0],
                                                        text=group.phrases[0].text.upper())))
    with pytest.raises(ValueError):
        replace(group.phrases[0], role="invalid")  # type: ignore[arg-type]
    with pytest.raises(FrozenInstanceError):
        group.phrases[0].text = "Changed"  # type: ignore[misc]
    mutable = [group.phrases[0]]
    copied = CueGroup("copy", "Copy", "Synthetic", mutable)  # type: ignore[arg-type]
    mutable.clear()
    assert len(copied.phrases) == 1
    assert replace(CATALOG).digest == CATALOG.digest
    assert replace(CATALOG, groups=CATALOG.groups[::-1]).digest != CATALOG.digest
