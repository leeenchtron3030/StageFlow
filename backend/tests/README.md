# Backend Tests

## Purpose

This directory contains backend tests.

## Current Scope

ED-0002 includes minimal coverage for application creation and the health endpoint.

ED-0004 adds shared contract tests for identifiers, results, errors, clocks, time ranges, and base domain events.

ED-0005 adds Production Context timeline contract tests under `backend/tests/`, following the existing backend test convention instead of nesting tests inside application packages.

## What Does Not Belong Here

- Tests for unimplemented domain behavior.
- Tests requiring a database, object storage, workers, media processing, or external integrations.
