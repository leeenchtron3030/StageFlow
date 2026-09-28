# StageFlow operational frontend

## Purpose

This Next.js workspace implements the first locally runnable StageFlow operational UI.
Its current milestone is a testable Producer experience, with a minimum Editorial shell
that reserves the accepted temporal workspace without fabricating AI output.

The UI is a presentation client. The backend/domain remains authority.

## Implemented routes

| Route | Current purpose |
| --- | --- |
| `/` | Producer Mission Control with fixed Stage order, bounded Attention, and Infrastructure summary |
| `/event` | Event lifecycle/readiness plus visibly unavailable authority actions |
| `/sessions` | Active/assembling and completed Session operational views |
| `/sessions/[sessionId]` | Session lifecycle, declared boundaries, package revision, media aggregate, and read-only Outputs |
| `/stages/[stageKey]` | Previous/current/next Stage context and source/media consequences |
| `/infrastructure` | Health, impact, and Attention as separate dimensions |
| `/editorial` | Minimum development-only temporal/Candidate shell; no real AI or transcript execution |

Stage and Session drill-down can also render bounded Media Timing Evidence when available.
Observed recorder facts, Derived candidate intervals, recorder-profile qualification, and
limitations remain visibly advisory and never enter ordinary Producer Attention.

## Prerequisites

- Node.js compatible with the committed Next.js version (the verified local run used
  Node `24.14.0`).
- npm and the committed `package-lock.json`.
- For Kernel mode: the StageFlow backend and its existing Kernel configuration/runtime
  prerequisites.

Install exactly from the lockfile:

```powershell
cd C:\Dev\StageFlow\frontend
npm ci
```

## UI Host allowlist

Every page, API route and static asset passes through `middleware.ts`. It checks the
original `Host` header and returns an empty **421** response for unapproved or missing
hosts. The default authorities are `localhost:<port>`, `127.0.0.1:<port>` and
`[::1]:<port>`, where `<port>` is the actual Next.js listening port.

The Node-runtime middleware reads `process.env.PORT` on each request. The installed
Next.js `next dev` / `next start` server sets this from `server.address().port` before
handling requests (`next/dist/server/lib/start-server.js`), covering the default port,
`PORT`, CLI `--port`, and automatic development fallback when a port is occupied.
It never infers the port from `Host`, the request URL, or forwarded headers. A missing
or invalid runtime port fails closed. Custom server launchers must supply their actual
listening port in `PORT` before serving requests.

For access over a trusted LAN, set the optional **server-only** variable before launch:

```powershell
$env:STAGEFLOW_UI_ALLOWED_HOSTS = "producer.lan:3000,192.168.1.20:3000,[fd00::1]:3000"
```

Entries are comma-separated exact `host:port` authorities (DNS names, IPv4, or bracketed
IPv6); surrounding entry whitespace is removed and DNS letter case is ignored. Ports
must be decimal 1–65535 without leading zeros. An explicit port is required. Browsers omit
default ports, so a Host without a port is always refused: serve the UI (or its proxy) on a
non-default port; entries naming 80 or 443 never match. No schemes, paths, credentials, wildcards, trailing-dot names, or suffix matches
are accepted. Malformed entries are ignored individually and grant no access. Entries
may explicitly name a different port, for example an operator-managed reverse proxy.
No hosts are discovered automatically. This gate supplements the existing capability
method/path allowlists, same-origin checks, launch context, and server-held API secret.

## Editorial Unicode developer tooling

`src/experience/editorial-unicode.ts` records the backend Python Unicode version.
The backend drift test compares it with `unicodedata.unidata_version`; the frontend
test requires one well-formed exported version. Regenerate using the backend virtual
environment's Python from the repository root, then rerun both tests and the frontend
normalization parity tests:

```powershell
.\backend\.venv\Scripts\python.exe frontend/scripts/generate-editorial-unicode.py
.\backend\.venv\Scripts\python.exe frontend/scripts/generate-editorial-unicode.py --check
```

The script is developer tooling only, never imported by production. `--check` verifies
the full generated file byte-for-byte, preserving the checkout's LF or CRLF line endings.

## Fixture-mode operator preview

From the repository root, the dev-only preview helper keeps child output attached to the
current terminal and stops only processes it started:

