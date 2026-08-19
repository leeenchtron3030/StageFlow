# Demo hardware rehearsal

## Status

In progress - core Razer/Mac flow proven; restart, offline, and representative-corpus qualification pending

## Execution authority

- Classification: Green autonomous rehearsal plus bounded compatibility correction
- Authority evidence: the explicit 2026-08-19 requests to begin a separate Demo Hardware
  Rehearsal workstream after merged PR #63, to correct the confirmed LAN UUID blocker, and to
  normalize the confirmed provider IndexError and harden isolated CUDA preflight; the completed
  [Demo Single-Stage Vertical Slice](demo-single-stage-vertical-slice.md); accepted
  ADR-0022 through ADR-0025 and ADR-0027; and the scoped Demo 1 transcription baseline.
- Implementation-ready: Yes for the bounded UUID and provider-failure compatibility corrections,
  isolated CUDA preflight, rehearsal, and evidence capture. No product-capability expansion is
  authorized.
- Required escalation or approval, if any: stop for any other proposed production code, dependency,
  schema, migration, public contract, authority-semantic, trust-boundary, or Devcon-write change.
  Production deployment and production-data access remain prohibited.
  The later [Demo rehearsal controller](demo-rehearsal-controller.md) records the separately approved
  Demo-only, explicitly confirmed Devcon publication boundary; it does not change the LAN UI.

## Related findings or ADRs

- Finding/disposition: Demo 1 and the first local transcription implementation are accepted;
  broader provider/model selection remains conditional on representative accented/noisy evidence.
- ADR: ADR-0022 through ADR-0025 and ADR-0027.
- Engineering Directive or other authority: merged PR #63; Product Constitution; ED-0053.

## Problem statement

The Demo Single-Stage Vertical Slice is implemented, CI-qualified, and has now run as a real
Razer/vMix/Next.js/Mac system. This workstream must continue qualifying the merged architecture,
correct only demonstrated bounded blockers, and record truthful evidence without implying
production or Event readiness.

## Verified current behavior

- PR #63 merged to main at f4e0398721ea29f9e5de116694aeeee0354e51d3 with both GitHub
  quality-matrix jobs green.
- The Razer reports an NVIDIA GeForce RTX 3080 Ti Laptop GPU with driver 581.57.
- vMix is present at its common Windows installation location and frontend dependencies exist.
- The concrete Demo TOML remains external to the repository. Its referenced model and media
  directories are populated, and the Demo PostgreSQL secret is available at Windows User scope;
  no path or secret value is recorded here.
- The real launcher has now proved valid configuration, one ready Stage, loopback-only backend,
  LAN-bound Producer UI, five External Program Expectations, and CUDA/float16 inference.
- The HTTP LAN-facing Producer UI exposed a confirmed compatibility blocker: Web Crypto is
  available, but randomUUID is absent. Direct frontend calls prevented authority commands from
  constructing operation IDs; backend and authority semantics were not implicated.
- The frontend compatibility correction now uses native randomUUID when present and a
  getRandomValues-only RFC 4122 UUID-v4 construction otherwise. Frontend tests, TypeScript,
  ESLint, the production build, and focused Demo API/authority/launcher checks pass.
- Three real faster-whisper CUDA Operations produced durable Transcript Evidence revisions. A
  later asset raised provider-originated IndexError and terminated the original worker process.
- The corrected adapter maps immediate and lazy IndexError to provider_execution_failed. The real
  failed Operation exhausted its existing bounded attempts and finalized terminally; the worker
  remained alive until controlled interruption. All three prior evidence identities were preserved.
- The launcher now supplies the isolated external cublas runtime only to its process and owned
  children. A real silent-audio inference probe passed before readiness; no NVIDIA driver or global
  CUDA environment was modified.

## Desired behavior

Using external configuration and non-customer rehearsal media, the Razer runs the merged
launcher, loopback backend/PostgreSQL, vMix media path, CUDA worker, and LAN-facing Next.js UI.
A Mac exercises explicit human controls and observes bounded Program Expectations, Operations,
Transcription Evidence, provenance, timing, limitations, and declared Moments. Restart and
offline-cache behavior are demonstrated without expanding product semantics.

## In scope

- Provision and verify an external concrete Demo config, Demo database secret, exact qualified
  large-v3-turbo model revision, controlled media directory, LAN identity, and vMix output.
- Run launcher, Devcon online-to-offline cache, vMix media, CUDA worker, Mac UI, human controls,
  restart, and reconstruction checks.
- Use synthetic, licensed, or consented non-customer accented/noisy samples.
- Capture bounded evidence and correct only a demonstrated Green rehearsal blocker.

## Out of scope

- New product features, providers, models, dependencies, schemas, migrations, APIs, authority
  semantics, automatic Session/Moment behavior, automatic or generic Devcon writes, production
  deployment, and production or customer data. A real bounded Devcon PUT is permitted only through
  the separately approved controller gates and a new explicit human confirmation.
- Broader provider/model acceptance or an Event-readiness claim.
- Committing DSNs, credentials, model files, media, transcripts, raw provider payloads, or
  private local paths.

## Constraints

- Architecture and terminology constraints: Program Expectations remain External; Transcript
  Evidence remains non-authoritative; human commands remain explicit and attributable.
