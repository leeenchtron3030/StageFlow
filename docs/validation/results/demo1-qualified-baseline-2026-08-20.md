# Demo 1 qualified fallback baseline - 2026-08-20

## Status and marker

**QUALIFIED FALLBACK - preserve unchanged while Demo 2 is evaluated.**

- Commit: `504b32567cf856082642697b6974859290c65020`
- Local annotated tag: `demo1-qualified-2026-08-20`
- PR #70 and migration 0009 are merged and qualified.
- Preserve Demo 1 databases, reports, Events, Sessions, media/evidence,
  model/runtime directories, secrets, and external configuration.
- The tag is local until authorized publication; nothing was pushed.

## Qualified runtime and topology

- faster-whisper 1.2.1; CTranslate2 4.8.1; converted `large-v3-turbo`
  revision `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`.
- Profile `faster-whisper-large-v3-turbo-cuda-float16` 1.0;
  NVIDIA CUDA/float16; no silent CPU fallback.
- Windows 11 Razer; RTX 3080 Ti Laptop GPU; 16 GiB VRAM; driver 581.57;
  32 GiB RAM. Process-scoped CUDA/cuBLAS; restored `PATH`; no global change;
  real silent-audio inference preflight passed.
- Razer runs modular FastAPI control plane, CUDA worker, and LAN Next.js UI.
  PostgreSQL `stageflow_demo` is authoritative; MacBook is Producer browser.
- Control plane/worker share PostgreSQL Operations, attempts, leases, capabilities,
  presence, and evidence. No broker/cloud service is required.
- Runtime profile `demo-single-stage`; external secret-free config; Devcon Event
  `test-devcon-8`, room `stage-1`; Expectations remain External.
- Qualified Razer-local/vMix recordings directory.

Private paths, DSNs, credentials, launch contexts, transcripts, and config values
are omitted. This is Demo 1 scope, not production/Event readiness.

## Devcon, Program, and manual workflow

Devcon GET and Program reconciliation passed. Current/Changed/Withdrawn and
realized-Session isolation passed live; Added/Restored and failed-snapshot
preservation passed deterministic tests. One separately authorized guarded PUT
returned HTTP 204 and exact Git persistence was verified. No further PUT is
authorized here.

1. `StageFlow-Demo.ps1 prepare` verifies DB/config/CUDA/bootstrap/Devcon GET.
2. `start`; open the Producer UI from the MacBook.
3. Select a Current Expectation and explicitly start the Session.
4. Let media stabilize; use `Process / Transcribe`.
5. The accepted cycle discovers, observes, stabilizes, registers, associates
   conservatively, and enqueues one durable transcription Operation.
6. CUDA worker creates provider-neutral Transcript Evidence.
7. Explicitly mark Moments and end Presentation.
8. Separately mark Package Ready and approve the exact revision when available.
9. Guarded publication is a third separately confirmed action.
10. Status/report/stop/restart use durable state, not browser memory.

Demo 1 demonstrated the real vertical slice and durable verification. Media and
Program refresh remain manual. A known projection may report the working worker as
`not_current`; that is observability only. Demo 1 remains fallback until Demo 2
passes a fresh two-machine dress rehearsal.