```powershell
.\scripts\preview\Start-StageFlowPreview.ps1 -Mode Fixture -Scenario quiet
```

Press `Ctrl+C` in that terminal to stop the preview. The helper requires `npm.cmd` on
`PATH`; it does not install packages or create production orchestration.

Development defaults to fixture mode. The explicit environment value makes the source
choice obvious:

```powershell
cd C:\Dev\StageFlow\frontend
$env:STAGEFLOW_UI_DATA_MODE = "fixture"
npm run dev
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000). The navigation rail exposes requested
operational scenarios A through G and sanitized Run 002/003/004 reference states. Every
fixture surface is persistently labeled `Development fixture` and `Not production
authority`.

Fixture query examples:

```text
http://127.0.0.1:3000/?scenario=quiet
http://127.0.0.1:3000/?scenario=turnover
http://127.0.0.1:3000/?scenario=source-unavailable
http://127.0.0.1:3000/?scenario=run-004
http://127.0.0.1:3000/?scenario=scale
```

## Read-only Kernel mode

After setting `STAGEFLOW_KERNEL_CONFIG_PATH` and its referenced DSN secret, the same
helper can start the backend and frontend together:

```powershell
.\scripts\preview\Start-StageFlowPreview.ps1 -Mode Live
```

Terminal 1:

```powershell
cd C:\Dev\StageFlow\backend
# Configure STAGEFLOW_KERNEL_CONFIG_PATH and its referenced DSN secret first.
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd C:\Dev\StageFlow\frontend
$env:STAGEFLOW_UI_DATA_MODE = "kernel"
$env:STAGEFLOW_KERNEL_STATUS_URL = "http://127.0.0.1:8000/api/v1/kernel/status"
$env:STAGEFLOW_MTE_API_BASE_URL = "http://127.0.0.1:8000/api/v1"
npm run dev
```

The frontend fetches the existing bounded read-only status response server-side and maps
it into a presentation model. It does not duplicate association policy or expose command
authority. If the endpoint is unavailable, it identifies the local client connection
loss without inventing database state; it never silently falls back to fixture state.

The persistent source indicator uses exactly four operator states:

- `LIVE — connected`
- `LIVE — unavailable`
- `LIVE — unconfigured`
- `DEVELOPMENT FIXTURE`

An unavailable frontend-to-Kernel connection never fabricates PostgreSQL or source
health. An unconfigured backend remains a connected setup state rather than a database
failure.

Production builds default to Kernel mode unless `STAGEFLOW_UI_DATA_MODE=fixture` is set
explicitly. An explicitly enabled production-build fixture remains visibly labeled and is
still not production authority.

## Validation

```powershell
cd C:\Dev\StageFlow\frontend
npm test
npm run lint
npm run typecheck
npm run build
```

The test suite uses Node's native TypeScript-capable test runner and adds no test
dependency.

Focused behavior coverage includes MTE fixture/projection labeling and verifies that
unqualified timing evidence remains advisory drill-down rather than Producer Attention.

## Dependency-security status

Next.js is pinned through the compatible 16.2.11 patch. Current npm advisory paths,
runtime reachability, install-script notices, and accepted residual development-tooling
findings are documented in
[Producer UI dependency-security triage](../docs/ux/producer-ui-dependency-security.md).
Do not run `npm audit fix --force` or approve install scripts as part of routine preview
setup.

## Known limitations

- Status is server-rendered on navigation/refresh; continuous polling is not implemented.
- Outside the existing Demo controls, general Event/Session/package actions remain
  disabled with an explanation. The Outputs panel is read-only; capability command
  routes are access foundations for later UI phases.
- No authentication, authorization, multi-operator command conflict handling, or role
  permissions are implemented.
- Editorial media playback, transcripts, Candidate execution, and decisions are not
  implemented. Fixture Candidate text is synthetic and visibly labeled.
- Worker/GPU, Internet, cloud, and transfer status render only when modeled by fixtures;
  the current Kernel projection does not report those capabilities.
- The interface is an operator-review milestone, not Event-readiness evidence.
- The Kernel media list is deliberately bounded. Asset drill-down labels it as bounded
  recent evidence and does not claim it is a complete Session membership export.


## Session Outputs access foundation

Session Detail includes a read-only Outputs panel in fixture and Kernel modes. The
fixture is synthetic and explicitly marked as non-authoritative. Kernel reads use the
shared server-only proxy transport; failure never falls back to fixture data. Assembly,
render operations, Rendered Outputs, and per-asset media timing fail independently.
The panel preserves frozen member order, discloses timing qualification and validation
issue codes, distinguishes latest timing evidence from frozen proposal evidence, and
shows output metadata without content keys, paths, or playback. Reads refresh on navigation
or page refresh; no command is started by this panel.

Assembly reads use the backend's current revision number, including when the first
page contains only historical revisions. Render lists show at most 100 records each
and disclose additional records. Timing reads cover at most 100 unique current Assembly
members/recent Session assets, in groups of eight, and do not claim complete membership.

The following optional **server-only** variables configure loopback HTTP bases. Defaults
are `http://127.0.0.1:8000/api/v1/<capability>`:

