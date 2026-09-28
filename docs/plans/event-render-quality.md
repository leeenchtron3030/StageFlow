# Render quality chosen per Event

## Status

Completed (2026-09-27). The owner approved the plan, including the preset catalog and
adjustment ranges, when merging PR #133.

## Execution authority

- Classification: explicit approval granted for the design (owner, 2026-09-27; ADR-0032
  amendment 4B). The work becomes Green autonomous when the owner approves this plan,
  which includes the preset catalog.
- Authority evidence: the owner's answers of 2026-09-27 to "Can the user determine the
  audio and video quality of final renders before beginning an event?":
  - **Presets plus limited adjustments.** Owner-approved presets; only safe values
    adjustable within bounds.
  - **Chosen in the Producer interface, per Event**, stored with provenance.
  - **Changeable mid-event, affecting future renders only.** Existing outputs keep their
    settings, and re-rendering is explicit.
  - [ADR-0032](../adr/ADR-0032-render-durable-operation.md) amendment 4B.
- Implementation-ready: Yes (plan approved 2026-09-27). It depends on ED-0098 being
  merged, because the presets carry audio.
- Required escalation: stop if the work needs:
  - adjustable values beyond video and audio bitrate;
  - automatic re-rendering;
  - per-Session or per-Stage settings;
  - a change to an existing constraint, key, or column in `0015`;
  - a worker that cannot declare more than one profile;
  - any change to Assembly, approval, or publication semantics.
- Engineering Directive: **ED-0099**. The owner delegated ED numbering, and this is the
  next number after ED-0098.

## Preserved accepted decisions

- ADR-0032: human-only render authority; one lease per GPU; the LGPL FFmpeg identity
  check; Rendered Output identity; history is immutable.
- ED-0087 decision (a), refined by amendment 4B: the work key stays the revision plus the
  profile ID and version. Only when adjustments are present, a digest of them is added.
- ED-0098: audio in every requestable profile, the two-stage encode, and the sync
  guarantee.
- ED-0093 D1: the frontend reaches capabilities only through per-capability same-origin
  server routes with explicit method and path allowlists. Commands are idempotent and
  appear in the capability command audit log.
- The owner's UI rule: summary first, show exceptions rather than repetition, and
  collapse the evidence.

## Problem statement

Render quality is fixed in code. The operator cannot choose between file size and
quality for an Event. For example, a streaming-archive Event may want smaller files, and
a broadcast-delivery Event may want a higher bitrate. The decision belongs before the
Event, but must stay correctable.

## Verified current behavior

- `backend/app/contexts/rendering/contracts.py:42-68`: one current profile, and
  `require_profile` accepts only that profile.
- `backend/app/contexts/work_execution/application.py:79-86`: the render work key schema
  v1 is the revision plus the profile ID and version.
- `0015_render_durable_operation_forward.sql`:
  - `render_operation_input` holds the revision, profile ID and version, and output
    token. It is immutable by trigger.
  - `rendered_output` references the operation input by (operation, revision, profile ID,
    version).
- The render request digest covers the revision, profile, and actor
  (`backend/app/contexts/rendering/service.py`).
- Event-scoped, versioned, append-only operator configuration already exists:
  `editorial_phrase_list` (migration `0019`) is keyed by Event and version with
  `created_by`/`created_at`. It is the precedent for storage shape.
- `work_worker_capability` has one row per capability, keyed by its own UUID with
  execution profile ID and version (`0007`). Before relying on it, verify that one worker
  can declare several profile rows and that claims match any of them.
- Producer interface: the Event page is `frontend/app/event/page.tsx`. Session render
  actions and history are in `frontend/src/components/session-outputs-panel.tsx` and
  `frontend/src/experience/output-actions.ts`.

## Desired behavior

### Preset catalog (for owner approval)

This is a closed catalog defined in code. Each preset is a versioned Render Profile.
Changing any fixed value creates a new version.

Fixed values shared by every preset:
- CUDA decode;
- H.264 `h264_nvenc` p4 VBR, GOP 60;
- constant 30000/1001;
- AAC-LC 48 kHz stereo;
- MP4.

