# Vision Source Adapter

ED-0021 adds backend-only Vision Source Adapter contracts.

A Vision Source Adapter reports that visual detections or visual artifacts exist. It reports observable visual phenomena only.

## Runtime Flow

Vision Source -> Vision Source Adapter -> Production Event -> Dispatcher -> Interpreter -> Observation

Vision adapters report visual detections. They do not report meaning. Semantic interpretation belongs to later Interpreters and reasoning.

## Production Event Mapping

Visual detection events may be mapped only to generic Production Event types:

- `visual_detection_available`
- `system_status_changed`

`created`, `updated`, and `finalized` detection statuses map to `visual_detection_available`. `failed`, `deleted`, and `unknown` map to `system_status_changed`.

## Exclusions

Reporting visual detection activity is not computer vision execution.

This package does not implement OCR, object detection, face recognition, logo recognition, scene understanding, model calls, source APIs, persistence, queues, workers, dispatch execution, frontend behavior, or visual meaning interpretation.

The mapping does not create Observations, Evidence, Hypotheses, Findings, Operational Products, Sessions, RecordingBlocks, TimelinePositions, or TimelineRanges.
