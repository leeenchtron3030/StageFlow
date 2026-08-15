from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from qualification import calibration_harness as harness

# Assertions intentionally traverse JSON-like qualification reports.
# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false


def _marker_payload(indices: list[int], spec: harness.MarkerSpec) -> bytes:
    frames = bytearray()
    for index in indices:
        bits: list[int] = list(harness.SYNC_PATTERN)
        bits.extend((index >> bit) & 1 for bit in range(spec.counter_bits))
        frames.extend(255 if bit else 0 for bit in bits)
    return bytes(frames)


def _base_report(media_count: int = 2) -> dict[str, object]:
    media: list[dict[str, object]] = []
    for index in range(media_count):
        start = datetime(2026, 8, 14, 20, 0, index * 2, tzinfo=UTC)
        media.append(
            {
                "media_ref": f"media-{index:05d}",
                "raw_observations": {
                    "media_inspection": {
                        "container": {
                            "tags": {"creation_time": start.isoformat()},
                            "duration_seconds": 2.0,
                        }
                    },
                    "filesystem_proxy": {"authority": "non_authoritative_filesystem_proxy"},
                },
                "derived_candidate_interval": {
                    "start_at": start.isoformat(),
                    "end_at": datetime.fromtimestamp(
                        start.timestamp() + 2, tz=UTC
                    ).isoformat(),
                },
            }
        )
    return {
        "observed_at": "2026-08-14T20:00:00+00:00",
        "source": {"alias": "safe-corpus", "media_count": media_count},
        "inspection_tool": {"name": "ffmpeg6.exe", "version": "6.0"},
        "media": media,
    }


def _trial(*, vmix_exercised: bool = True) -> harness.TrialContext:
    return harness.TrialContext(
        trial_id="normal-r1",
        condition="normal_segmentation",
        batch_id="batch-a",
        repetition=1,
        recorder_product="vMix",
        recorder_version="29.0.0.48",
        recorder_profile_id="vmix-mp4-h264-aac-60s",
        recorder_profile_revision=1,
        segment_duration_seconds=2.0,
        vmix_exercised=vmix_exercised,
        clock_status="verified_stable",
        clock_source="controlled_external_log",
        timeline_origin_utc=datetime(2026, 8, 14, 20, 0, tzinfo=UTC),
        configuration=("video=h264", "audio=aac"),
    )


def test_generation_command_contains_visible_audio_and_binary_markers(tmp_path: Path) -> None:
    spec = harness.MarkerSpec(frame_rate=30)

    command = harness.build_generation_command(
        "ffmpeg6.exe",
        tmp_path / "source.mp4",
        spec=spec,
        duration_seconds=185,
        boundary_seconds=60,
        width=1280,
        height=720,
        timeline_origin_utc=datetime(2026, 8, 14, 20, 0, tzinfo=UTC),
    )
    joined = " ".join(command)

    assert "testsrc2=size=1280x720:rate=30:duration=185" in joined
    assert harness.MARKER_SCHEMA == "binary-frame-clock-v1"
    assert "drawbox" in joined
    assert "mod(t\\,1)" in joined
    assert "1000" in joined
    assert "1700" in joined
    assert "500" in joined
    assert "750" in joined
    assert "creation_time=2026-08-14T20:00:00+00:00" in joined
    assert "-n" in command


def test_marker_decode_preserves_boundaries_and_reports_sequence_defects() -> None:
    spec = harness.MarkerSpec(frame_rate=10, counter_bits=8)

    result = harness.decode_marker_payload(_marker_payload([10, 11, 11, 14, 13], spec), spec)

    assert result["first_content_offset_seconds"] == pytest.approx(1.0)
    assert result["content_end_exclusive_offset_seconds"] == pytest.approx(1.4)
    assert result["duplicate_transition_count"] == 1
    assert result["missing_source_frame_count"] == 2
    assert result["reverse_transition_count"] == 1
    assert result["sequence_repeatable"] is False


def test_marker_decode_rejects_invalid_or_unsynchronized_payload() -> None:
    spec = harness.MarkerSpec(frame_rate=30, counter_bits=8)

    with pytest.raises(harness.CalibrationError, match="invalid size"):
        harness.decode_marker_payload(b"abc", spec)
    with pytest.raises(harness.CalibrationError, match="no valid"):
        harness.decode_marker_payload(bytes(spec.marker_cells), spec)


