# Repository cleanup 2026-09-28: stale current-state docs and small leftovers

## Status

Approved (2026-09-28).

## Execution authority

- Classification: Green autonomous (documentation accuracy and tooling hygiene).
- Authority evidence:
  - AGENTS.md: "Update current architecture documents when an accepted decision or
    implemented boundary changes."
  - Open follow-ups recorded in the
    [hardening follow-ups plan](hardening-follow-ups-2026-09-27.md) completion record: the
    Next 16 `middleware.ts` deprecation and E501 lines in the Unicode generator.
  - ED-0100 review notes (`render-quality-ux-follow-ups.md` completion record).
  - The owner's direction on 2026-09-28 to continue with Green work.
- Implementation-ready: Yes.
- Required escalation: stop if a change would alter runtime behaviour beyond the rename,
  change any security check, or rewrite a historical document (reviews, completed plans,
  dated validation results).
- Engineering Directive: **ED-0102**. The owner delegated ED numbering.

## Verified findings

1. `docs/architecture/post-kernel-capability-layer.md`, render section: it says "GPU
   audio sync, determinism and throughput qualification remain the owner's Run 003 step".
   Runs 003 and 004 are complete.
2. `docs/ux/README.md` ("Editorial" list): it says no candidate-review workflow and no
   Editorial queue are implemented. ED-0095 implemented the Editorial review surface
   (`/editorial`, Event review queue, review actions).
3. `docs/architecture/durable-kernel-operations.md:92` says "verify all five migrations".
   Twenty migrations are now registered.
4. `CHANGELOG.md` stops at "Unreleased - 2026-08-21".
5. `frontend/middleware.ts` uses Next 16's deprecated `middleware` file convention. The
   build warns about it.
6. `frontend/scripts/generate-editorial-unicode.py` has 6 Ruff E501 lines. CI Ruff covers
   only `backend/`.
7. ED-0100 review note: the "Latest output … · Current setting …" reason line is not
   associated with the "Render again at current quality" button (`aria-describedby`).

## In scope

1. **Current-state documents (findings 1–3):**
   - Correct the wording to match the implemented state, citing the Run 003 and Run 004
     results and ED-0095.
   - For finding 3, say "all registered migrations" rather than a count.
   - Keep each edit minimal. Do not touch reviews, completed plans or dated results.
2. **CHANGELOG (finding 4):** add dated entries from 2026-08-22 to 2026-09-28, in the
   file's existing style: one line per merged PR group, naming the EDs, taken from the ED
   index and merge history. Keep "Unreleased" accurate.
3. **Rename `middleware.ts` to `proxy.ts` (finding 5):**
   - Use Next 16's file convention and export name.
   - Keep the same matcher, the same Host-header allowlist behaviour and the same tests.
   - Update any imports or references and the tests' module path.
   - The build must no longer print the deprecation warning.
   - Verify against the installed Next version's documentation or types, not memory.
4. **E501 (finding 6):** wrap the long lines in the Unicode generator with no behaviour
   change. The generated table's drift check must still pass.
5. **Accessibility (finding 7):** give the reason line an ID and reference it from the
   button's `aria-describedby`. Test it.

## Out of scope

- The ED-0100 hydration and timezone note, and history rows showing no date. Both are
  recorded; no change without an owner decision.
- Any other code change, dependency change or migration.

## Constraints

- No behaviour change except the rename (item 3) and the accessibility association
  (item 5).
- The Host-header allowlist must behave identically, proven by the existing tests passing
  unchanged apart from a module path.
- White-label; no private paths.

## Test strategy

- Frontend: `npm run test`, lint, typecheck and build. The build output must show no
  middleware deprecation warning.
- Ruff on `frontend/scripts/generate-editorial-unicode.py`, and the Unicode drift test.
- Backend full suite, because contract tests read documentation text.
- `git diff --check`.

## Acceptance criteria

- [ ] Findings 1–7 are resolved as described, and all checks pass on the host.

## Rollback

Revert the commit.

## Completion record

- Implemented revision:
- Commands and tests actually run:
- Results:
- Remaining work:
