# Real transcription engine evaluation

## Status

Completed

## Execution authority

- Classification: Green autonomous
- Authority evidence: the operator-authorized evaluation objective; Product Constitution
  principles 8-12, 16-17, and 22-25; accepted ADR-0025 and ADR-0027; the
  transcription-evidence readiness and post-Kernel capability architecture; and the
  repository bounded-autonomous-execution policy.
- Implementation-ready: Yes
- Required escalation or approval, if any: selecting a production engine/model,
  introducing its consequential runtime dependency, changing deployment, or promoting
  benchmark findings into Event/Editorial authority is Yellow and remains excluded.

## Related findings or ADRs

- Finding/disposition: transcription evidence is an approved post-Kernel capability;
  provider selection and production integration remain open decisions.
- ADR: accepted ADR-0025 (durable operations/workers) and ADR-0027 (Media Timing
  Evidence).
- Engineering Directive or other authority: operator-authorized reversible research and
  benchmarking; `PRODUCT_CONSTITUTION.md`; `ENGINEERING_DIRECTIVES.md`;
  `docs/architecture/transcription-evidence-readiness.md`;
  `docs/architecture/post-kernel-capability-layer.md`.

## Problem statement

The durable transcription worker substrate has a provider-neutral execution port but no
measured evidence identifying which local/offline Windows RTX transcription engines and
models are viable. StageFlow needs reproducible performance, accuracy, timing,
operational, licensing, and offline-readiness evidence before architecture can select a
production provider and dependency set.

## Verified current behavior

- `TranscriptionExecutionPort` accepts a fenced operation/attempt request and returns a
  provider-neutral `NormalizedTranscriptResult`.
- `TranscriptionWorker.run_once` owns claim, running-state transition, lease renewal,
  failure classification, and atomic evidence application through the repository.
- The execution request identifies an immutable media asset and manifest but deliberately
  carries no provider-specific DTO or local filesystem path.
- No real transcription provider dependency exists in `backend/pyproject.toml`.
- Existing qualification tooling emits sanitized, versioned, non-authoritative evidence
  and keeps external media out of the repository.
- The evaluation host is Windows 11 with an NVIDIA RTX 3080 Ti Laptop GPU (16 GiB), 32
  GiB system memory, and no system FFmpeg on `PATH`; these are observed host facts, not
  deployment guarantees.

## Desired behavior

Provide a provider-neutral, deterministic qualification harness that can run serious
local/offline candidates, normalize results through the accepted transcription contract,
measure accuracy/performance/timing/resource behavior without leaking media or secrets,
and exercise the leading candidate through the actual fenced worker lifecycle. Publish a
sanitized comparison and the exact Yellow production-selection decision; do not make the
decision in this plan.

## In scope

- Research current serious Windows/RTX candidates from primary sources.
- Add qualification-only benchmark contracts, metrics, result validation, and CLI.
- Add optional, lazily imported evaluation adapters without changing production
  dependencies.
- Define a deterministic external corpus manifest and non-sensitive synthetic fixture
  generator or explicitly licensed external corpus inputs.
- Measure cold/warm latency, real-time factor, throughput, WER/CER where reference text
  exists, timestamp structure, failure behavior, runtime/model identity, and known
  resource observations.
- Exercise the leading runnable candidate behind `TranscriptionExecutionPort` through the
  real `TranscriptionWorker` lifecycle using isolated qualification state.
- Add behavior-first regression tests and sanitized validation documentation.

## Out of scope

- Selecting or configuring a production-default engine or model.
- Adding provider/model dependencies to production or development lockfiles.
- Schema changes, migrations, automatic enqueue, public APIs, UI, deployment, brokers,
  or recorder qualification.
- Granting Session, package, editorial, evidence-acceptance, or wall-clock authority to a
  provider or benchmark result.
- Committing model weights, media, raw provider payloads, private paths, credentials, or
  sensitive transcripts.

## Constraints

- Architecture and terminology constraints: provider DTOs remain behind the execution
  port; Transcript Evidence Revision remains asset/manifest scoped; asset-relative
  transcript timing and Media Timing Evidence wall-clock derivation remain separate.
- Compatibility constraints: existing production contracts and worker semantics do not
  change; qualification adapters must normalize into the current contract.
- Offline/event-mode constraints: distinguish first-use acquisition from verified warm
  offline execution; record cache/model identity and network assumptions explicitly.
- Security and data-handling constraints: outputs contain only caller-supplied safe
  aliases, digests, aggregate metrics, normalized non-sensitive fixture text, and
  sanitized errors; they exclude absolute paths, environment values, credentials, and
  raw provider payloads.

## Implementation approach

1. Build a primary-source candidate matrix covering Windows/CUDA support, model and
   runtime licensing, timestamps, diarization/alignment options, offline caching,
   dependency size, and operational risks.
2. Implement versioned qualification contracts, WER/CER and timing metrics, privacy-safe
   serialization, deterministic corpus generation/validation, and a CLI with bounded
   inputs and atomic new-file output.
3. Implement evaluation-only adapters for the candidates that can be installed in an
   isolated temporary environment; imports stay lazy and provider packages remain absent
   from StageFlow dependency manifests.
4. Run deterministic self-checks and real host benchmarks against exact runtime/model
   revisions, preserving both successes and failures as evidence.
5. Bridge the leading runnable adapter through `TranscriptionExecutionPort` and exercise
   claim, running, lease-renewal, normalization, atomic apply, replay/fence behavior, and
   provider failure in qualification tests.
