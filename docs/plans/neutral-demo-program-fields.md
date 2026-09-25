# Neutral Demo program-source fields

## Status

Approved

## Execution authority

- Classification: Green autonomous. Additive, white-label naming for Demo operator
  tooling output. The legacy keys stay as documented compatibility aliases.
- Authority evidence:
  - [ADR-0031](../adr/ADR-0031-white-label-identity-and-provider-neutral-program-sources.md)
    decision 1: provider names may not appear outside adapters.
  - The ADR-0031 residual recorded by ED-0082 in `docs/adr/README.md` and
    `docs/architecture/principles.md`.
  - The follow-up named in the [ED-0082 plan](post-merge-documentation-reconciliation.md)
    completion record.
- Implementation-ready: Yes.
- Required escalation: stop if the change would alter a public HTTP API field, stored data,
  or a schema.
- Engineering Directive: **ED-0084**. The owner delegated ED numbering.

## Problem statement

Demo operator tooling still names the provider-neutral program source after one provider:

- `backend/app/demo/cli.py` preflight JSON writes `devcon_read_available` and
  `devcon_program_items`, and raises `devcon_read_not_configured` and
  `configured_devcon_program_empty`. The value it reports is the neutral
  `components.program_source`.
- `backend/app/demo/controller.py` writes the rehearsal-report and status summary under a
  top-level `devcon` key. That summary already carries a neutral `provider` field.
- `scripts/demo/StageFlow-Demo.ps1` reads `$payload.devcon.*`.

These are demo application and tooling files, not adapters.

## Desired behavior

Operator tooling uses neutral names, and the legacy names keep working for one transition.

## In scope

1. **Preflight JSON.**
   - Add `program_source_available` and `program_source_items`, carrying the same values.
   - Keep `devcon_read_available` and `devcon_program_items` as documented deprecated
     aliases, emitted with identical values.
2. **Preflight errors.** Rename `devcon_read_not_configured` to
   `program_source_not_configured`, and `configured_devcon_program_empty` to
   `configured_program_source_empty`. These are operator-visible failure codes. No
   in-repository consumer matches them; the launcher checks only exit codes. Record the
   renames in the plan's compatibility notes.
3. **Rehearsal report and status summary.**
   - Add a top-level `program` object identical to the current `devcon` object.
   - Keep `devcon` as a deprecated alias with identical content.
   - Keep the report's `schema_version` unchanged, because the change is additive.
4. **Launcher.** `StageFlow-Demo.ps1` reads `$payload.program.*`. Its displayed text is
   unchanged.
5. **Tests.** Behaviour tests for:
   - the neutral keys and error codes;
   - the legacy aliases being present and identical;
   - the launcher reading the neutral key.

   Update `test_demo_rehearsal_controller.py` and
   `test_demo_rehearsal_controller_script.py` accordingly.
6. **Documentation.**
   - Mark the ADR-0031 residual resolved, noting the legacy aliases and their removal
     criteria, in `docs/adr/README.md` and `docs/architecture/principles.md`.
   - Update any operator documentation that names the old keys.

## Out of scope

- HTTP API fields, including the Kernel status payload.
- Stored data, the legacy `devcon_*` external-reference fallback, and the Devcon adapter
  itself.
- Removing the legacy aliases. That is a later change, once the removal criteria are met.

## Compatibility and removal criteria

The legacy aliases (`devcon_read_available`, `devcon_program_items`, and the report's
`devcon` object) may be removed once no in-repository consumer reads them. This change
switches the only consumer, the launcher, to the neutral names. Removal needs one release
with the neutral names in place.

The two renamed error codes have no in-repository matcher; operators who pattern-match the
old codes must update.

## Acceptance criteria

- [ ] Preflight emits the neutral keys, with the legacy aliases identical. The neutral
  error codes are used.
- [ ] The report and status summary carry `program`, with `devcon` identical. The schema
  version is unchanged.
- [ ] The launcher displays the same text, read from `program`.
- [ ] Tests cover the neutral keys, alias identity, error codes, and the launcher read.
- [ ] The ADR-0031 residual is marked resolved, with the aliases and removal criteria
  documented.
- [ ] The full backend suite, Ruff, and Pyright pass on the host. No API, schema, or
  stored-data change.

## Rollback

Revert the commit. The legacy keys were never removed.

## Completion record

_(Filled in on completion.)_
