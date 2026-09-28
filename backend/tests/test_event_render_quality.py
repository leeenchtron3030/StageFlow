import hashlib
import json
from dataclasses import FrozenInstanceError, replace

import pytest

from app.contexts.rendering.contracts import (
    CURRENT_RENDER_PROFILE,
    RENDER_PRESETS,
    RENDER_PROFILE_V1,
    RENDER_PROFILE_V2,
    RenderAdjustments,
    RenderError,
    RenderPreset,
    RenderProfile,
    effective_profile,
    normalize_adjustments,
    require_requestable,
)
from app.contexts.work_execution.application import render_work_key
from tests.test_render_work_execution import render_request


def test_catalog_exact_and_immutable() -> None:
    assert [(p.profile.id, p.profile.version, p.profile.width, p.profile.height,
             p.profile.bit_rate, p.video_min, p.video_max, p.video_step,
             p.profile.audio_bit_rate, p.audio_choices) for p in RENDER_PRESETS] == [
        ("h264-nvenc-1080p-video", "3", 1920, 1080, 8000000, 6000000, 12000000, 500000,
         192000, (128000, 160000, 192000, 256000)),
        ("h264-nvenc-1080p-high", "1", 1920, 1080, 14000000, 10000000, 20000000, 500000,
         256000, (192000, 256000, 320000)),
        ("h264-nvenc-720p", "1", 1280, 720, 4000000, 3000000, 6000000, 500000,
         128000, (96000, 128000, 160000, 192000)),
    ]
    with pytest.raises(FrozenInstanceError):
        RENDER_PRESETS[0].__setattr__("video_min", 1)
    with pytest.raises(FrozenInstanceError):
        RenderAdjustments().__setattr__("audio_bit_rate", 1)


@pytest.mark.parametrize("preset", RENDER_PRESETS)
def test_edges_defaults_and_effective_profile(preset: RenderPreset) -> None:
    assert normalize_adjustments(preset, RenderAdjustments(
        preset.profile.bit_rate, preset.profile.audio_bit_rate)) == RenderAdjustments()
    assert effective_profile(preset, RenderAdjustments()) == preset.profile
    for video in range(preset.video_min, preset.video_max + 1, preset.video_step):
        for audio in preset.audio_choices:
            profile = effective_profile(preset, RenderAdjustments(video, audio))
            require_requestable(profile)
            assert (profile.bit_rate, profile.audio_bit_rate) == (video, audio)
            assert replace(profile, bit_rate=preset.profile.bit_rate,
                           audio_bit_rate=preset.profile.audio_bit_rate) == preset.profile
    for video in (preset.video_min - 1, preset.video_min + 1, preset.video_max + 1):
        with pytest.raises(RenderError, match="render_adjustment_out_of_bounds"):
            effective_profile(preset, RenderAdjustments(video))
    with pytest.raises(RenderError, match="render_adjustment_out_of_bounds"):
        effective_profile(preset, RenderAdjustments(audio_bit_rate=123456))


@pytest.mark.parametrize("profile", [RENDER_PROFILE_V1, RENDER_PROFILE_V2,
    replace(CURRENT_RENDER_PROFILE, id="unknown"), replace(CURRENT_RENDER_PROFILE, width=1280)])
def test_only_catalog_fixed_properties_are_requestable(profile: RenderProfile) -> None:
    with pytest.raises(RenderError, match="render_profile_unsupported"):
        require_requestable(profile)


def test_unadjusted_work_key_is_byte_identical_and_only_adjustments_add_v2() -> None:
    request = render_request()
    request = replace(request, input=replace(request.input,
        execution_profile_id=CURRENT_RENDER_PROFILE.id, execution_profile_version="3"))
    document = {"schema": "stageflow.render_operation.work-key.v1",
        "assembly_revision_id": request.input.assembly_revision_id.value,
        "execution_profile_id": CURRENT_RENDER_PROFILE.id, "execution_profile_version": "3"}
    expected = hashlib.sha256(json.dumps(document, sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    assert render_work_key(request) == expected
    assert render_work_key(replace(request, input=replace(request.input,
        event_render_setting_version=4))) == expected
    adjusted = replace(request, input=replace(request.input, video_bit_rate=6_500_000))
    assert render_work_key(adjusted) != expected
    assert render_work_key(adjusted) == render_work_key(replace(adjusted,
        input=replace(adjusted.input, event_render_setting_version=99)))
    assert render_work_key(adjusted) != render_work_key(replace(adjusted,
        input=replace(adjusted.input, audio_bit_rate=128_000)))
