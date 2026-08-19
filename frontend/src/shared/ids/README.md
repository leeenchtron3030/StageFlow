# Shared IDs

## Purpose

Contains frontend identifier contracts.

## Current Scope

- `EntityId`
- `CorrelationId`
- cryptographic UUID-v4 generation with a Web Crypto `getRandomValues` compatibility path

These are branded strings with UUID-compatible constructors. Domain-specific IDs do not belong here yet.
