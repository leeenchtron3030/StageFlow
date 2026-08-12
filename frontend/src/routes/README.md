# Routes

## Purpose

Next.js App Router pages live in `frontend/app/`. This directory remains available for
shared route metadata if route complexity later justifies it.

## What Belongs Here

- Shared route constants or metadata only when several routes need them.
- Presentation-safe navigation helpers that do not own domain policy.

## What Does Not Belong Here

- Backend route or API definitions.
- Domain/authority behavior.
