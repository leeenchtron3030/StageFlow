# ADR-0029: NVENC hardware-accelerated rendering and the NVIDIA GPU worker requirement

## Status

Accepted

## Date

2026-08-28

## Context

Session Assembly and rendering are accepted future capabilities
([post-Kernel capability layer](../architecture/post-kernel-capability-layer.md)) with no
implementation yet: `RenderRequest` is documented as "a separate future Durable
Operation," and nothing in this repository currently decodes, concatenates, or encodes
video. This ADR does not authorize building that capability; it decides, ahead of time,
which encoder approach it will use once built, because that choice determines what
hardware every render-eligible worker must have.

Two motivating findings drove this decision:

1. **Packaging speed is an explicit product priority**, and analysis (transcription)
   already has real evidence that hardware acceleration on this project's target GPU
   class is dramatically faster than CPU-only processing (faster-whisper CUDA measured
   at real-time factor 0.0203 — roughly 49x real-time — against whisper.cpp CPU at
   1.1570, per the
   [transcription engine evaluation](../plans/transcription-engine-evaluation.md)).
2. **The bundled FFmpeg build already carries a confirmed GPL exposure.** The installed
   `av` (PyAV) 18.1.0 wheel that `faster-whisper` depends on bundles `libx264` and
   `libx265` as separate DLLs
   (`av.libs/libx264-165-....dll`, `av.libs/libx265-....dll`), directly inspected on
   2026-08-28. FFmpeg can only include those encoders when built with
   `--enable-gpl --enable-libx264 --enable-libx265`; there is no LGPL configuration that
   includes them. This confirms the "license review pending" finding in
   [the ED-0066 SBOM report](../security/dependency-license-sbom-2026-08-21.md) as an
   actual GPL-licensed FFmpeg build, not an unknown one. StageFlow itself is MIT-licensed
   (`LICENSE`); shipping this exact build inside a distributed StageFlow artifact would
   create a real GPL-compatibility obligation on that artifact. This decision does not
   resolve that exposure — it exists independently on the transcription decode path — but
   it deliberately avoids compounding it by adding a second, rendering-side dependency on
   `libx264`.

