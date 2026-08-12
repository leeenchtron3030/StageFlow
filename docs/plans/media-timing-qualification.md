# Media timing reconnaissance and qualification tooling

## Status

Completed

## Execution authority

- **Classification:** Green autonomous
- **Authority evidence:** Operator-authorized autonomous Phase A; Product Constitution
  principles 22 through 25; accepted ADR-0021, ADR-0023, and ADR-0024; accepted Durable
  Event-Mode Kernel architecture; the completed Run 004 partial-qualification result;
  root bounded-autonomy policy.
- **Implementation-ready:** Yes
- **Required escalation or approval:** None for qualification-only code and documentation.
  Durable production Media Timing Evidence, recorder-time qualification as production
  truth, persistence, and any association-policy change remain Yellow.

## Related findings or ADRs

- **Finding/disposition:** Run 004 is lifecycle/preservation/policy-conformance PASS and
  content-correct automatic turnover association INCONCLUSIVE / NOT QUALIFIED.
- **Accepted ADR:** ADR-0021 (time authority), ADR-0023 (Session/media authority), and
  ADR-0024 (conservative association).
- **Proposed ADR:** ADR-0025 (durable operations/workers) and ADR-0026 (automatic
  authority); neither is accepted by this work.
- **Engineering Directive or other authority:** ED-0048 Completed Media Asset, existing
  validation-tooling conventions, and the operator-authorized Phase A objective.

## Problem statement

Run 004 media contains embedded recorder/container timing evidence that was not inspected
during Kernel qualification. Read-only reconnaissance found zero-based per-file PTS/DTS,
monotonic embedded UTC creation times, and deterministic candidate intervals, but the
semantics and precision of those anchors are not qualified as content truth. The finding
needs a durable sanitized record and a reusable, bounded way to inspect future calibration
corpora without introducing a production FFmpeg dependency or changing authority.

## Verified current behavior

- Completed Media Assets already preserve stable asset/manifest identity, recorder and
  adapter provenance, optional technical duration/timecode, and optional recording start
  and end timestamps; those fields do not model raw observations, derivation lineage, or
  qualification status.
- Generic Evidence contracts organize references to Semantic Observations. They do not
  provide a durable media-timing observation or calibration-profile contract.
- Transcript adapters report provider-neutral transcript activity and optional relative
  timeline references; they do not execute transcription or establish absolute media time.
- The Kernel persists optional media start/end facts and advisory Session boundary
  proposals, while accepted association remains deterministic and conservative.
- Proposed ADR-0025 is still required before durable transcription worker coordination.
- No production inspection port, FFmpeg boundary, recorder profile, Media Timing Evidence
  aggregate, schema, migration, or automatic association use exists.
- vMix supplies locally installed FFmpeg binaries, but no FFmpeg dependency exists in the
  repository and none is required for application runtime.

## Desired behavior

StageFlow has qualification-only tooling that shallowly inspects explicitly supplied media,
records raw container/stream observations separately from derived candidate intervals,
emits secret-free JSON and Markdown, identifies the inspection tool/version, and labels all
candidate intervals unqualified and non-authoritative. Sanitized documentation records the
Run 004 finding and a controlled future calibration experiment.

## In scope

- A directly executable Python qualification probe under `backend/tests/qualification/`.
- Explicit caller-supplied FFmpeg executable; no bundled binary and no dependency change.
- Bounded single-file or shallow-directory MP4 inspection without decoding/transcoding.
- Secret-free JSON and Markdown outputs with tool/probe provenance.
- Raw observations, packet timing, filesystem-proxy labels, derived candidate intervals,
  adjacency residuals, limitations, and qualification-only status.
- Behavior-first focused tests using mocked FFmpeg output and temporary synthetic files.
- Sanitized Run 004 reconnaissance, a future vMix calibration design, and index updates.
- A proposed provider-neutral production architecture and exact Yellow decision boundary.

## Out of scope

- Production code, dependencies, schema, migrations, Runtime composition, workers,
  transcription execution, provider/model selection, APIs, frontend, deployment, or Event
  readiness.
- Accepting vMix `creation_time` as authoritative content start.
- Changing Session boundaries, automatic media association, package membership, or
  automation authority.
- Running the calibration experiment or modifying Runs 001 through 004.

## Constraints

- **Architecture and terminology:** Observed raw timing, Derived candidate interval,
  Inferred semantics, External recorder log, and Declared Session authority remain distinct.
- **Compatibility:** Qualification output is not a production/public contract and cannot be
  consumed as Kernel authority.
- **Offline/Event Mode:** The probe uses only an explicitly supplied local executable and
  local media; it performs no network work.
- **Security and data handling:** Outputs omit source paths and filenames, never contain
  credentials/provider payloads, and use caller-supplied safe aliases.

## Implementation approach

1. Add a standard-library-only qualification CLI that validates bounds and paths, invokes
   FFmpeg without a shell, parses header plus bounded first/last packet probes, and never
   writes beside source media implicitly.
2. Serialize stable sanitized media aliases, raw observations, derived unqualified
   intervals, derivation rule/version, adjacency residuals, and explicit limitations.
