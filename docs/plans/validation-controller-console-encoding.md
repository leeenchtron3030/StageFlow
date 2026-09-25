# Validation controller console encoding

## Status

Completed (2026-09-25).

## Execution authority

- Classification: Green autonomous. A bounded correction to qualification tooling output
  encoding; no product semantics change.
- Authority evidence:
  - Every recent completion record reports four host failures of
    `backend/tests/test_validation_controller.py::test_turnover_boundaries_emit_exact_live_operation_checkpoints`
    as known Windows console-encoding cases. Examples: `demo2-generalization.md`,
    `provider-neutral-program-source.md`, `session-assembly-foundation.md`.
  - The 2026-09-25 `roadmap-scout` review ranked restoring a clean full-suite gate as a
    Green candidate.
- Implementation-ready: Yes.
- Engineering Directive: **ED-0083**. The owner delegated ED numbering.

## Problem statement

The guarded turnover checkpoints printed by `scripts/validation/Invoke-StageFlowValidation.ps1`
contain an em dash (`[char]0x2014`). Under Windows PowerShell with redirected output, the
console used the OEM code page, so the character degraded to `-`. The exact-checkpoint
tests, which decode UTF-8, then failed on every Windows host run. They passed on Linux CI,
so the host full-suite gate was never clean.

## Change

- Set `[Console]::OutputEncoding` to UTF-8 (no BOM) immediately before the controller's
  main `try` block.
- Restore the caller's previous encoding in the existing `finally` block.
- The operator-visible checkpoint text is unchanged; it now arrives intact on Windows.

## Out of scope

Any change to checkpoint wording, controller guards, or other scripts.

## Acceptance criteria

- [x] The four turnover checkpoint cases pass on the Windows reference host.
- [x] The whole `test_validation_controller.py` file and the full backend suite pass on the
  host, and CI passes.
- [x] The caller's console encoding is restored after the run.

## Rollback

Revert the script change.

## Completion record

- **Implemented revision:** branch `fix/ed-0083-validation-console-encoding`.
- **Files changed:** `scripts/validation/Invoke-StageFlowValidation.ps1` and this plan,
  plus the ED and plan-index rows.
- **Commands actually run:**
  - host `uv run --no-sync pytest tests/test_validation_controller.py`: all passed,
    including the four previously failing cases;
  - host full suite `uv run --no-sync pytest`: **2,122 passed, 0 failed, 2 skipped**
    (the POSIX-only cases). This is the first fully green Windows host run.
- **Execution authority:** Green.
- **Deviations:** none.
- **Remaining work:** none.
