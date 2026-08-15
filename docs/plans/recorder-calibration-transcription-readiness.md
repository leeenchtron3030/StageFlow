# Recorder calibration and transcription readiness

## Status

Completed

## Execution authority

- **Classification:** Green autonomous for qualification-only tooling, synthetic
  calibration evidence, and proposed architecture/decision documentation.
- **Authority evidence:** Operator-authorized recorder-calibration/transcription-readiness
  objective; Product Constitution principles 3, 5, 9-11, 16, and 22-25; accepted
  ADR-0021 through ADR-0024 and ADR-0027; accepted Media Timing Evidence v1 architecture;
  completed media-timing qualification tooling plan; root bounded-autonomy policy.
- **Implementation-ready:** Yes for the bounded Green scope below.
- **Required escalation or approval:** Recorder-profile qualification and acceptance of
  ADR-0025 remain Yellow. Provider/dependency selection, production transcription or
  inspection execution, automatic Session/media authority, and automatic AI authority
  remain separately gated.

## Related findings or ADRs

- **Finding/disposition:** Run 004 proved repeatable candidate timing but did not provide
  independent content-time ground truth.
- **Accepted ADR:** ADR-0021, ADR-0022, ADR-0023, ADR-0024, and ADR-0027.
- **Proposed ADR:** ADR-0025 PostgreSQL durable operations and workers.
- **Engineering Directive or other authority:** ED-0054 Durable Advisory Media Timing
  Evidence v1 and the operator-authorized controlled-calibration objective.

## Problem statement

StageFlow can inspect vMix MP4 timing but cannot yet measure embedded `creation_time`
against deterministic content markers. It also lacks an accepted provider-neutral
transcription evidence model and a sufficiently concrete first-worker decision package.
Qualification evidence and implementation-ready architectural boundaries are needed
without changing Session, association, package, Editorial, provider, or AI authority.

## Verified current behavior

- Local `main` and `origin/main` both point to `05cc375`; the feature branch starts there.
- The worktree contained a pre-existing generated `frontend/next-env.d.ts` path change,
  which this plan preserves and excludes.
- vMix `29.0.0.48` is installed. Its bundled `ffmpeg6.exe` reports FFmpeg `6.0` with
  deterministic video/audio source and draw-box filters; no repository/runtime FFmpeg
  dependency exists.
- The existing qualification probe records container, stream, packet, filesystem-proxy,
  and unqualified candidate timing, but it neither creates calibration media nor decodes
  independent content markers.
- MTE v1 is durable advisory evidence and explicitly permits future transcript alignment;
  no recorder profile is qualified.
- Current transcript adapters report activity through Production Events. They do not
  execute transcription or own a durable revisioned transcript result.
- ADR-0025 is Proposed and no production Operation/Attempt/Worker implementation exists.
- The Editorial experience is an explicitly simulated development shell; real transcript,
  Candidate, Hot Moment, and Clip execution are not represented as implemented.

## Desired behavior

Qualification tooling can generate deterministic, non-sensitive marker media and analyze
recorded segments into sanitized raw and derived results. Repository documentation records
what was and was not tested, proposes a recorder-profile envelope only when evidence
supports it, defines provider-neutral transcript evidence and MTE alignment, and presents
the smallest first-transcription-worker decision package. No Yellow decision is silently
accepted or implemented.

## In scope

- Standard-library-only qualification code under `backend/tests/qualification/`.
- Explicit caller-supplied local FFmpeg-compatible executable and tool/version provenance.
- Deterministic visual binary frame/time markers, once-per-second/boundary markers,
  start/end slates, and known audio clicks/tones.
- Content-marker decoding plus per-segment raw/derived timing, adjacency, precision,
  repeatability, and limitation reporting.
- Unit/fixture coverage independent of vMix and one generated local synthetic corpus.
- Sanitized human-readable and machine-readable evidence committed only when it contains
  no paths, filenames, credentials, private media, or provider payloads.
- Proposed provider-neutral transcription evidence, MTE derivation, provider-port, and
  first-worker decision documentation.
- Read-only verification that the accepted Editorial shell already labels simulated
  transcript/Candidate/Hot Moment/Clip content; only a bounded correction is permitted if
  this verification finds a bug.

## Out of scope