| Preset (UI label) | Profile ID / version | Resolution | Video default (adjustable range) | Audio default (choices) |
| --- | --- | --- | --- | --- |
| 1080p Standard *(default)* | `h264-nvenc-1080p-video` v3 (the ED-0098 profile) | 1920×1080 | 8 Mbit/s (6–12, steps of 0.5) | 192 kbit/s (128, 160, 192, 256) |
| 1080p High | `h264-nvenc-1080p-high` v1 | 1920×1080 | 14 Mbit/s (10–20, steps of 0.5) | 256 kbit/s (192, 256, 320) |
| 720p Compact | `h264-nvenc-720p` v1 | 1280×720 | 4 Mbit/s (3–6, steps of 0.5) | 128 kbit/s (96, 128, 160, 192) |

- Only the video bitrate and the audio bitrate are adjustable.
- Resolution, codec, frame rate, GOP, preset, sample rate, channels, and container are
  never adjustable.

### Event Render Setting

- Each Business Event has zero or more immutable, versioned settings. Each records:
  - the preset ID and version;
  - an optional video bitrate adjustment and an optional audio bitrate adjustment;
  - the human actor and the aware selection time from the injected clock;
  - the command ID.
- The highest version is current. When no setting exists, the current setting is
  **1080p Standard with no adjustments**, and it is shown as the default.
- Choosing a setting is a human, idempotent command.
  - It names the version it replaces (`expected_version`, or none), so two operators
    cannot overwrite each other silently. A stale expectation is refused with a bounded
    409 `render_setting_changed`.
  - Adjustments are checked against the preset's bounds. A value out of bounds is
    refused with `render_adjustment_out_of_bounds`.
  - An adjustment equal to the preset default is stored as "no adjustment", so the same
    effective settings always have one representation.
- A setting may be chosen or changed at any time. There is no Event-start lock.

### Render requests

- A render request resolves the Event of the Assembly revision and that Event's current
  setting at receipt time. It freezes into the operation input:
  - the preset ID and version;
  - the effective adjustments;
  - the setting version it used, or none for the default.
- The request carries `expected_setting_version`: the version the human saw in the
  confirmation, or none. If it no longer matches, the request is refused with a 409
  `render_setting_changed`, and nothing is enqueued.
- The profile fields in the request body become optional, for compatibility with
  ED-0098 clients. If supplied, they must equal the resolved preset, or the request gets
  the same 409.
- Work key:
  - unchanged (schema v1) when there are no adjustments, so an unadjusted Standard render
    after ED-0099 keeps the key of the same render made under ED-0098;
  - schema v2 when adjustments are present: the v1 fields plus a digest of the
    adjustments.
  - A request with identical effective settings therefore reuses the operation, and a
    request with different effective settings creates a new one.
- The command digest includes the effective settings.
- Workers declare every catalog preset. They check the adjustments against the preset's
  bounds again before encoding, and encode with the effective values. The sidecar
  manifest records the effective video and audio bitrates next to the profile ID and
  version.
- Changing the setting never touches existing operations or outputs. Re-rendering at the
  current setting is an explicit human render request.

### Producer interface

- **Event page, "Render quality" section.**
  - Summary line, for example "1080p Standard · video 8 Mbit/s · audio 192 kbit/s",
    followed by "Default" or by who chose it and when.
  - "Change" opens the preset choice and the two bounded controls. The controls show
    only the values the preset allows.
  - The confirmation states the consequence first: "Applies to renders requested from
    now on. Existing outputs keep their quality."
  - Previous settings are collapsed.
- **Session outputs panel.**
  - Each operation and output shows its quality label.
  - The request-render confirmation names the quality that will be used.
  - When the Session's latest output was made with settings different from the current
    Event setting, one secondary action appears: "Render again at current quality". No
    repeated notice appears on every row.
- All wording lives in `ui-labels.ts`.
- The new routes are added to the rendering capability allowlist, and the new command
  appears in the capability command audit log.

## In scope

1. Glossary first: add Render Preset, Render Adjustment, and Event Render Setting; refine
   Render Request (current setting, expected version); add UI wording rows.
