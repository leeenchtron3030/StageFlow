# Devcon AV write smoke-test qualification tooling

## Status

Completed

## Execution authority

- Classification: Green autonomous for qualification-tooling setup only.
- Authority evidence: Product Constitution Principles 8, 11, 13, and 21; accepted
  ADR-0004 and ADR-0005; the operator-requested Devcon AV write-test objective; and the
  upstream `av-write-test.ts` reference implementation.
- Implementation-ready: Yes for the bounded tooling and offline tests described here.
- Required escalation or approval, if any: Running `--execute` performs two external
  writes and requires a separate explicit operator approval immediately before the run.
  A future StageFlow runtime integration remains outside this Green scope and requires
  its own external-side-effect decision and bounded plan.

## Related findings or ADRs

- Finding/disposition: None. This is qualification tooling, not architecture-baseline
  remediation.
- ADR: ADR-0004 (StageFlow owns workflow, not conference data); ADR-0005 (external
  integrations use adapters). No new runtime adapter is implemented.
- Engineering Directive or other authority: Product Constitution Principle 21 and the
  user-authorized qualification objective. Existing Engineering Directives do not
  authorize production Devcon API composition.

## Problem statement

Devcon exposes `PUT /sessions/sources/:id` for day-of AV enrichment. The upstream
reference script includes a reversible smoke test against a known `test-devcon-8`
session, but StageFlow has no bounded local harness or regression tests for that
operator check. Copying the upstream script unchanged would also expose an arbitrary
single-update mode that can modify real conference sessions.

StageFlow needs a fixed-target qualification harness that can prove request access,
round-trip visibility, restoration, and Git-backed durability without becoming a
production publishing integration or a general-purpose mutation tool.

## Verified current behavior

- `backend/app/contexts/integration/README.md` and
  `backend/app/contexts/publishing/README.md` are package placeholders only.
- `docs/architecture/system-context.md` reports no implemented publishing/delivery
  destination and no outbound HTTP side effect.
- The accepted ADR index records that provider adapters remain absent and requires an
  ADR for a durable external-side-effect boundary.
- The upstream script fixes the target to session
  `a-dacc-vision-for-decentralized-ai`, requires `eventId == test-devcon-8`, writes
  `sources_youtubeId`, restores the original value, and defines health as two HTTP 204
  responses plus two `[skip deploy]` commits in the session-data path.
- A read-only preflight on 2026-08-17 resolved that session to `test-devcon-8`; no PUT
  was performed during planning.

## Desired behavior

Provide an operator-invoked, dry-run-by-default Python harness that:

- has one immutable test session, event, field, API origin, and marker;
- refuses a write unless the current session resolves to `test-devcon-8`;
- requires an exact target confirmation and process-only API key for live mode;
- attempts restoration only after revalidating the target and detecting no concurrent
  third-party field change;
- verifies the marker and restoration through GET requests;
- treats two new path-scoped `[skip deploy]` Git commits as required durability
  evidence; and
- emits a sanitized JSON summary without credentials, raw response bodies, or arbitrary
  provider payloads.

## In scope

- Qualification-only harness under `backend/tests/qualification/`.
- Offline tests using injected fake API and persistence boundaries.
- Operator runbook and validation/plan indexes.
- Dry-run preflight execution against the public GET endpoint if explicitly run.

## Out of scope

- Executing the live round-trip in this implementation task.
- Obtaining, opening, storing, printing, or committing the AV API key or password-manager
  share link.
- Arbitrary session, event, field, value, API-origin, or production-write CLI options.
- StageFlow runtime composition, Durable Operations, workers, queues, automatic retries,
  public APIs, UI, or provider SDKs.
- Changing Devcon API, GitHub, Render, Cloudflare, or conference data.

## Constraints

- Architecture and terminology constraints: the harness is validation tooling, not a
  StageFlow integration adapter or publication authority.
- Compatibility constraints: match the upstream endpoint, `x-api-key` header, patch
  field, test identity guard, and `[skip deploy]` persistence signal.
- Offline/event-mode constraints: the tool may fail when offline; that failure must not
  affect StageFlow event operation or readiness.
- Security and data-handling constraints: the credential exists only in the current
  process environment, never in arguments, files, logs, reports, or committed fixtures.
  Redirects are not followed for authenticated PUTs.

## Implementation approach

1. Define fixed qualification constants and injected protocols for the API and commit
   evidence boundaries.
2. Implement a preflight that reads the test session and rejects event mismatch, invalid
   field shape, and a pre-existing marker value before any write.
3. Implement live orchestration with an exact confirmation gate, marker verification,
   target revalidation, concurrency detection, bounded restoration, and final GET.
4. Capture a pre-write Git baseline and require two new path-scoped `[skip deploy]`
   commits before returning pass.
5. Keep HTTP details in qualification-only clients using the existing development
   dependency; catch provider exceptions and emit only typed, sanitized failures.
6. Add behavior-first tests for dry-run, identity mismatch, success, non-204 memory
   mutation, exceptions, restoration failure, concurrency, persistence failure, and
   secret non-disclosure.
