# Render quality UX follow-ups (ED-0099 checkpoint)

## Status

Completed (2026-09-28).

## Execution authority

- Classification: Green autonomous (presentation and wording only).
- Authority evidence:
  - the owner's ED-0099 UX checkpoint decisions of 2026-09-27, recorded in
    [operator feedback](../ux/operator-feedback.md) under "ED-0099 review checkpoint:
    render quality";
  - [render validation Run 004](../validation/results/render-durable-operation-004.md) for
    the 320 kbit/s wording.
- Implementation-ready: Yes.
- Required escalation: stop if a change needs a backend, API, contract, catalog or command
  change, or alters any authority, concurrency or confirmation behaviour.
- Engineering Directive: **ED-0100**. The owner delegated ED numbering.

## Scope (frontend only)

1. **Event page Render quality section**
   (`frontend/src/components/event-render-quality.tsx` plus the styles it uses):
   - the same panel header as the Authority and Attention panels (kicker and title);
   - one control per row with its label above;
   - a padded history list;
   - reuse the existing panel and form styles; add no new design language.
2. **Provenance:**
   - the summary and history lines show "Chosen <local time>" (the same time style as
     "Status observed");
   - the operator ID and the full ISO timestamp move into a Details disclosure;
   - "Default" stays unchanged.
3. **Re-render reason:** next to "Render again at current quality", one line: "Latest
   output: <quality label> · Current setting: <quality label>". It appears only when the
   action does.
4. **320 kbit/s label:** the audio choice labels 320 kbit/s as "up to 320 kbit/s", in the
   selector and wherever that effective setting is summarized. Other choices are
   unchanged. The catalog, API and stored values stay unchanged.
5. All wording goes in `ui-labels.ts`. Tests: summary and provenance rendering, the reason
   line present only on a mismatch, the 320 label, and the existing render-quality and
   output-action tests unchanged apart from the wording the owner approved.

## Out of scope

Backend, API, contracts, catalog, migrations, command behaviour, confirmation text for
anything other than the 320 label, and operator display names.

## Acceptance criteria

- [x] Items 1–4 are implemented. Frontend test, lint, typecheck and build pass on the
  host. The owner reviews screenshots.

## Rollback

Revert the frontend change.

## Completion record

- **Implemented revision:** branch `codex/ed-0100-render-quality-ux`. Codex implemented it
  and the owner committed it.
- **Changed files** (frontend only):
  - `globals.css`, with one rule (`.render-quality-panel form` padding). Everything else
    reuses the existing section-heading, form and outputs styles;
  - `event-render-quality.tsx` and `session-output-actions.tsx`;
  - `ui-labels.ts`;
  - `render-quality.test.ts` and `output-actions-ui.test.ts`.
- **Changed existing assertion:** one, `/Chosen by/` → `/Chosen \d{2}:\d{2}:\d{2}/`,
  which is the wording the owner approved.
- **Tests (host):**
  - `npm run test` 266/266; lint, typecheck and build pass.
  - The full backend suite was run as the gate.
- **Review:** `directive-reviewer` returned APPROVE, with no blocking findings. Its
  non-blocking notes are recorded for later:
  - a possible hydration mismatch when the server's timezone differs from the browser's;
  - history rows show a time with no date;
  - the reason line is not in the button's `aria-describedby`.
- **Owner screenshots:** `review-screenshots/ed-0100` (not in git).
- **Remaining work:** none.