2. Contracts:
   - the preset catalog with bounds;
   - an immutable `RenderAdjustments` value;
   - `effective_profile(preset, adjustments)`;
   - `require_requestable` replaces `require_profile`: the profile is in the catalog and
     its adjustments are within bounds. v1, v2, and uncatalogued profiles stay refused;
   - the `EventRenderSetting` contract;
   - typed reasons `render_adjustment_out_of_bounds` and `render_setting_changed`.
3. Migration `0020`, forward and reverse (see Data considerations).
4. Application:
   - choose and read Event Render Setting, idempotent through
     `human_command_idempotency`;
   - resolve the setting in `request_render`;
   - work key schema v2 when adjustments are present;
   - the command digest includes the effective settings.
5. Worker:
   - capability rows for every catalog preset;
   - claim matching on any of them;
   - bounds re-checked;
   - the adapter uses the effective width, height, video bitrate, and audio bitrate.
     These are the only values that vary, and they come from validated integers.
6. API:
   - `GET /rendering/presets`;
   - `GET` and `POST /rendering/events/{event_id}/render-setting`;
   - the render request adds `expected_setting_version` and makes the profile fields
     optional;
   - operation and output listings add the effective adjustments and the setting
     version. These are additive fields.
7. Frontend: the Event page section, the outputs panel changes, typed zod clients,
   server-route allowlist entries, and audit log entries.
8. Tests: see Test strategy.
9. Documentation:
   - the rendering README;
   - `post-kernel-capability-layer.md`;
   - `docs/ux/operator-feedback.md` checkpoint notes;
   - the config README, if any worker configuration changes.
10. **Owner steps:**
    - a UX checkpoint on the Event page section and the outputs panel changes;
    - render validation Run 004 on the reference GPU (see Acceptance criteria).

## Out of scope

- Adjustable resolution, codec, frame rate, GOP, NVENC preset, sample rate, or channels.
- Custom presets made by operators. Changing the catalog is a code change with owner
  approval.
- Per-Session or per-Stage settings. Automatic re-rendering. Locking at Event start.
- Deleting or replacing older outputs. Retention is ABR-010 and is Yellow.
- Loudness normalization, overlays, publication, and delivery.

## Constraints

- Architecture:
  - catalog, bounds, and resolution are pure domain code in `contexts/rendering`, with no
    FastAPI, UI, or FFmpeg knowledge;
  - the API, worker, and UI only call it;
  - settings belong to the rendering context and reference the Business Event. They do
    not change Kernel-owned Event facts.
- Compatibility:
  - ED-0098 request bodies (`profile_version: "3"`, no expected version) keep working.
    They receive the current setting, and are refused only if an adjusted or non-Standard
    setting conflicts with the named profile.
  - All listing changes are additive.
- Offline: local only; no network.
- Security:
  - human-only commands;
  - no caller text reaches FFmpeg;
  - bitrates are validated integers from a closed catalog;
  - the new routes are behind the existing same-origin server-route protections and
    allowlists.
- White-label naming. Immutable contracts. Aware timestamps from the injected clock.

## Implementation approach

1. Glossary, contracts, and catalog, with unit tests (pure).
2. Migration `0020` with forward, reverse, and migration tests.
3. Setting commands and the repository, with idempotency, concurrency, and bounds tests.
4. Render request resolution, the work key, and the digest, with replay and conflict
   tests.
5. The worker, adapter, and manifest, with fake-FFmpeg tests for each preset and
   adjustment.
6. The API.
7. The frontend, then the owner UX checkpoint.
8. Documentation, then Run 004.

Backend steps 1–6 can merge before the UI. With no setting chosen, behaviour equals
ED-0098.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `docs/architecture/*glossary*` | New terms and UI wording, first |
| `backend/app/contexts/rendering/contracts.py`, `planning.py`, `service.py`, new `settings.py` | Catalog, adjustments, effective profile, setting commands, request resolution |
| `backend/app/contexts/work_execution/` | `RenderOperationInput` adjustments; work key schema v2 |
| `backend/app/infrastructure/postgres/sql/0020_*` (+ migration registry) | Additive storage |
| `backend/app/infrastructure/postgres/render_repository.py` | Settings persistence; input columns; listings |
| `backend/app/infrastructure/rendering/ffmpeg.py`, `execution.py` | Effective values; manifest fields |
| `backend/app/demo/render_worker.py` | One capability per preset |
| `backend/app/api/v1/rendering.py` | Preset and setting endpoints; request field |
| `frontend/app/event/page.tsx`, `session-outputs-panel.tsx`, `output-actions.ts`, `ui-labels.ts`, server routes, zod clients (+ tests) | Producer interface |
| Rendering README, capability layer, UX feedback log | Documentation |

