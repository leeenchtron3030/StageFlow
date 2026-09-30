"""Read an external corpus manifest and print sanitized policy metrics."""
import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from .contracts import ScheduleOffsetEntry
from .evaluate_cli import SanitizedArgumentParser
from .harness import markdown_report, parse_manifest, run_manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = SanitizedArgumentParser(prog="session-suggestion-harness", description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--policy-version", choices=("1", "2", "3"), default="3")
    parser.add_argument("--schedule-source", choices=("manifest", "drift"), default="manifest")
    parser.add_argument("--drift-model", choices=("whole-day", "two-part", "independent"),
                        default="whole-day")
    parser.add_argument("--magnitude-seconds", type=int, default=0)
    parser.add_argument("--seeds", type=int, nargs="+", default=[0])
    parser.add_argument("--cue-profile")
    parser.add_argument("--producer-offset", nargs=2, action="append", default=[],
                        metavar=("AWARE_ISO", "SECONDS"))
    parser.add_argument("--markdown", action="store_true",
                        help="append a Markdown metric table after the JSON report")
    try:
        args = parser.parse_args(argv)
        stages = parse_manifest(args.manifest.read_text(encoding="utf-8"))
        offsets = tuple(ScheduleOffsetEntry(datetime.fromisoformat(t), int(s))
                        for t, s in args.producer_offset)
        report = run_manifest(
            stages, policy_version=args.policy_version, schedule_source=args.schedule_source,
            drift_model=args.drift_model, magnitude_seconds=args.magnitude_seconds,
            seeds=args.seeds, cue_profile=args.cue_profile, producer_offsets=offsets,
        )
        output = json.dumps(report, sort_keys=True, allow_nan=False)
        if args.markdown:
            output += "\n\n" + markdown_report(report)
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        print('{"error_count": 1}')
        return 1
    except Exception:
        print('{"error_count": 1}')
        return 1
    print(output)
    return 0 if all(s["target_pass"] for s in report["scenarios"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
