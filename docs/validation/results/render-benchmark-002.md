# Native FFmpeg render benchmark - Run 002

## Status and authority boundary

**MEASURED - The native FFmpeg pipeline encoded the same eleven-block corpus as ED-0073
8.49x faster than a same-run PyAV baseline. CUDA decode with frames kept on the GPU took
48.91 seconds for 657.39 seconds of source, about 13.4x real time, with very little
variation between repetitions. The ED-0073 throughput conclusion therefore described the
harness, not NVENC.**

This is the sanitized result for ED-0078 under
[ADR-0029](../../adr/ADR-0029-nvenc-rendering-and-gpu-worker-requirement.md) and the
[approved plan](../../plans/native-ffmpeg-render-benchmark.md). It follows
[Run 001](render-benchmark-001.md) (ED-0073). It is qualification evidence and
first-order input to render-fleet sizing. It is **not** a throughput guarantee, a hardware
qualification, a production renderer, a Worker Capability, or evidence of Event
readiness.

The run took place on 2026-09-25. No media, media path, filename, username, transcript
content, or FFmpeg log text is recorded here.

## Where each part ran

- The harness extension and its focused tests were implemented in a sandboxed workspace
  that had no GPU, FFmpeg, or corpus access. Those tests use a fake FFmpeg executable and
  mocked processes.
- **Every measurement arm below ran on the reference host, outside any sandbox,** with
  the real GPU, FFmpeg binary, corpus, and transcription runtime.

## Host, FFmpeg, and corpus

- The reference host from Run 001: Windows 11, AMD64, Python 3.13.15, NVIDIA GeForce
  RTX 3080 Ti Laptop GPU, driver 581.57.
- PyAV 18.1.0 with bundled libavcodec 62.28.102, used only for the PyAV baseline arm and
  for quality analysis.
- A standalone FFmpeg CLI, supplied to the harness by explicit path and recorded by
  identity only:
  - version `n8.1.2-50-g1a748fe2cd-20260831`;
  - SHA-256 `9c60da6c0b083110d59084ea39f60ae149aa3e031c3b4bb4f573fafa1c1e7cea`;
  - GPL configuration: **not enabled** (LGPL build, no libx264 or libx265).
- The corpus is the eleven Demo 2 live-run recording blocks from 2026-08-26:
  657.390691 seconds, 19,700 frames, 1920x1080, normalized to 29.97 fps as in Run 001. Its
  corpus fingerprint, `29fe9035d88690c7ee62d4d839ee4cb08c41f67fc37cd71e0fa00179c52a1599`,
  is **identical** to the fingerprint recorded in all three Run 001 reports. Both runs
  measured exactly the same input. A later, unrelated recording in the same source folder
  was excluded.

## Measurement settings

Every arm used the Run 001 NVENC settings: `h264_nvenc`, preset p4, VBR, 8,000,000 bit/s
target, GOP 60, yuv420p-equivalent output, MP4, video only. These are measurement
inputs, not accepted StageFlow output defaults.

| Arm | Pipeline |
| --- | --- |
| Native CPU decode | FFmpeg concat demuxer, software decode, NVENC encode |
| Native CUDA decode | FFmpeg concat demuxer, `-hwaccel cuda -hwaccel_output_format cuda`, frames kept on the GPU, NVENC encode. No GPU pixel conversion was needed. |
| PyAV baseline | Run 001's unchanged harness path: software decode, per-frame `reformat()`, Python frame iteration, NVENC encode |

The timer covers the whole FFmpeg process, or the whole PyAV encode for the baseline.
Quality analysis ran after each encode and outside the timed region.

`real_time_factor` has Run 001's meaning, **wall-clock seconds ÷ source seconds**, so
lower is faster. "Source speed" is its inverse: source seconds encoded per wall-clock
second.

## Results

### Native arms, three repetitions each