## Data or migration considerations

Migration `0020`, additive only:

- New table `event_render_setting`:
  - columns: `event_id` (FK `business_event`), `version` (bigint > 0),
    `render_profile_id`, `render_profile_version`, `video_bit_rate` (nullable, > 0),
    `audio_bit_rate` (nullable, > 0), `command_id` (unique), `selected_by`,
    `selected_at timestamptz`;
  - primary key `(event_id, version)`;
  - immutable by trigger, following the `render_history_is_immutable` pattern;
  - bounds are enforced in the domain. The database checks only positivity and
    non-blank values, so a catalog change needs no migration.
- `render_operation_input` adds nullable `video_bit_rate`, `audio_bit_rate`, and
  `event_render_setting_version`.
  - Existing rows stay null, meaning "profile defaults, no setting".
  - The immutability trigger and every existing constraint, key, and foreign key are
    unchanged. Adding nullable columns does not fire the update trigger; verify this.
- The reverse drops the new columns and table only when no `event_render_setting` rows
  exist and every new input column is null. Otherwise it refuses with a clear message,
  as the `0015` reverse does.
- Nothing is backfilled, rewritten, or deleted. A pg_dump of the demo database is taken
  before applying the migration, following existing practice.

## Failure and recovery considerations

- Setting commands:
  - an idempotent replay returns the same version;
  - a concurrent change is refused with a 409, never lost;
  - a transaction failure leaves no partial version.
- Render requests:
  - the setting is read in the same transaction that enqueues the operation, so the
    frozen settings are exactly those checked against `expected_setting_version`;
  - an ambiguous commit behaves as it does today.
- Workers:
  - an adjustment out of bounds at execution is `render_profile_unsupported`, which is
    not retryable. This can only happen if the catalog changed between request and
    execution;
  - a worker that lacks a preset never claims its work, so the work stays visible as
    pending.

## Observability requirements

- Operators can see:
  - the Event's current quality and its history;
  - which quality each operation and output used;
  - whether the latest output matches the current setting.
- Refusals are bounded codes. The audit log records setting commands with outcome and
  resulting version, and no free text.

## Test strategy

- Pure:
  - catalog shape and immutability;
  - bounds at the edges (minimum, maximum, off-step, and out-of-range values);
  - an adjustment equal to the default normalizes to none;
  - `effective_profile` for each preset;
  - v1, v2, and uncatalogued profiles are refused.
- Migration:
  - forward and reverse on empty tables;
  - the reverse refuses when rows exist;
  - existing render rows are unaffected;
  - the immutability trigger works on the new table.
- Application and repository:
  - choosing a setting is idempotent;
  - a stale `expected_version` gets a 409;
  - the default applies when no setting exists;
  - a request freezes the current setting;
  - a stale `expected_setting_version` gets a 409 with nothing enqueued;
  - the unadjusted work key equals ED-0098's key;
  - adjustments produce a new operation, and identical adjustments replay the same one;
  - a mid-event change leaves existing operations and outputs byte-for-byte unchanged.
- Worker and adapter (fake FFmpeg):
  - scale, bitrate, and audio-bitrate arguments for each preset, with and without
    adjustments;
  - bounds are re-checked;
  - claims match every declared preset;
  - the manifest carries effective values.
- API:
  - endpoint shapes;
  - ED-0098 body compatibility;
  - bounded errors.
- Frontend:
  - summary rendering (default and chosen);
  - bounded controls offer only the allowed values;
  - consequence-first confirmation;
  - "Render again at current quality" appears only on a mismatch;
  - allowlist entries;
  - audit log lines.
- Quality gate:
  - the full host backend suite, Ruff, and Pyright;
  - frontend build, lint, typecheck, and test;
  - `git diff --check`.

