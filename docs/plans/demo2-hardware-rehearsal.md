# Demo 2 hardware rehearsal

## Status

Executed 2026-08-26 — **PARTIAL QUALIFICATION**. Seven of ten acceptance criteria
passed; criteria 4, 6, and 7 were not exercised and are recorded as not qualified. Demo 2
is **not promotion-qualified**; PR #71 remains draft. See the
[Run 001 result](../validation/results/demo2-hardware-rehearsal-001.md).

## Execution authority

- Classification: Green autonomous rehearsal plus bounded compatibility correction, same
  pattern as the completed [Demo 1 hardware rehearsal](demo-hardware-rehearsal.md).
- Authority evidence: PR #71's own qualification status ("Demo 2 is not
  promotion-qualified. The remaining gate is a fresh two-machine live rehearsal covering
  automatic media progression, real CUDA evidence, human workflow, and durable restart
  reconstruction."); the completed Demo 1 hardware rehearsal and
  [Demo rehearsal controller](demo-rehearsal-controller.md); ED-0063's
  [Demo 2 rebase and coordinator exception safety net](demo2-rebase-and-coordinator-safety-net.md),
  whose own out-of-scope line explicitly deferred "anything from the still-pending live
  two-machine rehearsal gate" to this plan; ADR-0022 through ADR-0025 and ADR-0027; and
  the explicit 2026-08-24 user request to prepare a real Demo 2 rehearsal on this machine
  (Wenceslas) paired with the user's Mac, reusing the same simulated-recording approach
  and Devcon test API already qualified for Demo 1.
- Implementation-ready: Yes for the bounded rehearsal, evidence capture, and any
  demonstrated Green compatibility correction. No product-capability expansion is
  authorized.
- Required escalation or approval, if any: stop for any proposed production code,
  dependency, schema, migration, public contract, authority-semantic, trust-boundary, or
  Devcon-write change beyond what this plan and the existing controller already approve.
  A real Devcon PUT remains gated by `scripts/demo/StageFlow-Demo.ps1 publish-devcon`'s
  existing package-approved, identity-checked, digest-bound, explicit human confirmation
  — this plan changes none of that gate. **PR #71 must remain draft and must not merge
  regardless of rehearsal outcome**; that is PR #71's own stated condition, not a
  decision this plan makes or reopens.

## Related findings or ADRs

- Finding/disposition: PR #71 ("Demo 2: Autonomous Event Node candidate") is open,
  CI-green, and code-complete — it adds the bounded autonomous coordinator, default-off
  5-second media reconciliation and 120-second Devcon Program GET reconciliation, shared
  automatic/manual media processing with stable transcription Operation identity,
  corrected worker identity/availability/capacity/GPU-readiness projection, audited
  exact-revision Package Approval, and deterministic unresolved-association-lifecycle
  reevaluation limited to material Session identity/revision changes. Its own body states
  the sole remaining gate is this rehearsal.
- Finding/disposition: association reevaluation is recorded in PR #71's body as "a
  separately approved Yellow semantic extension of the accepted association policy." That
  approval is not reopened, revisited, or re-litigated by this plan.
- ADR: ADR-0022 through ADR-0025, ADR-0027, ADR-0028 (Devcon external integration
  boundary).
