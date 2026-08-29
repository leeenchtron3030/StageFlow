# NVENC render benchmark - Run 001

## Status and authority boundary

**MEASURED - NVENC was faster than libx264 in this bounded end-to-end harness, but
neither encoder met the plan's anticipated sub-minute duration. One narrow
NVENC-plus-CUDA-transcription overlap run showed no degradation beyond ordinary
single-run variation.**

This is the sanitized result for ED-0073 under
[ADR-0029](../../adr/ADR-0029-nvenc-rendering-and-gpu-worker-requirement.md) and the
[approved benchmark plan](../../plans/nvenc-render-benchmark-spike.md). It is
qualification evidence only. It does not implement or qualify production rendering,
Session Assembly, a RenderRequest, Worker Capability matching, output-product settings,
or Event readiness.

The run occurred on 2026-08-29. No media, media path, filename, transcript content,
credential, or raw provider output is recorded here.

## Host and corpus

- Windows 11, AMD64, Python 3.13.15.
- NVIDIA GeForce RTX 3080 Ti Laptop GPU, 16 GiB VRAM, driver 581.57.
- PyAV 18.1.0 with bundled libavcodec 62.28.102.
- One Demo 2 rehearsal corpus: 11 already-closed MP4 recording blocks,
  657.390691 seconds (10 minutes 57.391 seconds), 5,881,711,898 source bytes,
  19,700 decoded video frames, 1920x1080.
- Ten blocks reported an average rate of 29.97 fps. One reported approximately
  29.9367 fps. All used the same 1/29970 stream time base. The harness normalized
  output timing to the first block's 29.97 fps and recorded the observed rate range.
- The source recording blocks themselves were the quality reference.

This is one real corpus on one machine. It is not a throughput guarantee or general
hardware qualification.

## Measurement settings

Both standalone arms used MP4, H.264, yuv420p, an 8,000,000 bit/s target, GOP 60, and
the same ordered source frames:

| Arm | Encoder settings |
| --- | --- |
| NVENC | h264_nvenc, preset p4, VBR |
| Software | libx264, preset medium |

The benchmark output was video-only. Audio encode cost and bytes were excluded. These
are measurement inputs, not accepted StageFlow output defaults.

SSIM is the primary quality measure and PSNR is secondary. Both were calculated over
all 19,700 decoded frames against the source blocks. The installed build did not provide
libvmaf, so VMAF was not measured.

## Standalone encoder results

| Encoder | Encode wall time | RTF | Source speed | Output bytes | Mean-frame SSIM | Mean-frame PSNR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| h264_nvenc | 435.540964 s | 0.662530 | 1.509366x | 632,101,393 | 0.996887551 | 47.770912 dB |
| libx264 | 616.446733 s | 0.937717 | 1.066419x | 654,975,207 | 0.997581141 | 48.962269 dB |

In this harness, NVENC was 1.415359x as fast as libx264, reducing encode wall time by
29.3465%. Its output was 3.4923% smaller at the matched target bitrate. Its mean-frame
SSIM was 0.000693590 lower and its mean-frame PSNR was 1.191356 dB lower.

The measured encode timer includes source decode, frame normalization, Python/PyAV
frame iteration, encoder submission, and MP4 muxing. It is an end-to-end measurement of
this qualification harness, not a pure hardware-encoder microbenchmark. The absolute
duration therefore must not be generalized to a future native production render path.

## Concurrent CUDA transcription result

The concurrency command used faster-whisper 1.2.1, CTranslate2 4.8.1, the pinned
large-v3-turbo converted model revision
0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf, CUDA, float16, beam size 5, no VAD, and
no word timestamps. The model and CUDA runtime were loaded from explicit local
directories. No network acquisition or fallback occurred.

The command first measured a warm-model transcription baseline over all 11 blocks. It
then started a second real transcription pass and NVENC encode together behind one
barrier.

