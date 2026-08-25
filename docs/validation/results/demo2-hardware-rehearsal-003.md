# Demo 2 repeatability and second-write rehearsal 003

## Result

**A second clean write-bearing Demo 2 flow qualified; PR promotion remains
unqualified.**

On 2026-08-25, the Razer/Wenceslas node and Mac Producer UI completed a new isolated
Demo 2 Session against the same Devcon test API/event used by Demo 1. Four rolling vMix
segments progressed autonomously through bounded discovery, deterministic association,
CUDA transcription, exact package approval, and one newly authorized controller-gated
Devcon PUT. Durable Git and the public API converged to the same result.

Two earlier attempts in the same operator session stopped safely without a PUT. They
exposed accepted unresolved-media reevaluation behavior, a globally colliding source
binding key, existing-Event bootstrap ordering, and fail-closed current-Session
selection after multiple ended Sessions. Those findings remain evidence and are not
silently treated as promotion-qualified behavior. ED-0063's unexpected-exception
degraded-loop gate remains unproven, so PR #71 remains draft and unmerged.

## Authority and environment

- Branch revision: `f74c07e` on `codex/demo2-autonomous-event-node`; PR #71 remained
  draft/open and both GitHub quality-matrix jobs passed at that revision.
- Runtime profile: `demo-single-stage`; autonomous media interval 5 seconds; Program
  refresh interval 120 seconds.
- PostgreSQL authority: preserved database `stageflow_demo`, already upgraded through
  accepted migration 0010. No schema or migration action occurred in this rehearsal.
- Devcon: official `https://api.devcon.org`, test event `test-devcon-8`, selected target
  `test-a-fast-confirmation-rule-for-ethereum`.
- Transcription: faster-whisper 1.2.1, `large-v3-turbo`, accepted model revision,
  CUDA/float16. Real silent-audio inference passed before stack startup.
- The user explicitly authorized exactly one new guarded PUT on 2026-08-25 after
  read-only verification found that an earlier reported PUT had not enriched the
  selected target. The later controller execution consumed that authorization; no retry
  or compensating write occurred.
- Operator UUID, DSNs, credentials, private paths, media, transcripts, provider payloads,
  and launch-context values are omitted.

## Safely stopped attempts

### Existing Event/source repeatability attempt

- Before the new Session, the Stage contained 10 registered assets: 6 associated to the
  prior approved Session and 4 deterministic unresolved assets captured in a later
  recording window.
- Starting a new Session changed the material Session input set. The accepted Demo 2
  lifecycle reevaluated and associated the four unresolved assets to the new Session.
- Timestamp-only inspection showed those assets preceded the new recording window, so
  the package would have mixed capture windows. The operator stopped recording, ended
  the Session, and did not approve its package. No publication action ran.
- After two Sessions on that Stage were ended, bounded controller status failed closed
  with `demo_current_session_ambiguous`. Selecting a recent ended Session automatically
  would affect publication authority and was not improvised during the rehearsal.

### First isolated Event/source attempt (`put2`)

- A new empty folder and local Event/deployment were created, but the profile initially
  reused durable source key `razer-recordings`.
- The Stage/source table owns source-binding keys globally. Media reconciliation failed
  with `candidate_source_stage_conflict`; the documented idempotent manual fallback
  returned HTTP 409 with the same code. No asset registered through that path.
- The source key was corrected to `razer-recordings-put2`. Because the Event already
  existed, normal component loading attempted startup reconciliation before the CLI
  bootstrap could attach the new binding. One accepted idempotent Kernel bootstrap
  attached the missing unique binding; its bounded summary print failed after the
  bootstrap because it referenced a nonexistent projection attribute, but the durable
  bootstrap itself completed.
- By then the operator had ended and approved the Session. Six files registered after
  its active window and remained unresolved; transcript evidence stayed zero. The
  guarded publisher therefore had no valid candidate. Read-only public and durable
  checks confirmed the selected target remained unenriched. No PUT ran.

## Qualified isolated flow (`put3`)

1. A fresh external profile used unique deployment, Event, source folder, and globally
   unique source-binding identities from the outset. Its source contained zero files.
2. Guarded diagnosis verified database compatibility, empty-source availability, four
   current Devcon Program items, NVIDIA GPU availability, and real CUDA/float16 model
   inference.
3. Standard launcher bootstrap created the Event/Stage/source successfully. Initial
   status showed zero media/Sessions/failures, a current CUDA worker, and autonomous
   coordinator ownership.
4. The Mac started Session `0f83022b-ab7a-4d20-84f6-fe6931c24bc0` before vMix recording.
   The operator kept it active until recording stopped and every final file settled.
5. Without a manual processing cycle, four rolling MP4 segments registered and
   associated to that Session; four durable operations succeeded; four complete
   Transcript Evidence revisions appeared; no media remained stabilizing, unresolved,
   or conflicting; terminal failures stayed zero.
6. Autonomous Devcon Program refresh continued successfully during the recording. The
   Mac marked one Editorial Candidate Moment.
7. After all four evidence items were complete, the Mac ended the Session and approved
   exact package revision 1. Final sanitized report: ready true; package complete and
   approved; media registered/associated 4/4; operations succeeded 4; evidence complete
   4/4; Moments 1; current CUDA worker ready; terminal failures 0.

## Publication

- The controller reverified ended Session state, exact approved package revision,
  complete/untruncated evidence, current Program mapping, credential presence, remote
  identity, and candidate digest
  `95022e4c182870d7c88ce474bcb86da3babb6a3105830edb12f96d7ba5da047c`.
- Exact target: `test-devcon-8 / test-a-fast-confirmation-rule-for-ethereum`.
- Exact fields: `transcript_text` and `duration`.
- Exactly one PUT was sent. Devcon accepted it; durable Git persistence verified; the
  public API converged; status `published_durable_api_converged`.
- Final bounded read-only comparison: public and durable duration 226 seconds,
  transcript length 2,148 characters, transcript SHA-256
  `36b56b1a2f8b548c2c475eda08f88fcb3e06100b0a3a0f24b4c5bcb8a8af24f7`; records
  matched. Transcript content was not printed or stored in Git.

## Validation and final state

- Commands actually run: controller `diagnose`, `start`, repeated `status`, one local
  idempotent process-media diagnostic, `rehearsal-report`, `publish-devcon`, and `stop`;
  public/durable adapter GET comparisons; Git/PR status inspection; and source filename,
  size, and timestamp inspection without opening media content.
- The first-run full validation remained current at branch revision `f74c07e`: backend
  1822 passed, 5 skipped; Ruff passed; Pyright zero errors/warnings. GitHub subsequently
  passed Backend/Python 3.13 and Frontend/Node 22 quality jobs at that revision. No full
  suite was rerun for this supplemental rehearsal because repository production code did
  not change.
- The launcher-owned backend, worker, frontend, and coordinator were stopped; ports 8000
  and 3000 had no remaining listeners. vMix was not launcher-owned.
- External put2/put3 configuration, media, sanitized reports, and durable database facts
  were preserved. No repository dependency, schema, migration, or runtime default
  changed.
- PR #71 remains draft, open, unmerged, and promotion-unqualified pending the remaining
  ED-0063 live gate and explicit disposition of the observed fail-closed limitations.
