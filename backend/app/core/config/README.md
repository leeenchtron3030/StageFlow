# Core Config

## Purpose

This package contains minimal backend configuration loading.

## Current Scope

It loads process-level service metadata and the explicit versioned Durable Kernel
deployment definition. Secrets are resolved by environment-variable name and excluded
from redacted summaries.

The optional `runtime_profile` defaults to `standard`. The bounded
`demo-single-stage` value requires exactly one Stage, a StageFlow Node role, local
transcription configuration, and exactly one program source: `[local_schedule]` or
`[devcon_read]`. It is a development/demo topology label, not Event-readiness certification.

## Program source configuration (ED-0079)

The default choice for development, tests, and rehearsals is an offline local JSON file:

```toml
[local_schedule]
path = 'C:/example/schedule.json'
```

This section accepts only `path`: an absolute local filesystem path, without parent
traversal, URL, or UNC/network path. On POSIX use an absolute POSIX path. The operator
must supply the file; configuration loading does not read it or bootstrap business state.
`offline`, `local_only`, and `optional` network policies all support this source. Do not
configure both sources, including in the `standard` profile. That profile may omit both.

Existing `[devcon_read]` TOML remains valid and keeps its bounded official endpoint,
Event/room, paging, timeout, and optional-Internet profile requirement. Its configuration
class/defaults now live in the adapter; the old configuration import remains available.

The [example schedule](../../../../../examples/local-schedule.example.json) documents JSON
schema version `"1.0"`. The root requires `schema_version`, the configured `event_key`,
and `sessions` (an array, including an empty array for a successful empty snapshot).
Each session requires `session_key`, `title`, `speakers` (an array of display strings),
`stage_key`, `planned_start`, and `planned_end`. Keys and text must be nonempty strings;
timestamps must be ISO 8601 strings with a timezone offset or `Z`, with end at or after
start. The Event key must match configuration and every Stage key must be configured.
Session keys are stable and unique across the file. Unknown fields, duplicate JSON
members, duplicate normalized session keys, invalid types, and naive times are rejected.
No CSV is accepted. Reads are bounded to 4 MiB and 10,000 sessions.

The adapter validates the whole file before reconciling the requested Stage's complete
snapshot through the existing durable repository. Import never creates a realized
Session. A malformed/unreadable file raises a typed `ProgramSourceUnavailableError`
subclass and preserves cached expectations and the latest successful synchronization.
Reordering or moving the file preserves identity; absent items are withdrawn and retained,
and reappearing items restore the same identity. Cross-Stage move semantics are not
qualified by this single-Stage directive.

Results and Kernel status attribute the source as `local_file` or `devcon`; file paths
are not returned. API field names are unchanged. `KernelComponents.program_source` and
`sync_program()` are the neutral composition surface. `devcon_program_sync` (read/write)
and `sync_devcon_program()` are compatibility aliases, removable once the Demo 2 branch
no longer calls them.

New source records use `external_session_id`, `external_event_id`, and
`external_room_id`. Reconciliation and Kernel status prefer these keys and fall back to
legacy `devcon_*` equivalents. Remove that fallback only after all writers use neutral
keys and retained current and historical records no longer depend on legacy keys. This
directive rewrites no persisted history and introduces no migration. Presentation copy,
launcher output, and the example deployment TOML remain ED-0080 work.

## Out of scope

- Secret storage or display.
- Automatic business-state bootstrap while parsing configuration.
- Runtime-profile authority over Session, association, package, or publication decisions.
