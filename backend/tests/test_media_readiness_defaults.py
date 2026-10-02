import pytest
from pydantic import ValidationError

from app.core.config.deployment import ResourceLimits


def test_default_stability_interval_tolerates_recorder_write_pauses() -> None:
    # ED-0124: a 5 s window registered an in-place recording mid-write in Live Replay Run 002.
    assert ResourceLimits().minimum_stable_seconds == 30


@pytest.mark.parametrize("seconds", [1, 5, 3600])
def test_operator_may_still_choose_any_bounded_interval(seconds: int) -> None:
    assert ResourceLimits(minimum_stable_seconds=seconds).minimum_stable_seconds == seconds


@pytest.mark.parametrize("seconds", [0, 3601])
def test_stability_interval_bounds_are_unchanged(seconds: int) -> None:
    with pytest.raises(ValidationError):
        ResourceLimits(minimum_stable_seconds=seconds)