The user separately confirmed the accepted production topology this decision assumes:
vMix instances run independently at each Stage, record locally, and transfer completed
file blocks to a central NAS (a Minisforum N5 Air is the leaning choice, unconfirmed).
Independent worker machines — not co-located with vMix — pull blocks from the NAS and
perform processing. This removes CPU-contention-with-capture as a factor in the
encoder choice (a worker's CPU is otherwise idle between jobs) and instead makes
**throughput per worker across a horizontally scaled fleet** the operative question,
consistent with the existing durable Worker/Capability model
([ADR-0025](ADR-0025-postgresql-durable-operations-and-workers.md)), which already
scopes capability by provider/model/runtime and local/cloud class per worker.

## Decision

StageFlow's future rendering/Assembly capability will use NVIDIA NVENC hardware
encoding as its primary encode path, not software `libx264` encoding.

Consequently:

- Any worker capable of claiming a future render Durable Operation must have a
  compatible NVIDIA GPU. This becomes a required capability class for render-eligible
  workers, expressed the same way `WorkerCapability` already expresses provider/model/
  local-cloud eligibility in ADR-0025 — it is a capability-matching fact, not a new
  authority concept.
- Future worker-fleet scaling (adding capacity for transcription and/or rendering)
  requires NVIDIA-GPU-equipped machines. This is now an accepted deployment/procurement
  constraint, not an incidental fact about the current Razer/Wenceslas machine.
- `h264_nvenc`, `hevc_nvenc`, and `av1_nvenc` are already compiled into the exact PyAV/
  FFmpeg build currently installed for transcription (confirmed 2026-08-28 via
  `av.codecs_available`). No new dependency is required to reach a working NVENC path
  once a renderer is implemented; the encoder is already present, unused.
- This decision covers **encoding for rendered output only**. It does not decide,
  resolve, or defer the separate ED-0066 PyAV/FFmpeg GPL exposure on the transcription
  **decode** path, which still requires its own choice among the options already
  recorded there (own an LGPL-only build, accept the GPL build under counsel-reviewed
  compliance, or do not distribute the transcription group).
- Packaging-asset identity, Assembly templates/proposals/revisions, and the render
  Durable Operation itself remain unresolved/unimplemented. This ADR fixes the encoder
  choice for when that work is authorized; it does not authorize that work.

## Alternatives

### Software encoding via libx264

Rejected as the primary path. In the confirmed dedicated-worker topology, libx264 no
longer competes with vMix for CPU (the contention argument from earlier discussion does
not hold once capture and processing are separate machines), so it remains a reasonable
choice on pure quality-per-bit grounds. It loses on the now-operative axis: fleet
throughput. Matching NVENC's aggregate packages-per-hour across a worker pool would
require sizing meaningful extra CPU capacity into every worker on top of whatever CUDA
transcription already needs, where NVENC uses hardware every worker already carries for
transcription. It also keeps the GPL exposure open on a second, avoidable path. Not
rejected outright — remains available as a deliberate quality-over-throughput choice for
a specific output tier if that need arises later (e.g., an archival master distinct from
a fast review/delivery package), which would be its own bounded decision.

### Intel Quick Sync Video (QSV)

Rejected. `h264_qsv`/`hevc_qsv`/`av1_qsv` are also present in the installed build, but
Intel QSV requires Intel GPU hardware, and the transcription baseline already commits
worker hardware to NVIDIA CUDA. Standardizing render-eligible workers on the same GPU
vendor already required for transcription avoids maintaining two hardware-encode
qualification paths and two worker hardware SKUs in the fleet.

### Cloud transcoding/rendering service

Rejected as the primary path, consistent with ADR-0025's existing rejection of a
cloud-dependent job service for Event-critical work and its "cloud-required work
defaults to deferred unless the active versioned policy explicitly permits it" Event Mode
rule. A cloud render/transcode capability is not architecturally excluded — ADR-0025
already models a `local/cloud` class on `WorkerCapability` precisely so cloud-eligible
work can be classified and claimed after (or with lag tolerance from) the live capture
window. This ADR does not decide whether a cloud-class render worker is added later; it
decides that the default, event-adjacent rendering path is local NVENC, matching the
project's local-first principle.

## Consequences

### Positive

- A concrete, already-available hardware path exists for the fastest realistic render
  approach once Assembly/rendering is built; no new dependency or build work is needed to
  reach a working encoder.
- Fleet throughput scales by adding NVIDIA-GPU workers rather than by provisioning
  additional CPU capacity per worker.
- Avoids compounding the existing FFmpeg GPL exposure with a second use of `libx264`.
- Standardizes on one GPU vendor for both transcription and rendering capability
  qualification.

### Negative

- Every render-eligible worker now has a hard NVIDIA GPU dependency; this excludes
  CPU-only or non-NVIDIA (including Apple Silicon) machines from the render-worker pool.
  The Mac in the current two-machine Demo topology is explicitly a UI/control surface,
  not a processing worker, so this is consistent with current use but is now a stated
  constraint rather than an incidental fact.
- NVENC output is generally lower quality-per-bit than a well-tuned libx264 encode at
  matched bitrate. Accepted as a deliberate speed/quality tradeoff for a packaging
  pipeline whose stated priority is speed; not evaluated for any future archival-master
  or bandwidth-constrained delivery tier, which would need its own decision.
- The transcription-side PyAV/FFmpeg GPL exposure remains open. This ADR narrows where
  that exposure can spread but does not close it.
- No throughput, quality, or concurrent-session evidence exists yet. NVENC session-count
  limits on consumer NVIDIA cards were historically capped (~2-3 concurrent sessions) on
  older drivers; the qualified Razer driver (581.57) postdates NVIDIA's removal of that
  cap for most consumer cards, but this has not been independently reverified on this
  exact card/driver.
- NAS transfer time and network I/O between Stage machines, the NAS, and worker machines
  is a newly relevant bottleneck candidate this topology introduces. No data exists yet
  on NAS throughput, network topology, or block transfer time; this ADR does not estimate
  it.

## Validation

None yet. This ADR records an encoder-choice and hardware-requirement decision ahead of
implementation, consistent with this repository's ADR practice of governing future work
rather than proving it built. The `h264_nvenc`/`hevc_nvenc`/`av1_nvenc` availability
check and the `libx264`/`libx265` DLL inspection were run directly against the installed
backend `.venv` on 2026-08-28; no renderer, benchmark, or worker-capability code exists
to validate further. A future bounded rendering spike (concatenate real recorded blocks,
measure NVENC wall-clock time and quality against libx264, and measure behavior
concurrent with a live CUDA transcription job) is the recommended next evidence step and
is not authorized by this ADR alone.

## Related documents

- [Post-Kernel capability layer](../architecture/post-kernel-capability-layer.md) —
  Session Assembly and future `RenderRequest`.
- [ADR-0025](ADR-0025-postgresql-durable-operations-and-workers.md) — Worker/Capability
  model, local/cloud class, and Event Mode cloud-deferral policy this decision reuses.
- [Transcription engine evaluation](../plans/transcription-engine-evaluation.md) —
  CUDA/RTF evidence motivating hardware acceleration.
- [Dependency license and SBOM refresh — 2026-08-21](../security/dependency-license-sbom-2026-08-21.md)
  (ED-0066) — the still-open PyAV/FFmpeg GPL exposure this decision does not resolve.
- [Demo hardware rehearsal](../plans/demo-hardware-rehearsal.md) and
  [Demo 2 hardware rehearsal](../plans/demo2-hardware-rehearsal.md) (ED-0071) — the
  qualified Razer/Wenceslas GPU (RTX 3080 Ti Laptop, driver 581.57) this decision assumes
  as the reference worker hardware class.
- ADR index "Unresolved ADR candidates" — Packaging asset identity remains a separate
  required decision before Assembly, and therefore rendering, can be implemented.
