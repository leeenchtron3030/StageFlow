from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.shared.ids import EntityId

from .asset_readiness_validation import normalize_limitations, require_aware
from .asset_resource_snapshot import AssetResourceSnapshot


@dataclass(frozen=True, slots=True)
class AssetStabilityWindow:
    candidate_id: EntityId
    resource_id: EntityId
    first_snapshot_id: EntityId
    last_snapshot_id: EntityId
    started_at: datetime
    ended_at: datetime
    elapsed: timedelta
    stable_size_bytes: int
    stable_filesystem_modified_at: datetime | None
    stable_resource_identity_token: str | None
    snapshot_ids: Sequence[EntityId]
    limitations: Sequence[str] = ()

    def __post_init__(self) -> None:
        require_aware(self.started_at, "AssetStabilityWindow.started_at")
        require_aware(self.ended_at, "AssetStabilityWindow.ended_at")
        snapshot_ids = tuple(self.snapshot_ids)
        if len(snapshot_ids) < 2:
            raise ValueError("Asset stability window requires at least two snapshots.")
        if len({snapshot_id.value for snapshot_id in snapshot_ids}) != len(snapshot_ids):
            raise ValueError("Asset stability window snapshot IDs must be unique.")
        if self.ended_at < self.started_at:
            raise ValueError("Asset stability window end must not precede start.")
        if self.elapsed != self.ended_at - self.started_at:
            raise ValueError("Asset stability elapsed duration must match its timestamps.")
        if self.elapsed <= timedelta(0):
            raise ValueError("Asset stability window must span positive elapsed time.")
        if self.stable_size_bytes < 0:
            raise ValueError("Asset stability window size must not be negative.")
        if snapshot_ids[0] != self.first_snapshot_id:
            raise ValueError("First snapshot identity must match ordered snapshot IDs.")
        if snapshot_ids[-1] != self.last_snapshot_id:
            raise ValueError("Last snapshot identity must match ordered snapshot IDs.")
        object.__setattr__(self, "snapshot_ids", snapshot_ids)
        object.__setattr__(
            self,
            "limitations",
            normalize_limitations(self.limitations, "AssetStabilityWindow.limitations"),
        )


def find_stability_window(
    snapshots: Sequence[AssetResourceSnapshot],
    minimum_interval: timedelta,
) -> AssetStabilityWindow | None:
    if minimum_interval <= timedelta(0):
        raise ValueError("Minimum stability interval must be positive.")
    ordered = tuple(sorted(snapshots, key=lambda item: (item.observed_at, item.id.value)))
    if len(ordered) < 2:
        return None
    runs: list[list[AssetResourceSnapshot]] = []
    current: list[AssetResourceSnapshot] = []
    for snapshot in ordered:
        if current and not _snapshots_compatible(current[-1], snapshot):
            runs.append(current)
            current = []
        current.append(snapshot)
    if current:
        runs.append(current)
    windows = [
        _window_from_run(run)
        for run in runs
        if len(run) >= 2 and run[-1].observed_at - run[0].observed_at >= minimum_interval
    ]
    if not windows:
        return None
    return max(
        windows,
        key=lambda window: (
            window.ended_at,
            window.elapsed,
            window.started_at,
            tuple(snapshot_id.value for snapshot_id in window.snapshot_ids),
        ),
    )


def _snapshots_compatible(
    first: AssetResourceSnapshot,
    second: AssetResourceSnapshot,
) -> bool:
    if first.candidate_id != second.candidate_id or first.resource_id != second.resource_id:
        return False
    if first.size_bytes != second.size_bytes:
        return False
    if (
        first.filesystem_modified_at is not None
        and second.filesystem_modified_at is not None
        and first.filesystem_modified_at != second.filesystem_modified_at
    ):
        return False
    if (
        first.stable_resource_identity_token is not None
        and second.stable_resource_identity_token is not None
        and first.stable_resource_identity_token
        != second.stable_resource_identity_token
    ):
        return False
    if (
        first.source_volume_id is not None
        and second.source_volume_id is not None
        and first.source_volume_id != second.source_volume_id
    ):
        return False
    return not (
        first.source_host_id is not None
        and second.source_host_id is not None
        and first.source_host_id != second.source_host_id
    )


def _window_from_run(run: Sequence[AssetResourceSnapshot]) -> AssetStabilityWindow:
    first = run[0]
    last = run[-1]
    filesystem_times = {
        snapshot.filesystem_modified_at
        for snapshot in run
        if snapshot.filesystem_modified_at is not None
    }
    identity_tokens = {
        snapshot.stable_resource_identity_token
        for snapshot in run
        if snapshot.stable_resource_identity_token is not None
    }
    limitations = {
        limitation for snapshot in run for limitation in snapshot.limitations
    }
    if any(snapshot.filesystem_modified_at is None for snapshot in run):
        limitations.add("filesystem modification timestamp unavailable")
    if any(snapshot.stable_resource_identity_token is None for snapshot in run):
        limitations.add("source identity token unavailable")
    return AssetStabilityWindow(
        candidate_id=first.candidate_id,
        resource_id=first.resource_id,
        first_snapshot_id=first.id,
        last_snapshot_id=last.id,
        started_at=first.observed_at,
        ended_at=last.observed_at,
        elapsed=last.observed_at - first.observed_at,
        stable_size_bytes=first.size_bytes,
        stable_filesystem_modified_at=(
            next(iter(filesystem_times)) if len(filesystem_times) == 1 else None
        ),
        stable_resource_identity_token=(
            next(iter(identity_tokens)) if len(identity_tokens) == 1 else None
        ),
        snapshot_ids=tuple(snapshot.id for snapshot in run),
        limitations=tuple(limitations),
    )
