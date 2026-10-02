# Media readiness hardening (ED-0124, ED-0125)

## Status

- **Part 1 (ED-0124): Approved** by the owner on 2026-10-01. Raise the default stability interval.
- **Part 2 (ED-0125): Proposed.** It needs owner approval of D2–D4 before it is implementation-ready.

## Execution authority

- **Classification:**
  - **Part 1 is Green.** It is a default-value change inside the existing ED-0049 policy.
  - **Part 2 is Green once approved.** It implements an existing ED-0049 port and the existing
    `require_inactive_write_when_available` parameter. No new policy or contract is needed.
- **Authority evidence:**
  - ED-0049 (asset stability and readiness), ED-0052 (media collection ports), ED-0050 (runtime
    capabilities);
  - the owner's 2026-10-01 approval of "raise the default now, active-writer detection as a
    follow-up plan";
  - the Live Replay Run 002 attempts recorded below.
- **Implementation-ready:** Part 1 yes; Part 2 no.
- **Escalation:** stop if Part 2 needs a readiness-policy, contract or schema change, or a new
  dependency.

## Problem statement

A recorder that writes a file in place can be registered as a **Completed Media Asset while it is
still being written**. Today readiness uses the stability route alone: a file becomes ready once
snapshots taken `minimum_stable_seconds` apart (default **5 s**) are unchanged. Two settings make
that the only route:
- `require_inactive_write_when_available=False` (`backend/app/bootstrap/runtime_factory.py`);
- no adapter implements `WriteStateObservationCollectionPort`.

Any writer pause of 5 s or more therefore registers a truncated recording. Downstream timing,
segmentation, transcription and suggestions would all use incomplete media.

## Verified current behavior

- **Readiness parameters** (`runtime_factory.py`, about lines 273–284):
  - `minimum_stable_interval = minimum_stable_seconds`;
  - `require_read_access_for_stability=True`;
  - `require_post_finalization_presence=True`;
  - strong finalization by `ATOMIC_RENAME_OBSERVED` only;
  - `require_inactive_write_when_available=False`.
- **Default:** `ResourcesConfiguration.minimum_stable_seconds` is `Field(default=5, ge=1, le=3600)`
  (`backend/app/core/config/deployment.py:333`).
- **Policy** (`conservative_asset_readiness_policy.py`, `_stability_route`):
  - when an inactive write state is observed after the stability basis, that is recorded as a
    reason;
  - when the parameter requires it and no observation exists, the route is refused with
    `WRITE_STATE_UNKNOWN`;
  - otherwise the limitation "write state not independently assessed" is recorded.
- **Runtime validation** (`runtime_validation.py`, about line 802) refuses
  `require_inactive_write_when_available` unless the capability reports `write_state_support`.
- **No implementation:** no class implements `WriteStateObservationCollectionPort`
  (`media_collection/ports/observation_collection_ports.py`).
- **Evidence from Live Replay Run 002**, attempt a (growing arrival, 1×, 5 s default):
  - block 10 was registered at about 1.3 of 2.4 GB while still being written;
  - the Windows power log shows Modern Standby throttling at that moment, which paused the writer.

  The trigger was environmental, but the exposure is general: a recorder pause, a network share
  stall or a throttled process all look like "stable".

## Decisions

- **D1 (Part 1, approved).** Change the default `minimum_stable_seconds` from 5 to **30**.
  - Attempt b of Run 002 measured registration at about 38 s median after a block closed with
    30 s, against 14 s with 5 s.
  - The operator can still set any value from 1 to 3,600.
  - Update the operator templates and docs that show 5. Tests that set their own value keep it.
- **D2 (Part 2, proposed).** A **Windows write-state observation adapter** implementing
  `WriteStateObservationCollectionPort`.
  - **Method:** open the resolved file read-only with a share mode that denies other writers
    (`FILE_SHARE_READ` only), then close it at once.
    - Success means no process holds a write handle: `INACTIVE`.
    - A sharing violation means a writer is active: `ACTIVE`.
    - Any other error means `UNKNOWN`, with a limitation.
  - **Safety:** no data is read or written. The adapter never holds the handle, so it cannot
    block the recorder.
  - **Recommended default:** Windows only. POSIX reports no write-state support (no portable
    equivalent), so readiness there stays on the stability route with the existing limitation.
- **D3 (Part 2, proposed).** When the runtime capability reports `write_state_support`, set
  `require_inactive_write_when_available=True`.
  - On Windows, the stability route then also needs an inactive-write observation after the
    stability basis.
  - Elsewhere, behavior is unchanged.
- **D4 (Part 2, proposed).** Readiness latency stays bounded by the stability interval. The
  write-state check runs in the same discovery cycle; it adds no waiting.

## In scope

- **Part 1:**
  - the default in `deployment.py`;
  - the durable-kernel operations doc example, and the validation controller's config template in
    `scripts/validation/Invoke-StageFlowValidation.ps1`;
  - a test asserting the default.
- **Part 2:**
  - the Windows adapter and its wiring in the media collection dependencies;
  - the capability flag and the parameter switch;
  - tests: fake OS calls for active, inactive and unknown; and a Windows-only host test with a real
    file held open for writing by a child process;
  - docs: the readiness architecture doc and the operator README.

## Out of scope

- Any change to the ED-0049 policy logic, its reason codes or its contracts.
- Recorder-specific integrations, and POSIX lease or `lsof` approaches.
- Late-media or finality semantics.

## Constraints

- No dependency (Part 2 uses `ctypes` and the Win32 API through the standard library).
- No schema or migration change.
- Read-only, non-destructive file access only. Never hold a handle beyond the check.
- Offline.

## Test strategy

- **Part 1:** the default value test; the full host suite; Ruff; Pyright.
- **Part 2:**
  - adapter unit tests with fakes;
  - a Windows host test where a child process writes slowly and the adapter reports `ACTIVE`,
    then `INACTIVE` after close;
  - a policy integration test where a stable but still-open file is not ready, and becomes ready
    after close;
  - runtime validation with and without the capability.
- **Owner check:** rerun a growing-arrival replay (as in Run 002) and confirm no registration
  happens before close.

## Acceptance criteria

- [x] ED-0124 merged (PR #193; the validation controller template deliberately keeps its explicit 5 s for synthetic media): default 30 s; templates and docs updated.
- [ ] ED-0125 approved and merged: a Windows write-state adapter, and inactive write required when
  supported.
- [ ] Owner replay check: no mid-write registration under growing arrival.

## Rollback

- **Part 1:** revert the default. Operators can set any value regardless.
- **Part 2:** revert, or report no capability. The parameter then stays False, and readiness
  returns to stability only.

## Open questions

- For network shares (SMB), a remote writer's handle may not be visible, so the adapter would
  report `INACTIVE`. Should SMB sources keep the stability route only? **Recommended:** detect
  UNC or network paths and report `UNKNOWN`. The 30 s stability window then remains the
  safeguard.

## Completion record

- Implemented revision:
- Files and migrations actually changed:
- Commands and tests actually run:
- Results and warnings:
- Execution authority used:
- Approved deviations:
- Rollback status:
- Remaining work:
