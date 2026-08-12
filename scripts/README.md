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

## Local application preview

- [Frontend launch guide](../frontend/README.md) documents locked npm setup, fixture-mode
  operator review, read-only Kernel mode, routes, validation, and current limitations.
