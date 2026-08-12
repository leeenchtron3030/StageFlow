# Real-Event Playback Validation and UX Calibration

## Status

Completed — bounded validation runner implemented and validated. Run 002 is accepted as
**PASS — Real-media Durable Event-Mode Kernel baseline**. Run 003 is **INVALID — intended
same-Stage turnover qualification not executed**, with a secondary conservatism
diagnostic pass. Run 004 is a partial qualification: lifecycle, preservation, and
accepted-policy conformance passed; content-correct automatic turnover association is
inconclusive/not qualified. These dispositions are not Event-readiness or
production-deployment approval.

## Execution authority

- **Classification:** Green autonomous for documentation and isolated, non-production
  validation against the accepted Durable Event-Mode Kernel.
- **Authority evidence:** Product Constitution Principles 2, 3, 8, 9, 11, 12, 16, 17,
  18, and 24; accepted ADR-0019 through ADR-0024; the
  [Durable Event-Mode Kernel architecture](../architecture/durable-event-mode-kernel.md);
  the [reference-node operations guide](../architecture/durable-kernel-operations.md);
  the [post-Kernel capability architecture](../architecture/post-kernel-capability-layer.md);
  and the user-authorized real-event validation objective.
- **Implementation-ready:** Yes for the bounded validation-only runner and an isolated
  current-Kernel replay after local media, paths, PostgreSQL, and vMix settings are
  supplied. Future worker, Candidate, Editorial, Assembly, and automation experiments
  are not implementation-ready.
- **Required escalation or approval:** None for this documentation or a reversible,
  isolated current-Kernel run. ADR-0025 remains required before worker coordination;
  ADR-0026 remains required before automatic authority; Packaging Asset identity remains
  unresolved before Assembly persistence. Production deployment, destructive database
  operations, machine-policy changes, or use of footage without appropriate rights need
  their own authorization.

## Related documents

- [Segment and media lifecycle](../architecture/segment-lifecycle.md)
- [Session lifecycle](../architecture/session-lifecycle.md)
- [Persistence boundary](../architecture/persistence.md)
- [Post-Kernel capability plan](post-kernel-capability-layer.md)
- [Event-Day UX Scenario Validation](../ux/event-day-scenario-validation.md)
- [Reference-corpus manifest example](../validation/reference-corpus-manifest.example.yaml)
- [Playback-run result template](../validation/real-event-playback-run-result-template.md)
- [Run 002 baseline result](../validation/results/real-event-playback-run-002.md)
- [Run 003 invalid-turnover result](../validation/results/real-event-playback-run-003.md)
- [Run 004 qualification-tooling hardening](run-004-qualification-tooling-hardening.md)
- [Run 004 partial-qualification result](../validation/results/real-event-playback-run-004.md)
- [Run 004 qualification closure](run-004-qualification-closure.md)
- [Historical Razer qualification](../reviews/durable-kernel-razer-qualification.md)

## Run 002 baseline disposition

Run 002 is the first successful real-media execution of the one-Session vMix experiment.
It preserved 20 physical MP4 blocks as 20 durable Candidates, 20 registered Completed
Media Assets, and 20 deterministic Session associations, with zero final stabilizing,
unresolved, or conflicting media and no media loss. Authoritative Presentation Start and
End, trailing-media assembly, Package Ready, human completion of package revision 1,
Session revision 4, and fresh startup reconstruction were all preserved.

The exact accepted statement, measurements, qualification findings, limitations, and UX
evidence are recorded in the
[sanitized Run 002 result](../validation/results/real-event-playback-run-002.md). This
validates current Kernel/media behavior and durability only. It does not validate the
visual Producer or Editorial UX or any post-Kernel AI, worker, Candidate Moment,
Assembly, automation, render, or delivery capability.

## Run 003 disposition

Run 003 did not execute the intended same-Stage turnover procedure. Program Expectations
A and B were created, but no Session was realized. The Kernel conservatively registered
35 MP4-backed Candidates as 35 Completed Media Assets, associated none, retained all 35
as unresolved with `no_safely_eligible_session`, and reported zero conflicts. Sixty
trailing cycles eventually completed.

The Codex host stopped waiting without terminating the child, later reconcile/checkpoint
operations overlapped it, and the child's late whole-document save overwrote their newer
external command entries. PostgreSQL reconciliation evidence retained the actual
operations. The sanitized
[Run 003 result](../validation/results/real-event-playback-run-003.md) is authoritative
for this invalid-run disposition. Run 003 is a bounded pass for preservation and
conservatism without Session authority, not a turnover success.

## Run 004 disposition

Run 004 preserved 49 physical MP4s as 49 durable Candidates and 49 registered assets.
Thirty-two were associated automatically with Session A; zero were associated
automatically with Session B; 17 remained unresolved with
`multiple_eligible_sessions`; zero were conflicting or stabilizing. This is the expected
accepted interval-less same-Stage policy, not an established policy defect.

The Run is **PASS** for same-Stage lifecycle execution with an authority timestamp-quality
caveat, **PASS** for preservation/conservative ambiguity, and **PASS** for accepted-policy
conformance. It is **INCONCLUSIVE / NOT QUALIFIED** for content-correct automatic turnover
association because B's real substantive start predates but is not recoverable from its
durable authority timestamp and the assets lack trustworthy content intervals. The
[sanitized Run 004 result](../validation/results/real-event-playback-run-004.md) is the
authoritative repository record of that disposition.

## Problem statement