def test_report_combines_raw_marker_facts_with_derived_absolute_timing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "private-a.mp4"
    second = tmp_path / "private-b.mp4"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    spec = harness.MarkerSpec(frame_rate=10, counter_bits=8)
    payloads = {
        first: _marker_payload(list(range(0, 20)), spec),
        second: _marker_payload(list(range(20, 40)), spec),
    }
    monkeypatch.setattr(
        harness.timing_probe,
        "build_report",
        lambda *args, **kwargs: _base_report(),  # noqa: ARG005
    )
    monkeypatch.setattr(
        harness,
        "run_marker_decode",
        lambda executable, media, marker_spec: payloads[media],  # noqa: ARG005
    )

    report = harness.build_calibration_report(
        tmp_path,
        source_alias="safe-corpus",
        executable="C:/private/ffmpeg6.exe",
        spec=spec,
        trial=_trial(),
        observed_at=datetime(2026, 8, 14, 20, 0, tzinfo=UTC),
    )
    serialized = json.dumps(report)

    assert report["qualification_status"] == "unqualified_candidate_evidence"
    assert report["qualification_grade_trial"] is True
    assert report["media"][0]["raw_observations"]["content_markers"][
        "epistemic_kind"
    ] == "observed"
    assert report["media"][0]["derived_content_timing"][
        "embedded_anchor_minus_content_start_seconds"
    ] == pytest.approx(0)
    assert report["content_adjacency_residuals"][0][
        "gap_positive_overlap_negative_seconds"
    ] == pytest.approx(0)
    assert report["trial_statistics"]["all_marker_sequences_repeatable"] is True
    assert str(tmp_path) not in serialized
    assert "private-a" not in serialized
    assert "C:/private" not in serialized


def test_report_without_external_origin_keeps_absolute_claim_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media = tmp_path / "segment.mp4"
    media.write_bytes(b"x")
    spec = harness.MarkerSpec(frame_rate=10, counter_bits=8)
    monkeypatch.setattr(
        harness.timing_probe,
        "build_report",
        lambda *args, **kwargs: _base_report(media_count=1),  # noqa: ARG005
    )
    monkeypatch.setattr(
        harness,
        "run_marker_decode",
        lambda *args, **kwargs: _marker_payload([0, 1], spec),
    )
    trial = _trial(vmix_exercised=False)
    trial = harness.TrialContext(
        trial_id=trial.trial_id,
        condition=trial.condition,
        batch_id=trial.batch_id,
        repetition=trial.repetition,
        recorder_product=trial.recorder_product,
        recorder_version=trial.recorder_version,
        recorder_profile_id=trial.recorder_profile_id,
        recorder_profile_revision=trial.recorder_profile_revision,
        segment_duration_seconds=trial.segment_duration_seconds,
        vmix_exercised=False,
        clock_status="not_verified",
        clock_source="not_recorded",
        timeline_origin_utc=None,
        configuration=trial.configuration,
    )

    report = harness.build_calibration_report(
        tmp_path,
        source_alias="safe",
        executable="ffmpeg",
        spec=spec,
        trial=trial,
    )
    derived = report["media"][0]["derived_content_timing"]

    assert "candidate_content_started_at" not in derived
    assert "embedded_anchor_minus_content_start_seconds" not in derived
    assert "no independently verified playback origin" in derived["limitations"][0]
    assert report["qualification_grade_trial"] is False


