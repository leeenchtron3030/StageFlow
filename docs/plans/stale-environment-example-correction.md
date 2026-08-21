# Stale environment example correction

## Status

Completed

## Execution authority

- Classification: Green autonomous
- Authority evidence: ED-0059 and the explicit 2026-08-21 request to implement ED-0055 through ED-0062.
- Implementation-ready: Yes
- Required escalation or approval, if any: None.

## Related findings or ADRs

- Finding/disposition: Due-diligence documentation-accuracy residue.
- ADR: None required.
- Engineering Directive: ED-0059.

## Problem statement

The repository-root `.env.example` names legacy variables that current code does not read. ED-0059 refers to `backend/.env.example`, but that path does not exist.

## Verified current behavior

The root example contains six unused legacy names. Current backend, frontend, Kernel, and Demo configuration uses `STAGEFLOW_*` names; ED-0055 adds API-security settings.

## Desired behavior and scope

Correct the directive path and replace every unused legacy entry with current, operator-relevant service, Kernel, API-security, frontend, and Demo names. Use only empty or synthetic values. Do not add dotenv loading, change precedence, or commit credentials.

## Implementation approach and affected files

Rewrite `.env.example` from verified runtime reads after ED-0055 and correct `ENGINEERING_DIRECTIVES.md`. There is no data, schema, migration, runtime, or recovery effect.

## Test strategy and acceptance criteria

- Search runtime code to confirm every documented name is current.
- Confirm no real secret or DSN is present.
- Run `git diff --check`.

## Rollback or reversal

Revert the two documentation changes.

## Open questions

None.

## Completion record

Implemented 2026-08-21.

- Replaced all six unused placeholder variables in the root `.env.example` with current
  backend, deployment, frontend, and Demo-controller variables.
- Secret values remain blank; the file contains no credential or real event data.
- Verified consumers with repository search and passed `git diff --check`.