At plan creation, StageFlow had closure-validated Kernel contracts and bounded synthetic
qualification but had not been exercised against representative event footage or vMix
rolling recording behavior. Run 002 now supplies the first bounded real-media evidence
for the implemented filesystem-to-Session path. Repeatable runs, including same-Stage
turnover, remain necessary for comparison and later intelligence/worker calibration.

The validation workflow must preserve media outside Git, separate observed results from
implementation claims, and avoid changing production ingestion semantics merely to make
testing convenient.

## Verified current behavior

The repository inspection for this plan established the following executable path:

| Concern | Verified current boundary | Operational consequence |
| --- | --- | --- |
| Event and Stage configuration | A version `1.0` TOML file defines one Event, Stages, absolute shallow source directories, extensions, bounds, Runtime identity, Event Mode, and stability parameters. PostgreSQL is supplied through an environment-resolved secret reference. | Configuration validates; it does not create durable Event/Stage authority. |
| Schema | `PostgresMigrationRunner.apply_event_mode_kernel_v1()` explicitly applies migrations `0001` through `0005`. | Migration is a separate maintenance action. Startup never auto-migrates. |
| Event/Stage authority | `KernelComponents.explicit_bootstrap(...)` idempotently creates or resolves the configured Business Event and Stages, composes the Runtime, and performs startup reconciliation. | Stable operation and actor IDs must be retained for intentional retry. |
| Program context | `DurableEventModeKernel.record_program_expectation(...)` can record planned title, speakers, Stage, and planned times. | A Program Expectation remains External context and does not realize a Session. |
| Session start/end | `start_session(StartSessionRequest(...))` realizes a human-authorized Session. `correct_session_boundary(..., boundary_kind="end")` declares the authoritative end. | No public mutation route or Producer control UI currently exposes these commands. |
| Discovery | `KernelComponents.run_media_cycle(...)` invokes one synchronous, shallow, bounded, read-only filesystem pass. | There is no watcher, poller, daemon, or scheduled scan loop. A caller must request each cycle. |
| Readiness | A cycle persists file snapshots/presence/read-access facts and evaluates the conservative readiness policy. Stability-derived readiness requires qualifying observations separated by `minimum_stable_seconds`. | A newly discovered or still-growing file remains stabilizing. Normally at least two cycles are needed after a block closes. |
| Registration | `safe_to_read` produces and registers a Completed Media Asset by reference, then emits stable ingress. | StageFlow does not copy, decode, checksum, concatenate, transcode, or delete media. |
| Association | Registration records `associated`, `unresolved`, or `conflict`. A single structurally and temporally eligible Session can be selected deterministically. | Filesystem-derived assets currently lack probed media start/end intervals. During same-Stage turnover, interval-less media may correctly remain unresolved. |
| Package state | Session membership and package revision are durable. `mark_package_ready(...)` is an explicit application call that requires an authoritative Presentation End; `complete_package(...)` is an attributable human decision for one revision and enforces the same end guard. | The Kernel does not build an Assembly or output media package. “Package” in this run means the authoritative Session media-membership revision. The current Kernel does not require non-empty membership or gate readiness on every unresolved/conflicting/stabilizing asset. |
| Producer status | `GET /api/v1/kernel/status` reports bounded Event, Stage, recent Session/media, package, association, source, reconciliation, and attention state. | HTTP is read-only. The current Next.js shell is not a Producer workflow. |
| Recovery | Startup reconstructs PostgreSQL authority and runs a bounded source reconciliation. Same-process PostgreSQL recovery requires explicit reconciliation. | Ready means PostgreSQL is reachable and reconciliation is fresh; database availability alone is insufficient. |
| Existing harnesses | Kernel tests and `backend/tests/qualification/durable_kernel_razer.py` demonstrate application composition, synthetic media, migrations, restart, recovery, and bounded endurance. The validation-only `backend/tests/qualification/real_event_playback.py` now supplies explicit finite subcommands and external run records for real-event replay. | The historical Razer harness remains synthetic/scenario-specific. The new runner is not production code, a watcher, or a public control surface. |

There is currently no supported upload endpoint, public Session command API, automatic
media-cycle scheduler, media-duration/timecode probe, Candidate persistence,
transcription worker, Assembly, or operational Producer UI. The validation runner is an
internal qualification CLI over existing application boundaries.

## Desired outcome

StageFlow operators can run the same representative footage repeatedly in two modes:

1. direct controlled arrival of already closed media; and
2. real-time vMix playback into approximately 60-second recording blocks.

Each run records exact corpus identity, replay configuration, current-Kernel timestamps
and outcomes, restart behavior, UX-calibration observations, limitations, and links to
the Event-day scenario contract. Later capability runs reuse the same source and ground
truth without converting annotations into authoritative runtime Candidate records.

## In scope

- A small external reference corpus and repository-held human annotations.
- Direct and vMix replay procedures against an isolated current Kernel.
- Current Kernel measurement definitions and result recording.
- UX calibration observations and Event-day scenario linkage.
- Placeholders for later workflow-latency, Moment, worker, and coexistence evaluation.
- A bounded validation-only caller under `backend/tests/qualification/` that invokes
  existing application methods through explicit subcommands.

## Out of scope

- Committing footage, transcripts containing sensitive content, credentials, or raw
  provider payloads.
- Production ingestion changes, public command APIs, watchers, polling services, or
  unbounded loops.
- Frontend implementation or claims about current Mission Control usability.
- AI workers, transcription, Moment generation, Candidate persistence, Editorial Clip,
  Assembly, rendering, automation, publishing, or delivery.