| Arm | Rep | Wall time | RTF | Source speed | Frames | Output bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Native CPU decode | 1 | 86.481 s | 0.131552 | 7.602x | 19,700 | 649,732,689 |
| Native CPU decode | 2 | 91.623 s | 0.139374 | 7.175x | 19,700 | 649,732,689 |
| Native CPU decode | 3 | 91.354 s | 0.138965 | 7.196x | 19,700 | 649,732,689 |
| Native CUDA decode | 1 | 48.969 s | 0.074490 | 13.425x | 19,700 | 649,732,689 |
| Native CUDA decode | 2 | 48.876 s | 0.074349 | 13.450x | 19,700 | 649,732,689 |
| Native CUDA decode | 3 | 48.885 s | 0.074363 | 13.448x | 19,700 | 649,732,689 |

All six repetitions succeeded. None failed, none were discarded, and the harness's CUDA
fallback guard did not trigger.

| Arm | Mean wall time | Population SD | Min-max | Mean RTF | Mean source speed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Native CPU decode | 89.820 s | 2.363 s | 86.481-91.623 s | 0.136631 | 7.324x |
| Native CUDA decode | 48.910 s | 0.042 s | 48.876-48.969 s | 0.074400 | 13.441x |

Keeping decode on the GPU made the pipeline **1.836x** faster than software decode. It
also removed almost all run-to-run variation. The CPU-decode arm's 5.1-second spread
suggests it is sensitive to CPU and host load. The CUDA-decode arm varied by less than
0.1 second.

### Comparison with PyAV

| Measurement | Wall time | RTF | Source speed | Output bytes |
| --- | ---: | ---: | ---: | ---: |
| Run 001 PyAV NVENC (2026-08-29) | 435.541 s | 0.662530 | 1.509x | 632,101,393 |
| Same-run PyAV NVENC baseline (1 run) | 415.162 s | 0.631529 | 1.583x | 632,101,393 |
| Native CPU decode (mean of 3) | 89.820 s | 0.136631 | 7.324x | 649,732,689 |
| Native CUDA decode (mean of 3) | 48.910 s | 0.074400 | 13.441x | 649,732,689 |

- The same-run PyAV baseline was 4.68% faster than Run 001. This is the environment drift
  between the two runs. Its output was **byte-identical** to Run 001's output, which
  confirms that the harness, corpus, and encoder behaved the same way.
- Against the same-run baseline, native CUDA decode was **8.488x** faster and native CPU
  decode was **4.622x** faster. Against Run 001, native CUDA decode was 8.905x faster.

### Quality

SSIM is the primary measure and PSNR is secondary. Both were computed over all 19,700
frames against the source blocks, using Run 001's measurement code.

| Output | Mean-frame SSIM | Mean-frame PSNR |
| --- | ---: | ---: |
| All native outputs | 0.997837794 | 50.497080 dB |
| Same-run PyAV baseline (and Run 001 NVENC) | 0.996887551 | 47.770912 dB |

- **All seven native outputs are byte-identical.** That covers the three CPU-decode
  repetitions, the three CUDA-decode repetitions, and the concurrent-arm encode. The
  decode path and the concurrent load did not change the encoded result, only the time it
  took. The per-output quality figures are therefore the same.
- The native outputs scored higher than the PyAV path, by 0.000950 SSIM and 2.726 dB
  PSNR. They were also 2.79% larger (about 7.91 versus 7.69 Mbit/s against the 8 Mbit/s
  target).
- **This run does not diagnose that difference.** The PyAV path adds per-frame
  `reformat()` and timestamp normalization, and either could plausibly account for it.
  The difference does not select an output tier, and no conclusion about native versus
  libx264 quality should be drawn across pipelines.

### NVENC concurrent with CUDA transcription

This arm ran the native CUDA-decode arm once while a real CUDA transcription job ran.
The transcription job used faster-whisper 1.2.1, the pinned large-v3-turbo model revision
`0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`, float16, beam size 5, no VAD, and no word
timestamps, over the same eleven blocks. As in Run 001, a warm-model transcription pass
ran first as the transcription baseline. The encode baseline is the native CUDA-decode
mean above.

| Measurement | Baseline | Concurrent | Change |
| --- | ---: | ---: | ---: |
| Native CUDA-decode NVENC encode | 48.910 s (mean of 3) | 50.385 s | +3.014% |
| CUDA transcription | 21.074 s | 22.000 s | +4.392% |

