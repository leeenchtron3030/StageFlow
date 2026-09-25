# Multi-encode render benchmark - Run 003

## Status and authority boundary

**MEASURED - Running 1 to 4 native CUDA-decode → NVENC encodes at the same time on the
reference GPU did not increase total throughput. Aggregate speed stayed at about 13.6×
real time at every level, because a single encode already saturates the GPU's video
encoder (NVENC averaged 99.6% utilization). Extra simultaneous encodes share that
capacity equally. No session was refused up to N = 4, and every output was
byte-identical to the single-encode reference.**

This is the sanitized result for ED-0085 under
[ADR-0029](../../adr/ADR-0029-nvenc-rendering-and-gpu-worker-requirement.md) and the
[approved plan](../../plans/multi-encode-render-benchmark.md). It follows
[Run 002](render-benchmark-002.md) (ED-0078). It is first-order input for render-fleet
sizing on one laptop GPU. It is **not** a throughput guarantee, a hardware qualification,
production render code, or evidence of Event readiness.

The run took place on 2026-09-25. No media, media path, filename, username, or FFmpeg log
text is recorded here.

## Where each part ran

- The `native-parallel` harness arm and its focused tests were implemented in a sandboxed
  workspace with no GPU, FFmpeg, or corpus.
- An independent review first returned FIX-FIRST, because the reference output could be
  discarded. After the fix it approved.
- **The measurement ran on the reference host, outside any sandbox.**

## Host, FFmpeg, and corpus

- The reference host from Runs 001 and 002: NVIDIA GeForce RTX 3080 Ti Laptop GPU,
  driver 581.57, Windows 11.
- FFmpeg `n8.1.2-50-g1a748fe2cd-20260831`, LGPL (GPL configuration not enabled). It was
  identified by version and SHA-256 as in Run 002, and never by path.
- The same eleven-block corpus as Runs 001 and 002: fingerprint `29fe9035…`, 657.39
  seconds, 19,700 frames, 1920x1080.
- Settings as in Run 002: `h264_nvenc`, preset p4, VBR at 8,000,000 bit/s, GOP 60,
  video-only MP4, and CUDA decode with frames kept on the GPU.

## Method

For each N in {1, 2, 3, 4}, the arm ran two repetitions. In each repetition, N FFmpeg
processes encoded the full corpus at the same time, released together by one barrier.

- **Aggregate window:** from the first process start to the last process end.
- **Aggregate speed:** (N × 657.39 s) ÷ aggregate wall.
- **Scaling efficiency:** aggregate speed ÷ (N × the mean N = 1 speed), within the same
  run.
- **Output check:** each output's SHA-256 was compared with the N = 1 reference output.
  SSIM would have run only on a mismatch, and none occurred.
- **Cleanup:** verified non-reference outputs were deleted after hashing; the reference
  output was kept.

## Results

| N | Rep | Aggregate wall | Per-encode wall (range) | Aggregate speed | Scaling efficiency |
| ---: | ---: | ---: | --- | ---: | ---: |
| 1 | 1 | 48.892 s | 48.89 s | 13.446× | 1.000 |
| 1 | 2 | 48.901 s | 48.90 s | 13.443× | 1.000 |
| 2 | 1 | 96.534 s | 96.26-96.53 s | 13.620× | 0.507 |
| 2 | 2 | 96.642 s | 96.48-96.64 s | 13.605× | 0.506 |
| 3 | 1 | 144.695 s | 144.18-144.69 s | 13.630× | 0.338 |
| 3 | 2 | 144.776 s | 144.28-144.78 s | 13.622× | 0.338 |
| 4 | 1 | 192.874 s | 192.42-192.87 s | 13.634× | 0.254 |
| 4 | 2 | 192.819 s | 192.07-192.82 s | 13.637× | 0.254 |

| N | Mean aggregate wall (population SD) | Mean aggregate speed (population SD) |
| ---: | ---: | ---: |
| 1 | 48.896 s (0.004) | 13.445× (0.001) |
| 2 | 96.588 s (0.054) | 13.612× (0.008) |
| 3 | 144.735 s (0.040) | 13.626× (0.004) |
| 4 | 192.846 s (0.027) | 13.636× (0.002) |

