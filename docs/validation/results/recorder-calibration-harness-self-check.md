# Recorder calibration harness self-check

## Result

**PASS for qualification-tool readiness; NOT RUN for vMix recorder qualification.**

The local self-check ran on 2026-08-14/15 using non-sensitive synthetic media. It proves
that the harness can generate, segment, decode, and report deterministic content timing.
It does not establish vMix `creation_time` semantics, production recorder suitability,
or Event readiness.

## Sanitized environment and provenance

| Fact | Observed value |
| --- | --- |
| Installed vMix product | `29.0.0.48` |
| vMix exercised | No; the GUI/recorder was not started or reconfigured |
| Qualification tool | `stageflow-recorder-calibration-harness` `1.0` |
| Local generator/inspection tool | vMix-bundled `ffmpeg6.exe`, FFmpeg `6.0` |
| OS facts retained in JSON | Windows, release 11, AMD64, Pacific Daylight Time |
| Source | 190.0 s, 1280x720, 30 fps, H.264/AAC synthetic calibration content |
| Marker precision | 0.0333333333333333 s |
| Clock status | `synthetic_fixture`; not an independent real-time clock check |
| Recorder profile status | Candidate-only / unqualified |

No private paths, filenames, user identity, credentials, source content, or arbitrary
tool diagnostics are retained in the committed artifacts.

## Source result

- 5,700 of 5,700 expected content frames decoded.
- Frame indices were exactly `0` through `5699`.
- Duplicate, missing, reversed, and invalid-marker counts were all zero.
- The synthetic source's explicit `creation_time` matched its fixed manifest origin with
  a measured delta of `0.0 s`.
- This zero delta validates harness arithmetic only because FFmpeg wrote both fixture
  values; it says nothing about vMix.

Machine-readable evidence:
[source manifest](recorder-calibration-harness-source.json) and
[source result](recorder-calibration-harness-source-result.json).

## Approximately 60-second segmentation fixture

FFmpeg copy segmentation produced four files from the 190-second source. This simulates
consecutive and partial-file analysis, not vMix recorder behavior.

| Media ref | Container duration (s) | Decoded content interval (s) | Frames | Sequence |
| --- | ---: | --- | ---: | --- |
| `media-00000` | 61.02 | `[0.0, 61.0)` | 1,830 | Repeatable |
| `media-00001` | 60.00 | `[61.0, 121.0)` | 1,800 | Repeatable |
| `media-00002` | 60.00 | `[121.0, 181.0)` | 1,800 | Repeatable |
| `media-00003` | 9.00 | `[181.0, 190.0)` | 270 | Repeatable partial |

Every adjacent content residual was `0 frames / 0.0 s`. Segment outputs did not retain
an embedded `creation_time`, so anchor-error samples are correctly absent rather than
invented. The first 61-second split is fixture muxer/keyframe behavior and demonstrates
why configured duration is not assumed to equal observed content duration.

Machine-readable evidence:
[60-second result](recorder-calibration-harness-60s-result.json).

## Alternate 30-second segmentation fixture

The same source produced seven files: one 31-second initial file, five 30-second files,
and one 9-second partial file. All 5,700 source frames decoded exactly once in continuous
order, every segment sequence was repeatable, and all six adjacency residuals were
`0 frames / 0.0 s`.

Machine-readable evidence:
[30-second result](recorder-calibration-harness-30s-result.json).

## Defect found and corrected

The real FFmpeg 6 run exposed two qualification-tool defects that mocked fixtures had
not covered:

1. packet identifiers may use `input:stream` form such as `0:1`, while the original
   probe parsed only a single integer; and
2. marker decoding needed passthrough frame timing to avoid FFmpeg inserting a duplicate
   frame at a segment edit boundary.

Both corrections now have focused/static validation. Marker encoding also rounds the
frame-time expression to avoid floating-point boundary duplicate/gap pairs.

## Coverage and limitations

| Requested condition | Current evidence |
| --- | --- |
| Normal segmentation | Harness/FFmpeg fixture PASS; vMix NOT RUN |
| Alternate segmentation | Harness/FFmpeg fixture PASS; vMix NOT RUN |
| Stop mid-segment | Final partial-file analysis PASS in fixture; vMix NOT RUN |
| Recorder restart | Representable by trial/batch identity; vMix NOT RUN |
| Multiple recording batches | Representable and aggregatable by profile/batch; vMix NOT RUN |
| Embedded anchor semantics | Fixture arithmetic PASS; vMix evidence absent |
| Repeatability | Source/segment marker decoding repeatable; no vMix repetitions |
| Clock/timezone mutation | Not performed; disposable environment required |

No recorder-profile qualification candidate is ready. The only supportable conclusion is:

> The qualification harness measures content boundaries and timing deltas at one-frame
> precision for its tested synthetic FFmpeg fixtures. vMix 29.0.0.48 recorder semantics
> remain untested and unqualified.

## Required next evidence

Run the isolated vMix matrix from the
[recorder calibration harness runbook](../recorder-calibration-harness.md), with three
valid repetitions per included condition and independent stable-clock/playback-origin
evidence. Only then calculate a profile-scoped tolerance and prepare Yellow recorder
acceptance.