- vMix/NDI/SDI control, recorder control, production deployment, destructive database
  resets, or Event-readiness certification.

## Constraints

- **Sessions, not files:** rolling blocks remain storage artifacts. Validation evaluates
  their contribution to one continuous Session timeline and package revision.
- **Authority:** Program Expectations and annotations are references. Human Session
  commands remain authoritative; machine association remains categorical and
  explainable.
- **Preservation:** source media, registered assets, associations, package revisions,
  decisions, and run evidence are never silently deleted or rewritten.
- **Offline/event mode:** the current-Kernel run uses local or mounted storage and local
  PostgreSQL without continuous Internet dependency.
- **Data handling:** the operator must have appropriate rights to use the footage.
  Large media and machine-local path mappings remain outside Git.
- **Reversibility:** use a dedicated validation database and directory. Never reverse
  Kernel migrations against shared or operational data merely to reset a run.

## Reference-corpus recommendation

Start with three to six recordings, not a large dataset. One recording may satisfy
multiple categories.

| Category | Minimum useful characteristic | Primary validation purpose |
| --- | --- | --- |
| Straightforward talk | Clean substantive start/end; one primary speaker | Baseline Session, registration, association, and package behavior |
| Talk with Q&A | Q&A clearly belongs to the presentation | Substantive end and future Candidate context |
| Panel or multiple participants | Several voices/participants | Future participant display and speaker uncertainty |
| Difficult Session start | Introduction, setup, delayed slides, or speaker present before substance | Human boundary semantics |
| Same-Stage turnover | Adjacent Sessions with ordinary transition ambiguity | Association, unresolved ownership, and package revision behavior |
| Editorially rich Session | Several human-selected verbal, visual, reaction, announcement, or Q&A Moments | Future Candidate and Editorial regression benchmark |

Recommended first corpus:

- one 30–60 minute straightforward talk that also contains several useful Moments;
- one talk with Q&A or a difficult start; and
- two adjacent same-Stage Sessions for turnover.

## Media and annotation storage model

Store footage in a human-controlled location outside the repository, for example:

```text
<external-corpus-root>/
  <corpus-item-id>/
    source/
    prepared-blocks/       # optional, still outside Git
    local-run-notes/       # may include machine-specific paths
```

The repository stores only:

- a human-readable manifest based on
  [the example](../validation/reference-corpus-manifest.example.yaml);
- source characteristics and stable external identifiers;
- checksums when policy and file size make them practical;
- source-relative and Session-relative ground truth;
- human Moment annotations and rationale;
- non-sensitive validation results; and
- references to externally retained screenshots or evidence.

Do not put an absolute local media path in the committed corpus manifest. Map the
manifest's `path_alias` to an absolute local path in an untracked operator run sheet or
environment-specific configuration. Do not copy media under `docs/validation/`.

### Annotation rules

- Identify offsets as integer milliseconds from a named origin.
- `source_offset_ms` is measured from the source recording's beginning.
- `session_offset_ms` is measured from the annotated substantive Session start and may
  be negative for introductions/setup.
- Expected substantive start/end are ground truth for evaluation, not runtime commands.
- Human reference Moments are evaluation labels, not StageFlow Candidate IDs.
- Each Moment records anchor, preferred range, rationale, optional importance, and one
  or more categorical kinds.
- Record uncertainty explicitly rather than fabricating precision.

## Validation modes

### Mode 1 — direct controlled media

Use this mode to validate configuration, identity, readiness, registration, association,
package reconstruction, and restart without real-time playback.

1. Use an empty, dedicated StageFlow source directory.
2. If the source is already a finalized supported media file, copy it into a staging
   directory outside the configured source.
3. For controlled arrival, copy to a suffix excluded by discovery, such as `.partial`,
   then rename to the final allowed extension only after the copy closes. The copy/rename
   harness remains outside production architecture.
4. Invoke one bounded media cycle to discover/observe the file.
5. Wait at least the configured stability interval without changing the file, then
   invoke another bounded cycle.
6. Record readiness, registration, ingress, association, and status outcomes.

A single long file validates the path but does not reproduce rolling-block cadence. For
arrival/replay testing without vMix, use already prepared closed blocks and release one
block at a time. Do not add a media splitter to StageFlow.

### Mode 2 — vMix rolling replay

Use vMix as the recorder-behavior simulator:

```text
external reference recording
  -> vMix input/playback at recorded speed
  -> vMix recording output in approximately 60-second blocks
  -> configured StageFlow source directory
  -> caller-triggered bounded Kernel media cycles
  -> durable registration, association, package, and status evidence
```

StageFlow continues to observe filesystem artifacts only. No NDI/SDI integration or vMix
control is required.

## vMix configuration assumptions

Record the exact installed vMix version and the actual setting labels used; do not infer
them from this document. The run assumes:

- input is the exact identified source recording;
- playback is `1.0x` unless a deliberately varied run says otherwise;
- output uses a supported final extension (`.mov`, `.mp4`, `.mxf`, `.mkv`, or `.wav`
  when allowed by the deployment configuration);
- segment duration is targeted at approximately 60 seconds and actual close times are
  measured rather than assumed;
- codec, container, resolution, frame rate, audio layout, and encoder mode are recorded;
- the output directory is a dedicated absolute path bound to the intended Stage;
- filename pattern produces unique, deterministically ordered block names;
- temporary/in-progress naming behavior is recorded;
- recording closes each block before StageFlow is expected to declare it stable; and
- vMix and StageFlow clocks are synchronized closely enough for wall-clock measurement,
  with the observed offset recorded.

