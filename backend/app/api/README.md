# API

## Purpose

`api` contains the HTTP interface layer for the backend.

## What Belongs Here

- Versioned route registration.
- Request and response schemas for approved endpoints.
- Thin HTTP adapters that call into lower layers.

## What Does Not Belong Here

- StageFlow business logic.
- Domain model ownership.
- Database or integration implementation.
- Background worker logic.

## Dependency Rule

`api` may depend on `contexts`, `shared`, and `core`. Lower layers must not import from `api`.
