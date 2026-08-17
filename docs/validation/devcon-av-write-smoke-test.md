# Devcon AV write smoke-test runbook

## Purpose and authority

This runbook exercises the existing Devcon AV enrichment health check against one fixed
`test-devcon-8` session. It is qualification tooling only. It does not implement a
StageFlow publication adapter or authorize writes to real conference sessions.

The upstream references are:

- [`av-write-test.ts`](https://github.com/efdevcon/monorepo/blob/main/devcon-api/src/scripts/av-write-test.ts)
- [Devcon AV stack overview](https://github.com/efdevcon/monorepo/blob/main/docs/av/av-stack-overview.md)

## Fixed safety boundary

The harness has no CLI option for an arbitrary session, event, field, value, or API
origin. Its immutable target is:

| Property | Value |
| --- | --- |
| API origin | `https://api.devcon.org` |
| Event | `test-devcon-8` |
| Session | `a-dacc-vision-for-decentralized-ai` |
| Field | `sources_youtubeId` |
| Marker | `jNQXAC9IVRw` |

Before a write, the public GET response must resolve the session to exactly
`test-devcon-8`. A mismatch aborts with no PUT.

## Dry-run preflight

From `backend/`:

```powershell
uv run python -m tests.qualification.devcon_av_write_smoke
```

Dry run performs one public GET, validates the fixed event identity and field shape, and
prints sanitized JSON. It does not read an API key and cannot perform a PUT.

## Credential preparation

Obtain the AV API key through the approved password-manager workflow. Do not paste the
key or its share link into Codex, shell history, source, `.env`, documentation, test
fixtures, or command-line arguments.

Load the key into the current process environment under:

```text
STAGEFLOW_DEVCON_AV_API_KEY
```

The harness reads the value only to construct the `x-api-key` request header. It never
prints or persists the value. Clear the process environment after the run.

## Live round trip

Live execution requires separate, explicit operator approval immediately before it is
run. After approval and credential preparation, use:

```powershell
uv run python -m tests.qualification.devcon_av_write_smoke `
  --execute `
  --confirm-target test-devcon-8/a-dacc-vision-for-decentralized-ai
```

The sequence is:

1. Capture the path-scoped Git commit baseline.
2. GET and verify `eventId == test-devcon-8`.
3. PUT the marker with `x-api-key` and require HTTP 204.
4. GET and verify the marker is visible.
5. Revalidate event identity and detect concurrent field changes.
6. PUT the original value and require HTTP 204.
7. GET and verify restoration.
8. Require two new path-scoped `[skip deploy]` commits before returning pass.

The process exits non-zero if any required condition is missing. A memory-visible value
with a non-204 response is a failure even if restoration succeeds, because durability is
not established.

## Failure handling

- `wrong_event`: no PUT is made.
- `marker_already_present`: no PUT is made because restoration intent is ambiguous.
- `target_unverifiable`: no blind restore is attempted; escalate to the Devcon API
  operator because session-ID resolution may have changed.
- `concurrent_change`: an unexpected third value is not overwritten.
- `restore_failed` or `restore_unverified`: manual upstream inspection is required.
- `persistence_unverified`: both HTTP operations may have succeeded, but the required Git
  durability evidence did not appear; treat the pipeline as unhealthy.

Do not use an arbitrary production update as a diagnostic fallback.

## Evidence and cleanup

The JSON output is designed to be safe to retain, but review it before committing any
run result. It contains no raw response body, request header, credential, or original
field value. A live pass intentionally leaves two `[skip deploy]` commits in the upstream
Git history; those commits are durability evidence and must not be rewritten.

After a run, clear `STAGEFLOW_DEVCON_AV_API_KEY` from the current process environment.