The first experiment does not certify that a Razer can safely run vMix and future GPU
workers together.

## Required local inputs from the human

Before the first run, supply or confirm:

- lawful access to one 30–60 minute source recording and its corpus item ID;
- the recording's absolute local path, kept outside Git;
- a dedicated empty vMix/StageFlow output directory outside Git;
- installed vMix version and available rolling-recording settings;
- chosen codec/container and approximately 60-second split configuration;
- an isolated PostgreSQL DSN supplied only through the configured environment secret;
- a version `1.0` Kernel TOML outside source control with a unique validation Event key,
  one Stage, one source binding, allowed extensions, bounds, and stability interval;
- stable actor and operation IDs for bootstrap, Session start/end, media correction, and
  package completion, retained in the private run sheet;
- human annotations for substantive Session start/end, at minimum;
- the repository validation runner invoked from `backend/`; and
- a result artifact created from the repository template with secrets and absolute paths
  omitted.

## Bounded caller requirements

There is no public mutation API or general replay CLI. The smallest execution path is a
local, non-production caller modeled on the existing qualification harness. It should:

1. load the external TOML and environment-resolved DSN;
2. use `PostgresMigrationRunner` only in an explicit isolated maintenance step;
3. create `KernelComponents` and call `explicit_bootstrap`;
4. record an optional Program Expectation without treating it as Session truth;
5. call `start_session` with the human authoritative start;
6. request `run_media_cycle` at an explicit bounded interval and maximum count;
7. support manual cancellation without altering source files;
8. call the human end-boundary command, run final bounded cycles, explicitly mark the
   package ready, and record the human completion decision;
9. serialize only non-sensitive measurements/results; and
10. stop without reversing migrations or deleting media/database history.

The user-authorized bounded runner task implements this caller under validation tooling.
It must remain an explicit finite command surface, require isolated-database
acknowledgement for database-affecting commands, keep its run/result file outside the
repository, retain operation identities, and never become a watcher or production
ingestion service.

### Runner implementation scope and acceptance

- **Expected code:** `backend/tests/qualification/real_event_playback.py` and focused
  tests only; production packages remain unchanged.
- **Command shape:** explicit `initialize`, `migrate`, `bootstrap`, optional expectation,
  Session start/end, one or bounded repeated cycles, package-ready/completion, status,
  assignment, and fresh-process reconstruction commands.
- **State:** one local JSON run record with a generated Markdown summary; operation IDs
  are retained and may be explicitly supplied/reused.
- **Safety:** mutating/reconciling commands refuse to run without an explicit isolated
  validation-database acknowledgement, and the local run record is refused inside the
  repository.
- **Bounds:** repeated cycles require a positive maximum count and bounded cadence;
  cancellation records a clean interruption.
- **Cadence semantics:** `--cycle-every-seconds` is a monotonic start-to-start target.
  When one synchronous cycle exceeds the interval, the next cycle starts immediately;
  cycles never overlap and the interval is not a post-completion delay. Compare recorded
  invocation times and durations to identify a missed requested cadence.
- **Tests:** configuration/state initialization, repository-output refusal, operation-ID
  retention/conflict, deterministic recording, bounded cycle behavior, and failure
  recording.

### Runner outputs and safety

The runner writes one machine-readable JSON run record and one Markdown summary with the
same basename. The `--run-file` must end in `.json` and must resolve outside the
repository. The output never stores the DSN or configured source path. Filenames are
omitted unless `initialize --include-filenames` is explicitly selected.

Every database-affecting or reconciling command requires
`--confirm-isolated-validation-database`. This is an explicit operator acknowledgement,
not proof that the database is isolated; the human must still supply an isolated DSN.
Commands are sequential. Do not run two commands against one run file concurrently.

Operation IDs are generated once and retained in the JSON record unless explicitly
supplied. Repeating a command label reuses the retained ID; a conflicting supplied ID is
rejected. Preserve the original command arguments when deliberately testing replay.

### Safe local controller implementation record

- **Execution classification:** Green. The controller is reversible qualification
  tooling over the accepted runner and does not add or change application or domain
  semantics.
- **Authority:** this plan's accepted isolated-validation workflow, the runner command
  contract above, and the user-authorized preparation for the same-Stage turnover run.
- **Objective acceptance:** one PowerShell entry point derives Run-specific external
  paths, generates the accepted one-Stage/one-source Kernel configuration, invokes only
  existing runner subcommands, presents a concise operator summary, records redacted
  environment metadata, refuses known unsafe combinations, and propagates failures.
- **Bounded scope:** non-production local validation only. No database creation,
  recorder control, watcher, scheduler, production runtime, public API, schema,
  migration definition, worker, queue, or frontend behavior is added.
- **Validation:** focused behavior tests cover path derivation, command construction,
  existing-run refusal, database-name/run mismatch, secret-safe failures, offline
  status interpretation, and child-command failure propagation; PowerShell parsing,
  relevant pytest, documentation links, and `git diff --check` are also required.
- **Implementation-ready:** Yes. All controller actions map to existing runner commands;
  unresolved product or architecture decisions are not required.
- **Completion:** Implemented under `scripts/validation/` with focused behavior tests,
  accepted-schema configuration validation, PowerShell parsing, static checks, link
  validation, and whitespace validation passing. Run 003 was later executed but is
  invalid for turnover because no Session was realized; fresh Run 004 has not begun.

### Exact first-run command sequence