| Measurement | Baseline | Concurrent | Change |
| --- | ---: | ---: | ---: |
| NVENC encode wall time | 435.540964 s | 436.052645 s | +0.1288% |
| CUDA transcription wall time | 24.081776 s | 22.166632 s | -7.9527% |

- Actual overlap was 22.166541 seconds.
- The overlap covered 5.0829% of the encode and 99.9996% of the transcription.
- Both transcription passes processed all 11 blocks and produced the same sanitized
  segment count (168). No transcript text was retained.
- Concurrent NVENC produced 632,101,393 bytes, identical to the standalone NVENC arm.
- NVENC remained available; no session-limit finding and no software fallback occurred.

One negative transcription delta is ordinary single-run variation, not evidence that
contention improves transcription. This run observed no material degradation in either
operation, but the short 22.167-second overlap is too narrow to establish general
coexistence capacity.

## Plan-assumption reconciliation

The approved plan anticipated that approximately 11 minutes of footage would encode in
under one minute and therefore finish below laptop thermal steady state. That
anticipation did not hold for this harness: NVENC took 7 minutes 15.541 seconds and
libx264 took 10 minutes 16.447 seconds. These results must not be described as
sub-minute encodes.

The plan also anticipated approximately 13 seconds for CUDA transcription. The measured
warm-model runs were 24.082 and 22.167 seconds. Transcription was still much shorter than
encoding, so the intended contention window remained narrow.

The three raw external reports were created with pre-run limitation labels derived from
the approved plan's sub-minute anticipation. Their measured values contradict those
labels. This committed result treats the measurements as authoritative evidence,
explicitly rejects the sub-minute description, and the harness now emits
duration-neutral limitation labels for future runs. The artifact hashes below preserve
traceability to the original run records rather than silently rewriting them.

These are finite single runs without repeated trials or thermal instrumentation. They
do not establish sustained-load or thermal steady-state throughput even though their
encode times exceeded the plan's estimate. A longer corpus and repeated trials remain
better evidence for sustained capacity.

## Quality-analysis overhead

Full-frame SSIM and PSNR were diagnostic passes after encoding and were excluded from
encode wall time. The first NVENC run processed the two metrics sequentially and took
1,005.334 seconds. After that bounded harness correction, the independent filters ran
concurrently for libx264 and took 504.374 seconds. The quality values use the same
filters, definitions, and complete frame set; analysis wall times are not comparable
benchmark outcomes.

The concurrency arm did not repeat quality analysis because it measured degradation and
overlap; quality was already measured for both standalone encoder outputs.

## Limitations and outcome

- One corpus, machine, driver, encoder setting, and run per arm cannot establish
  throughput distributions, session-count capacity, or hardware qualification.
- The harness is Python/PyAV orchestration and includes software decode/reformat costs.
- Video-only output understates a future package's audio cost and size.
- Average-rate normalization was required for one recorder block.
- No VMAF, GPU-utilization time series, energy, temperature, or thermal-throttling
  telemetry was captured.
- No NAS transfer was measured.
- SSIM and PSNR differences do not select a product output tier or quality threshold.
- The original raw-report limitation labels included the disproved pre-run duration
  anticipation; the measured fields and this reviewed result provide the corrected
  interpretation.

Within those bounds, the run supplies StageFlow's first real rendering evidence:
NVENC was available and faster than libx264 with slightly lower measured quality, and
one short overlap with real CUDA transcription showed no material contention. The
absolute encode speed did not validate the packaging-speed assumption and warrants
further renderer-path investigation before any production capability claim.

## External sanitized artifact hashes

| Artifact | SHA-256 |
| --- | --- |
| NVENC report | 06955a8dc7970f0bebcb7cc6e552940033eb81dbccd7e92908272ab9322d2c97 |
| libx264 report | 2e90807d0b09c0ebd62f16f3626f738f7de52c71034e1edd31667cf753d43c39 |
| Concurrent report | 213d03fae858485a75b400a449c6a6443eca884074dd28a468cc86040328672b |