- **All succeeded.** All 20 encodes succeeded, each with all 19,700 frames. No encode was
  refused, failed, or retried, and the CUDA fallback guard never triggered.
- **Throughput is flat.** Aggregate speed rose only 1.4% from N = 1 to N = 4 (13.445× to
  13.636×). Aggregate wall grew almost exactly linearly with N (48.9, 96.6, 144.7, 192.8
  s), and every simultaneous encode took about N times as long as a single one.
  Efficiency ≈ 1/N is the signature of one shared, saturated resource.
- **The N = 1 speed reproduces Run 002.** Run 002 recorded 48.910 s and 13.441×; this
  run recorded 48.896 s and 13.445×.

### Output identity

All 19 non-reference outputs were byte-identical to the N = 1 reference. The reference
output's SHA-256 begins `a2de2745d0205882`, the same value observed for the Run 002
native outputs. Concurrency therefore did not change the encoded result, and the Run 002
quality figures (SSIM 0.997837794, PSNR 50.497080 dB) apply to every output here.

## GPU telemetry (diagnostic, 2 s sampling)

Over 480 busy samples:

| Measure | Value |
| --- | --- |
| Video encoder (NVENC) utilization | mean 99.6%, minimum 84% |
| Video decoder (NVDEC) utilization | mean 93.7% |
| General GPU utilization | mean 4.3% |
| Graphics / video clocks | steady at about 1,905 / 1,665 MHz |
| Power | 63-90 W |
| Temperature | peak 66 °C |

The video encoder was saturated at every N, including N = 1. That explains the flat
throughput. The decoder ran close to its limit as well.

A hardware-slowdown clock-event flag (`0x48`, which includes thermal slowdown) appeared in
2 of 489 samples during the N = 3 window. The graphics and video clocks did not drop in
those samples, and the N = 3 timings varied by only 0.04 s. It had no measurable effect,
but it is recorded.

## What this changes

- **Capacity is a per-GPU total, not a per-lease figure.** On this GPU one encode already
  uses the whole video encoder. A render worker can run several render leases at once
  without losing throughput and without refusals up to 4, but it gains nothing from
  doing so. Every concurrent render finishes later in proportion to how many share the
  GPU.
- **Sizing input.** Plan render capacity as about 13.4-13.6 seconds of 1080p source
  encoded per wall-clock second **per GPU**, however many simultaneous jobs there are.
  One hour of Session video is therefore about 4.5 minutes of GPU encode time on this
  GPU, whether it is rendered alone or alongside others. This is an arithmetic
  illustration for this GPU; it was not measured beyond the 11-minute corpus.
- **Implication for the render Durable Operation.** One render lease per GPU gives the
  lowest per-render latency with the same total throughput. More leases per GPU only
  make sense for fairness, for example so a short job is not queued behind a long one.
  That is a scheduling decision for the render plan, not something this benchmark
  settles.

## Limitations

- One laptop GPU model and driver, one corpus, one encoder setting, and two repetitions
  per level. GPUs with more than one NVENC engine, such as some workstation and desktop
  parts, may scale differently. Nothing here measures them.
- N was probed only up to 4. The session limit on this GPU and driver was not reached,
  so its value is unknown.
- Video only. There is no audio, muxing of multiple packaging assets, or transfer.
- The flat-throughput conclusion applies to this CUDA-decode → NVENC pipeline. A pipeline
  bound by CPU or GPU compute could behave differently.
- The session or resource refusal classification (`nvenc_session_unavailable`) was never
  triggered, so it is untested on real hardware.

## External sanitized artifact hashes

| Artifact | SHA-256 |
| --- | --- |
| `native-parallel` report | 8198c5f5835384a236e8cc55ca8a19e1689cdca53e52b656b06f19cdc7eba020 |
| Reference output (retained outside the repository) | a2de2745d0205882a2c382fcde8440f75de1b0126d0ec0cb12ee8e904f34f138 |
