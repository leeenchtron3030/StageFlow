# Recorder calibration harness runbook

## Status

**Green qualification tooling implemented and self-checked.** The harness has not yet
recorded a controlled vMix trial. No recorder profile is qualified.

## Purpose and boundary

`backend/tests/qualification/calibration_harness.py` generates deterministic,
non-sensitive calibration media and analyzes recorded MP4 segments. It composes the
existing media-timing probe with an independently decodable content-frame clock.

The tool is qualification-only. It does not import production code, bundle FFmpeg,
control vMix, alter the workstation clock/timezone, or change Session, association,
package, Producer, Editorial, or AI authority.

## Calibration source

The source contains:

- a 24-bit binary frame counter at fixed top-left coordinates, with sync cells;
- 1/frame-rate source-time precision (33.333 ms at 30 fps);
- continuously changing test content behind the marker strip;
- green start and blue end slates;
- a visible once-per-second white band;
- a visible red band at the configured segmentation interval;
- 1 kHz once-per-second clicks;
- 1.7 kHz boundary tones; and
- distinct 500 Hz start and 750 Hz end tones.

The binary counter is intentionally machine-decodable after re-encoding. It gives each
recorded segment an External source-timeline start/end marker without relying on
container timestamps or filenames.

## Generate source media

Use an explicitly discovered local FFmpeg-compatible executable. Keep generated media
outside Git and choose new output paths; the tool refuses overwrite.

```powershell
cd backend
uv run python tests/qualification/calibration_harness.py generate `
  --ffmpeg '<local-ffmpeg>' `
  --output '<external-corpus>/source.mp4' `
  --manifest-output '<external-corpus>/source.json' `
  --source-alias vmix-calibration-profile-r1 `
  --timeline-origin-utc '2026-08-15T03:00:00Z' `
  --duration-seconds 190 `
  --boundary-seconds 60 `
  --frame-rate 30 `
  --width 1280 `
  --height 720
```

The source manifest's timeline origin is deterministic source metadata. It becomes an
absolute content-time reference only when an independent generator/playback log proves
the actual real-time relationship. Do not assume that file playback began at the
manifest timestamp.

## Controlled vMix trial requirements

Before each trial record a sanitized profile fingerprint:

- exact vMix version/build;
- output container, video/audio codecs, frame rate, sample rate, segmentation setting,
  encoder mode, and relevant recorder options;
- safe recorder-profile identity/revision and batch/trial/repetition identities;
- OS release/architecture and timezone needed for reproduction;
- local FFmpeg tool/version;
- external playback/generator clock source/status before and after the trial; and
- independently logged playback/source-frame-zero UTC and recorder start/stop actions.

Do not include source/output paths, filenames, customer content, account/user identity,
credentials, arbitrary vMix/FFmpeg logs, or raw provider diagnostics in committed
reports.

Run at least three repetitions per nominal condition:

| Condition ID | Procedure | Required evidence |
| --- | --- | --- |
| `normal_segmentation` | Approximately 60-second segmentation across at least three boundaries | Consecutive content markers, anchors, durations, finalization |
| `alternate_segmentation` | One other supported duration with an isolated saved profile | Same measurements and profile fingerprint |
| `stop_mid_segment` | Stop away from a boundary | Final partial file and explicit stop/content/finalization times |
| `recorder_restart` | Stop/start recording, preserving source timeline | New batch identity and whether anchors/sequence semantics reset |
| `multiple_recording_batch` | Independent normal recordings | Cross-batch anchor/error distribution |
| `near_boundary_stop` | Stop within five seconds of a split | Inclusion/exclusion and partial behavior |
| `long_run` | Ten or more segments | Drift, cadence residual, and repeatability |
| `input_discontinuity` | Interrupt input without host-clock change | Marker discontinuity and recorder behavior |

Process restart, host reboot, supported pressure, and fault trials remain separate
conditions. Clock-step/timezone mutation must run only in a disposable controlled
environment; never mutate the development workstation for qualification.

## Analyze a recorded batch

The supplied timeline origin must come from the independently verified playback/
generator log, not from the source file's metadata alone.

```powershell
cd backend
uv run python tests/qualification/calibration_harness.py analyze `
  --source '<external-batch-directory>' `
  --source-alias vmix-normal-r1 `
  --ffmpeg '<local-ffmpeg>' `
  --json-output '<external-results>/vmix-normal-r1.json' `
  --markdown-output '<external-results>/vmix-normal-r1.md' `
  --trial-id normal-r1 `
  --condition normal_segmentation `
  --batch-id batch-a `
  --repetition 1 `
  --recorder-product vMix `
  --recorder-version '<exact-version>' `
  --recorder-profile-id '<safe-profile-id>' `
  --recorder-profile-revision 1 `
  --segment-duration-seconds 60 `
  --frame-rate 30 `
  --timeline-origin-utc '<verified-frame-zero-utc>' `
  --clock-status verified_stable `
  --clock-source '<safe-clock-source>' `
  --configuration video=h264 `
  --configuration audio=aac `
  --configuration segmentation=60s `
  --vmix-exercised
```

For each segment the report preserves container/stream/packet/filesystem-proxy facts,
decoded first/last content markers, decoded-frame sequence quality, content precision,
candidate absolute content interval when supported, embedded-anchor/content-start delta,
and content gap/overlap against adjacent segments.

After collecting repeated reports for one exact profile revision, create sanitized
machine- and human-readable aggregate statistics:

```powershell
uv run python tests/qualification/calibration_harness.py summarize `
  --report '<external-results>/normal-r1.json' `
  --report '<external-results>/normal-r2.json' `
  --report '<external-results>/normal-r3.json' `
  --json-output '<external-results>/profile-summary.json' `
  --markdown-output '<external-results>/profile-summary.md'
```

The summarizer rejects mixed recorder-profile revisions so tolerance is never silently
generalized across configuration changes.

## Interpretation and quality gates

- `qualification_grade_trial: true` means the trial has vMix, a verified stable clock,
  an independent origin, and repeatable marker decoding. It does **not** qualify the
  recorder profile.
- Missing content markers, unverified clock, naive/missing anchor, changed configuration,
  or a clock step remains an explicit limitation/exclusion.
- Positive content adjacency is a gap; negative is overlap; zero is frame-contiguous
  within the recorded precision.
- Embedded-anchor error is `embedded creation_time - observed content start`.
- Candidate end error is `creation_time + container duration - observed content end`.
- Filesystem timestamps remain non-authoritative proxies.

The Yellow recorder package requires one exact profile/revision, at least three valid
repetitions per included condition, error distribution/tolerance, repeatability,
exclusions, untested conditions, expiry/requalification triggers, and explicitly allowed
advisory consumers. It never generalizes to all vMix or MP4 output.

## Current evidence

The [sanitized harness self-check](results/recorder-calibration-harness-self-check.md)
proves marker generation/decoding and report composition with FFmpeg fixtures. It does
not exercise vMix and cannot support a recorder semantic statement.
