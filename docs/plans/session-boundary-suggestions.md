# Session boundary suggestions (ADR-0034)

## Status

Approved (2026-09-28). Phase 1 (ED-0103) is implementation-ready. Phases 2–5 are outlined
here; each gets a detailed section, reviewed by the owner, before it starts.

## Execution authority

- Classification: Green for Phase 1 under the accepted ADR. Later phases are Green once
  their detailed sections are approved.
- Authority evidence:
  - [ADR-0034](../adr/ADR-0034-session-boundary-suggestions.md), accepted by the owner on
    2026-09-28: scope B, transcript cues in v1, and the v1 quality target;
  - ADR-0025 (Durable Operations), ADR-0027 and ADR-0033 (advisory media timing, the
    explicit-path LGPL binary pattern), ADR-0023 and ADR-0024 (human Session authority),
    ED-0092 (phrase matching).
- Required escalation, any phase: stop if the work would need:
  - automatic Session realization or boundary authority;
  - a change to Session, association, package or Program Expectation semantics;
  - a new dependency;
  - committed real-event media, names or paths;
  - a model-based detector.
- Engineering Directives: **ED-0103** is Phase 1. The owner delegated ED numbering; later
  phases take the next free numbers when they are detailed.

## Phases

| Phase | Outcome | Migration |
| --- | --- | --- |
| **1. Media segmentation evidence (ED-0103)** | Advisory freeze and silence intervals per Completed Media Asset, from a new `media_segmentation` Durable Operation | `0021` |
| 2. Session Suggestions core | Suggestion aggregate, deterministic `boundary-suggestion` policy v1 (schedule, timing, segmentation, transcript cues), human-invoked suggestion run, confirm and reject commands (confirm reuses the existing human Session realization and boundary commands) | `0022` |
| 3. Boundary proposals for realized Sessions | The same policy produces `session_boundary_proposal` rows (existing table) for confirmed Sessions | none expected |
| 4. Producer surfaces | Work Queue item "confirm presentation" (additive), and suggestion review on Session Detail and Mission Control under the owner's scanning rule; UX checkpoint | none |
| 5. Validation harness and Run 001 | Replay the ground-truth corpus (outside the repo) and measure recall, precision and start/end error against the ADR target; sanitized result | none |

## Phase 1: media segmentation evidence (ED-0103)

### Verified current behavior

- **The ADR-0033 media timing inspection is the template:**
  - a `media_timing` operation kind (migration `0017`);
  - an explicit-path LGPL `ffprobe` adapter with an identity check and a demuxer
    allowlist;
  - a CPU worker (`backend/app/demo/media_timing_worker.py`);
  - bounded, idempotent, default-off enqueue (`[local_media_timing]`, the ED-0096
    amendment);
  - advisory evidence with lineage.
- **The FFmpeg render adapter** (`backend/app/infrastructure/rendering/ffmpeg.py`) already
  has the explicit-path FFmpeg identity check (refuses GPL and nonfree builds), argument
  construction without a shell, heartbeats and demuxer allowlists.
- **Real-footage measurement (2026-09-28):**
  - Filters: `fps=5,scale=320:-2,freezedetect=n=0.003:d=4` and
    `silencedetect=n=-40dB:d=3`.
  - Speed: about 5.7× real time on the CPU for a 10-minute 1080p block.
  - Result: freeze and silence intervals bracketed a changeover within 3–9 s of the
    ground-truth boundaries.

### Desired behavior

- **Operation:** a new Durable Operation kind **`media_segmentation`** on the shared
  substrate.
  - The work key is the asset, the manifest and the segmentation profile ID and version.
  - Other operation kinds are unchanged, and each kind's constraints stay exact for that
    kind, following the ADR-0032 amendment 2 rule.
- **Profile v1** (constants, recorded as lineage): the filter chain and thresholds above,
  CPU decode, and the demuxer allowlist.
- **Worker:** a CPU worker using the operator-installed FFmpeg by explicit path (a new
  `[local_media_segmentation]` config section: `enabled`, `ffmpeg_path`). It runs both
  filters in one pass and parses `freeze_start`/`freeze_end` and
  `silence_start`/`silence_end`. Only bounded numeric values are kept; stderr text is
  never stored.
- **Evidence:** immutable per asset and operation.
  - Each interval records kind (`freeze` or `silence`), start and end offsets in integer
    microseconds from the asset start, and the profile ID and version.
  - An asset has at most 10,000 intervals. Exceeding that is a typed failure, not
    truncation.
  - Evidence is advisory, with no authority.
