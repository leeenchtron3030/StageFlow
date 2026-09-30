"""Generic synthetic intervals only: deterministic, media-free regression scenarios."""
from datetime import UTC, datetime, timedelta
from typing import Any

SCENARIOS = ("clean-day", "recording-gaps", "multi-part", "wrong-clock",
             "short-evenly-spaced", "late-recording-start")
_START = datetime(2000, 1, 1, 9, tzinfo=UTC)


def _time(seconds: int) -> str:
    return (_START + timedelta(seconds=seconds)).isoformat()


def _block(start: int, end: int, freezes: tuple[tuple[int, int], ...] = ()) -> dict[str, Any]:
    return {"start": _time(start), "duration_us": (end - start) * 1_000_000,
            "intervals": [{"kind": kind, "start_us": (a - start) * 1_000_000,
                           "end_us": (b - start) * 1_000_000}
                          for a, b in freezes for kind in ("freeze", "silence")]}


def generate_scenario(name: str) -> dict[str, Any]:
    """Return a fresh JSON-serializable manifest; unknown labels are never echoed."""
    if name not in SCENARIOS:
        raise ValueError("unknown_scenario")
    truth = ((0, 1800), (2100, 3900), (4200, 6000))
    plans = truth
    blocks = [_block(0, 6000, ((1800, 2100), (3900, 4200)))]
    if name == "recording-gaps":
        blocks = [_block(0, 1800), _block(2100, 3900), _block(4200, 6000)]
    elif name == "multi-part":
        truth = plans = ((0, 3900), (4200, 6000))
    elif name == "wrong-clock":
        blocks.append(_block(2 * 365 * 86400, 2 * 365 * 86400 + 6000))
    elif name == "short-evenly-spaced":
        truth = tuple((i * 420, i * 420 + 300) for i in range(8))
        # One-slot schedule shift exposes v3's periodic alignment ambiguity.
        plans = tuple((a + 420, b + 420) for a, b in truth)
        blocks = [_block(-120, 8 * 420, tuple((i * 420 - 120, i * 420) for i in range(9)))]
    elif name == "late-recording-start":
        blocks = [_block(300, 6000, ((1800, 2100), (3900, 4200)))]
    return {"stages": [{"blocks": blocks,
                        "schedule": [{"key": f"talk-{i}", "planned_start": _time(a),
                                      "planned_end": _time(b)} for i, (a, b) in enumerate(plans)],
                        "truth": [{"start": _time(a), "end": _time(b)} for a, b in truth]}]}