For Run 003 and later, the repository's
[safe local validation controller](../../scripts/validation/README.md) is the preferred
operator entry point and preserves this sequence with additional Run-isolation guards.
The raw commands remain documented here as the underlying qualification contract.

Run from `backend/` in PowerShell. Replace placeholders with external paths and make the
environment variable name match the TOML's `postgres_dsn_secret_ref`.

```powershell
$validationRunner = "tests/qualification/real_event_playback.py"
$validationConfig = "C:\external\stageflow-validation\kernel.toml"
$validationRun = "C:\external\stageflow-validation\run-001.json"
$env:STAGEFLOW_VALIDATION_DSN = "<isolated-validation-postgresql-dsn>"

uv run python $validationRunner initialize --config $validationConfig --run-file $validationRun --mode vmix --corpus-item "reference-main-001" --source-assumption "playback_rate=1.0x" --source-assumption "segment_duration=approximately_60_seconds"
uv run python $validationRunner migrate --config $validationConfig --run-file $validationRun --confirm-isolated-validation-database
uv run python $validationRunner bootstrap --config $validationConfig --run-file $validationRun --confirm-isolated-validation-database
uv run python $validationRunner expectation --config $validationConfig --run-file $validationRun --confirm-isolated-validation-database --key "reference-main-001" --title "Reference Main Session" --stage-key "main"
uv run python $validationRunner start-session --config $validationConfig --run-file $validationRun --confirm-isolated-validation-database --session-label "main" --stage-key "main" --expectation-key "reference-main-001" --at now
uv run python $validationRunner drive-cycles --config $validationConfig --run-file $validationRun --confirm-isolated-validation-database --cycle-every-seconds 2 --max-cycles 1800 --scope "validation-live"
```

Start vMix recording before or immediately after `start-session`, according to the
annotated substantive boundary. The driver is finite. At the human-selected Session end,
press `Ctrl+C`; the driver records a clean interruption and saves completed cycle
results. Then continue sequentially:

```powershell
uv run python $validationRunner end-session --config $validationConfig --run-file $validationRun --confirm-isolated-validation-database --session-label "main" --at now --reason "human_confirmed_substantive_end"
uv run python $validationRunner drive-cycles --config $validationConfig --run-file $validationRun --confirm-isolated-validation-database --cycle-every-seconds 2 --max-cycles 60 --scope "validation-trailing-media"
uv run python $validationRunner status --config $validationConfig --run-file $validationRun --confirm-isolated-validation-database
uv run python $validationRunner package-ready --config $validationConfig --run-file $validationRun --confirm-isolated-validation-database --session-label "main"
uv run python $validationRunner complete-package --config $validationConfig --run-file $validationRun --confirm-isolated-validation-database --session-label "main" --approve --reason "human_reviewed_validation_membership"
uv run python $validationRunner status --config $validationConfig --run-file $validationRun --confirm-isolated-validation-database
uv run python $validationRunner ux-note --config $validationConfig --run-file $validationRun --field "media_cadence_noisy" --answer "<human observation>"
uv run python $validationRunner record-stop --config $validationConfig --run-file $validationRun --at now --reason "fresh_process_reconstruction_check"
uv run python $validationRunner reconstruct --config $validationConfig --run-file $validationRun --confirm-isolated-validation-database
```

Before playback, verify that the configured `[[event.stages.sources]].path` resolves to
the exact directory where vMix is writing this run. Before `package-ready`, verify the
preceding `end-session` command succeeded and `status` shows `presentation_ended` with a
non-null `authoritative_end`. The authoritative application guard rejects package review
readiness and completion while the presentation remains active.

`reconstruct` creates a fresh Kernel composition, runs the existing startup source
reconciliation, captures the recovered status, and uses the most recently recorded stop
time unless `--stop-at` is explicitly supplied. The runner never stops PostgreSQL,
StageFlow, or vMix itself.

To reference a manifest, add `--corpus-manifest
"..\docs\validation\corpora\<manifest>.yaml"` to `initialize`. The file must exist;
only a repository-relative reference or an external basename is recorded.

### Explicit identity and optional correction

`initialize --actor-id <uuid>` and the human commands' `--operation-id <uuid>` options
allow predetermined identities. If omitted, the runner generates and retains them once.
For a deliberate existing-authority correction, use:

```powershell
uv run python $validationRunner assign-asset --config $validationConfig --run-file $validationRun --confirm-isolated-validation-database --asset-id "<registered-asset-uuid>" --session-label "main" --reason "human_validated_assignment"
```

The command calls the existing attributable human assignment boundary; it does not
inject an expected association into policy.

## Current-Kernel measurement model

Use timezone-aware UTC instants for recorded wall-clock measurements. Preserve each
meaning rather than collapsing them into one “ingest latency.”