- **Enqueue:** default off, bounded at 100 per cycle, and idempotent by work key, for
  registered Event assets lacking a segmentation operation. This is the ED-0096 pattern.
  An explicit human backfill command is also provided.
- **API:** a bounded read of segmentation evidence per asset and per Session.
- **Failure mapping:** reuse the render and timing typed codes where they fit (identity
  refused, input missing, non-zero exit retryable, output invalid). New codes only as
  needed, and listed.

### In scope

Migration `0021` (forward and reverse); contracts; the adapter; the worker and its
config; enqueue and backfill; repository (memory and PostgreSQL); API read; tests;
documentation (glossary term "Media Segmentation Evidence", capability layer, config
README).

### Out of scope

The Phase 2 policy and suggestions, transcript cues, UI, title-card detection, GPU decode,
and any change to media timing, rendering or transcription.

### Constraints

- Identity check and argument safety are the same as the render adapter. No caller text
  in arguments. `shell=False`. Demuxer allowlist.
- Offline. No new dependency. No media content or paths are stored. Aware timestamps from
  the injected clock.
- Every existing constraint stays exact for its operation kind. The reverse migration
  refuses while segmentation rows exist.

### Test strategy

- **Fake-binary tests:**
  - argument construction and parsing of freeze and silence output, including edge cases:
    an interval open at end of file, no intervals, and malformed lines;
  - failure mapping;
  - the interval cap;
  - heartbeats.
- **PostgreSQL:**
  - migration forward and reverse, including the reverse refusing while rows exist;
  - work-key idempotency;
  - bounded enqueue;
  - evidence immutability and reads;
  - other operation kinds unaffected.
- **Real FFmpeg check** (owner step on the host): run the worker on synthetic clips with
  known freeze and silence spans. **Fake binaries cannot prove filter semantics**, the
  lesson from ED-0098. Record a sanitized Segmentation Run 001, including one real-corpus
  changeover compared with ground truth.
- **Quality gate:** the full host backend suite, Ruff, Pyright, and `git diff --check`.

### Acceptance criteria

- [ ] Segmentation operations run end to end and store advisory freeze and silence
  intervals with profile lineage. Every other operation kind is unchanged.
- [ ] Migration `0021` forward and reverse tests pass. The demo database is backed up
  before it is applied.
- [ ] All checks pass on the host. The owner's real-FFmpeg run is recorded.

### Rollback

Revert the code. Reverse `0021` only while no segmentation rows exist.

## Ground-truth corpus handling (all phases)

- Real-event media, the decoded ground truth and scripts stay outside the repository:
  `C:\StageFlowDemo\ground-truth\`.
- Committed results use only anonymous identifiers (`talk 1`, `stage A`), durations and
  error statistics.

## Completion record

- **Phase 1 (ED-0103), implemented revision:** branch `codex/ed-0103-media-segmentation`.
  Codex implemented it and the owner committed it.
- **Changed files:**
  - migration `0021` (a `media_segmentation` operation kind; three kind-membership
    constraints widened, with exact requirements kept for existing kinds; evidence and
    interval tables; a guarded reverse);
  - the `media_segmentation_evidence` context;
  - the FFmpeg segmentation adapter (shares the render identity check through
    `identify_ffmpeg`);
  - the CPU worker and the `[local_media_segmentation]` config;
  - default-off bounded enqueue and backfill;
  - the bounded API;
  - the PostgreSQL repository;
  - tests and documentation.
  - No dependency.
- **Changed existing assertions:** three migration-order lists, which were pre-authorized.
- **Review:** `directive-reviewer` returned FIX-FIRST, then APPROVE.
  - F1: an end-of-file silence end overshooting the measured duration made the asset fail
    permanently. The owner fixed it: only an *end* offset up to 1 s past the duration is
    clamped, and starts stay strict.
  - F2: tests now use the real FFmpeg 8.1 line shapes.
- **Tests (host):** full backend suite **2,765 passed, 0 failed, 2 skipped**, on a freshly
  reset test database. Earlier parallel sandbox runs had left the shared test schema
  inconsistent. Ruff and Pyright clean.
- **Owner real-FFmpeg run:**
  [Segmentation Run 001](../validation/results/media-segmentation-001.md).
- **Remaining work:**
  - migrate the demo database to `0021` after merge, backing it up first;
  - Phase 2 (the suggestions core and policy) needs its detailed section.
  - Non-blocking review notes for later:
    - the fixed 3600 s timeout does not scale with asset length;
    - `N/A` `out_time_us` handling;
    - only the first audio track is analysed;
    - results are tied to the current profile version.
