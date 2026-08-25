# Demo 2 hardware rehearsal 002

## Result

**Core write-bearing flow qualified; PR promotion remains unqualified.**

On 2026-08-25, the Razer/Wenceslas node and Mac Producer UI completed the real
Demo 2 flow against the same Devcon test API/event used by Demo 1. The run proved
automatic rolling-media progression, CUDA transcription, Program refresh, exact-revision
Package Approval, durable restart reconstruction, one human Editorial Candidate Moment,
and one guarded Devcon test PUT with durable and public read-back verification.

PR #71 remains draft and unmerged. Promotion remains unqualified because the attempted
source interruption exercised expected source-unavailable handling rather than throwing
an unexpected coordinator-cycle exception; therefore ED-0063's live exception/degraded-
loop safety-net criterion was not demonstrated. This is a bounded Demo qualification,
not production deployment or Event-readiness evidence.

## Environment and authority

- Branch revision at publication: `9b028aa` on
  `codex/demo2-autonomous-event-node`; PR #71 remained draft/open.
- Runtime profile: `demo-single-stage`; autonomous media interval 5 seconds; autonomous
  Program refresh interval 120 seconds.
- PostgreSQL authority: exact database `stageflow_demo`.
- Devcon: official `https://api.devcon.org`, test event `test-devcon-8`, room `stage-1`,
  target Session `test-a-dacc-vision-for-decentralized-ai`.
- Transcription: faster-whisper 1.2.1, `large-v3-turbo`, accepted model revision,
  CUDA/float16; real silent-audio preflight passed.
- Operator identity was the one actor UUID consistently present across all preserved
  Demo Sessions. The value is omitted from this report.
- The user explicitly authorized the one test API write on 2026-08-24. The Mac UI
  supplied Session, Moment, Session-end, and exact-revision Package Approval authority.
- DSNs, API secrets, private paths, media, transcripts, raw provider payloads, and
  launch contexts are omitted.

## Database compatibility upgrade

- Preflight found migrations 0001 through 0009 and no 0010.
- Focused Editorial migration/repository suite passed: 6 tests, with the existing
  Starlette/httpx deprecation warning.
- A PostgreSQL 17 custom-format full backup was created before mutation: 203,021 bytes,
  234 archive entries, SHA-256
  `daf269b2653612e888c9e2810f3cf36cb497b1f843c9081eba08be365cfb7d2e`.
- `0010_editorial_candidate_moment` was applied through the accepted migration runner.
- Every pre-existing table count remained identical. The migration ledger advanced from
  9 to 10 and the new location-history table appeared empty, as expected.
- The backup remains external and preserved. No restore or reversal was required.

## Live flow evidence

1. Guarded diagnosis verified exact database identity, external configuration, source,
   real CUDA inference, and Devcon GET with five Program items.
2. The first startup failed closed because the accepted API shared secret was absent.
   A generated 64-character local Demo secret was stored at Windows User scope without
   printing its value. The controller was corrected to import and clear it at Process
   scope for the four API-bearing actions.
3. The next live status call exposed that the Python controller omitted the accepted
   `X-StageFlow-API-Secret` header. The single loopback GET boundary was corrected and
   behavior-tested; browser proxy behavior was unchanged.
4. The Mac manual Program refresh succeeded. Autonomous Program refresh continued and
   reconciled the current/withdrawn set without a failure code or local interruption.
5. The Mac started Session `79df8289-bad7-4676-82a0-53260f3b0751`. vMix wrote six
   closed rolling MP4 segments into the configured Demo 2 source.
6. Without `Process / Transcribe` or another manual cycle, all six assets registered and
   associated; six durable Operations succeeded; six complete Transcript Evidence
   revisions were produced; terminal failures remained zero.
7. A launcher-owned stop/start while recording reconstructed the same active Session,
   already-registered media/evidence, coordinator ownership, Program state, and current
   CUDA worker, then processed later segments idempotently.
8. The Mac declared one Editorial Candidate Moment. The canonical projection reported
   count 1, `healthy`, zero location conflicts, no truncation.
9. The Session ended, reached `ready_for_review`, and the Mac approved exact package
   revision 1. The durable Session then reported `complete`; the Producer Work Queue
   returned zero after that decision was resolved.
10. Final sanitized report: ready true; package complete/approved revision 1; registered
    6; associated 6; Transcript Evidence complete 6 of 6; Moments 1; current worker
    available with GPU transcription ready; terminal failures 0.

## Publication

- The first invocation stopped before PUT with
  `demo_publish_transcript_projection_truncated`: the UI workspace intentionally exposed
  only four of six transcript assets.
- The API retained its default limit of four and gained an authenticated bounded query
  parameter capped at 100. Only the guarded controller requests the full bounded view.
  The fail-closed asset and per-evidence segment truncation checks remain unchanged.
- Validation then showed all six transcript-evidence assets complete and untruncated.
- The controller reverified test event, target Session, package approval, credential
  presence, candidate digest, and exactly two fields: `transcript_text` and `duration`.
- One PUT was sent. Result: write accepted, durable Git persistence verified, public API
  converged, publication status `published_durable_api_converged`.
- No retry or compensating write was issued.

## Controlled failure and recovery

- With vMix recording stopped and the Session still in the end/package transition, the
  exact Demo source directory was renamed briefly and restored in a `finally` block.
- The coordinator remained running and recovered with all six assets preserved, but it
  treated the missing source as expected unavailable input; it did not enter `degraded`
  or produce an unexpected-cycle failure code.
- Therefore source recovery passed, but the ED-0063 unexpected-exception/degraded-loop
  criterion remains unproven live. No riskier database, ACL, network, or process fault
  was manufactured merely to make the criterion pass.

## Compatibility corrections

- `scripts/demo/StageFlow-Demo.ps1`: import the accepted API shared secret only for
  API-bearing controller actions and clear Process scope afterward.
- `backend/app/demo/controller.py`: authenticate loopback reads using the canonical
  header; request the complete bounded transcript-asset workspace for publication.
- `backend/app/api/v1/demo.py`: additive `transcript_asset_limit` query, range 1-100,
  default 4. Existing UI/default response behavior remains compatible.
- Direct contract/behavior tests and controller documentation were updated. No new
  dependency, provider, migration beyond accepted 0010, payload field, automatic write,
  or authority semantic was introduced.

## Validation performed

- Editorial migration/repository tests: 6 passed.
- Controller/authority/authentication tests before the transcript correction: 37 passed.
- Demo API/controller/authentication tests after the transcript correction: 39 passed.
- Scoped Ruff: passed.
- Scoped Pyright: zero errors/warnings.
- PowerShell AST parse: passed.
- Known warning: existing Starlette/httpx deprecation from FastAPI TestClient.
- Full final backend and repository validation is recorded in the ED-0072 completion
  record after this result is committed.

## Final state

- The launcher-owned backend, worker, frontend, and coordinator were stopped; ports 8000
  and 3000 had no remaining listeners.
- vMix remained open but was no longer recording; it was not a launcher-owned process.
- The external database, backup, media, User-scope local API secret, and durable Devcon
  test write were preserved.
- PR #71 remained draft and unmerged.

