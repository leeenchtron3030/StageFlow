"""The frontend's generated normalization tables must match backend Python."""

import re
import unicodedata
from pathlib import Path


def test_frontend_unicode_version_matches_backend_runtime() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "frontend/src/experience/editorial-unicode.ts"
    ).read_text(encoding="utf-8")
    regenerate = (
        "Regenerate frontend/src/experience/editorial-unicode.ts using backend/.venv's Python: "
        "python frontend/scripts/generate-editorial-unicode.py (from the repository root), "
        "then rerun the backend drift test and frontend normalization parity tests."
    )
    versions = re.findall(
        r'^export const backendUnicodeVersion = "([0-9]+\.[0-9]+\.[0-9]+)";$',
        source,
        re.MULTILINE,
    )
    assert len(versions) == 1, regenerate
    assert versions[0] == unicodedata.unidata_version, regenerate
