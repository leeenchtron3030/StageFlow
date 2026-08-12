from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from qualification import media_timing_probe as probe

# Test assertions intentionally traverse JSON-like qualification payloads.
# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

HEADER_TEMPLATE = (
    """
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'PRIVATE_NAME.mp4':
  Metadata:
    major_brand     : mp42
    minor_version   : 0
    compatible_brands: mp41isom
    creation_time   : {creation_time}
  Duration: 00:01:00.020000, start: 0.000000, bitrate: 1234 kb/s
  Stream #0:0[0x1](und): Video: h264 (High), yuv420p, 1920x1080, 29.97 fps, 29.97 tbr, 29970 tbn
  Stream #0:1[0x2](und): Audio: aac (LC), 48000 Hz, stereo, fltp, 128 kb/s
demuxer -> ist_index:0 type:video pkt_pts:0 pkt_pts_time:0 pkt_dts:0 pkt_dts_time:0 """
    "duration:1000 duration_time:0.0333667\n"
    "demuxer -> ist_index:1 type:audio pkt_pts:0 pkt_pts_time:0 pkt_dts:0 "
    "pkt_dts_time:0 duration:1024 duration_time:0.0213333\n"
)

TAIL = (
    "demuxer -> ist_index:0 type:video pkt_pts:1799000 pkt_pts_time:60.0267 "
    "pkt_dts:1798000 pkt_dts_time:59.9933 duration:1000 duration_time:0.0333667\n"
    "demuxer -> ist_index:1 type:audio pkt_pts:2879488 pkt_pts_time:59.9893 "
    "pkt_dts:2879488 pkt_dts_time:59.9893 duration:1024 duration_time:0.0213333\n"
)


def test_parser_separates_raw_packet_timing_from_derived_interval() -> None:
    raw = probe.parse_ffmpeg_observations(
        HEADER_TEMPLATE.format(creation_time="2026-08-12T00:51:01.000000Z"), TAIL
    )

    assert raw["epistemic_kind"] == "observed"
    assert raw["container"]["format"] == "mov,mp4,m4a,3gp,3g2,mj2"
    assert raw["container"]["duration_seconds"] == pytest.approx(60.02)
    assert raw["streams"][0]["time_base_hz"] == 29970
    assert raw["streams"][1]["sample_rate_hz"] == 48000
    assert raw["packet_timing"]["first_by_stream"][0]["pts_seconds"] == 0
    assert raw["packet_timing"]["last_by_stream"][1]["pts_seconds"] == pytest.approx(
        59.9893
    )

    candidate = probe.derive_candidate_interval(raw)
    assert candidate is not None
    assert candidate["epistemic_kind"] == "derived"
    assert candidate["status"] == "unqualified_candidate"
    assert candidate["start_at"] == "2026-08-12T00:51:01+00:00"
    assert candidate["end_at"] == "2026-08-12T00:52:01.020000+00:00"
    assert candidate["authority_use_prohibited"] is True


@pytest.mark.parametrize("creation_time", ["2026-08-12T00:51:01", "not-a-time"])
def test_naive_or_invalid_creation_time_is_preserved_but_not_derived(
    creation_time: str,
) -> None:
    raw = probe.parse_ffmpeg_observations(
        HEADER_TEMPLATE.format(creation_time=creation_time), TAIL
    )

    assert raw["container"]["tags"]["creation_time"] == creation_time
    assert probe.derive_candidate_interval(raw) is None


def test_report_is_bounded_sanitized_and_marks_residual_as_arithmetic_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "private-corpus"
    source.mkdir()
    first = source / "customer-private-001.mp4"
    second = source / "customer-private-002.mp4"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    creation_times = {
        first: "2026-08-12T00:51:01Z",
        second: "2026-08-12T00:52:01Z",
    }

    monkeypatch.setattr(
        probe,
        "inspect_tool",
        lambda executable: {"name": "ffmpeg6.exe", "version": "6.0"},  # noqa: ARG005
    )

    def fake_run(executable: str, media: Path, *, tail: bool = False) -> str:
        del executable
        return TAIL if tail else HEADER_TEMPLATE.format(creation_time=creation_times[media])

    monkeypatch.setattr(probe, "run_ffmpeg", fake_run)

    report = probe.build_report(
        source,
        source_alias="vmix-calibration-a",
        executable="C:/private/tool/ffmpeg6.exe",
        observed_at=datetime(2026, 8, 12, tzinfo=UTC),
    )
    serialized = json.dumps(report)

    assert report["source"] == {"alias": "vmix-calibration-a", "media_count": 2}
    assert report["authority_use_prohibited"] is True
    assert report["production_semantics_changed"] is False
    assert [item["media_ref"] for item in report["media"]] == [
        "media-00000",
        "media-00001",
    ]
    assert report["adjacent_candidate_residuals"] == [
        {
            "from_media_ref": "media-00000",
            "to_media_ref": "media-00001",
            "epistemic_kind": "derived",
            "arithmetic_residual_seconds": pytest.approx(-0.02),
            "interpretation": "not_a_content_gap_or_overlap_measurement",
            "authority_use_prohibited": True,
        }
    ]
    assert str(tmp_path) not in serialized
    assert "customer-private" not in serialized
    assert "C:/private/tool" not in serialized


def test_discovery_rejects_excess_media_and_symlink_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "corpus"
    source.mkdir()
    (source / "a.mp4").write_bytes(b"a")
    (source / "b.mp4").write_bytes(b"b")

    with pytest.raises(probe.ProbeError, match="max-files"):
        probe.discover_media(source, ".mp4", 1)

    link = source / "a.mp4"
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path == link or original_is_symlink(path),
    )
    with pytest.raises(probe.ProbeError, match="symbolic-link"):
        probe.discover_media(link, ".mp4", 1)


def test_report_writes_are_atomic_and_refuse_overwrite(tmp_path: Path) -> None:
    report = {
        "source": {"alias": "safe", "media_count": 0},
        "inspection_tool": {"name": "ffmpeg", "version": "6.0"},
        "media": [],
    }
    json_output = tmp_path / "report.json"
    markdown_output = tmp_path / "report.md"

    probe.write_reports(report, json_output, markdown_output)

    assert json.loads(json_output.read_text(encoding="utf-8"))["source"]["alias"] == "safe"
    assert "Authority use: **prohibited**" in markdown_output.read_text(encoding="utf-8")
    with pytest.raises(probe.ProbeError, match="already exists"):
        probe.write_reports(report, json_output, markdown_output)


def test_probe_is_directly_executable_for_help() -> None:
    script = Path(probe.__file__).resolve()

    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0
    assert "qualification only" in completed.stdout
    assert "--source-alias" in completed.stdout