| Measurement | Start | End | Current evidence source / qualification |
| --- | --- | --- | --- |
| Block close estimate | vMix-reported close, recorder log, or observed final modification time | Same instant | Filesystem modification time is only a proxy unless vMix provides a close event. |
| Discovery delay | Block close estimate | durable candidate `discovered_at` | Includes caller cycle cadence. |
| Stabilization/readiness delay | First durable observation | readiness evaluation yielding `safe_to_read` | Depends on `minimum_stable_seconds` and cycle cadence. |
| Registration delay | `safe_to_read` evaluation | Completed Media Asset `registered_at` | Direct synchronous boundary in the cycle. |
| Candidate inspection race | one bounded inspection begins | inspection outcome | `candidate_replaced_during_observation` is typed transient evidence that the file changed across the open/read/stat check; retain the Candidate and retry a later bounded cycle. Other `OSError` results remain generic unless safely classified. |
| Association outcome/time | Asset registration | association `decided_at` | Record categorical outcome, authority, reasons, policy, and inputs. |
| Session association coverage | Expected block set | associated/unresolved/conflict counts | Never infer correctness from count alone. |
| Package-ready time | authoritative Session end or last relevant block close | explicit `mark_package_ready` result time captured by caller | Current code exposes an explicit transition, not automatic Assembly. |
| Package completion time | package-ready projection | human `complete_package` decision time | Applies to one package revision. |
| Restart reconstruction | process stop/start | fresh reconciliation completes and status is ready | Compare stable Event/Stage/Session/media IDs and counts before/after. |
| Reconciliation recovery | reconciliation start | completed/failed result | PostgreSQL availability alone is not readiness. |
| Human authority occurrence | operator declaration accepted by qualification agent | explicit Start/End `-At` value | Capture at controller entry before guards/runner startup. Keep occurrence, request/decision, and database commit times distinct. |

Also record every cycle's requested time, scope, candidates seen, assets registered,
source failures, per-candidate outcome, and duration measured by the caller. Current
Kernel measurements do not establish transcription, intelligence, Editorial, render, or
end-to-end workflow latency.

## First experiment — one straightforward Session

### Purpose

Prove the smallest repeatable real-media path without worker or AI complexity.

### Procedure

1. Complete the corpus manifest and substantive start/end annotation for one 30–60
   minute straightforward Session.
2. Create an isolated PostgreSQL database and apply migrations `0001`–`0005` explicitly.
3. Create the external Kernel TOML with one Event, one Stage, and the dedicated empty
   vMix output directory.
   Confirm the configured source path exactly matches the directory vMix will write.
4. Bootstrap Event/Stage authority with retained operation and actor IDs.
5. Optionally record the Program Expectation, visibly classified as External.
6. Start the realized Session at the annotated substantive start during vMix playback.
7. Play the exact source at `1.0x` and record approximately 60-second blocks into the
   configured directory.
8. Invoke bounded media cycles throughout playback. Ensure each closed block receives
   observations separated by at least the configured stability interval.
9. Declare the authoritative Session end at the annotated substantive end. Included Q&A
   remains inside the boundary.
   Confirm the command succeeded and status reports `presentation_ended` with a non-null
   `authoritative_end` before attempting package readiness.
10. Continue bounded cycles until all expected closed blocks are registered or a
    documented unresolved/failure condition remains.
11. Review association outcomes and correct only through the existing attributable
    human assignment boundary where the experiment explicitly calls for correction.
12. Explicitly mark the current Session package revision ready, review membership, and
    record the human completion decision. Do not describe this as Session Assembly.
13. Capture `/api/v1/kernel/status` and read-only PostgreSQL evidence.
14. Stop and restart StageFlow against the same database, configuration, and source.
15. Wait for fresh startup reconciliation; confirm stable identities, membership,
    package revision/completion history, and no duplicate assets or ingress effects.
16. Complete the run-result template, including deviations and UX observations.

### Pass conditions

- Every expected block is preserved as a candidate and either registered or carries a
  specific explainable non-registration result.
- Registration occurs only after `safe_to_read`.
- Every registered block has one categorical association outcome and durable provenance.
- One active Session receives the expected safe associations; ambiguity is not hidden.
- The human end and package-completion decisions are preserved for the correct revision.
- Restart reconstructs the same Event, Stage, Session, media, association, and completion
  identities, then reaches ready only after fresh reconciliation.
- Source files are unchanged by StageFlow.

## Second experiment — same-Stage turnover

Use two adjacent real Sessions from the same Stage, preferably with ordinary transition
content between them.

1. Start Session A and replay its rolling blocks.
2. Declare Session A ended, but leave its package assembling.
3. Start Session B on the same Stage while late/turnover blocks can still arrive.
4. Continue bounded media cycles through the transition.
5. Record which interval-less blocks associate safely and which remain unresolved.
6. Resolve only the deliberately selected cases through attributable human assignment.
7. Verify that Session A and Session B retain separate package membership and revisions.
8. Complete each package independently, then test one delayed relevant block if safe.
9. Confirm that material late membership reopens the affected completed package revision
   and preserves the earlier completion snapshot/history.
10. Record Stage Detail, Work Queue, boundary, and block-visibility implications without
    claiming those interfaces exist.

This experiment specifically tests the accepted behavior that an interval-less block is
not automatically assigned during same-Stage turnover merely because Session B is
currently active.

Run 004 executed the authority/ingest portion through first observation but intentionally
did not assign assets or advance packages. It passed lifecycle, preservation, and
accepted conservative-policy behavior. Content-correct association remains unqualified
because qualification-agent latency delayed B's durable start and no asset had a
trustworthy content interval. Future live declarations must invoke the controller as the
first action so `-At now` is captured at controller entry and forwarded explicitly.

## Controlled live-simulation variants

After the first two baseline runs are repeatable, vary one condition per run:

| Variant | Safe method | Expected observation |
| --- | --- | --- |
| Delayed block | Hold one finalized block outside the configured directory, then release it later | Late registration/association and package-revision consequence |
| Source interruption | Stop and resume vMix output without deleting prior blocks | Source/media cadence gap; no inferred Session end |
| Source directory unavailable | Use only an isolated validation binding and a reversible move/unmount procedure approved for that directory | Other state preserved; affected reconciliation fails/degrades and later recovers |
| Process restart | Stop StageFlow between cycles and restart against the same DB/source | Fresh reconciliation and stable identity |
| Client disconnect, later | Disconnect only a future Producer client while backend remains healthy | Client stale gating, not backend failure |
| Worker loss, later | Stop only a future intelligence worker while Kernel ingest continues | Intelligence delay, not production failure |

