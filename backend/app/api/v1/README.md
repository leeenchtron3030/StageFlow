# API v1

## Purpose

This package contains version 1 HTTP routes.

## Current Scope

The API currently exposes:

- `GET /api/v1/health` for process liveness; and
- `GET /api/v1/kernel/status` for the bounded, read-only Producer Kernel projection.
- `GET /api/v1/media-assets/{asset_id}/timing-evidence` for sanitized, revision-preserving
  advisory Media Timing Evidence linked to one registered Completed Media Asset.
- `POST /api/v1/editorial/moments/mark` for idempotent human declaration of one
  unreviewed Editorial Candidate Moment; and
- `GET /api/v1/editorial/sessions/{session_id}/moments` for a bounded candidate list and
  count/latest-activity/generation/conflict projection.

Kernel status reports configuration progress, database availability, reconciled
readiness, Event/Stage/Session package state, aggregate media, recent bounded media,
boundary proposals, and attention codes without exposing DSNs or configured source paths.
Its bounded Session entries include Editorial candidate activity when the Editorial
repository is available and report `unknown` rather than fabricating worker state when it
is not.
The MTE history projection separates Observed facts from Derived candidate intervals and
includes provider/tool/profile, qualification, limitations, and `advisory_only` use. It
omits operation digests, credentials, paths, filenames, and raw provider diagnostics.

All operational routers are included behind the ED-0055 shared-secret dependency.

## Out of Scope

- Per-operator identity, sessions, or role-based authorization.
- Machine-origin candidates, Editorial review decisions, and Editorial Clip creation.
- General domain CRUD APIs.
- Integration endpoints.
