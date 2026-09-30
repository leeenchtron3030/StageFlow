"""Generic synthetic intervals only: deterministic, media-free regression scenarios."""
from datetime import UTC, datetime, timedelta
from random import Random
from typing import Any, Literal, overload

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


@overload
def realistic_schedule_error(seed: int, *, talk_count: int = 30, slot_seconds: int = 1500,
                             dropped: bool = False, added: bool = False,
                             after_program: bool = False,
                             timeline: Literal[False] = False) -> dict[str, Any]: ...


@overload
def realistic_schedule_error(seed: int, *, talk_count: int = 30, slot_seconds: int = 1500,
                             dropped: bool = False, added: bool = False,
                             after_program: bool = False,
                             timeline: Literal[True]) -> tuple[dict[str, Any], dict[str, Any]]: ...


def realistic_schedule_error(seed: int, *, talk_count: int = 30, slot_seconds: int = 1500,
                             dropped: bool = False, added: bool = False,
                             after_program: bool = False, timeline: bool = False,
                             ) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
    """Fresh manifest Stage, optionally with plain relative-second replay data.

    RNG string (version 2): stageflow:session-suggestions:realistic:v1:{seed}.
    Draw order: initial lateness, dropped index, added index, then each scheduled
    talk's integer percent error and changeover jitter (including dropped talks),
    and added duration when applicable. Parameters never enter the seed string.
    Duration error is discrete uniform -40..40 percent, truncated toward zero
    to whole seconds (preserving symmetry and bounds); the changeover is 180 s
    plus discrete uniform -60..60 s. Their accumulation is the lateness walk.
    A dropped slot consumes no time; an added talk extends the walk by its duration
    plus a 180 s changeover. Tail content is a separate unscheduled 900 s interval.
    No media is generated; replay rendering is an owner step.
    """
    if (type(seed) is not int or seed < 0 or type(talk_count) is not int
            or not 2 <= talk_count <= 60 or type(slot_seconds) is not int
            or not 1200 <= slot_seconds <= 1800
            or any(type(flag) is not bool for flag in (dropped, added, after_program, timeline))):
        raise ValueError("invalid_scenario_options")
    rng = Random(f"stageflow:session-suggestions:realistic:v1:{seed}")
    cursor = rng.randint(-300, 300)
    drop_index = rng.randrange(talk_count)
    add_index = rng.randrange(talk_count)
    duration = slot_seconds - 180
    plans = [(i * slot_seconds, i * slot_seconds + duration) for i in range(talk_count)]
    talks: list[dict[str, Any]] = []
    for i in range(talk_count):
        percent = rng.randint(-40, 40)
        error = duration * abs(percent) // 100
        actual_duration = duration + (error if percent >= 0 else -error)
        gap = 180 + rng.randint(-60, 60)
        if not dropped or i != drop_index:
            talks.append({"schedule_index": i, "start_seconds": cursor,
                          "end_seconds": cursor + actual_duration})
            cursor += actual_duration + gap
        if added and i == add_index:
            extra = rng.randint(600, 1200)
            talks.append({"schedule_index": None, "start_seconds": cursor,
                          "end_seconds": cursor + extra})
            cursor += extra + 180
    if after_program:
        talks.append({"schedule_index": None, "start_seconds": cursor,
                      "end_seconds": cursor + 900})
    first, last = talks[0]["start_seconds"] - 120, talks[-1]["end_seconds"] + 120
    holds = [(first, talks[0]["start_seconds"]),
             *((a["end_seconds"], b["start_seconds"])
               for a, b in zip(talks, talks[1:], strict=False)),
             (talks[-1]["end_seconds"], last)]
    blocks: list[dict[str, Any]] = []
    replay_blocks: list[dict[str, Any]] = []
    for start in range(first, last, 600):
        end = min(start + 600, last)
        freezes = tuple((max(a, start), min(b, end)) for a, b in holds if a < end and b > start)
        blocks.append(_block(start, end, freezes))
        replay_blocks.append({"start_seconds": start, "end_seconds": end,
                              "holding_intervals": [list(x) for x in freezes]})
    stage = {"blocks": blocks,
             "schedule": [{"key": f"talk-{i}", "planned_start": _time(a),
                           "planned_end": _time(b)} for i, (a, b) in enumerate(plans)],
             "truth": [{"start": _time(t["start_seconds"]), "end": _time(t["end_seconds"])}
                       for t in talks]}
    return (stage, {"talks": talks, "blocks": replay_blocks}) if timeline else stage