## Acceptance criteria

- [x] A producer can see and choose an Event's render quality (a preset plus bounded
  bitrates) in the Producer interface before and during an Event. The choice is recorded
  with actor and time.
- [x] Renders use the Event's current setting at request time. Changing it affects only
  later requests. Existing outputs and operations are unchanged, and re-rendering is
  explicit.
- [x] Out-of-bounds values and stale confirmations are refused with typed codes.
- [x] ED-0098 clients keep working. An unadjusted Standard render keeps its work key.
- [x] Migration `0020` forward and reverse tests pass. The demo database is backed up
  before applying it.
- [x] All required checks pass. The owner UX checkpoint is recorded.
- [x] **Run 004** on the reference GPU renders one validation revision at each preset's
  default, plus 1080p High at 20 Mbit/s with 320 kbit/s audio and 720p Compact at
  3 Mbit/s with 96 kbit/s audio. Each output must show:
  - the expected resolution and stream set;
  - an average video bitrate within ±20% of the target (VBR);
  - the nominal audio bitrate;
  - the ED-0098 sync criteria;
  - a full decode.
  Throughput is recorded against Run 003.

## Rollback or reversal

- Revert the frontend, then the backend. Apply the `0020` reverse only when no ED-0099
  rows exist. Otherwise keep the schema and revert only the code: the new columns are
  nullable and older code ignores them. After such a code-only rollback, older code
  shows adjusted renders as the unadjusted preset. The recorded history itself stays
  correct.
- Outputs made at any preset stay readable as recorded history.

## Open questions

- None. The owner approved the preset catalog and ranges as proposed (2026-09-27).

## Completion record

- **Implemented revision:**
  - PR #136 (branch `codex/ed-0099-event-render-quality`), merged as `6133fa4`.
  - Codex implemented it. The owner rebased it onto the ED-0098 audio-length fix (#135),
    resolved the `ffmpeg.py` stage 1 conflict and committed it.
- **Files changed:**
  - the rendering contracts (preset catalog, adjustments, `effective_profile`,
    `require_requestable`), a new `settings.py`, the service and planning;
  - work-execution contracts and the work key (schema v2 only for adjustments);
  - `0020_event_render_setting` forward and reverse, and the migration registry;
  - the render and transcription-work repositories (a shared-transaction enqueue);
  - execution, the FFmpeg adapter and the render worker (every preset);
  - the API routes;
  - the Event page section, the outputs panel and actions, labels, zod clients, the
    server-route allowlist and the audit log;
  - three new backend test files and one new frontend test file;
  - the glossary, the rendering README and the capability layer.
  - No new dependency.
- **Tests (host):** full backend suite 2,677 passed, 0 failed, 2 skipped. Ruff and Pyright
  clean. Frontend 262/262; lint, typecheck and build pass. CI green.
- **Review:**
  - Codex stopped once as Yellow: the plan named `human_command_idempotency`, whose
    constraint must not change.
  - **Approved deviation:** a capability-owned `command_id` and `request_digest` on
    `event_render_setting`, the 0012/0013/0019 pattern.
  - `directive-reviewer` returned APPROVE. From its notes, the owner fixed ED-0098 body
    compatibility (bodies with no expected version default to Standard v3) and documented
    the retry behaviour of reuse-only commands.
- **Owner steps:**
  - The demo database was backed up with `pg_dump`, then migrated to `0020`.
  - UX checkpoint: [operator feedback](../ux/operator-feedback.md), "ED-0099 review
    checkpoint: render quality". The flows work. Four presentation changes were approved
    and moved to ED-0100.
  - [Run 004](../validation/results/render-durable-operation-004.md) passed with one
    criterion not met as written:
    - Every preset and adjustment bound renders at the right resolution, with video
      within 5% of target and the ED-0098 sync guarantees unchanged.
    - 320 kbit/s audio measured 261 kbit/s (native AAC). The owner decided to keep it,
      labelled "up to 320 kbit/s".
- **Rollback:** revert the code. Reverse `0020` only while no settings or adjusted inputs
  exist.
- **Remaining work:** ED-0100, the UX follow-ups.