| Variable | Capability |
| --- | --- |
| `STAGEFLOW_ASSEMBLY_API_BASE_URL` | `assembly` |
| `STAGEFLOW_RENDERING_API_BASE_URL` | `rendering` |
| `STAGEFLOW_EDITORIAL_API_BASE_URL` | `editorial` |
| `STAGEFLOW_MEDIA_TIMING_API_BASE_URL` | `media-timing` |

All use the existing `STAGEFLOW_API_SHARED_SECRET`. New browser commands additionally
require the current `STAGEFLOW_DEMO_LAUNCH_CONTEXT` header and a valid server-held
`STAGEFLOW_DEMO_OPERATOR_ID`; the proxy supplies that actor identity. Requests with a
foreign Origin or cross-site fetch metadata are refused. Reads follow the Demo read
pattern and do not require a launch context. Commands are capped at 32 KiB (including
the server-supplied actor); responses at 12 MiB. New routes stop oversized streams,
refuse echoed secrets, preserve query parameters for backend scope/pagination, refuse
redirects, and return only no-store JSON responses. Demo behavior and attribution remain
unchanged. This is the existing local launch trust model, not user authentication or
multi-operator authorization.

Exact allowlists, relative to `/api/stageflow/<capability>/` (forwarded under
`/api/v1/<capability>/`), are below. Each pattern is anchored at both ends. `U` means
`[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}`.
Literal path segments are case-sensitive. All other method/path pairs return 404.

| Capability | Method | Path regex (between `^` and `$`) |
| --- | --- | --- |
| assembly | GET | `events/U/templates` |
| assembly | POST | `templates` |
| assembly | GET | `events/U/sessions/U/revisions` |
| assembly | POST | `sessions/U/revisions` |
| assembly | POST | `sessions/U/approvals` |
| assembly | GET | `events/U/sessions/U/metadata-overrides` |
| assembly | POST | `sessions/U/metadata-overrides` |
| assembly | GET | `events/U/packaging-assets` |
| assembly | GET | `events/U/packaging-assets/U/revisions` |
| assembly | POST | `packaging-assets` |
| assembly | POST | `packaging-assets/U/revisions` |
| assembly | POST | `packaging-assets/U/approvals` |
| rendering | GET | `operations` |
| rendering | GET | `outputs` |
| rendering | POST | `requests` |
| editorial | POST | `moments/U/reviews` |
| editorial | GET | `sessions/U/moments` |
| editorial | GET | `events/U/review-queue` |
| editorial | GET | `events/U/phrase-lists` |
| editorial | POST | `events/U/phrase-lists` |
| editorial | POST | `sessions/U/derivations` |
| media-timing | GET | `events/U/operations` |
| media-timing | GET | `assets/U/latest` |

The command paths are access foundations for later explicitly confirmed UI actions.
Editorial marking remains on the existing Demo route. Media-timing enqueue is not in
this allowlist. Packaging Asset upload and metadata editing have no UI in this phase.

`npm test` loads a Node-only resolver for the `server-only` marker; Next.js still enforces
that marker in application builds. The three new test files cover all method/path pairs,
proxy protections and stream caps, backend-shaped schemas, current-revision selection,
bounded/partial reads, and rendered labels. Existing test assertions are unchanged.
If sandbox process spawning is blocked, run each listed test file separately using
`node --import ./src/experience/server-test-runtime.ts --test --test-isolation=none <file>`.
This avoids test worker spawning without changing any assertion or the normal CI command.