- Accepting any recorder/source profile as qualified timing authority.
- Production FFmpeg/transcription/provider dependencies or adapters.
- Production Durable Operation, attempt, lease, Worker, schema, migration, or runtime.
- Starting or reconfiguring vMix without an isolated, recorded trial configuration.
- Changing the Windows clock/timezone, Session boundaries/membership, ADR-0024 association,
  package authority, automatic AI authority, production deployment, or credentials.
- Broad Producer or Editorial UX redesign.

## Constraints

- **Architecture and terminology:** Observed provider/container/content-marker facts,
  Derived intervals/errors, Inferred semantics, External calibration authority, and
  Declared human authority remain distinct.
- **Compatibility:** Qualification schemas are non-production and cannot be consumed as
  Kernel authority. Existing transcript ingress remains unchanged.
- **Offline/Event Mode:** Tooling uses only explicitly supplied local tools and files.
- **Security and data handling:** Reports use safe aliases and omit paths, filenames,
  raw provider diagnostics, source content, and unnecessary workstation facts.

## Implementation approach

1. Add a deterministic source generator that invokes an explicitly supplied FFmpeg
   without a shell and emits a source plus sanitized manifest using no-clobber writes.
2. Encode a frame-index clock in a fixed visual marker strip and independently decode it
   from recorded outputs; preserve marker observations separately from calculations.
3. Compose the existing timing probe observations with decoded content markers to report
   per-segment content boundaries, embedded-anchor error, actual content gap/overlap,
   precision, sequence discontinuity, and condition/repetition groupings.
4. Add behavior-first tests for marker encoding/decoding, reporting, sanitization,
   malformed/discontinuous content, bounds, atomic output, and CLI help.
5. Generate a local synthetic corpus with the discovered vMix-bundled FFmpeg, analyze it
   as a harness self-check, and publish sanitized non-vMix evidence.
6. Document the transcription evidence aggregate, provider execution port, original
   asset-relative and derived wall-clock timing, partial/failure/reprocessing semantics,
   and prohibited authority effects.
7. Refine the Proposed ADR-0025 package only as needed for its first transcription
   consumer. Do not implement it.
