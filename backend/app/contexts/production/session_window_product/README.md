# Production Session Window Product

ED-0012 adds the first specialized Operational Product in the Production bounded context.

A Session Window Product is the verified production-media window for scheduled session information inside a continuous `RecordingBlock`. It is not the scheduled session itself.

## Product Relationship

The product connects:

- an `OperationalProduct` by ID
- a `RecordingBlock` by ID
- a `ScheduleReference`
- a `TimelineRange`
- Finding and Verification Decision IDs through lineage

The product does not embed `OperationalProduct`, `Finding`, or `VerificationDecision` objects.

## Boundary Quality

`SessionWindowProductBoundary` records start and end boundary confidence from `0.0` through `1.0`.

Boundary confidence is a specialized product quality signal. It is not Finding confidence, review state, verification state, or editorial scoring.

## Lineage

`SessionWindowProductLineage` keeps ID-only traceability to the reasoning that produced the product. At least one Finding ID or Verification Decision ID is required.

## Relationship To ED-0005 SessionWindow

ED-0005 `SessionWindow` remains a timeline contract that can represent proposed or verified media ranges.

ED-0012 `SessionWindowProduct` is a higher-level specialized Operational Product created downstream of verified reasoning. Future architecture work should decide whether the ED-0005 name should be narrowed, deprecated, or folded into this product model once full Session modeling exists.

## Exclusions

This package does not implement Session aggregates, speaker metadata, schedule synchronization, file paths, media chunks, transcript text, clips, rendering, packages, APIs, persistence, workers, queues, or provider-specific integrations.
