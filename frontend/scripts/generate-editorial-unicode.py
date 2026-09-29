"""Regenerate with backend/.venv's Python; no production imports or dependencies."""

import argparse
import json
import unicodedata
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "src/experience/editorial-unicode.ts"


def ranges(points: list[int]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for point in points:
        if result and result[-1][1] == point - 1:
            result[-1] = (result[-1][0], point)
        else:
            result.append((point, point))
    return result


def generate() -> bytes:
    lines = [
        f"// Generated from the installed backend Python Unicode {unicodedata.unidata_version}; "
        "no runtime dependency.",
        "// Regeneration over range(0x110000):",
        "// casefoldMappings = {chr(i): chr(i).casefold() for i in ... "
        "if chr(i).casefold() != chr(i)}",
        "// assignedRanges = consecutive ranges where unicodedata.category(chr(i)) != 'Cn'",
        "// alphanumericRanges = consecutive ranges where chr(i).isalnum()",
        "// Update alongside a backend Unicode-version change "
        "and rerun normalization parity tests.",
        f'export const backendUnicodeVersion = "{unicodedata.unidata_version}";',
        "export const casefoldMappings: Readonly<Record<string, string>> = {",
    ]
    mappings = [(chr(i), chr(i).casefold()) for i in range(0x110000)
                if chr(i).casefold() != chr(i)]
    lines.extend(f"  {json.dumps(key)}: {json.dumps(value)}," for key, value in mappings)
    lines[-1] = lines[-1].removesuffix(",")
    lines.append("};")
    for name, points in [
        ("assignedRanges", [i for i in range(0x110000) if unicodedata.category(chr(i)) != "Cn"]),
        ("alphanumericRanges", [i for i in range(0x110000) if chr(i).isalnum()]),
    ]:
        lines.append(f"export const {name}: readonly (readonly number[])[] = [")
        pairs = ranges(points)
        for start in range(0, len(pairs), 8):
            line = ", ".join(f"[{first}, {last}]" for first, last in pairs[start:start + 8])
            lines.append(f"  {line}" + ("," if start + 8 < len(pairs) else ""))
        lines.append("];")
    # Git checkouts may use LF or CRLF; preserve the target's existing style.
    newline = "\r\n" if TARGET.exists() and b"\r\n" in TARGET.read_bytes() else "\n"
    return (newline.join(lines) + newline).encode("utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify byte-for-byte without writing")
    args = parser.parse_args()
    generated = generate()
    if args.check:
        if TARGET.read_bytes() != generated:
            raise SystemExit(
                "Unicode table drift: run this script with backend/.venv's Python, "
                "then rerun normalization parity tests."
            )
        print(
            f"Unicode {unicodedata.unidata_version}: "
            f"byte-for-byte match ({len(generated)} bytes)"
        )
    else:
        TARGET.write_bytes(generated)
        print(
            f"Generated {TARGET.name} with Unicode {unicodedata.unidata_version}; "
            "rerun normalization parity tests."
        )
