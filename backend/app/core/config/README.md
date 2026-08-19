# Core Config

## Purpose

This package contains minimal backend configuration loading.

## Current Scope

It loads process-level service metadata and the explicit versioned Durable Kernel
deployment definition. Secrets are resolved by environment-variable name and excluded
from redacted summaries.

The optional `runtime_profile` defaults to `standard`. The bounded
`demo-single-stage` value requires exactly one Stage, a StageFlow Node role, and
optional Internet connectivity so Devcon can synchronize without becoming a continuous
Event Mode dependency. It is a development/demo topology label, not Event-readiness
certification.

## Out of scope

- Secret storage or display.
- Automatic business-state bootstrap while parsing configuration.
- Runtime-profile authority over Session, association, package, or publication decisions.
