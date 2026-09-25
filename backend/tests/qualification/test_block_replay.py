from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import BinaryIO

import pytest
from qualification import block_replay as replay


@pytest.fixture
def folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    # Synthetic external layout within pytest's sandbox; production uses the real root.
    repository = tmp_path / "repository"
    repository.mkdir()
    monkeypatch.setattr(replay, "REPOSITORY_ROOT", repository)
    source, watched = tmp_path / "source", tmp_path / "watched"
    source.mkdir()
    watched.mkdir()
    (source / "b.mp4").write_bytes(b"second synthetic block")
    (source / "a.mp4").write_bytes(b"first synthetic block")
    (source / "ignored.txt").write_bytes(b"not media")
    return source, watched


def test_order_cadence_atomic_visibility_and_source_preservation(
    folders: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, watched = folders
    before = {path.name: path.read_bytes() for path in source.iterdir()}
    sleeps: list[float] = []
    published: list[str] = []
    rename = Path.rename

    def checked_rename(path: Path, target: Path) -> Path:
        assert path.suffix == ".tmp"
        assert not target.exists()
        assert path.read_bytes() == before[target.name]
        published.append(target.name)
        return rename(path, target)

    monkeypatch.setattr(Path, "rename", checked_rename)
    assert replay.replay_blocks(
        source, watched, count=2, cadence_seconds=5,
        sleep=sleeps.append, monotonic=iter([0.0, 0.25]).__next__,
    ) == 2
    assert sleeps == [4.75]
    assert published == ["a.mp4", "b.mp4"]
    assert {path.name: path.read_bytes() for path in source.iterdir()} == before
    assert sorted(path.name for path in watched.iterdir()) == published


@pytest.mark.parametrize("count", [0, -1, 1001, True])
def test_count_is_bounded(folders: tuple[Path, Path], count: int) -> None:
    with pytest.raises(ValueError, match="count_out_of_bounds"):
        replay.replay_blocks(*folders, count=count, cadence_seconds=1)


@pytest.mark.parametrize("cadence", [0, -1, 3601, float("nan"), float("inf")])
def test_cadence_is_bounded(folders: tuple[Path, Path], cadence: float) -> None:
    with pytest.raises(ValueError, match="cadence_out_of_bounds"):
        replay.replay_blocks(*folders, count=1, cadence_seconds=cadence)


def test_total_duration_is_bounded(folders: tuple[Path, Path]) -> None:
    with pytest.raises(ValueError, match="cadence_out_of_bounds"):
        replay.replay_blocks(*folders, count=1000, cadence_seconds=3600)


@pytest.mark.parametrize("side", ["source", "watched"])
def test_repository_paths_are_refused(folders: tuple[Path, Path], side: str) -> None:
    source, watched = folders
    inside = replay.REPOSITORY_ROOT / "blocks"
    inside.mkdir()
    with pytest.raises(ValueError, match="outside_repository"):
        replay.replay_blocks(
            inside if side == "source" else source,
            inside if side == "watched" else watched,
            count=1, cadence_seconds=1,
        )
    assert list(watched.iterdir()) == []


def test_relative_and_overlapping_paths_are_refused(folders: tuple[Path, Path]) -> None:
    source, watched = folders
    with pytest.raises(ValueError, match="absolute"):
        replay.replay_blocks(Path("relative"), watched, count=1, cadence_seconds=1)
    for target in [source, source / "nested"]:
        target.mkdir(exist_ok=True)
        with pytest.raises(ValueError, match="must_not_overlap"):
            replay.replay_blocks(source, target, count=1, cadence_seconds=1)


def test_preflight_refuses_collision_and_insufficient_blocks(folders: tuple[Path, Path]) -> None:
    source, watched = folders
    with pytest.raises(ValueError, match="insufficient_blocks"):
        replay.replay_blocks(source, watched, count=3, cadence_seconds=1)
    (watched / "b.mp4").write_bytes(b"existing")
    with pytest.raises(FileExistsError, match="destination_exists"):
        replay.replay_blocks(source, watched, count=2, cadence_seconds=1)
    assert [path.name for path in watched.iterdir()] == ["b.mp4"]
    assert (watched / "b.mp4").read_bytes() == b"existing"


def test_partial_copy_is_never_published_and_owned_temps_are_cleaned(
    folders: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, watched = folders
    before = (source / "a.mp4").read_bytes()

    def fail_copy(input_file: BinaryIO, output: BinaryIO) -> None:
        output.write(input_file.read(3))
        assert not (watched / "a.mp4").exists()
        raise OSError("synthetic storage fault")

    monkeypatch.setattr(replay.shutil, "copyfileobj", fail_copy)
    with pytest.raises(OSError, match="storage fault"):
        replay.replay_blocks(source, watched, count=1, cadence_seconds=1)
    assert list(watched.iterdir()) == []
    assert (source / "a.mp4").read_bytes() == before


def test_existing_replay_lock_is_preserved(folders: tuple[Path, Path]) -> None:
    source, watched = folders
    lock = watched / ".stageflow-block-replay.lock"
    lock.write_bytes(b"another run")
    with pytest.raises(FileExistsError):
        replay.replay_blocks(source, watched, count=1, cadence_seconds=1)
    assert lock.read_bytes() == b"another run"
    assert len(list(watched.iterdir())) == 1


def test_linked_block_is_refused(
    folders: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Path.is_symlink
    def linked(path: Path) -> bool:
        return path.name == "a.mp4" or original(path)

    monkeypatch.setattr(Path, "is_symlink", linked)
    with pytest.raises(ValueError, match="source_link_forbidden"):
        replay.replay_blocks(*folders, count=1, cadence_seconds=1)


def test_helper_is_directly_executable() -> None:
    result = subprocess.run(
        [sys.executable, str(Path(replay.__file__)), "--help"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--cadence-seconds" in result.stdout