- Compatibility constraints: exercise merged PR #63 without intentional contract changes.
- Offline/event-mode constraints: demonstrate local operation after explicit Devcon sync.
- Security and data-handling constraints: backend/PostgreSQL remain loopback-only; only Next.js
  binds to the trusted Demo LAN; secrets and transcript content stay out of normal logs and
  browser storage.

## Implementation approach

1. Correct and qualify the bounded frontend UUID-v4 compatibility blocker without changing
   authority, idempotency, API, backend, or LAN security behavior.
2. Normalize demonstrated provider IndexError failures and qualify process-scoped isolated CUDA
   runtime loading with a real inference preflight.
3. Provision and validate external config, Demo database identity, model revision, controlled
   media, LAN/Mac reachability, and vMix output without starting authority commands.
4. Run launcher preflight and capture bounded component/version/readiness evidence.
5. Synchronize Devcon, confirm External Program Expectations, remove upstream connectivity, and
   verify the durable cache remains visible.
6. Execute one Session through Start, vMix media, Process/Transcribe, Presentation End, Package
   Ready, and Mark Moment from the Mac UI.
7. Restart launcher-owned processes and verify reconstruction of Session, media, Operation,
   Transcription Evidence, and declared Moment state.
8. Repeat with representative accented/noisy non-customer samples and record limitations.
9. Publish a factual result distinguishing passed, failed, unavailable, and unqualified facts.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| docs/plans/demo-hardware-rehearsal.md | Plan, progress, and completion record |
| docs/validation/results/demo-hardware-rehearsal-001.md | Factual result after execution |
| frontend/src/shared/ids and Demo command construction | UUID-v4 LAN compatibility fix and tests |
| backend provider adapter, Demo preflight, and tests | Bounded provider failure and real CUDA inference readiness |
| scripts/demo launcher and documentation | Process-scoped isolated CUDA runtime configuration |
| External Demo configuration | Local-only values and secret references; never committed |

Bounded frontend, provider-adapter, Demo-preflight, and launcher corrections are authorized and
implemented. No dependency, migration, schema, API, authority, trust-boundary, database-data,
or global runtime-default change is planned.

## Data or migration considerations

No schema or migration is authorized. Use only an approved development/Demo database. Cleanup
may remove only data created by the rehearsal and identified by recorded Event, Stage, Session,
Operation, or command identities. Abort if ownership is uncertain. Migration reversal is not
normal rehearsal cleanup.

## Failure and recovery considerations

- Stop if any database identity, model revision, CUDA mode, source, LAN bind, or upstream identity
  differs from the approved configuration.
- Preserve failed Operation and bounded launcher output; do not hide failure by changing provider,
  model, device, compute type, or authority semantics.
- Stop only launcher-owned processes. Restart must use durable state, not browser/process memory.
- Abort cleanup if unexpected dependencies or non-rehearsal data appear.

## Observability requirements

Record versions, GPU/device/compute type, profile/deployment identity, loopback/LAN binds, Devcon
cache state, Session/package revisions, media lifecycle, Operation state, transcript evidence
provenance/timing/limitations, Moment lineage, restart outcome, and bounded failure codes. Never
record secret values, media paths, raw diagnostics, or unapproved transcript text.

## Test strategy

- Keep the merged backend/frontend/launcher validation as baseline.
- Run real launcher preflight and verify profile/model/CUDA/loopback/LAN facts, including an actual
  silent-audio CUDA inference before readiness.
- Exercise real Devcon offline cache and controlled vMix discovery/association.
- Exercise the real worker, transcript projection, controls, restart, and Mac UI.
- Run secret/privacy checks and git diff --check for evidence-document changes.

## Acceptance criteria

- [x] Frontend UUID-v4 generation supports native randomUUID and a cryptographic
  getRandomValues-only fallback, including Demo command operation IDs.
- [x] Provider-originated IndexError is bounded at immediate and lazy execution boundaries; the
  existing max-attempt policy applies and the worker continues polling.
- [x] External config, Demo DSN, exact model revision, controlled media, vMix output, and LAN
  identities are verified without secret or private-path disclosure.
- [x] The real Razer stack starts with backend/PostgreSQL loopback-only and Next.js reachable from
  the trusted Mac.
- [ ] Real Devcon Program Expectations remain External and visible from cache while offline.
- [x] Controlled vMix media reaches safe Session association, durable Operations, and three real
  CUDA/float16 Transcript Evidence revisions; one later provider failure is preserved separately.
- [ ] The Mac UI shows bounded evidence and attributable controls without persistence, path/secret
  exposure, or Devcon write capability.
- [ ] Restart reconstructs important Session/media/Operation/evidence/Moment state.
- [ ] Accented/noisy non-customer samples are evaluated without an automatic broader claim.
- [ ] A factual result distinguishes rehearsal success from production or Event certification.

## Rollback or reversal

Stop only launcher-owned processes, preserve evidence, and remove only recorded rehearsal-owned
database rows or non-customer artifacts. Do not reverse migration 0008, delete unrelated state,
or alter production. Revert documentation-only commits if the plan is abandoned.

## Open questions

- Which approved representative accented/noisy non-customer corpus will complete the scoped model
  qualification?
- Which remaining Mac workflow, offline-cache, and restart/reconstruction steps will be captured in
  the factual completion result?

## Completion record

- Implemented revision:
- Files and migrations actually changed:
- Commands and tests actually run:
- Results and warnings:
- Execution authority used: Green autonomous rehearsal plus bounded compatibility correction.
- Approved deviations:
- Rollback status:
- Remaining work:
