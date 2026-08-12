# StageFlow Mission Control UX Specification
**Status:** Draft v0.1
**Source fidelity:** Recovered accepted UX direction; not a verbatim reproduction.

> **Repository interpretation:** This is a recovered accepted-design summary from the
> handoff bundle, not a verbatim historical chat draft. It records product direction
> without claiming the described frontend or supporting capabilities are implemented.

## Purpose

Mission Control is the Producer's default MacBook screen and should answer:

**Does anything need me?**

Within roughly two seconds the Producer should understand:

- overall Event health,
- whether any Stage requires attention,
- whether any human intervention is required.

Within roughly ten seconds the Producer should understand:

- what happened,
- where,
- operational consequence,
- evidence,
- next action.

## Stable five-region structure

1. Event Header
2. Global Attention Banner
3. Stage Matrix
4. Attention Panel
5. Infrastructure Strip

## Stage Matrix

Default columns:

- Stage
- Session
- Media
- State

Moment/intelligence activity may appear as compact contextual information, such as Candidate counts and processing lag.

Rows remain in fixed configured Stage order. Alerts do not reorder the Stage matrix.

## Attention

Attention is not a chronological log. Sort by operational urgency, impact, then age.

Each attention item should answer:

- what,
- where,
- since when,
- impact,
- evidence,
- action.

## Worker / intelligence representation

Prefer consequence-first language:

- `Moment detection +41 sec behind`
- `Transcription +28 sec behind`

Raw GPU/VRAM belongs in drill-down diagnostics.

If a worker is unavailable:

**Moment detection deferred. Session recording and media ingest continue normally.**

## PostgreSQL loss/recovery

If PostgreSQL is unavailable:

- StageFlow authority is paused,
- primary media remains untouched,
- authoritative actions are disabled.

When PostgreSQL returns but before a fresh reconciliation succeeds:

**Recovering**

Do not report ready merely because the database is reachable again.

## Turnover ambiguity

When prior assembling Session and current active Session are both plausible for interval-less media:

- show a Review item,
- state that media is preserved,
- do not guess ownership.

## Reopened completion

If late media or reassignment changes a completed package:

- prior approval remains historical,
- new package revision requires review.

---
