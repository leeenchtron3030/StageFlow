# ADR-0035: User-defined boundary markers

## Status

Accepted (owner, 2026-09-29), with these decisions:

- **Authority:** markers are the strongest boundary evidence, and a producer confirms the
  resulting suggestions. **In addition**, each Event gets a producer switch that enables
  **automatic Session creation** from detected marker pairs. It is off by default and
  delivered as its own later phase under ADR-0026.
- **Marker types in v1:** a **color or graphic flash**, and a **reference sound**. A
  clapper (a combined sound and visual transient) comes later.
- **Setup:** on the **Event page in the Producer UI**, versioned, with a test-marker
  readiness check.
- **Reference-sound matching:** a **lightweight fingerprint** extracted with FFmpeg and
  matched in pure Python. **No new dependency.**

Implementation follows a phased plan, to be written as a detailed section of
[session-boundary-suggestions.md](../plans/session-boundary-suggestions.md) or its own plan,
reviewed by the owner before each phase.

## Date

2026-09-29

## Context

- ADR-0034 builds Session suggestions from inferred evidence:
  - schedule, recorder timing, freeze and silence changeovers, and transcript cues;
  - a deterministic, versioned policy (v1 is merged; v2, joint day alignment, is in
    ED-0105);
  - Session creation stays with a human.
- The owner's early accuracy check
  ([001](../validation/results/session-suggestions-accuracy-001.md)) found inferred
  changeovers alone reach about 79% of true edges within 60 s. With transcript cues, that
  rises to 96% on the same corpus (measured 2026-09-29).
- **Controlled environments can do better by design.** Examples are press junkets and taped
  interview series:
  - a sequence of short recorded interviews, often in one room with one crew;
  - tighter schedules;
  - a crew that can deliberately **plant a marker** at a session's start or end, such as a
    tone or sting, a slate or clapper, or a brief full-screen color, graphic or slide.
  - A planted marker is **intentional evidence**, far stronger than an inferred
    changeover.
- **Repository facts:**
  - Events are created from the operator's configuration at startup
    (`bootstrap/event_mode_kernel.py`); there is no Event-creation UI.
  - Event-scoped, versioned producer settings already exist: the render quality setting
    (ED-0099) and phrase lists (ED-0092).
  - Operator-supplied reference content with SHA-256 identity already exists: Packaging
    Assets (ED-0076).
  - The core backend has no numerical library.
  - FFmpeg is operator-installed LGPL, given by explicit path (ADR-0032, ADR-0033).
  - Segmentation evidence (ED-0103) is the template for per-asset detection as a Durable
    Operation.
- **Authority:** ADR-0023 and ADR-0024 keep Session realization human. ADR-0026 defines
  evidence, then policy, then authority, with scoped activation and durable provenance;
  no automatic authority is active today.

## Decision

1. **Boundary Marker definition (Event-scoped, versioned, human-set).** A producer defines
   markers for an Event, optionally scoped to a Stage or room. Each marker has:
   - **kind:** `color_flash` (a target color and tolerance), `graphic` (a reference image),
     or `sound` (a reference audio clip). The later kind `clapper` is reserved;
   - **role:** `start`, `end` or `both`;
   - **minimum hold** for visual markers, and a **match threshold**;
   - for the `graphic` and `sound` kinds, reference content stored like Packaging content,
     with an opaque key, SHA-256 and size;
   - who set it and when, with append-only history (the render-setting pattern).
2. **Marker detection evidence.** A new Durable Operation kind, `marker_detection`, on the
   shared substrate, the ED-0103 pattern:
   - It uses the operator-installed LGPL FFmpeg by explicit path.
   - **Color and graphic flashes:** frames are downscaled per block, then:
     - a `color_flash` must match the target color on at least a coverage fraction of the
       frame for the minimum hold, using per-frame statistics from FFmpeg built-ins;
     - a `graphic` is matched against a small perceptual signature of the reference.
   - **Reference sound:** FFmpeg extracts a low-rate, band-energy envelope of the block
     and of the reference. Matching uses normalized correlation of that coarse envelope in
     pure Python, then a finer local alignment around candidates.
   - Output: advisory **marker hits**, each with marker ID and version, the offset in
     integer microseconds, a score, and detector lineage. No new dependency. No stored
     media content.
3. **Policy.** A new policy version gives a matched marker absolute precedence as an edge
   of its role:
   - A start-marker hit sets the start of a suggestion.
   - An end-marker hit sets the end.
   - With `both`, hits alternate in time order.
   - When markers are defined for an Event, **marker pairs define suggestions**, and the
     schedule only names or labels them in time order. Inferred evidence is used only
     where a marker is missing, and those suggestions are flagged.
   - Suggestions carry a new strength level, `marked`.
4. **Authority, default:** marked suggestions are confirmed by a producer through the
   existing ED-0104 confirm command, one at a time or as a batch. Nothing is automatic.
5. **Authority, optional: automatic Session creation per Event.** This is the first
   ADR-0026 activation and **a separate, later phase**. It needs:
   - an explicit, scoped, versioned policy switch on the Event (off by default), recording
     who and when;
   - automation only for **complete marker pairs** (start and end, or `both`) above the
     match threshold, with no conflict or overlap, and never for inferred evidence;
   - durable provenance for each automatic decision: policy version, marker hits and
     evidence;
   - human correction and undo through the existing boundary and correction commands;
   - a readiness gate: automatic creation can be switched on only after a **passing
     test-marker check** for that Event, and after the detector's measured accuracy on
     validation media meets an agreed target.
6. **Readiness check (setup).** Before the event, the crew records the markers once, and
   StageFlow reports whether it detected each with its score. A failed check blocks
   automatic creation and warns in the UI.

## Options considered

- **Authority:**
  - confirm only;
  - confirm plus an optional automatic switch (**chosen**);
  - automatic only (rejected: too risky without measured detection accuracy).
- **Marker types:** color or graphic flash plus sound (**chosen for v1**); clapper later,
  because a sharp transient is ambiguous with applause and bumps.
- **Setup surface:** the Event page (**chosen**) or operator configuration.
- **Sound matching:**
  - a lightweight fingerprint with no dependency (**chosen**);
  - adding NumPy (a precise cross-correlation, but a new core dependency).

## Consequences

- Controlled environments get near-definitive boundaries.
- In open, live stages without markers, ADR-0034 inference continues unchanged.
- ADR-0026 gets its first concrete activation path. It stays inactive until the owner
  enables it for an Event after a passing readiness check.
- New schema covers marker definitions and history, marker-detection operations and hits,
  and the automatic-creation policy switch with provenance, spread over its phases.
- Detection cost is about one downscaled decode per recorded minute, the same order as
  segmentation. It can run alongside segmentation or as its own operation.

## Validation approach

- Synthetic clips with known color, graphic and sound markers, including noise, partial
  frames, near-miss colors and similar sounds. Measure precision, recall and time error.
- A controlled real test: record markers in a rehearsal. Target: every planted marker
  detected within one frame (visual) or 50 ms (sound), with no false hits in normal
  content.
- These results gate the optional automatic phase.
