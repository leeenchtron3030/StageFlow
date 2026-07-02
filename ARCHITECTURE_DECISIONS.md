# Architecture Decisions

## Purpose

This document records approved Architecture Decision Records for StageFlow. ADRs in this file describe foundational choices that implementation must respect.

## ADR-0001 StageFlow Is Implemented as a Modular Monolith

StageFlow is implemented as a modular monolith. Internal boundaries should follow the approved architecture layers and bounded contexts before any distributed-service boundary is introduced.

## ADR-0002 Sessions Are the Primary Production Aggregate

Sessions are the primary production aggregate. Implementation work must treat session-centered production coordination as a core architectural organizing principle.

## ADR-0003 Media Chunks Are Storage Artifacts, Not Editorial Objects

Media Chunks are storage artifacts. They must not be promoted into editorial domain objects unless a future approved architecture decision changes that boundary.

## ADR-0004 StageFlow Owns Workflow, Not Conference Data

StageFlow owns production workflow. It must not become the source of truth for conference data that belongs to external systems or upstream conference management processes.

## ADR-0005 External Integrations Use Adapters Within the Integration Context

External integrations use adapters within the Integration Context. Integration-specific concerns should remain behind adapter boundaries rather than leaking into core domain workflows.