7. Document exact operator preparation and require a separate approval before live use.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/tests/qualification/devcon_av_write_smoke.py` | Fixed-target harness and CLI |
| `backend/tests/test_devcon_av_write_smoke.py` | Offline behavior/failure tests |
| `docs/validation/devcon-av-write-smoke-test.md` | Credential-safe operator runbook |
| `docs/validation/README.md` | Validation artifact index entry |
| `docs/plans/README.md` | Plan index entry |
| `docs/plans/devcon-av-write-smoke-test.md` | Authority, scope, evidence, completion |

## Data or migration considerations

No StageFlow schema, migration, persisted state, identity, configuration file, dependency,
or runtime data changes. A separately approved live run temporarily mutates one field in
the upstream test dataset and restores it; Git retains both upstream commits by design.

## Failure and recovery considerations

- No write begins until session/event identity and the Git baseline are available.
- A timed-out or non-204 marker request is followed by a read; restoration proceeds only
  if the target is still the test event and the field is either the marker or the original
  value.
- An unexpected third value is treated as concurrency and is not overwritten.
- Event mismatch or unverifiable target identity blocks restoration and requires upstream
  operator intervention, because a blind retry could touch a real event.
- Restoration failure and missing commit evidence produce non-zero/inconclusive results;
  they never produce pass.
- The harness itself does not retry writes.

## Observability requirements

The sanitized result identifies dry-run/live mode, target aliases, phase outcomes, HTTP
status codes, marker/restoration observations, new durable commit count, failure codes,
and whether manual intervention is required. It never includes the API key, request
headers, raw response bodies, or the original field value.

## Test strategy

- Focused pytest behavior and fault tests with no network.
- Ruff on the harness and test module.
- Pyright on the harness and test module.
- Direct dry-run CLI help/argument checks without a credential.
- Repository secret-pattern and whitespace checks.
- Do not run `--execute` during automated validation.

## Acceptance criteria

- [x] Default invocation cannot perform a write.
- [x] Live mode is fixed to the upstream test identity and requires exact confirmation.
- [x] Wrong-event resolution causes zero PUT calls.
- [x] Marker application, restoration, and two durable commits are all required for pass.
- [x] Non-204, timeout, target drift, concurrency, restore failure, and missing Git
      evidence return sanitized non-pass results.
- [x] Tests prove the API key cannot appear in reports or expected error paths.
- [x] No production code, dependency, schema, migration, runtime configuration, or
      frontend file changes.

## Rollback or reversal

Revert the qualification harness, tests, runbook, and index entries. No StageFlow data or
runtime rollback is required. Upstream Git commits created by a later approved live run
are audit evidence and are not rewritten or deleted.

## Open questions

- When the harness is ready, does the operator explicitly approve the two-write live
  round trip using the locally supplied AV API key?
- A future production Devcon publication adapter needs a separate external-side-effect
  ADR/plan covering operation identity, retries, reconciliation, secrets, and ownership.

## Completion record

- Implemented revision: `6d9eba0a04ceba2a617d1ff76a674dc3c66a808b`.
- Files and migrations actually changed: qualification-only harness and offline tests;
  plan and validation indexes; plan and runbook. No migrations.
- Commands and tests actually run: focused pytest with cache disabled; focused Ruff;
  focused strict Pyright; the default live-API dry-run; public path-scoped GitHub commit
  query; strict UTF-8, relative-link, credential-signature, and Git whitespace checks.
- Results and warnings: 14 tests passed; Ruff passed; Pyright reported zero errors and
  warnings; the read-only preflight verified `test-devcon-8` and performed no PUT; the
  fixed Git path returned commit history; documentation/privacy checks passed. Git line
  ending normalization warnings were informational. The live write/restore was not
  authorized or executed.
- Execution authority used: Green qualification-tooling setup only.
- Approved deviations: None.
- Rollback status: Revert-only; no live PUT authorized or performed.
- Remaining work: Request explicit approval immediately before a live round trip; load
  the AV key into the process environment through the approved password-manager
  workflow; coordinate exclusive use of the fixed test field. A production StageFlow
  Devcon adapter remains a separate architecture and implementation task.

## Subsequent live qualification result

The operator subsequently approved the bounded live round trip. On 2026-08-17 the fixed
marker PUT returned HTTP 204 and persisted as `[skip deploy]` commit
`a4d195f48514e6c22199375ef56b42d7be16c2ee`. The restoration PUT returned HTTP 500. The
live API then reported the original empty value, but an independent read found the Git
file still contained the marker at blob
`0303e9d3866b1095461177ef5f914216990512f7`; no restoration commit was observed.

The failed qualification evidence is retained in
[`docs/validation/results/devcon-av-write-smoke-test-2026-08-17.md`](../validation/results/devcon-av-write-smoke-test-2026-08-17.md).
No retry or additional write is authorized. Upstream data must not be modified
autonomously. Restoration requires an independently observed upstream commit after the
marker commit plus matching original-empty state in both Git and the live API. Devcon
live-write qualification remains blocked after restoration pending disposition of the
HTTP 500 persistence failure; unrelated StageFlow Green work may resume only after
restoration is verified.
