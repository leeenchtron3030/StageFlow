# ADR-0037: Owner-operated GPU appliance as the deployment baseline

## Status

Accepted (owner, 2026-09-30).

## Date

2026-09-30

## Context

- **Where StageFlow runs.** StageFlow sits at the tail of a live production's signal
  flow. It analyses recordings as they appear in small blocks, then helps assemble and
  package media. Speed is a primary goal throughout.
- **Existing constraints:**
  - Event mode must work without continuous Internet connectivity.
  - ADR-0029 already requires NVIDIA GPUs for render-capable workers, and for fleet
    growth for transcription and rendering.
- **Owner direction (2026-09-30):**
  - StageFlow is **operated by the owner and their team**, tailored per event, and is not
    handed to clients. "White-label" means event identity comes from configuration
    (ADR-0031), not resale.
  - The owner intends a **small custom hardware appliance**: purpose-built, with
    optimized GPUs and processing hardware, deployed as a hardware and software bundle.
- **Current gaps:**
  - Validation so far runs on one development machine.
  - No document states what StageFlow's software may assume about the machine it runs
    on.
  - Performance work, the GPU budget and offline provisioning have had no stable target.

## Decision

1. **The production baseline is an owner-operated StageFlow appliance.**
   - One node, or a small set of nodes, operated by the owner's team at the event. It
     runs the modular monolith, PostgreSQL, and the workers: timing, segmentation,
     transcription and render.
   - This is a deployment baseline, not a change of architecture. The modular monolith,
     PostgreSQL as the operational store (ADR-0022) and Durable Operations (ADR-0025) are
     unchanged, and no broker or microservices are introduced.
2. **Software may assume the following on the appliance:**
   - at least one NVIDIA GPU with NVENC and CUDA, with a pinned, qualified driver and
     runtime;
   - a pinned, LGPL FFmpeg binary at an explicit path (ADR-0027, ADR-0033 and ADR-0036);
   - pre-provisioned, checksum-verified model weights (ADR-0036);
   - local storage for watched source folders, derived media and packages, sized per
     Event;
   - the Event network is local; the Internet is optional and deferrable.
3. **GPU work is budgeted, not incidental.**
   - Transcription, NVENC rendering and any GPU-accelerated segmentation are declared
     worker capabilities (ADR-0025 and ADR-0029).
   - Their concurrency is configured per appliance profile so that the live chain has
     priority: block to evidence to suggestion. Renders take the remaining GPU capacity.
   - The exact scheduling rule is a later plan, driven by measurement.
4. **Appliance profiles are versioned configuration.** They record hardware class,
   concurrency, model and binary versions, and are recorded in qualification evidence.
   Qualification results name the profile they ran on.
5. **Out of scope for this ADR:**
   - the physical hardware design (form factor, specific GPUs, cooling, enclosure);
   - multi-appliance clustering;
   - remote fleet management.
   - Each needs its own decision when it is pursued.

## Alternatives

- **Commodity machines chosen per event (the status quo).** Flexible, but the targets for
  performance, drivers and GPU contention move with every event, and qualification can't
  be reused. Not selected.
- **A cloud or hybrid deployment.** It conflicts with Event-mode offline operation and the
  latency goal at the tail of the signal flow. Not selected; the Internet stays optional.
- **Client-installed software.** This contradicts the owner's operating model, and it
  would reopen the distribution and licensing questions (ADR-0036). Not selected.

## Consequences

- **Performance targets gain a fixed reference.** Latency budgets can be stated per
  appliance profile: seconds from a block closing to a suggestion, per stage of the
  chain.
- **Driver, CUDA, model and FFmpeg versions are pinned per profile.** Upgrades are
  qualified changes.
- **The development machine is recorded as a provisional profile** until real appliance
  hardware exists. Results on it are labelled as such.
- **Setup and provisioning become first-class concerns:** installing models and binaries
  offline, and checking readiness before an Event. They are planned separately.

## Validation

- **Live Replay Run 002** records the profile it ran on: the development machine as a
  provisional profile.
- **After ADR-0036's engine spike:** a first latency budget per stage of the chain, stated
  against the provisional profile.
- **When appliance hardware is chosen:** the same replay and qualification rerun on it,
  before the first Event on that hardware.

## Related documents

- [ADR-0022](ADR-0022-postgresql-authoritative-operational-store.md),
  [ADR-0025](ADR-0025-postgresql-durable-operations-and-workers.md),
  [ADR-0029](ADR-0029-nvenc-rendering-and-gpu-worker-requirement.md),
  [ADR-0031](ADR-0031-white-label-identity-and-provider-neutral-program-sources.md),
  [ADR-0036](ADR-0036-core-transcription-gpl-free-engine.md).
- The architecture index: `docs/architecture/README.md`.