8. Verify the current Editorial simulation labels, run proportionate checks, audit the
   diff and repository-tracked artifacts for privacy/secrets, and complete this plan.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/tests/qualification/calibration_harness.py` | Deterministic source generation and recorded-segment analysis CLI |
| `backend/tests/test_calibration_harness.py` | Qualification fixture/unit/CLI coverage |
| `docs/validation/` | Harness runbook and sanitized evidence/result |
| `docs/architecture/` | Proposed transcription evidence and MTE alignment boundary |
| `docs/adr/ADR-0025-postgresql-durable-operations-and-workers.md` | Concrete first-transcription-worker Yellow package while retaining Proposed status |
| `docs/plans/README.md` | Plan index entry |
| `docs/validation/README.md` and `docs/architecture/README.md` | New artifact index entries |

## Data or migration considerations

None for this Green milestone. Qualification outputs are caller-owned evidence, and all
new architecture/storage shapes remain proposed. No production schema, migration,
backfill, durable identity, or runtime configuration changes are authorized.

## Failure and recovery considerations

- Tool discovery, generation, decoding, media inspection, bounds, and output conflicts
  fail visibly with path-free errors.
- Source/segment media is never overwritten. Reports publish atomically and no-clobber.
- Missing/invalid marker sequences remain explicit limitations; they are never converted
  to zero or interpolated.
- Interrupted qualification runs can be repeated to new external output locations.
- A missing isolated vMix run prevents recorder qualification but does not block tooling,
  architecture, worker-decision, or Editorial-readiness work.

## Observability requirements

Reports identify schema/tool/harness versions, safe corpus/trial/profile aliases,
configuration fingerprint, OS facts needed for reproduction, raw container and marker
facts, derived calculations, exclusions, precision, repeatability, and limitations.
They explicitly state that authority use is prohibited and whether vMix was exercised.

## Test strategy

- Focused pytest for the new harness plus existing media-timing probe tests.
- Focused Ruff and Pyright over qualification tooling/tests.
- Direct CLI `--help` and one local generation/analysis self-check.
- Existing MTE tests if production MTE code is touched; none is planned.
- Frontend checks only if a bounded UI bug is changed.
- Strict UTF-8/relative-link inspection, `git diff --check`, privacy/secret scan, and
  deliberate diff review.

## Acceptance criteria

- [x] Deterministic calibration source includes decodeable continuous frame/time markers,
  once-per-second and segment-transition markers, start/end slates, and audio markers.
- [x] Analysis reports embedded/container/local timing, content-marker start/end,
  embedded-anchor delta, real content gap/overlap, precision, and limitations per segment.
- [x] Normal, alternate-duration, partial-stop, restart, and multi-batch trial identities
  are representable and summarized without pretending they ran.
- [x] Fixture/unit coverage does not require vMix or real media.
- [x] A sanitized generated-corpus self-check proves the harness locally.
- [x] Recorder evidence is not labeled qualified without Yellow approval.
- [x] Provider-neutral transcript evidence preserves asset/result revisions, provenance,
  relative timing, optional known-semantics confidence, partial/failure state, and
  reprocessing lineage.
- [x] MTE alignment preserves original relative timing and derived advisory wall-clock
  timing without changing Session/media/package/Producer authority.
- [x] ADR-0025 presents the smallest concrete first-transcription-worker Yellow choice.
- [x] Editorial simulated-content labeling is verified; no broad UX redesign occurs.
- [x] Proportionate checks, privacy scan, and diff review pass.

## Rollback or reversal

Remove the isolated qualification module/tests and new documentation/index entries, and
revert only the Proposed ADR clarification. External/generated corpus files are not
tracked. There is no production data, schema, dependency, configuration, or authority
change to reverse.

## Open questions

- **Yellow A:** Should a specific tested recorder profile be accepted as qualified timing
  evidence for explicitly stated advisory uses and tolerance?
- **Yellow B:** Should ADR-0025's specific first-transcription-worker PostgreSQL
  Operation/Attempt/lease topology be accepted?
- **Yellow provider:** Which local/cloud transcription provider and dependency, if any,
  should implement the provider-neutral port after the worker boundary is accepted?

## Completion record

- **Implemented revision:** Local milestone commit on
  `codex/recorder-calibration-transcription-readiness`; see Git history/PR for SHA.
- **Files and migrations actually changed:** Added the qualification-only calibration
  generator/analyzer/summarizer and focused tests; corrected FFmpeg 6 packet-identifier
  parsing in the existing probe; added sanitized source/60s/30s machine evidence and
  human self-check/runbook; added proposed Transcript Evidence/MTE alignment architecture;
  refined Proposed ADR-0025 for its first consumer; updated architecture, glossary,
  validation, plan, and script indexes. No production application code, frontend code,
  dependency, schema, migration, durable data, or runtime configuration changed.
- **Commands and tests actually run:** `git fetch origin --prune`; Git baseline/status/
  diff inspection; local vMix/FFmpeg discovery/version/filter inspection; direct harness
  generation and source/60s/30s/partial analysis; focused `pytest` for calibration and
  media timing; focused Ruff and Pyright; both qualification CLIs' `--help`; strict UTF-8,
  relative-link, JSON, privacy, and credential-signature checks; `git diff --check` and
  final cached diff/status review.
- **Results and warnings:** Baseline `main` matched `origin/main` at `05cc375`. The final
  focused suite passed 18 tests; Ruff passed; Pyright reported zero errors/warnings; CLI,
  documentation, JSON, privacy, and diff checks passed. The 5,700-frame source and both
  segment fixtures decoded without gaps/overlaps after correcting three harness/probe
  issues found by the real FFmpeg 6 run. vMix `29.0.0.48` was discovered but its GUI/
  recorder was not started or reconfigured, so recorder qualification remains not run.
  GitHub CLI authentication was invalid at publication time. The pre-existing generated
  `frontend/next-env.d.ts` working-tree change was preserved and excluded.
- **Execution authority used:** Green autonomous qualification/readiness scope only.
- **Approved deviations:** None.
- **Rollback status:** Reversible; no production state changes.
- **Remaining work:** Run the isolated controlled vMix matrix before Yellow recorder
  review; decide the specific ADR-0025 first-worker package before implementation; select
  a provider/dependency separately if consequential; restore GitHub authentication to
  push/open the milestone PR if it remains unavailable.
