from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

import pytest
from asset_readiness_fixtures import (
    BASE_TIME,
    CANDIDATE_ID,
    FILESYSTEM_TIME,
    HOST_ID,
    MINIMUM_INTERVAL,
    RESOURCE_ID,
    VOLUME_ID,
    entity_id,
    make_snapshot,
)

from app.contexts.production.asset_readiness import AssetStabilityWindow, find_stability_window


def test_two_equal_snapshots_form_a_stability_window() -> None:
    first = make_snapshot(1, BASE_TIME)
    second = make_snapshot(2, BASE_TIME + MINIMUM_INTERVAL)

    window = find_stability_window((first, second), MINIMUM_INTERVAL)

    assert window is not None
    assert window.first_snapshot_id == first.id
    assert window.last_snapshot_id == second.id
    assert window.started_at == BASE_TIME
    assert window.ended_at == BASE_TIME + MINIMUM_INTERVAL
    assert window.elapsed == MINIMUM_INTERVAL
    assert window.stable_size_bytes == 1000
    assert window.stable_filesystem_modified_at == FILESYSTEM_TIME
    assert window.stable_resource_identity_token == "resource-generation-a"
    assert window.snapshot_ids == (first.id, second.id)


def test_three_equal_snapshots_are_retained_in_one_window() -> None:
    snapshots = (
        make_snapshot(1, BASE_TIME),
        make_snapshot(2, BASE_TIME + timedelta(seconds=2)),
        make_snapshot(3, BASE_TIME + MINIMUM_INTERVAL),
    )

    window = find_stability_window(snapshots, MINIMUM_INTERVAL)

    assert window is not None
    assert window.snapshot_ids == tuple(snapshot.id for snapshot in snapshots)


@pytest.mark.parametrize(
    "second",
    (
        make_snapshot(2, BASE_TIME + MINIMUM_INTERVAL, size_bytes=1001),
        make_snapshot(
            2,
            BASE_TIME + MINIMUM_INTERVAL,
            filesystem_modified_at=FILESYSTEM_TIME + timedelta(seconds=1),
        ),
        make_snapshot(
            2,
            BASE_TIME + MINIMUM_INTERVAL,
            identity_token="resource-generation-b",
        ),
        make_snapshot(
            2,
            BASE_TIME + MINIMUM_INTERVAL,
            source_host_id=entity_id(901),
        ),
        make_snapshot(
            2,
            BASE_TIME + MINIMUM_INTERVAL,
            source_volume_id=entity_id(902),
        ),
    ),
)
def test_changed_resource_fact_breaks_stability(second: object) -> None:
    from app.contexts.production.asset_readiness import AssetResourceSnapshot

    assert isinstance(second, AssetResourceSnapshot)
    first = make_snapshot(1, BASE_TIME)

    assert find_stability_window((first, second), MINIMUM_INTERVAL) is None


def test_equal_snapshots_with_too_little_elapsed_time_do_not_form_a_window() -> None:
    snapshots = (
        make_snapshot(1, BASE_TIME),
        make_snapshot(2, BASE_TIME + MINIMUM_INTERVAL - timedelta(microseconds=1)),
    )

    assert find_stability_window(snapshots, MINIMUM_INTERVAL) is None


def test_intermediate_contradiction_cannot_be_skipped() -> None:
    snapshots = (
        make_snapshot(1, BASE_TIME, size_bytes=1000),
        make_snapshot(2, BASE_TIME + timedelta(seconds=3), size_bytes=1200),
        make_snapshot(3, BASE_TIME + timedelta(seconds=6), size_bytes=1000),
    )

    assert find_stability_window(snapshots, MINIMUM_INTERVAL) is None


def test_stability_calculation_is_input_order_independent() -> None:
    first = make_snapshot(1, BASE_TIME)
    middle = make_snapshot(2, BASE_TIME + timedelta(seconds=2))
    last = make_snapshot(3, BASE_TIME + MINIMUM_INTERVAL)

    forward = find_stability_window((first, middle, last), MINIMUM_INTERVAL)
    reversed_result = find_stability_window((last, first, middle), MINIMUM_INTERVAL)

    assert forward == reversed_result


