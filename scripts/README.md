# scripts

## Purpose

This directory is reserved for repository maintenance and developer utility scripts.

## What Belongs Here

- Small scripts approved by future Engineering Directives.
- Repository maintenance utilities.
- Developer tooling helpers that do not implement StageFlow business logic.

## What Does Not Belong Here

- Backend services.
- Worker processes.
- Application runtime code.
- FFmpeg, Whisper, integration, or deployment implementations before their directives exist.

## Expected Future Directives

- ED-0004 Development Tooling may populate this directory with approved tooling scripts.
- Future implementation directives may add narrowly scoped maintenance utilities.

## Validation utilities

- [Safe local validation controller](validation/README.md) wraps the bounded real-event
  qualification runner with external Run path derivation, conservative preflight
  checks, human-authority guards, and concise status summaries.
- [Media timing qualification probe](../backend/tests/qualification/media_timing_probe.py)
  shallowly inspects explicitly selected local media with caller-supplied FFmpeg and emits
  sanitized, non-authoritative JSON and Markdown evidence.

  ```powershell
  cd backend
  uv run python tests/qualification/media_timing_probe.py `
    --source <external-media-directory> `
    --source-alias <safe-alias> `
    --ffmpeg <local-ffmpeg-executable> `
    --json-output <new-report.json> `
    --markdown-output <new-report.md>
  ```

  The outputs must be new paths. The probe is shallow and bounded, performs no network
  work or media decode/transcode, and its candidate intervals are prohibited from
  production authority use.

- [Recorder calibration harness](../backend/tests/qualification/calibration_harness.py)
  generates deterministic visual/audio marker media, decodes recorded-segment content
  boundaries, composes them with the media timing probe, and summarizes repeated trials
  for one exact recorder-profile revision. See the
  [controlled runbook](../docs/validation/recorder-calibration-harness.md). It requires an
  explicitly supplied local FFmpeg-compatible executable and remains qualification-only.

## Local application preview

- [`Start-StageFlowPreview.ps1`](preview/Start-StageFlowPreview.ps1) is a dev-only
  convenience entry point for fixture or live read-only preview. It keeps subprocess
  output visible, fails if a child exits, and stops only child processes it created.

  ```powershell
  .\scripts\preview\Start-StageFlowPreview.ps1 -Mode Fixture -Scenario quiet
  .\scripts\preview\Start-StageFlowPreview.ps1 -Mode Live
  ```

- [Frontend launch guide](../frontend/README.md) documents locked npm setup, fixture/live
  distinction, shutdown, common failures, routes, validation, security triage, and current
  limitations.

## Demo single-stage launcher

- [`Start-StageFlowDemo.ps1`](demo/Start-StageFlowDemo.ps1) starts the bounded Demo 1
  profile after database, media-source, public Devcon-program, NVIDIA CUDA, and exact
  local-transcription preflight checks pass. The backend remains on loopback while the
  producer UI binds to one selected LAN IPv4 address.

  ```powershell
  cd backend
  uv sync --dev --group transcription --locked
  cd ..\frontend
  npm ci
  cd ..
  .\scripts\demo\Start-StageFlowDemo.ps1 `
    -ConfigPath .\examples\demo-single-stage.toml `
    -OperatorId <operator-uuid> `
    -CudaRuntimePath C:\StageFlowDemo\runtime\whisper-cuda-12.4\Release
  ```

  `OperatorId` is mandatory attribution for human authority commands; controls remain
  disabled when it is absent. `CudaRuntimePath` names the isolated, qualified Demo CUDA
  library directory. The launcher verifies its required libraries, prepends it only to
  the launcher process and owned children, performs a real silent-audio inference probe,
  and restores the prior process `PATH` on exit. It does not modify the system NVIDIA
  driver or global CUDA environment. The configuration names the process
  environment variable
  that contains the PostgreSQL DSN; the launcher never prints or persists that value.
  Devcon program data is fetched
  only during the explicit startup sync and remains available from the durable cache if
  connectivity is subsequently lost. Press Ctrl+C to stop only launcher-owned child
  processes.