Do not perform destructive machine, database, or source-media changes for fault testing.

## UX calibration observations

Current runs can collect evidence for future UX density even though the Producer and
Editorial interfaces are not implemented:

- blocks per Session and observed close/arrival cadence;
- simultaneous stabilizing/ready/registered counts;
- turnover density and ambiguous ownership frequency;
- time from presentation end to last relevant registered block and package-ready action;
- how often an operator needs candidate/media-level detail;
- which Event/Stage/Session identity and boundary context must remain visible;
- whether approximately 60-second blocks need default row-level visibility or a collapsed
  Session summary with drill-down;
- attention-code frequency and whether healthy updates would create noise;
- human command timing at the application boundary, clearly separated from future UI
  interaction time; and
- observations mapped to the existing visual, shared-state, Producer, Editorial, and
  cross-role specifications.

Do not claim current Mission Control click time, keyboard efficiency, Editorial queue
behavior, or `Mark Moment` speed. Those require their actual read models and interfaces.

## Event-day scenario linkage

Every result names the tested scenario sections from
[the UX validation specification](../ux/event-day-scenario-validation.md):

| Validation run | Primary scenario linkage |
| --- | --- |
| Normal one-Session playback | Scenario A — normal multi-Stage/normal-operation baseline, scoped to one Stage |
| Same-Stage turnover | Scenario B |
| Producer mark, later | Scenarios C and D |
| Worker stop or increasing intelligence lag, later | Scenarios E and F |
| Package correction/reopen | Scenario N |
| Boundary exclusion of a Candidate, later | Scenario O |
| Event closeout | Scenario Y |

The run result supplies evidence for a scenario. It never rewrites a scenario into an
implementation claim or marks the overall UX validated from one playback.

## Future workflow-latency measurement

Once the relevant durable capabilities exist, record this chain with distinct aware
timestamps and stable subject/input revisions:

```text
important content occurs
  -> media block closes
  -> candidate discovered
  -> media safe to read
  -> Completed Media Asset registered
  -> transcription artifact available
  -> Editorial Candidate Moment created
  -> Candidate eligible in Editorial queue
  -> Editorial opens Candidate
  -> Editorial approves/revises/rejects
  -> Editorial Clip available
  -> approved Assembly/render eligibility later
```

Call the end-to-end concept **workflow latency**. Report its components separately:
media availability, readiness, transcription, Candidate generation, queue delivery,
human review, Clip creation, and later render eligibility. Model/GPU execution time is
one diagnostic contributor, not a substitute for workflow latency.

## Future Moment evaluation

When Candidate persistence and generation exist, replay the exact same corpus revision
and compare automatic results with the human references. Report at least:

- reference Moments found, partially overlapped, and missed;
- useful Candidates outside the reference set;
- false or low-value Candidate volume;
- anchor and preferred-range error;
- Producer-mark relationship and priority effect;
- overlapping Candidate clusters without erasing durable identities;
- Editorial acceptance, rejection, defer, and range-adjustment rates;
- time to first useful Candidate and time to review; and
- results by Moment kind and Session category.

Do not compress these dimensions into one opaque confidence or quality score. Human
references remain evaluation evidence and do not become authoritative runtime Candidate
records.

## Future third and fourth experiments

### Third — Producer marks

After `Mark Moment` and Candidate persistence exist, replay a known Session, mark the
reference Moments during playback, verify Session-relative timing and provenance,
restart/reconstruct, and confirm the Editorial priority projection without treating a
Producer mark as Editorial approval.

### Fourth — transcription and machine Candidates

After ADR-0025 is accepted and transcription/Candidate generation exists, replay the
same corpus revision and measure transcription latency, Candidate latency and volume,
overlap with human references, and Editorial workflow latency. Keep worker performance,
workflow consequence, and Editorial delay distinct.

## Razer and vMix coexistence limits

Running vMix on the Razer for ingest simulation proves only that vMix can generate the
filesystem pattern observed during that run. It does not certify simultaneous future
worker execution.

Future coexistence qualification must separately measure:

- vMix CPU/GPU/encoder workload and dropped-frame/recording health;
- StageFlow worker CPU/GPU/VRAM workload;
- disk read/write throughput, queueing, and free-space behavior;
- thermal stability, throttling, and power behavior;
- media, transcription, and Candidate lag under load;
- bounded backlog recovery after pressure; and
- conference-representative duration.

Production recording/livestream health has priority. StageFlow may observe and reduce
its own optional work but must not control vMix, unrelated processes, OS resources, or
power policy. The earlier synthetic coexistence proxy and the present ingest simulation
are evidence of different things.

## Repository artifacts and result retention

Use `docs/validation/` for committed, non-media validation contracts and sanitized
results:

```text
docs/validation/
  README.md
  reference-corpus-manifest.example.yaml
  real-event-playback-run-result-template.md
  corpora/                         # future sanitized manifests only
  results/                         # reviewed sanitized completed results
```

Create `corpora/` or `results/` entries only when reviewed real values exist. Never
store footage, credentials, absolute private paths, raw database dumps, or sensitive
transcript content there.

## Test strategy for this documentation task

- Verify every current-capability claim against architecture, code, tests, or the
  historical qualification harness.