def test_latest_qualifying_stable_run_is_selected_deterministically() -> None:
    snapshots = (
        make_snapshot(1, BASE_TIME, size_bytes=1000),
        make_snapshot(2, BASE_TIME + timedelta(seconds=5), size_bytes=1000),
        make_snapshot(3, BASE_TIME + timedelta(seconds=6), size_bytes=1200),
        make_snapshot(4, BASE_TIME + timedelta(seconds=11), size_bytes=1200),
    )

    window = find_stability_window(snapshots, MINIMUM_INTERVAL)

    assert window is not None
    assert window.first_snapshot_id == snapshots[2].id
    assert window.last_snapshot_id == snapshots[3].id
    assert window.stable_size_bytes == 1200


def test_missing_optional_snapshot_facts_become_first_class_limitations() -> None:
    snapshots = (
        make_snapshot(
            1,
            BASE_TIME,
            filesystem_modified_at=None,
            identity_token=None,
        ),
        make_snapshot(
            2,
            BASE_TIME + MINIMUM_INTERVAL,
            filesystem_modified_at=None,
            identity_token=None,
        ),
    )

    window = find_stability_window(snapshots, MINIMUM_INTERVAL)

    assert window is not None
    assert window.limitations == (
        "filesystem modification timestamp unavailable",
        "source identity token unavailable",
    )


def test_stability_finder_requires_a_positive_explicit_interval() -> None:
    with pytest.raises(ValueError, match="positive"):
        find_stability_window((), timedelta(0))


def test_stability_window_validates_timing_identity_and_size() -> None:
    valid = AssetStabilityWindow(
        candidate_id=CANDIDATE_ID,
        resource_id=RESOURCE_ID,
        first_snapshot_id=entity_id(1),
        last_snapshot_id=entity_id(2),
        started_at=BASE_TIME,
        ended_at=BASE_TIME + MINIMUM_INTERVAL,
        elapsed=MINIMUM_INTERVAL,
        stable_size_bytes=1000,
        stable_filesystem_modified_at=FILESYSTEM_TIME,
        stable_resource_identity_token="resource-generation-a",
        snapshot_ids=(entity_id(1), entity_id(2)),
    )

    with pytest.raises(ValueError, match="elapsed"):
        replace(valid, elapsed=timedelta(seconds=4))
    with pytest.raises(ValueError, match="negative"):
        replace(valid, stable_size_bytes=-1)
    with pytest.raises(ValueError, match="First snapshot"):
        replace(valid, snapshot_ids=(entity_id(3), entity_id(2)))
    with pytest.raises(ValueError, match="unique"):
        replace(
            valid,
            last_snapshot_id=entity_id(1),
            snapshot_ids=(entity_id(1), entity_id(1)),
        )


def test_stability_window_defensively_normalizes_collections_and_is_frozen() -> None:
    first = make_snapshot(1, BASE_TIME, limitations=("coarse timestamp",))
    second = make_snapshot(
        2,
        BASE_TIME + MINIMUM_INTERVAL,
        limitations=("coarse timestamp",),
    )
    window = find_stability_window((first, second), MINIMUM_INTERVAL)

    assert window is not None
    assert isinstance(window.snapshot_ids, tuple)
    assert window.limitations == ("coarse timestamp",)
    with pytest.raises(FrozenInstanceError):
        window.elapsed = timedelta(seconds=10)  # type: ignore[misc]


def test_known_host_and_volume_are_compatible_when_unchanged() -> None:
    snapshots = (
        make_snapshot(1, BASE_TIME, source_host_id=HOST_ID, source_volume_id=VOLUME_ID),
        make_snapshot(
            2,
            BASE_TIME + MINIMUM_INTERVAL,
            source_host_id=HOST_ID,
            source_volume_id=VOLUME_ID,
        ),
    )

    assert find_stability_window(snapshots, MINIMUM_INTERVAL) is not None
