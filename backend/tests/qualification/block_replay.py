"""Bounded offline block replay for qualification; never a production media source."""

from __future__ import annotations

import argparse
import math
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BLOCK_SUFFIXES = frozenset({".mov", ".mp4", ".mkv", ".mxf", ".wav"})
MAXIMUM_BLOCKS = 1000
MAXIMUM_ENTRIES = 10_000


def _external_directory(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError("replay_path_must_be_absolute")
    resolved = path.resolve(strict=True)
    repository = REPOSITORY_ROOT.resolve()
    if resolved.is_relative_to(repository) or repository.is_relative_to(resolved):
        raise ValueError("replay_path_must_be_outside_repository")
    if not resolved.is_dir():
        raise ValueError("replay_path_must_be_directory")
    return resolved


def replay_blocks(
    source: Path,
    watched: Path,
    *,
    count: int,
    cadence_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> int:
    """Copy the first count media files by name; publish only fully copied blocks.

    Both folders must already exist outside the repository and must not overlap.
    Existing destinations are refused, never overwritten. A per-folder exclusive lock
    excludes simultaneous runs of this helper. Only this run's temp/lock files are removed.
    """
    if type(count) is not int or not 1 <= count <= MAXIMUM_BLOCKS:
        raise ValueError("replay_count_out_of_bounds")
    if (
        not math.isfinite(cadence_seconds)
        or not 0.1 <= cadence_seconds <= 3600
        or (count - 1) * cadence_seconds > 86_400
    ):
        raise ValueError("replay_cadence_out_of_bounds")
    source = _external_directory(source)
    watched = _external_directory(watched)
    if source.is_relative_to(watched) or watched.is_relative_to(source):
        raise ValueError("replay_directories_must_not_overlap")
    blocks: list[Path] = []
    for index, entry in enumerate(source.iterdir()):
        if index >= MAXIMUM_ENTRIES:
            raise ValueError("replay_source_entry_limit")
        if entry.suffix.lower() not in BLOCK_SUFFIXES:
            continue
        if entry.is_symlink() or entry.is_junction():
            raise ValueError("replay_source_link_forbidden")
        if entry.is_file():
            blocks.append(entry)
    blocks.sort(key=lambda path: path.name)
    if len(blocks) < count:
        raise ValueError("replay_insufficient_blocks")
    blocks = blocks[:count]
    lock_path = watched / ".stageflow-block-replay.lock"
    # Exclusive creation fails without touching another run's lock.
    with lock_path.open("xb"):
        pass
    try:
        for block in blocks:
            if (watched / block.name).exists() or (watched / block.name).is_symlink():
                raise FileExistsError("replay_destination_exists")
        deadline = monotonic()
        for index, block in enumerate(blocks):
            if index:
                sleep(max(0.0, deadline - monotonic()))
            # Recheck links immediately before reading; source files are read-only.
            if block.is_symlink() or block.is_junction():
                raise ValueError("replay_source_link_forbidden")
            temporary: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=watched, prefix=".stageflow-replay-", suffix=".tmp", delete=False,
                ) as output:
                    temporary = Path(output.name)
                    with block.open("rb") as input_file:
                        shutil.copyfileobj(input_file, output)
                destination = watched / block.name
                if destination.exists() or destination.is_symlink():
                    raise FileExistsError("replay_destination_exists")
                temporary.rename(destination)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            deadline += cadence_seconds
    finally:
        lock_path.unlink()
    return len(blocks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded offline qualification block replay")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--watched", type=Path, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--cadence-seconds", type=float, required=True)
    arguments = parser.parse_args()
    copied = replay_blocks(
        arguments.source, arguments.watched,
        count=arguments.count, cadence_seconds=arguments.cadence_seconds,
    )
    print(f"Replayed {copied} blocks.")


if __name__ == "__main__":
    main()
