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
| `/sessions/[sessionId]` | Session lifecycle, declared boundaries, package revision, and media aggregate |
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
- No HTTP authority-command surface exists, so Event/Session/package actions remain
  disabled with an explanation.
- No authentication, authorization, multi-operator command conflict handling, or role
  permissions are implemented.
- Editorial media playback, transcripts, Candidate execution, and decisions are not
  implemented. Fixture Candidate text is synthetic and visibly labeled.
- Worker/GPU, Internet, cloud, and transfer status render only when modeled by fixtures;
  the current Kernel projection does not report those capabilities.
- The interface is an operator-review milestone, not Event-readiness evidence.
- The Kernel media list is deliberately bounded. Asset drill-down labels it as bounded
  recent evidence and does not claim it is a complete Session membership export.
