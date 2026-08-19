# Real transcription engine evaluation

## Status and authority boundary

**Green qualification complete on 2026-08-18. Scoped acceptance recorded for Demo 1
and the first real local transcription implementation.**

This evaluation measures local/offline candidates behind TranscriptionExecutionPort. It
did not itself add a runtime dependency, change deployment, create transcript/editorial
authority, or qualify real event media. Based on this evidence, faster-whisper 1.2.1,
CTranslate2 4.8.1, and the pinned large-v3-turbo converted model are accepted for Demo 1
and StageFlow's first real local transcription implementation. Broader production-provider
or model selection remains subject to representative accented/noisy event qualification.

Evidence applies to one Windows 11 host with an Intel Core i7-12800H, 32 GiB system
memory, and an NVIDIA GeForce RTX 3080 Ti Laptop GPU with 16 GiB VRAM and driver 581.57.
It is not a general hardware claim.

## Candidate comparison

| Candidate | Exact identity | License and capabilities | Windows/offline outcome |
| --- | --- | --- | --- |
| faster-whisper / CTranslate2 | [faster-whisper v1.2.1](https://github.com/SYSTRAN/faster-whisper/releases/tag/v1.2.1), CTranslate2 4.8.1, large-v3-turbo converted snapshot 0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf | Runtime is [MIT](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE); underlying [OpenAI turbo model is MIT](https://huggingface.co/openai/whisper-large-v3-turbo). Multilingual segment/word timing and language detection; no speaker identity. | PyAV bundles FFmpeg. Pinned model passed with HF_HUB_OFFLINE=1. Stock host failed on missing cublas64_12.dll; adding only the verified local CUDA DLL directory from the official whisper.cpp archive made it pass. **Accepted for Demo 1 and the first real local transcription implementation; broader selection remains conditional.** |
| whisper.cpp | [v1.9.2](https://github.com/ggml-org/whisper.cpp/releases/tag/v1.9.2), commit 306c88f4d1286aec1bf96e544632897886af5501, GGML model revision 5359861c739e955e79d9a303bcbc70fb988958b1 | Runtime is [MIT](https://github.com/ggml-org/whisper.cpp/blob/master/LICENSE); model is MIT. Multilingual segment timing. Documented word timing is [experimental](https://github.com/ggml-org/whisper.cpp#word-level-timestamp-experimental), so the adapter does not normalize it as word evidence. | Official Windows CPU and CUDA 12.4 archives loaded; CUDA detected compute capability 8.6. Pinned 16-bit WAV ran offline. **Viable, simpler packaged fallback with higher latency and no normalized word timing.** |
| OpenAI Whisper reference runtime | [v20250625](https://github.com/openai/whisper/releases/tag/v20250625), turbo | [MIT](https://github.com/openai/whisper/blob/main/LICENSE); multilingual segment timing. | Official setup documents Python 3.8-3.11 and requires [system FFmpeg](https://github.com/openai/whisper#setup). This host used Python 3.13 and lacked system FFmpeg. The same model was measured through two more deployable runtimes, so this heavyweight PyTorch reference was not separately run. |
| NVIDIA Parakeet TDT 0.6B v3 / NeMo Speech | [Parakeet](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3), [NeMo Speech v3.0.0](https://github.com/NVIDIA-NeMo/Speech/releases/tag/v3.0.0) | Model is CC BY 4.0; NeMo Speech is [Apache 2.0](https://github.com/NVIDIA-NeMo/Speech/blob/main/LICENSE). Twenty-five listed languages, word/segment/character timing, 16 kHz mono WAV/FLAC. | Official [installation](https://docs.nvidia.com/nemo/speech/nightly/starthere/install.html) centers on a much larger PyTorch/CUDA or Linux container stack. No native-Windows RTX path was qualified. Serious non-Whisper candidate, but it needs separate portable-runtime/host qualification. |
| Distil-Whisper large-v3 | [distil-large-v3](https://huggingface.co/distil-whisper/distil-large-v3), MIT | English-only; vendor card reports lower latency near large-v3 accuracy. | Compatible with faster-whisper, but not a multilingual first baseline. Retain as an English-only profile candidate. |
| WhisperX | [v3.8.6](https://github.com/m-bain/whisperX/releases/tag/v3.8.6), BSD-2-Clause | Adds wav2vec2 alignment and optional pyannote diarization. Downstream model terms vary. | Treat as a future separable alignment/diarization stage, not a base engine. It adds dependencies, cache/credential handling, and provider-inferred speaker semantics. |

## Deterministic corpus

No event recording, customer content, credential, raw provider payload, or private
transcript was used or committed. Windows System.Speech generated three external PCM WAV
fixtures, pinned by SHA-256 and reference text.

| Alias | Condition | Duration | SHA-256 |
| --- | --- | ---: | --- |
| conference-clean-david | Synthetic clean conference language | 18.716372 s | e9fa7c68550a07be68b213c0c8a645d6348758e2939886267c84cad987745a78 |
| web3-jargon-zira | Synthetic Web3 technical terms | 21.905261 s | 29335e68e6cb6dde00870a2eca36cfaf8d8a3e1a3695ab5ba517d70087c3cc6e |
| conference-long-david | Synthetic long-form operations briefing | 79.354195 s | 6ca4fa7db43b9d563d58da6b2d1b6fc5562b155b8a3b351ddb4978fa697b9518 |

This is intentionally easy synthetic English. It does not qualify accents, crosstalk,
room acoustics, crowd noise, real conference cadence, multilingual accuracy,
hallucination under silence, or multi-hour stability.

## Measured results

All runs used beam size 5 and the same full-precision large-v3-turbo model family. RTF is
elapsed wall time divided by audio duration; lower is better.

| Runtime and mode | Trials | Initialization | Aggregate RTF | Realtime | Timing meaning |
| --- | ---: | ---: | ---: | ---: | --- |
| faster-whisper 1.2.1 / CTranslate2 4.8.1 / CUDA float16 | 9 | 1.969 s model/adapter initialization | 0.0203 | 49.21x | First/warm inference with model loaded |
| whisper.cpp 1.9.2 / CUDA 12.4 / f16 | 9 | 0.981 s adapter inspection | 0.0647 | 15.46x | Every trial includes fresh subprocess/model load |
| whisper.cpp 1.9.2 / CPU / f16 | 6 | 0.032 s adapter inspection | 1.1570 | 0.86x | Every trial includes fresh subprocess/model load |

| Runtime | Item | Mean elapsed | RTF | Realtime | WER | CER | Word timings |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| faster-whisper CUDA | Clean | 0.482 s | 0.0257 | 38.84x | 0.0571 | 0 | 36 |
| faster-whisper CUDA | Web3 | 0.415 s | 0.0190 | 52.77x | 0.0526 | 0 | 39 |
| faster-whisper CUDA | Long | 1.541 s | 0.0194 | 51.50x | 0 | 0 | 184 |
| whisper.cpp CUDA | Clean | 2.149 s | 0.1148 | 8.71x | 0.0571 | 0 | 0 |
| whisper.cpp CUDA | Web3 | 2.184 s | 0.0997 | 10.03x | 0.0526 | 0 | 0 |
| whisper.cpp CUDA | Long | 3.426 s | 0.0432 | 23.16x | 0 | 0 | 0 |
| whisper.cpp CPU | Clean | 25.812 s | 1.3791 | 0.73x | 0.0571 | 0 | 0 |
| whisper.cpp CPU | Web3 | 28.121 s | 1.2837 | 0.78x | 0.0526 | 0 | 0 |
| whisper.cpp CPU | Long | 84.876 s | 1.0696 | 0.93x | 0 | 0 | 0 |

Nonzero WER with zero CER is a word-boundary effect on identical normalized character
streams, such as splitting a compound. It is not evidence of character substitutions.
Accuracy parity is expected because both runtimes use the same model family and must not
be generalized beyond this corpus.

nvidia-smi samples are host-aggregate before/after observations, not process peak memory.
Artifacts used:

- whisper.cpp GGML model: 1,624,555,275 bytes; SHA-256
  1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69;
- faster-whisper snapshot: 1,621,668,947 bytes across seven files;
- official whisper.cpp CUDA archive: 670,611,449 bytes; SHA-256
  443110ddaad70d4290ab2e77179e31cf712035bbc4fad56bb4519a90c917b39c.

## Real worker lifecycle qualification

The faster-whisper leader ran through PostgresWorkExecutionRepository and
TranscriptionWorker against only stageflow_worker_test:

- local-only claim, fenced running transition, and lease renewal succeeded;
- normalized asset-relative segment/word timing applied atomically;
- operation and attempt finalized succeeded;
- evidence revision 1 held 3 segments and 36 word timings at fence generation 1;
- no wall-clock, Session, package, or Editorial authority was inferred.

Before cleanup, every migration-0007 row was verified to belong to this run. Migration
0007 was reversed, the reused earlier-migration asset was verified present, and 0007 was
reapplied with all its tables empty. No other database or earlier-migration data was
deleted.

## Evidence artifact hashes

External JSON excludes media paths, reference text, raw provider payloads, credentials,
and DSNs.

| External sanitized artifact | SHA-256 |
| --- | --- |
| faster-whisper CUDA v2 | f9c25e6d8f99889a3c77eb25facf939d69df950899c1667aab6bb0035992f73a |
| whisper.cpp CUDA v2 | 6da3fba52b1e55e3d5990c7454f54a39efd381908e22d71df4673570510ef4c4 |
| whisper.cpp CPU v2 | 359575ee04ca591fbf2c8ed55f40febb14fdbb87637631baff98a95f57066b6d |
| faster-whisper PostgreSQL cycle | 23f04db26d7b3fb9a4a8400b541c18327fccc4d9a0e0ebbb7ee001d4eefc7a62 |

## Reproduction contract

Run from backend with explicit external manifest/model/cache paths and a new external
output. Direct execution requires PYTHONPATH set to the backend directory. Example:

    uv run python tests/qualification/transcription_benchmark.py --corpus-manifest <manifest> --engine whisper-cpp --model <model> --model-version <revision> --executable <whisper-cli> --device cuda --compute-type f16 --repetitions 3 --output <new-report>

For faster-whisper, use a disposable environment, pinned local snapshot, forced offline
mode after acquisition, and explicitly reviewed DLL path. Do not add evaluation packages
to StageFlow dependency manifests merely to reproduce this run.

## Scoped acceptance decision

The evaluation originally posed this Yellow architecture/operations question:

> Should StageFlow adopt faster-whisper 1.2.1 with CTranslate2 4.8.1 and the pinned
> large-v3-turbo converted model as its first production Windows RTX provider, subject
> to reviewed local CUDA/cuBLAS packaging and offline-cache design; adopt whisper.cpp
> 1.9.2 as the simpler officially packaged Windows fallback despite higher per-job
> latency and no normalized word timing; or defer until a realistic accented/noisy
> conference corpus and portable Parakeet runtime are qualified?

Decision recorded on 2026-08-18:

- Accept faster-whisper 1.2.1 with CTranslate2 4.8.1 and the pinned large-v3-turbo
  converted model for Demo 1 and StageFlow's first real local transcription
  implementation.
- Retain whisper.cpp as measured fallback evidence rather than the selected first
  implementation baseline.
- Keep broader production-provider and model selection conditional on representative
  accented/noisy event qualification; the synthetic corpus does not resolve that wider
  decision.

This scoped acceptance does not itself change dependencies or runtime configuration.
The implementation plan must explicitly cover dependency/lockfile changes, model
distribution and license notices, CUDA/cuBLAS packaging, cache integrity/offline preflight,
worker lifetime, resource limits, support ownership, and any later alignment/diarization
stage.
