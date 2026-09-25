# Demo 2 hardware rehearsal — Run 001

**Run date:** 2026-08-26
**Directive:** ED-0071 ([plan](../../plans/demo2-hardware-rehearsal.md))
**Recorded under:** ED-0074
**Subject:** PR #71 `codex/demo2-autonomous-event-node` — Demo 2 Autonomous Event Node candidate
**Topology:** Two machines — Razer/Wenceslas reference host plus the operator's Mac

## Disposition

**PARTIAL QUALIFICATION.** The core Demo 2 lifecycle executed cleanly end-to-end with zero
failures. Three of ED-0071's ten acceptance criteria were not exercised and are recorded as
**NOT QUALIFIED**, not as passes.

**Demo 2 is not promotion-qualified by this run.** PR #71 remains open and draft.

This is a rehearsal result. It is not production readiness, Event readiness, or deployment
approval.

## Outcome summary

| Measure | Result |
| --- | --- |
| Media associated | 11 / 11 |
| Transcriptions complete | 11 / 11 |
| Declared Moments | 1 |
| Failures, conflicts, unresolved | 0 |
| Package revision | 1 — complete and approved |
| Devcon PUTs | 0 |
| Launcher-owned services | Stopped; ports 8000/3000 confirmed closed |
| Repository state | Clean and synchronized |

## Acceptance criteria

Assessed against ED-0071. A criterion with no supporting evidence is recorded as NOT
QUALIFIED rather than inferred.

| # | Criterion | Result |
| --- | --- | --- |
| 1 | Demo 2 stack starts on the real two-machine setup, backend/PostgreSQL loopback-only, Next.js reachable from the Mac, reusing Demo 1's configuration and Devcon identity | **PASS** |
| 2 | Media progresses automatically through the coordinator's own reconciliation timer during real vMix rolling-block recording, with no manual per-cycle trigger | **PASS** — 11/11 associated |
| 3 | Real CUDA transcription evidence produced automatically as part of that autonomous progression | **PASS** — 11/11 complete |
| 4 | Worker/deployment status projection reflects real GPU/capacity/availability state autonomously | **NOT QUALIFIED — not exercised** |
| 5 | Package Approval performed against an audited exact revision; Devcon publication remains gated by the existing explicit-confirmation workflow | **PASS** — revision 1 approved; 0 PUTs |
| 6 | One induced live-simulation failure causes visible `degraded` status with a bounded failure code, and the coordinator keeps attempting cycles (ED-0063 safety net proven live) | **NOT QUALIFIED — not exercised** |
| 7 | Restart of the launcher-owned stack reconstructs coordinator ownership, Session/media/package state, and worker projection | **NOT QUALIFIED — not exercised** |
| 8 | A factual result distinguishes rehearsal success from production or Event certification and states whether Demo 2 is promotion-qualified | **PASS** — this document |
| 9 | PR #71 remains open and draft, unmerged | **PASS** — verified 2026-08-28 |
| 10 | No schema, migration, dependency, authority-semantic, or association-reevaluation policy change | **PASS** |

**Seven pass, three not qualified.**

## What this run establishes

The autonomous coordinator's normal-path behaviour is real, not just unit-tested. Media
discovered during live vMix rolling-block recording progressed to association without a
manual per-cycle trigger, transcription followed automatically, and a human approved the
resulting package revision — all with zero unresolved media, zero conflicts, and zero
failures. Publication remained correctly gated: no Devcon PUT occurred, and none was
required for closure.

## What this run does not establish

Three criteria were confirmed by the operator as not exercised:

- **Worker/deployment status projection (4).** The projection's autonomous reflection of
  real GPU, capacity, and availability state was not observed.
- **ED-0063 coordinator safety net (6).** No failure was induced, so the safety net's live
  behaviour — visible `degraded` status with a bounded failure code, and loop survival —
  remains proven only by unit tests. This is the criterion most specific to what PR #71
  adds, and its absence is the primary reason this run is a partial qualification rather
  than a pass.
- **Restart reconstruction (7).** The launcher-owned stack was stopped cleanly at the end
  of the run, but no mid-run restart-and-reconstruct cycle was performed.

A zero-failure run is a good operational outcome and simultaneously means the failure-path
criteria could not be satisfied. Both statements are true; neither cancels the other.

## Limitations

- The operator's report is a final-state summary. It does not itemize per-criterion
  procedure detail for the passing criteria, so those passes rest on recorded final state
  rather than step-by-step attestation.
- Single run, single corpus, single hardware configuration. No claim is made about
  throughput, endurance, multi-Stage concurrency, or behaviour under resource pressure.
- Transcription quality was not assessed. Completion count is not an accuracy measure.
- No representative accented or noisy corpus was exercised, so the conditional broader
  provider/model qualification remains open.

## Evidence

- Sanitized operator report: `demo2-live-final-approved-no-put-20260826.json`, retained
  outside this repository on the reference host.
  SHA-256: `B6F1052696EDA50C511791778DA16A8F11053FDE578CC8BAEE61DB1A10624E07`
- PR #71 draft/open state verified directly via the GitHub API on 2026-08-28.
- No media, media paths, credentials, DSNs, transcript content, or raw provider payloads
  are recorded here.

## Required for full qualification

A follow-up run needs to exercise only the three outstanding criteria; the seven passing
criteria do not need re-running unless the branch changes materially:

1. Observe the worker/deployment status projection reflecting real GPU/capacity state.
2. Induce one controlled failure mid-run and confirm visible `degraded` status with a
   bounded failure code plus continued cycling.
3. Stop and restart the launcher-owned stack mid-run and confirm durable reconstruction.

Until then Demo 2 is not promotion-qualified and PR #71 must remain draft.
