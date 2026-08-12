# API v1

## Purpose

This package contains version 1 HTTP routes.

## Current Scope

The API currently exposes:

- `GET /api/v1/health` for process liveness; and
- `GET /api/v1/kernel/status` for the bounded, read-only Producer Kernel projection.
- `GET /api/v1/media-assets/{asset_id}/timing-evidence` for sanitized, revision-preserving
  advisory Media Timing Evidence linked to one registered Completed Media Asset.

Kernel status reports configuration progress, database availability, reconciled
readiness, Event/Stage/Session package state, aggregate media, recent bounded media,
boundary proposals, and attention codes without exposing DSNs or configured source paths.
The MTE history projection separates Observed facts from Derived candidate intervals and
includes provider/tool/profile, qualification, limitations, and `advisory_only` use. It
omits operation digests, credentials, paths, filenames, and raw provider diagnostics.

## Out of Scope

- Authentication.
- Authority-changing Event/Session/package commands.
- General domain CRUD APIs.
- Integration endpoints.
