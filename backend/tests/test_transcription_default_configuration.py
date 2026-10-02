import copy
import tomllib
from pathlib import Path
from typing import Any

import pytest

from app.core.config.deployment import (
    KernelDeploymentConfiguration,
    LocalTranscriptionConfiguration,
)

FFMPEG = str(Path(Path.cwd().anchor) / "synthetic" / "ffmpeg")


def deployment() -> dict[str, Any]:
    path = Path(__file__).parents[2] / "examples/demo-single-stage.toml.example"
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_ffmpeg_falls_back_to_segmentation_without_mutating_input() -> None:
    raw = deployment()
    raw["local_transcription"].pop("ffmpeg_path")
    raw["local_media_segmentation"] = {"ffmpeg_path": FFMPEG}
    original = copy.deepcopy(raw)
    config = KernelDeploymentConfiguration.model_validate(raw)
    assert config.local_transcription is not None
    assert config.local_transcription.ffmpeg_path == FFMPEG
    assert raw == original


def test_explicit_transcription_ffmpeg_takes_precedence() -> None:
    raw = deployment()
    raw["local_media_segmentation"] = {"ffmpeg_path": FFMPEG}
    config = KernelDeploymentConfiguration.model_validate(raw)
    assert config.local_transcription is not None
    assert config.local_transcription.ffmpeg_path == raw["local_transcription"]["ffmpeg_path"]


def test_missing_ffmpeg_is_a_closed_configuration_error() -> None:
    raw = deployment()
    raw["local_transcription"].pop("ffmpeg_path")
    raw.pop("local_media_segmentation", None)
    with pytest.raises(ValueError, match="local_transcription_ffmpeg_path_required"):
        KernelDeploymentConfiguration.model_validate(raw)
    with pytest.raises(ValueError, match="local_transcription_ffmpeg_path_required"):
        LocalTranscriptionConfiguration(model_path="/synthetic/model", model_version="synthetic")


@pytest.mark.parametrize("path", [None, "", "relative/ffmpeg", "/tools/ffmpeg.cmd"])
def test_invalid_explicit_path_is_never_silently_replaced(path: str | None) -> None:
    raw = deployment()
    raw["local_transcription"]["ffmpeg_path"] = path
    raw["local_media_segmentation"] = {"ffmpeg_path": FFMPEG}
    with pytest.raises(ValueError):
        KernelDeploymentConfiguration.model_validate(raw)