- Engineering Directive: ED-0071. Builds on ED-0063 (safety net, implemented on PR #71),
  the completed Demo 1 hardware rehearsal, and the completed Demo rehearsal controller.

## Problem statement

Demo 1's Razer(Wenceslas)/Mac two-machine rehearsal already proved the real vMix
simulated-recording path, real CUDA transcription, the real Devcon test API/event, and
the guarded `scripts/demo/StageFlow-Demo.ps1` operator controller. Demo 2 adds an
autonomous coordinator on top of that same foundation — automatic (not manually
cycle-triggered) media and Devcon reconciliation, worker projection, and audited Package
Approval — but has only been validated by unit/integration tests and CI, never against
real hardware, real recording, or a real second machine. PR #71 cannot be considered
promotion-qualified, and must not merge, until that gap is closed with real evidence.

## Verified current behavior

- PR #71 (`codex/demo2-autonomous-event-node`) is `OPEN`, `isDraft: true`, and
  `MERGEABLE` against current `main` (confirmed during the ED-0070 repository
  consistency closure: remote head `9c176d4` merge-simulates cleanly against main
  `e81b609` and later).
- Demo 1's hardware rehearsal already qualified, on this exact Razer/Wenceslas host: an
  NVIDIA GeForce RTX 3080 Ti Laptop GPU with a working CUDA/float16 faster-whisper
  inference path, a working vMix installation, a loopback-only backend with a LAN-bound
  Next.js UI reachable from the Mac, and a real Devcon test Session/event
  (`test-devcon-8`) reachable through the existing narrow authenticated GET/PUT adapter.
- The Demo rehearsal controller (`scripts/demo/StageFlow-Demo.ps1`: `prepare`, `start`,
  `status`, `diagnose`, `stop`, `rehearsal-report`, `publish-devcon`) already wraps exact
  database verification, config/CUDA/secret discovery, and the guarded publish workflow.
  It is Demo-version-generic infrastructure, not specific to Demo 1's coordinator code —
  reuse it as-is.
- Demo 2's autonomous coordinator, its 5-second media and 120-second Devcon Program GET
  reconciliation intervals, and the coordinator exception safety net (ED-0063: an
  unexpected cycle exception degrades status to `degraded` with a bounded failure code
  and keeps the loop alive rather than dying silently) exist only on the
  `codex/demo2-autonomous-event-node` branch, already checked out in the
  `tmp/demo2-worktree` worktree on this machine.
- The concrete external Demo configuration, Demo PostgreSQL secret, model revision, and
  media directory used for Demo 1 already exist outside this repository at Windows User
  scope on this machine. This plan reuses them; it does not request new ones.

## Desired behavior

Using the same Razer(Wenceslas)/Mac environment, the same real vMix simulated-recording
setup, the same real Devcon test API/event, and the same
`scripts/demo/StageFlow-Demo.ps1` controller already proven for Demo 1, run Demo 2's
branch through one full rehearsal that specifically exercises what Demo 1 could not:
autonomous (timer-driven, not manually cycle-triggered) media progression, autonomous
Devcon Program reconciliation, worker/deployment status projection, human Package
Approval performed from the Mac UI against an audited exact revision, and a coordinator
survival + durable restart/reconstruction check.

## In scope

- Check out `codex/demo2-autonomous-event-node` (already available in
  `tmp/demo2-worktree`) and rebase it onto current `main` if it has drifted since the
  ED-0070 closure's verification, resolving any conflict the same
  "main's merged side is canonical, keep Demo 2's unique additions" way ED-0063 already
  established — without force-pushing or merging PR #71 itself.
- Reuse Demo 1's exact external configuration, Demo database, model revision, media
  directory, and Devcon test event/credentials. Do not provision new ones.
- Explicitly enable the coordinator's default-off media and Devcon reconciliation
  intervals for the duration of this rehearsal only (a rehearsal-scoped configuration
  value, not a change to the shipped default).
- Run the full Demo 2 launcher/controller lifecycle: `prepare`, `start`, `status`,
  `diagnose`, and `stop`, plus `rehearsal-report`.
- Drive one real Session through vMix rolling-block simulated recording while the
  coordinator autonomously discovers, registers, and associates media without a manual
  per-cycle trigger.
- Observe the worker/deployment status projection reflect real GPU/CUDA/capacity state
  autonomously, not from a manual status call alone.
- Perform Package Approval from the Mac UI against the coordinator's audited exact
  revision (not by calling the API directly), and confirm the approval and any later
  publication follow the existing package-`complete` → `publish-devcon` gate unchanged.
- Deliberately induce one unexpected condition during a live cycle (e.g., a transient
  source interruption per the accepted controlled-live-simulation variants in
  [Real-Event Playback Validation](real-event-playback-validation.md)) and confirm the
  ED-0063 safety net degrades visibly and keeps running rather than dying.
- Stop and restart the launcher-owned stack mid-rehearsal and confirm the coordinator,
  Kernel, worker projection, and Session/media/package state reconstruct durably.
- Capture bounded evidence and correct only a demonstrated Green rehearsal blocker,
  exactly as Demo 1's rehearsal did for its UUID and provider-IndexError findings.

## Out of scope

- Merging PR #71. It remains draft regardless of this rehearsal's outcome; that decision
  belongs to the user, not this plan or its execution.
- New product features, providers, models, dependencies, schemas, migrations, APIs,
  authority semantics, or automatic/generic Devcon writes. A real bounded Devcon PUT is
  permitted only through the existing `publish-devcon` gate and a new explicit human
  confirmation at rehearsal time.
- Reopening or re-scoping the already-approved association-reevaluation Yellow extension.
- Changing the coordinator's shipped default-off reconciliation intervals outside this
  rehearsal's own scoped configuration.
- Broader Event-readiness, production-deployment, or production-data claims.
- Committing DSNs, credentials, model files, media, transcripts, raw provider payloads,
  or private local paths.

## Constraints

- Architecture and terminology constraints: Program Expectations remain External;
  Transcript Evidence remains non-authoritative; human commands remain explicit and
  attributable; association reevaluation only re-fires on material Session
  identity/revision change, never silently reassigns human or conflict-held membership.
- Compatibility constraints: exercise the merged/rebased Demo 2 branch without
  intentional contract changes.
- Offline/event-mode constraints: demonstrate autonomous local operation continuing
  correctly after Devcon sync, consistent with production having priority over AI/cloud
  connectivity.
- Security and data-handling constraints: backend/PostgreSQL remain loopback-only; only
  Next.js binds to the trusted Demo LAN reachable by the Mac; secrets and transcript
  content stay out of normal logs, reports, and browser storage.
- Reuse constraint: do not request, generate, or duplicate Devcon test credentials,
  DSNs, or model paths — the exact values already qualified for Demo 1 are the ones to
  reuse for Demo 2.

## Implementation approach

1. Rebase `codex/demo2-autonomous-event-node` onto current `main` if needed; confirm a
   clean `git merge-tree` simulation before touching anything else.
2. Run `scripts/demo/StageFlow-Demo.ps1 diagnose` against the existing external Demo 1
   configuration to confirm GPU/CUDA, vMix, Devcon test reachability, and the exact
   `stageflow_demo` database identity are all still valid on this machine.
3. Enable the coordinator's media and Devcon reconciliation intervals for this rehearsal
   run only, and start the launcher-owned stack (`prepare`, then `start`).
4. From the Mac, confirm LAN reachability to the Next.js UI and walk the worker/
   deployment status projection before any Session starts.
5. Start a real Session and begin vMix rolling-block recording at the qualified cadence;
   do not manually trigger media cycles — let the autonomous coordinator discover,
   stabilize, and register blocks on its own timer.
6. Confirm real CUDA/float16 transcription evidence is produced automatically as blocks
   register, without a manual per-block trigger.
7. Declare the Session's authoritative end; confirm the coordinator surfaces the resulting
   package state as an audited exact revision, then perform Package Approval from the
   Mac UI.
8. Induce one controlled live-simulation variant (e.g., a source interruption) mid-run and
   confirm the ED-0063 safety net degrades status visibly and the coordinator keeps
   attempting cycles rather than dying.
9. Stop only launcher-owned processes, then restart against the same database,
   configuration, and source; confirm fresh reconciliation reconstructs coordinator
   ownership, Session/media/package state, and worker projection identically.
10. Run `rehearsal-report`, record bounded evidence, and correct only a demonstrated Green
    blocker discovered live, following the same narrow-correction pattern Demo 1's
    rehearsal used for its UUID and provider-IndexError fixes.
11. Publish a factual result distinguishing passed, failed, unavailable, and unqualified
    facts. State explicitly whether Demo 2 is now promotion-qualified — that
    determination is evidence this plan produces, not a merge action this plan performs.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `docs/plans/demo2-hardware-rehearsal.md` | This plan (new) |
| `docs/validation/results/demo2-hardware-rehearsal-001.md` | Factual result after execution (new) |
| `codex/demo2-autonomous-event-node` branch | Rebased onto current `main` if drifted; no other change unless a Green blocker is demonstrated live |
| Bounded compatibility correction (if any) | Only if a real rehearsal blocker is demonstrated, following the Demo 1 rehearsal's narrow-correction precedent |
| External Demo configuration | Reused as-is from Demo 1; rehearsal-scoped reconciliation-interval override only; never committed |

## Data or migration considerations

No schema or migration is authorized. Use only the existing qualified Demo database.
Cleanup may remove only data created by this rehearsal and identified by recorded Event,
Stage, Session, Operation, or command identities. Abort if ownership is uncertain.
Migration reversal is not normal rehearsal cleanup.

## Failure and recovery considerations

- Stop if any database identity, model revision, CUDA mode, source, LAN bind, or Devcon
  test identity differs from the configuration already qualified for Demo 1.
- Preserve any failed Operation and bounded launcher/coordinator output; do not hide a
  failure by changing provider, model, device, compute type, or authority semantics.
- Stop only launcher-owned processes. Restart must reconstruct from durable state, not
  browser/process memory.
- If the coordinator's exception safety net does not degrade visibly and keep running
  under the induced failure, that is itself a rehearsal finding, not a blocker to
  suppress or work around.
- Abort cleanup if unexpected dependencies or non-rehearsal data appear.

## Observability requirements

Record versions, GPU/device/compute type, profile/deployment identity, loopback/LAN
binds, Devcon cache state, coordinator reconciliation cadence actually observed,
worker/deployment projection contents, Session/package revisions, media lifecycle,
Operation state, transcript evidence provenance/timing/limitations, the induced-failure
degradation and recovery, restart reconstruction outcome, and bounded failure codes.
Never record secret values, media paths, raw diagnostics, or unapproved transcript text.

## Test strategy

- Keep the merged backend/frontend/launcher validation from Demo 1 and Demo 2's own CI
  run as baseline; do not re-litigate what CI already covers.
- Run real launcher preflight and verify profile/model/CUDA/loopback/LAN facts, including
  an actual silent-audio CUDA inference before readiness (same as Demo 1).
- Exercise the real autonomous coordinator, not manual cycle calls, for media and Devcon
  reconciliation.
- Exercise the real worker/deployment projection, Package Approval UI workflow, induced
  failure/degradation, restart, and Mac UI.
- Run secret/privacy checks and `git diff --check` for evidence-document changes.

## Acceptance criteria

- [x] The Demo 2 branch starts on the real Razer/Wenceslas stack with backend/PostgreSQL
  loopback-only and Next.js reachable from the trusted Mac, reusing Demo 1's exact
  external configuration and Devcon test identity.
- [x] Media progresses automatically through the coordinator's own reconciliation timer
  during real vMix rolling-block recording — no manual per-cycle trigger.
- [x] Real CUDA/float16 transcription evidence is produced automatically as part of that
  autonomous progression.
- [ ] **NOT QUALIFIED — not exercised.** The worker/deployment status projection reflects
  real GPU/capacity/availability state autonomously.
- [x] Package Approval is performed from the Mac UI against an audited exact revision,
  and any Devcon publication remains gated by the existing explicit-confirmation
  `publish-devcon` workflow, unchanged.
- [ ] **NOT QUALIFIED — not exercised.** One induced live-simulation failure causes visible
  `degraded` status with a bounded failure code, and the coordinator keeps attempting cycles rather than dying (ED-0063
  safety net proven live, not just in unit tests).
- [ ] **NOT QUALIFIED — not exercised.** Restart of the launcher-owned stack reconstructs
  coordinator ownership,
  Session/media/package state, and worker projection from durable state.
- [x] A factual result distinguishes rehearsal success from production or Event
  certification, and explicitly states whether Demo 2 is now promotion-qualified.
- [x] PR #71 remains draft and unmerged after this plan's execution, regardless of
  outcome.
- [x] No schema, migration, dependency, authority-semantic, or association-reevaluation
  policy change was made.

## Rollback or reversal

Stop only launcher-owned processes, preserve evidence, and remove only recorded
rehearsal-owned database rows or non-customer artifacts. Do not reverse any migration,
delete unrelated state, or alter production. A real Devcon PUT, if performed, is not
reversible through this plan and requires its own separate operator decision — the
existing controller never retries or compensates automatically.

## Open questions

- Which representative rehearsal Session/media will be used, and is it the same corpus
  already qualified for Demo 1 or a new one?
- Which controlled live-simulation variant (source interruption, delayed block, process
  restart, etc.) will be used to exercise the ED-0063 safety net live?
- Should the rehearsal-scoped reconciliation-interval override be a temporary environment
  variable/config value, or does the coordinator already expose one cleanly? If not,
  adding one is in-scope Green work for this plan, not a new capability.

## Completion record

- **Executed:** 2026-08-26 on the two-machine Razer/Wenceslas + Mac topology, reusing Demo
  1's qualified external configuration, media path, and Devcon test identity. No new
  credentials, dependencies, or configuration were provisioned.
- **Result:** 11/11 media associated, 11/11 transcriptions complete, 1 declared Moment,
  0 failures/conflicts/unresolved, package revision 1 complete and approved, 0 Devcon PUTs.
  Launcher-owned services stopped with ports 8000/3000 confirmed closed.
- **Disposition:** PARTIAL QUALIFICATION — seven criteria pass, three not qualified.
  Criteria 4 (worker/deployment projection), 6 (ED-0063 safety net under induced failure),
  and 7 (restart reconstruction) were confirmed by the operator as not exercised. A
  zero-failure run cannot satisfy the failure-path criteria.
- **Promotion state:** Demo 2 is **not promotion-qualified**. PR #71 remains open and
  draft, verified 2026-08-28.
- **Evidence:** sanitized operator report retained outside the repository;
  SHA-256 `B6F1052696EDA50C511791778DA16A8F11053FDE578CC8BAEE61DB1A10624E07`. Full
  assessment in the [Run 001 result](../validation/results/demo2-hardware-rehearsal-001.md).
- **Deviations:** the induced-failure and restart steps in the implementation approach were
  not performed. Recorded as an honest gap rather than a plan amendment.
- **Remaining work:** a follow-up run exercising only criteria 4, 6, and 7.
- **Rollback status:** nothing to roll back; no repository, schema, or production state
  changed.