3. Publish JSON and Markdown atomically and refuse overwrite.
4. Add focused unit/CLI tests with deterministic mocked FFmpeg output; no real media.
5. Record the sanitized Run 004 finding, calibration procedure, current-contract audit,
   proposed production shape, and Yellow decision package.
6. Run focused tests, Ruff, Pyright, CLI `--help`, documentation/link/UTF-8 checks,
   `git diff --check`, and deliberate diff review.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/tests/qualification/media_timing_probe.py` | New non-production probe |
| `backend/tests/test_media_timing_probe.py` | Focused behavior and CLI tests |
| `docs/validation/` | Reconnaissance, calibration design, and index entries |
| `docs/architecture/` | Proposed Media Timing Evidence decision package and index entry |
| `docs/plans/` | This plan and index entry |
| `scripts/README.md` | Qualification-tool discovery link |

## Data or migration considerations

None. No production/durable schema, database, media, Run artifact, manifest, identity, or
runtime configuration changes. Qualification outputs are caller-created external/local
artifacts and are not StageFlow authority.

## Failure and recovery considerations

- Missing/invalid tools, unsupported/malformed metadata, unsafe aliases, symlinks, bounds,
  and existing output files fail visibly before authority-like output is emitted.
- FFmpeg is invoked without a shell and receives no output media path.
- Output writes use same-directory temporary files and atomic no-clobber publication only
  after both destinations pass preflight; existing outputs are never overwritten.
- A failed probe can be rerun to new output paths. No durable application state exists to
  reconcile.

## Observability requirements

Developers can identify probe schema/version, FFmpeg version/name, observation time,
source alias, per-file parse limitations, derivation rule/version, qualification status,
and candidate adjacency residuals. Reports explicitly prohibit authority use and omit
private paths and filenames.

## Test strategy

- Parser tests for format/stream tags, aware and naive timestamps, packet PTS/DTS, and
  derived interval behavior.
- Directory/report tests for deterministic ordering, sanitized output, monotonic anchors,
  adjacency residuals, bounds, and non-authority labels.
- CLI tests for direct execution, atomic JSON/Markdown creation, and overwrite refusal.
- Focused pytest, Ruff, Pyright, CLI `--help`, documentation checks, and `git diff --check`.

## Acceptance criteria

- [x] Tool inspects an explicit single file or shallow bounded directory without modifying
  source media or performing full decode/transcode.
- [x] JSON and Markdown identify tool/probe versions and contain no source paths or filenames.
- [x] Raw observations and derived candidate intervals are structurally separate.
- [x] Naive/missing recorder times are preserved as raw values but never normalized or used
  to derive an absolute interval.
- [x] Every derived interval is visibly unqualified, versioned, limitation-bearing, and
  prohibited from authority use.
- [x] Focused tests and proportionate static/document validation pass.
- [x] Run 004 reconnaissance and future calibration design are durably documented.
- [x] Production Media Timing Evidence remains stopped behind an exact Yellow package.

## Rollback or reversal

Remove the new qualification script, focused tests, and new documentation/index entries.
No production data, schema, dependency, configuration, or protected evidence requires
reversal.

## Open questions

- Yellow: which durable production owner/model stores raw recorder timing and derived
  interval revisions?
- Yellow: what calibration evidence qualifies a recorder profile for production use?
- Yellow: which policies may consume qualified interval evidence, and only as proposal
  input or as deterministic association evidence?

## Completion record

- **Implemented revision:** Uncommitted Green qualification changes on `74f23b4`; unrelated
  pre-existing working-tree changes were preserved.
- **Files and migrations actually changed:** Added the qualification probe and focused
  tests; added this plan, reconnaissance, calibration, and candidate-architecture docs;
  updated validation, architecture, plan, script, and Run 004 indexes/links. No migration.
- **Commands and tests actually run:** focused pytest with an explicit workspace temp root;
  focused Ruff and Pyright; direct CLI `--help`; strict UTF-8 and relative Markdown-link
  check over nine affected docs; `git diff --check`; targeted status/diff self-review.
- **Results and warnings:** 7 focused tests passed; Ruff passed; Pyright reported zero
  errors/warnings; CLI help passed; documentation checks passed; diff check had no
  whitespace errors. An initial test run exposed and then verified correction of one
  container-format parser defect and strict-type gaps. The default pytest temp root was
  unreadable, so final tests used an explicit workspace-local temp root. A later combined
  invocation from repository root could not find backend project tools; it was rerun from
  `backend` and passed. Git emitted pre-existing LF-to-CRLF working-copy warnings.
- **Execution authority used:** Green autonomous Phase A only.
- **Approved deviations:** None.
- **Rollback status:** Reversible by removing isolated qualification files/index entries.
- **Remaining work:** Explicit MTE-001 through MTE-005 decisions and applicable ADR-0025
  approval before any production Media Timing Evidence implementation.

## Subsequent authority

On 2026-08-12 the operator approved MTE-001 through MTE-005. ADR-0027 and the
[MTE v1 production plan](media-timing-evidence-v1.md) now govern the separate durable
advisory evidence implementation. This follow-up does not change the qualification-only
scope or historical results recorded above, and ADR-0025 remains Proposed.