- Validate all changed-document relative links.
- Confirm the manifest example is UTF-8, human-readable, and contains no real media path,
  credential, or runtime Candidate identity.
- Confirm terminology distinguishes Candidate, Completed Media Asset, Session Package,
  Editorial Candidate Moment, and Assembly.
- Run `git diff --check` and deliberately review the qualification-tooling,
  focused-test, and documentation diff.

Run focused runner tests and the directly affected Kernel composition/status and durable
Kernel regressions. Run targeted Ruff and strict Pyright checks for the qualification
tooling. Frontend checks remain unnecessary because no frontend is changed.

## Acceptance criteria

- [x] The current Event/Stage/configuration/discovery/readiness/registration/Session/
  package/status path is explicitly separated from missing tooling and future capability.
- [x] Real media remains outside Git and repository-safe manifest/result conventions are
  defined.
- [x] All six requested corpus categories and a lightweight annotation format are
  represented.
- [x] Direct and vMix validation modes preserve production ingestion semantics.
- [x] The first and turnover experiments are repeatable and have bounded pass conditions.
- [x] Current Kernel, UX calibration, future workflow-latency, and future Moment
  measurements remain distinct.
- [x] Razer ingest simulation is not treated as future worker coexistence qualification.
- [x] Event-day scenario linkage accumulates evidence without creating implementation
  claims.
- [x] No production runtime capability, dependency, schema, migration, worker, Candidate,
  Assembly, automation, or frontend is added; the new caller remains under qualification
  tooling.
- [x] Run 002 completed the first one-Session real-media baseline with 20 registered and
  associated blocks, authoritative boundaries, package completion, and fresh
  reconstruction.
- [x] Record Run 003 as an invalid turnover execution without rewriting its external
  evidence or calling it a turnover success.
- [x] Preserve Run 004 as a partial same-Stage turnover qualification with lifecycle,
  preservation, and policy-conformance passes and content-correct association explicitly
  inconclusive/not qualified.
- [x] Capture qualification Start/End `now` timestamps at controller entry and include
  safe shallow source entries in DriveCycles runtime telemetry.

## Rollback or reversal

This task adds independently reversible qualification tooling, focused tests, and
documentation. Removing the runner/tests and reverting the documentation/index links
reverses the repository change without touching production code. A real validation run
must preserve its media and PostgreSQL history unless an authorized operator deliberately
disposes of the isolated environment. Migration reversal is never a routine run reset.

## Open questions and execution gates

These are remaining run inputs or calibration questions:

- Which exact corpus recording and manifest revision should be used for any repeat run?
- What vMix version, format, encoder, and split behavior will be retained or deliberately
  varied for that experiment?
- What bounded cycle interval balances observation detail against unnecessary churn?
- Are individual 60-second blocks normally visible, summarized, or shown only on demand?
- What evidence is sufficient for an operator to declare each turnover package ready?
- Which additional environment and cadence metadata should be mandatory in a repeat run?

Changing predecessor automatic eligibility when a same-Stage successor begins is not a
calibration question. It is a Yellow Session/media-association decision involving
trustworthy media intervals, overlap handling, re-evaluation, and package consequences;
it is intentionally deferred.

The first real-media baseline is complete, Run 003's invalid attempt is preserved, and
Run 004 is preserved as the partial qualification above. Any repeat must use a fresh Run
number, database/configuration, media, and explicit Session authority. This status is not
production or Event readiness.

## Completion record

- **Implemented revision:** Working tree implementation; no commit was requested.
- **Files and migrations actually changed:** The validation-only runner, focused runner
  tests, this plan, and the validation/plan indexes. Earlier uncommitted corpus/template
  and bounded architecture/UX documentation remain present but are not implementation
  changes made by this runner task. No migration changed.
- **Commands and tests actually run:** Direct runner `--help`; focused pytest, Ruff, and
  strict Pyright checks; the focused runner tests together with the existing Kernel
  composition/status and durable-Kernel suites; relative-link, terminology, encoding,
  sensitive-content, and scope checks; and `git diff --check`.
- **Results and warnings:** The direct runner entry point works. The focused suite passes
  with 12 tests; Ruff passes; strict Pyright reports zero errors and warnings. The combined
  regression run passes with 49 tests, 6 PostgreSQL-dependent skips, and one existing
  Starlette/httpx deprecation warning. Documentation/link/encoding/safety checks and
  `git diff --check` pass. Frontend checks were skipped because no frontend changed; the
  full backend suite was skipped in favor of focused runner and directly affected Kernel
  regressions.
- **Execution authority used:** Green validation tooling under accepted Kernel
  architecture and the user-authorized objective.
- **Approved deviations:** None.
- **Rollback status:** Qualification tooling and documentation changes are independently
  reversible; no validation database or external media cleanup was performed.
- **Run 002 execution closure:** The first vMix-backed real-media experiment is retained
  as **PASS — Real-media Durable Event-Mode Kernel baseline** in the sanitized
  [Run 002 result](../validation/results/real-event-playback-run-002.md). The external
  database, media, result record, and corpus remain preserved outside this repository.
- **Closure documentation:** The sanitized result, validation/plan indexes, this runbook,
  and the project brief were updated. No production code, dependency, schema, migration,
  runtime configuration, worker, watcher, scheduler, queue, provider, or frontend changed
  in the closure task.
- **Remaining work:** Preserve Run 004 and use the immediate-capture/source-aware
  qualification procedure for later runs. Investigate stale durable `running`
  reconciliation status after interruption separately.
  Production control surfaces, watching, and automatic Session/package authority remain
  out of scope.