- The actual overlap was 21.999 seconds. It covered **43.66% of the encode** and 99.996%
  of the transcription. In Run 001 the overlap covered 5.08% of the encode.
- Both transcription passes processed all eleven blocks. Each produced 168 segments, the
  same sanitized count as Run 001. No transcript text was retained.
- The concurrent encode produced the same bytes as the standalone native arms, with no
  session-limit finding, failure, or fallback.
- The 1.47-second encode slowdown is about 35 times the CUDA arm's repetition SD, so it
  is a real effect, although a small one. The transcription change is a single paired
  sample with no measured variance.

Real concurrent use of NVENC and CUDA cost a few percent on each side in this window.
One run and one overlap window cannot establish sustained coexistence capacity.

## GPU telemetry (diagnostic only)

`nvidia-smi` sampled the GPU every 5 seconds throughout the run.

- **Temperature:** peaked at 58 °C during the native arms and 67 °C during the
  concurrency arm.
- **Clock-event reasons:** only "GPU idle" appeared during the native and PyAV arms. A
  software power cap appeared briefly during the concurrency arm, at a peak draw of about
  134 W. No hardware slowdown or thermal slowdown was reported.
- **Sampling limits:** 5-second sampling is too coarse to characterize utilization inside
  a 49-second encode. These samples do not establish thermal steady state.

## What this changes

- **The throughput conclusion changes.** Run 001 found that "the absolute encode speed
  did not validate the packaging-speed assumption." That finding described the
  Python/PyAV harness. With decode, scaling, and encode kept inside FFmpeg, about 11
  minutes of 1080p footage encoded in under a minute. That meets the sub-minute
  expectation Run 001's plan had anticipated and Run 001 could not show.
- **Keeping decode on the GPU matters.** GPU decode was about 1.8x faster than CPU decode
  and far more consistent. A future renderer should treat GPU-resident decode as the
  expected path, subject to its own plan.
- **First-order sizing arithmetic.** At the measured 13.44x source speed, one hour of
  1080p Session video would take about 4.5 minutes of video-only encode on this GPU.
  That figure assumes throughput holds for longer inputs, which this run did not measure.
  It is an arithmetic illustration for sizing discussions, not a measured or guaranteed
  duration.

## Limitations

- One machine, one laptop GPU, one driver, one corpus of about 11 minutes, and one
  encoder setting. Three repetitions per native arm show short-run variance only. They
  are not a throughput distribution or sustained-load measurement.
- The optional long-corpus arm was **not run**; no full-Session corpus was supplied.
- The concurrency arm and the PyAV baseline each ran once.
- **Not measured:**
  - multiple simultaneous encodes on one GPU, including NVENC session limits and how
    throughput scales per GPU. Fleet sizing needs this next;
  - audio encode and muxing;
  - assembly of multiple packaging assets, such as bumpers or title cards;
  - output-format and bitrate-ladder choices;
  - NAS or network transfer;
  - other GPU models.
- The CUDA fallback guard reads FFmpeg's log output. It catches a logged hwaccel setup
  failure. It cannot prove that every frame was decoded on the GPU if FFmpeg selects
  software decode without logging it. The identical output bytes and the stable 1.8x
  speed difference are consistent with GPU decode in this run.
- Quality analysis took about 500 seconds per output and ran between repetitions, so
  each repetition began after a CPU-heavy pause. That affects thermal starting
  conditions and is one reason these results are not steady-state figures.
- SSIM and PSNR differences do not select a product output tier or quality threshold.
  VMAF was not available.

## External sanitized artifact hashes

The reports stay outside the repository. Their hashes provide traceability.

| Artifact | SHA-256 |
| --- | --- |
| Native CPU-decode report | 0bf6a1c5063ce44b763d3d7cc7d5da6a8015b0406fff3b85720fdb74120df305 |
| Native CUDA-decode report | 9dacc471705079062e5e77092cb88e1275be686b86672f3c7f4955d4c903b679 |
| Native concurrent report | f575a27378d917b07675da989a54bd419bc86a232c36a09a808ea0f371c471fa |
| Same-run PyAV baseline report | 34356ddb46b5618e43e0e0b57660d2925ace08efdd85e9d5cc53d07461da9c4c |
