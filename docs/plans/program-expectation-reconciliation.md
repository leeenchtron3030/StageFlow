# Program Expectation Snapshot Reconciliation

## Status

Completed - Green reconciliation qualified

## Execution authority

- Classification: Green, explicitly authorized by the Program reconciliation milestone.
- Authority: approved Current/Withdrawn Program Expectation semantics, existing durable
  revision model, accepted Demo single-stage Devcon read boundary, and the narrow migration
  authorization in the milestone directive.
- Escalation boundary: stop before broad event-wide or multi-stage room-move semantics, a new
  background poller, new provider, Session authority changes, Devcon writes, or schema outside
  Program Expectation/synchronization lifecycle facts.

## Objective

Replace Devcon upsert-only synchronization with one complete-snapshot reconciliation that keeps
stable Program Expectation identity, records meaningful content/lifecycle revisions, marks absent
items Withdrawn only after a successful full fetch, restores reappearing identities, and exposes a
bounded Producer `Refresh Program` workflow without changing Session authority.

## Data model and transaction

- Migration `0009_program_expectation_reconciliation` adds first-class lifecycle state,
  synchronization scope, last-observed time, and lifecycle-change time to the current Program
  Expectation projection and lifecycle/scope facts to its existing revision history.
- One 0009-owned latest-success synchronization table stores the exact provider scope,
  synchronized time, bounded counts, and sanitized bounded change summary needed after restart.
- Existing rows backfill as Current with observation/lifecycle timestamps from `recorded_at`.
- Repository reconciliation locks and compares one exact provider scope, applies additions,
  meaningful changes, withdrawals, restorations, observation metadata, revision history, and the
  latest result in one PostgreSQL transaction. The in-memory test double uses copy-and-swap.
- The reverse migration drops only the 0009-owned synchronization table and 0009-added columns and
  constraints with PostgreSQL's restrictive default dependency behavior; it never deletes Program
  Expectations, Sessions, earlier revisions, or unrelated data.

## Bounded behavior

- Added: create one Current expectation and revision.
- Changed: retain identity, update approved provider-derived fields, and add one revision.
- Unchanged: update only `last_observed_at`; do not increment the content revision.
- Withdrawn: retain identity/history, add a lifecycle revision, and exclude from new realization.
- Restored: retain identity, return to Current, and add one lifecycle revision.
- Fetch, pagination, contract, or storage failure leaves the previous successful snapshot active.
- Startup synchronization and explicit Producer refresh are the only refresh points.
- Public Devcon GET caching is reported as provider fetch time, not bypassed.

## Producer/API scope

- Add one local Demo `POST /program/refresh` endpoint and a matching allowlisted Next.js proxy
  route. It performs only the configured Devcon GET plus local transactional reconciliation.
- Retain loopback backend and launch-context validation. Refresh is not a human Session authority
  command and carries no operator/operation semantics.
- Show provider, latest successful refresh, Current count, bounded result categories and reviewable
  approved-field diffs. Withdrawn records remain quiet historical external evidence.
- Only Current expectations are selectable. A selection absent from the refreshed Current set is
  invalidated before any Start Session request; the backend independently rejects Withdrawn IDs.

## Validation

- Deterministic backend reconciliation, pagination-failure, transactional-failure, revision,
  identity, Session-preservation, restart, API, migration, and no-Devcon-PUT tests.
- Frontend adaptation, ordering, refresh request/result, withdrawn display, stale-selection, ad-hoc,
  and proxy protection tests.
- Full backend/frontend tests, Ruff, Pyright, TypeScript, ESLint, Next build, migration
  apply/reverse/reapply against an isolated test database, `git diff --check`, and privacy audit.
- Bounded live read-only Devcon qualification if available; upstream schedule mutation remains
  pending unless performed by upstream engineers.

## Completion record

- Implemented revision: 2026-08-19 working tree on codex/program-reconciliation; commit deferred by directive.
- Migration qualification: 0009 restrictive dependency abort plus reverse/reapply passed in stageflow_worker_test; PostgreSQL rollback/restart and equal-instant timezone reconstruction passed. Forward 0009 applied to stageflow_demo with 3 Sessions and 14 expectations preserved.
- Automated validation: 1,787 backend tests passed (5 skipped); 54 frontend tests passed; Ruff, Pyright, TypeScript, ESLint, Next production build, and diff check passed.
- Live qualification: the post-fix baseline Producer refresh passed with 4 unchanged and no
  lifecycle/content changes. The accepted upstream-change refresh at
  `2026-08-20T16:22:17.174717-07:00` observed 3 provider items and reported 3 Changed, 0 Added,
  1 Withdrawn, 0 Unchanged, and 0 Restored, leaving 3 Current and 2 Withdrawn. Stable identities
  advanced exactly once: `frontrunning-the-future-a-cat-and-mouse-game`
  (`ce8def74-22f2-4d5c-9197-42d1de7b9673`) 10 to 11,
  `a-fast-confirmation-rule-for-ethereum` (`9b5a5f8c-f021-4f26-ba70-ae16506c44cd`) 10 to 11,
  and `a-dacc-vision-for-decentralized-ai` (`00a436b5-b725-49d3-9482-bc9467fa5b53`) 10 to 11.
  `a-deep-dive-into-zk-proofs-of-pods` (`a6505844-4ac0-4e04-ad0f-1ca5fdbb43a5`) became
  Withdrawn at revision 7 from revision 6. `a-mobile-based-light-client-solution` was already
  Withdrawn before the click and correctly did not transition again.
- Authority isolation: realized Session `3356fcf7-7907-42c4-bac1-3301927616cd` remained
  `presentation_ended`, package `complete` revision 1, Session revision 4, with authoritative
  start/end unchanged while its linked expectation advanced. Database totals remained 3 Sessions
  and 14 Program Expectations. No Devcon PUT, Session authority action, package authority action,
  retry, or compensation occurred.
- Qualification disposition: Unchanged, Changed, Withdrawn, realized-Session isolation, stable
  identity/revisioning, and Producer Refresh Program passed live. Added and Restored passed
  deterministic/automated coverage but were not exercised against the live provider. Failed or
  incomplete provider snapshot preservation passed automated coverage.
- Privacy/scope audit: no DSN, credential, launch capability, transcript text, provider body, media contents, or Devcon write payload persisted or printed. frontend/next-env.d.ts was restored exactly and remains unrelated.
- Warnings and remaining work: live-provider Added and Restored were not exercised and are accepted
  on deterministic/automated evidence. The in-app browser remained unavailable because of the
  Windows ACL helper; the human Producer completed both accepted refresh clicks. No periodic
  refresh or multi-Stage room-move semantics were added.