def test_summary_preserves_one_profile_and_calculates_repeatability_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media = tmp_path / "segment.mp4"
    media.write_bytes(b"x")
    spec = harness.MarkerSpec(frame_rate=10, counter_bits=8)
    monkeypatch.setattr(
        harness.timing_probe,
        "build_report",
        lambda *args, **kwargs: _base_report(media_count=1),  # noqa: ARG005
    )
    monkeypatch.setattr(
        harness,
        "run_marker_decode",
        lambda *args, **kwargs: _marker_payload(list(range(20)), spec),
    )
    report = harness.build_calibration_report(
        tmp_path,
        source_alias="safe",
        executable="ffmpeg",
        spec=spec,
        trial=_trial(),
    )

    summary = harness.summarize_reports([report, report])

    assert summary["trial_count"] == 2
    assert summary["qualification_grade_trial_count"] == 2
    assert summary["condition_counts"] == {"normal_segmentation": 2}
    assert summary["maximum_absolute_anchor_error_seconds"] == pytest.approx(0)
    assert summary["qualification_status"] == "candidate_only_unqualified"

    conflicting = json.loads(json.dumps(report))
    conflicting["recorder"]["profile_revision"] = 2
    with pytest.raises(harness.CalibrationError, match="one recorder profile"):
        harness.summarize_reports([report, conflicting])


def test_summary_load_and_write_are_bounded_and_sanitized(tmp_path: Path) -> None:
    report = {
        "schema_name": harness.REPORT_SCHEMA,
        "recorder": {"profile_id": "profile-a", "profile_revision": 1},
        "trial": {"condition": "normal_segmentation"},
        "qualification_grade_trial": False,
        "media": [],
        "content_adjacency_residuals": [],
    }
    input_path = tmp_path / "private-report-name.json"
    input_path.write_text(json.dumps(report), encoding="utf-8")

    summary = harness.summarize_reports(harness.load_reports([input_path]))
    json_output = tmp_path / "summary.json"
    markdown_output = tmp_path / "summary.md"
    harness.write_summary(summary, json_output, markdown_output)

    serialized = json_output.read_text(encoding="utf-8")
    assert "private-report-name" not in serialized
    assert summary["condition_counts"] == {"normal_segmentation": 1}
    assert "candidate evidence only" in markdown_output.read_text(encoding="utf-8")
    with pytest.raises(harness.CalibrationError, match="already exists"):
        harness.write_summary(summary, json_output, markdown_output)


def test_generate_source_records_provenance_and_removes_media_if_manifest_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "source.mp4"
    manifest = tmp_path / "source.json"
    monkeypatch.setattr(
        harness.timing_probe,
        "inspect_tool",
        lambda executable: {"name": "ffmpeg6.exe", "version": "6.0"},  # noqa: ARG005
    )

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        del kwargs
        Path(command[-1]).write_bytes(b"synthetic")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(harness.subprocess, "run", fake_run)

    result = harness.generate_source(
        "C:/private/ffmpeg6.exe",
        output,
        manifest,
        source_alias="calibration-a",
        spec=harness.MarkerSpec(frame_rate=30),
        duration_seconds=5,
        boundary_seconds=2,
        width=640,
        height=360,
        timeline_origin_utc=datetime(2026, 8, 14, 20, 0, tzinfo=UTC),
    )

    assert output.read_bytes() == b"synthetic"
    assert result["inspection_tool"] == {"name": "ffmpeg6.exe", "version": "6.0"}
    serialized = manifest.read_text(encoding="utf-8")
    assert "C:/private" not in serialized
    assert "generated source does not exercise vMix" in serialized


def test_report_write_is_atomic_and_refuses_overwrite(tmp_path: Path) -> None:
    report = {
        "trial": {
            "trial_id": "trial",
            "condition": "condition",
            "repetition": 1,
            "vmix_exercised": False,
            "clock_status": "not_verified",
        },
        "recorder": {
            "product": "fixture",
            "version": "1",
            "profile_id": "fixture",
            "profile_revision": 1,
        },
        "trial_statistics": {"all_marker_sequences_repeatable": True},
        "media": [],
    }
    json_output = tmp_path / "report.json"
    markdown_output = tmp_path / "report.md"

    harness.write_report(report, json_output, markdown_output)

    assert json.loads(json_output.read_text(encoding="utf-8"))["trial"]["trial_id"] == "trial"
    assert "candidate evidence only" in markdown_output.read_text(encoding="utf-8")
    with pytest.raises(harness.CalibrationError, match="already exists"):
        harness.write_report(report, json_output, markdown_output)


def test_harness_is_directly_executable_for_help() -> None:
    script = Path(harness.__file__).resolve()

    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0
    assert "recorder calibration" in completed.stdout
    assert "generate" in completed.stdout
    assert "analyze" in completed.stdout
