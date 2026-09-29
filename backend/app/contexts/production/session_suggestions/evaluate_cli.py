"""Read local anonymous interval JSON; emit aggregate numeric metrics only."""
import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn, cast

from .contracts import Span
from .evaluation import evaluate_accuracy


class SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        # argparse's default error includes caller-supplied arguments.
        raise ValueError("invalid_arguments")


def read_intervals(path: Path) -> tuple[Span, ...]:
    values = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(values, list):
        raise ValueError("interval_array_required")
    records = cast(list[dict[str, Any]], values)
    return tuple(Span(datetime.fromisoformat(v["start"]), datetime.fromisoformat(v["end"]))
                 for v in records)


def main(argv: Sequence[str] | None = None) -> int:
    parser = SanitizedArgumentParser(prog="session-suggestion-evaluate", description=__doc__)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("suggestions", type=Path)
    try:
        args = parser.parse_args(argv)
        truth = read_intervals(args.ground_truth)
        suggestions = read_intervals(args.suggestions)
        metrics = evaluate_accuracy(suggestions, truth)
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        # Never echo filenames, contents, identifiers, timestamps or exception text.
        print('{"error_count": 1}')
        return 1
    print(json.dumps(asdict(metrics), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
