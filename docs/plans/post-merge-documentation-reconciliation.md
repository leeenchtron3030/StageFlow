# Post-merge documentation reconciliation

## Status

Approved

## Execution authority

- Classification: Green autonomous. Documentation-only corrections to current-state
  documents; no accepted semantics change.
- Authority evidence:
  - `AGENTS.md`: current architecture documents are updated when an implemented boundary
    changes; historical documents are not rewritten.
  - Precedent: ED-0070 (repository consistency closure) and ED-0074 (plan-status
    reconciliation).
  - The 2026-09-25 `drift-auditor` sweep of `main` at `e36f370`, covering six areas, and
    the `roadmap-scout` review. Their findings are listed below with evidence.
- Implementation-ready: Yes.
- Required escalation: none. Stop if a correction would change an accepted decision,
  rename a public field, or rewrite a historical record.

## Related findings or ADRs

- ADR-0019, ADR-0025, ADR-0026, ADR-0031; ED-0063, ED-0071, ED-0077, ED-0081.
- Engineering Directive: **ED-0082**. The owner delegated ED numbering; ED-0082 is the next
  free number.

## Problem statement

PR #71 (Demo 2 Autonomous Event Node, ED-0081) merged to `main` as `085e01f` on
2026-09-25, with the owner's explicit approval given in the working session. Several
current-state documents still describe it as a draft awaiting approval. The sweep also
found current-state documents that omit implemented components or behaviour, use three
names for one action, or read as though accepted work is unselected or incomplete.

## Findings to correct (verified on `main` at `e36f370`)

1. **PR #71 merge status.**
   - `ENGINEERING_DIRECTIVES.md` rows ED-0063, ED-0071, and ED-0081 say "draft PR" or
     "merge pending owner approval".
   - `docs/plans/README.md` rows for ED-0063, ED-0071, and ED-0081 say the same. The
     "Demo 2 Autonomous Event Node" plan row still reads "In progress".
   - Correction: state "merged to `main` (`085e01f`, 2026-09-25)". Completed plans
     (`demo2-generalization.md`, `demo2-autonomous-event-node.md`,
     `demo2-rebase-and-coordinator-safety-net.md`) get a dated status note, not a rewrite.
   - The Run 002 result is a dated record and stays unchanged.
2. **ADR-0026 status in the capability layer.** `post-kernel-capability-layer.md` (lines
   29, 515, 679, and similar) calls ADR-0026 "proposed", but `docs/adr/README.md` lists it
   as Accepted (2026-08-28). Its line 621 says Assembly work "remains ED-0077 work", but
   ED-0077 is implemented. Correct these factual references only; the document's own
   "Proposed architecture" status stays.
3. **`system-context.md` runtime components.**
   - The table has no rows for Work Execution (the transcription worker process, migration
     `0007`), Editorial review (`0011`), Packaging Assets (`0012`), Session Assembly
     (`0013`), or the default-off Demo 2 Autonomous Event Node coordinator.
   - The text says "There is no watcher, broker, worker, or uncontrolled loop", and the
     actor table says "AI/media Event Worker | No implementation".
   - Correction: add the rows. Qualify the sentence: no broker; one durable transcription
     worker; one accepted, default-off, bounded coordinator loop under an advisory lock.
4. **Coordinator behaviour in `durable-event-mode-kernel.md`.** Document the ED-0063
   catch-all, which reports `degraded` with a bounded failure code, and the ED-0081
   per-kind recovery to `running`. Also document the rehearsal-only, one-shot
   `rehearsal_fault_media_cycle` setting, rejected outside `event_mode = "rehearsal"`.
5. **Kernel status fields.** `durable-kernel-operations.md` lists the
   `GET /api/v1/kernel/status` fields without `automation`. Add it.
6. **Program refresh terminology.**
   - The coordinator and status fields say `program_refresh_*`. The architecture document
     says "program-source reconciliation", and the domain type is Program Expectation
     reconciliation.
   - Correction: add a glossary entry. **Program refresh** is the coordinator's timed call
     of `sync_program()`, whose outcome is a Program Expectation reconciliation. Align the
     architecture wording. No field rename.
7. **ADR-0031 residual.**
   - Demo CLI preflight JSON (`devcon_read_available`, `devcon_program_items`), its error
     codes, and the Demo rehearsal-report `devcon` key remain outside adapters. This was
     disclosed in `demo2-generalization.md`.
   - Correction: record it as a known residual beside the ADR-0031 index row and in
     `principles.md` principle 9, pending a follow-up directive. No code change here.
8. **Transcription provider wording.**
   - `docs/adr/README.md` (ADR-0025 row), `post-kernel-capability-layer.md`, and
     `transcription-evidence-readiness.md` read as though no provider is selected.
     `docs/validation/transcription-engine-evaluation.md` records the 2026-08-18 acceptance
     of faster-whisper, CTranslate2, and large-v3-turbo as the first local provider; it is
     implemented behind the adapter as the optional, operator-installed transcription
     group (ED-0075).
   - Correction: cite that acceptance. State that the core Work Execution port remains
     provider-neutral.
9. **Stable ingress plan status.**
   - `docs/plans/README.md` and `stable-ingress-identity.md` say "real PostgreSQL
     execution pending". The ADR-0019 index row says ingress persistence was verified on
     isolated real PostgreSQL.
   - Correction: update the plan status only if the repository records that execution
     (cite it). Otherwise leave it and report the conflict.

## Out of scope

- Any code, test, API field, schema, or configuration change.
- Renaming `program_refresh_*` or `devcon_*` fields. The latter is a separate follow-up
  directive.
- Rewriting reviews, dated results, preserved ADR text, or completion-record bodies.

## Acceptance criteria

- [ ] Findings 1-8 corrected in current-state documents, with evidence citations where a
  claim is new.
- [ ] Finding 9 corrected with a citation, or reported as unresolved.
- [ ] No historical record body rewritten; dated notes only where needed.
- [ ] `git diff --check` passes. No file outside `docs/`, `ENGINEERING_DIRECTIVES.md`, or
  `docs/plans/README.md` changes. The full backend suite still passes, because some tests
  read documentation.

## Rollback

Revert the documentation commit.

## Completion record

_(Filled in on completion.)_