6. Validate the repository, deliberately review the diff, publish sanitized evidence,
   and stop at the exact Yellow engine/model/dependency selection decision.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/tests/qualification/` | Provider-neutral harness, corpus tooling, and optional evaluation adapters |
| `backend/tests/` | Harness and worker-lifecycle regression tests |
| `docs/validation/` | Candidate matrix, runbook, sanitized results, and Yellow decision package |
| `docs/plans/README.md` | Index this plan |
| `docs/plans/transcription-engine-evaluation.md` | Plan and completion evidence |

## Data or migration considerations

No schema or migration change. Media, models, caches, virtual environments, and raw run
artifacts remain in explicitly selected external temporary paths. Result schema versioning
is qualification-only and does not alter persisted StageFlow contracts.

## Failure and recovery considerations

The harness must fail closed on invalid manifests, unsafe aliases, existing outputs,
missing optional runtimes, malformed normalized results, non-finite metrics, or bounded
execution timeouts. Each corpus item is independent and results retain sanitized failure
classification. Interrupted model acquisition or benchmarks may be deleted from the
isolated evaluation cache and rerun. Worker qualification must preserve fencing,
idempotent replay, retry ownership, and repository atomicity; it must not bypass the
accepted worker lifecycle.

## Observability requirements

Evidence identifies harness/schema version, host facts, exact engine/runtime/model
revision and license source, device/compute mode, corpus alias and digest, cold/warm run,
duration, latency, real-time factor, throughput, WER/CER, timestamp capabilities,
resource-observation method, normalized status, and sanitized limitation/failure. No
secret or private absolute path may be serialized.

## Test strategy

- Unit tests for normalization, WER/CER, timestamps, manifest bounds, safe serialization,
  atomic output, timeout/failure classification, and deterministic fixture generation.
- Contract tests using deterministic fake adapters plus optional real-engine qualification.
- Worker-lifecycle qualification using the real coordinator and repository boundary,
  including lease renewal, apply, replay/fence rejection, and provider failure.
- Targeted `pytest`, `ruff`, and `pyright`; then the full backend suite and repository
  whitespace check. No frontend check is required unless a frontend file is intentionally
  changed.

## Acceptance criteria

- [x] At least three serious candidates have a current primary-source comparison, with
  unsupported or unmeasured claims labeled explicitly.
- [x] A provider-neutral qualification harness produces deterministic, versioned,
  privacy-safe evidence and is covered by behavior-first tests.
- [x] At least two viable engines/models are attempted on the evaluation host, or each
  unattempted candidate has a preserved, specific environmental blocker.
- [x] Real runs record exact runtime/model identity, cold/warm behavior, accuracy where
  references exist, timestamp structure, resource observations, and offline/cache state.
- [x] The leading runnable candidate is exercised behind `TranscriptionExecutionPort`
  through the accepted fenced worker lifecycle without production contract changes.
- [x] Production dependency manifests, schemas, migrations, runtime configuration, and
  public contracts remain unchanged.
- [x] Targeted and full proportionate validation pass, or unrelated/environmental
  failures are preserved and classified without weakening checks.
- [x] Sanitized documentation states the evidence limits and poses one exact Yellow
  provider/model/dependency selection decision without silently resolving it.

## Rollback or reversal

Delete the qualification-only modules, tests, documentation, and external evaluation
cache/virtual environments. No production data, schema, dependency manifest, runtime
configuration, or public contract requires reversal.

## Open questions

- Yellow decision: which engine, model, precision, runtime/dependency packaging, and
  optional alignment/diarization stages should StageFlow adopt for its first production
  Windows RTX transcription worker?
- What realistic, non-sensitive accented/noisy conference corpus may be retained or
  referenced for repeatable acceptance beyond the deterministic synthetic corpus?

## Completion record

- Implemented revision: `codex/transcription-engine-evaluation`; exact publication
  revision is recorded by Git/PR history.
- Files and migrations actually changed: qualification-only benchmark and adapter modules,
  behavior-first tests, this plan/index, and validation evidence/index. No production
  module, dependency manifest, schema, migration, runtime configuration, or public
  contract changed.
- Commands and tests actually run: targeted `pytest` (6 passed), targeted/full `ruff`,
  targeted/full `pyright`, full backend `pytest -p no:cacheprovider` (1,704 passed, 14
  skipped), `git diff --check`, direct CLI help, privacy scans, pinned artifact digest
  checks, real whisper.cpp CPU/CUDA runs, forced-offline faster-whisper CUDA runs, and one
  real isolated-PostgreSQL worker cycle with bounded migration-0007 reversal/reapply.
- Results and warnings: faster-whisper CUDA was the measured evidence leader at aggregate
  RTF 0.0203 versus whisper.cpp CUDA at 0.0647 and whisper.cpp CPU at 1.1570. The synthetic
  English corpus is not real-event readiness evidence; GPU memory samples are not process
  peaks. Stock faster-whisper required an explicit local cuBLAS DLL path. The full suite
  emitted one existing Starlette/httpx deprecation warning, and PostgreSQL-gated tests were
  skipped in the non-DSN full run after the separate real database qualification passed.
- Execution authority used: Green autonomous.
- Approved deviations: None.
- Rollback status: qualification files can be deleted directly; the isolated database was
  restored with migration 0007 applied and its tables empty; the reused base asset remained.
- Remaining work: the documented Yellow provider/model/dependency/packaging decision and a
  future realistic accented/noisy/multilingual conference corpus qualification.
