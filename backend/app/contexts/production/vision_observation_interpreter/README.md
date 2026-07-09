# Vision Observation Interpreter

ED-0030 adds a concrete Observation Interpreter for Vision Source events.

The Vision Observation Interpreter translates vision-related `ProductionEvent` objects into objective `Observation` objects such as:

- `text_region` -> `Visual text region was detected.`
- `slide_change` -> `Visual slide change was detected.`
- `image_change` -> `Visual image change was detected.`
- `camera_obstruction` -> `Visual camera obstruction was detected.`
- vision-source `system_status_changed` -> `Vision source status changed.`

Vision systems report visual phenomena. This interpreter reports that visual phenomena were detected. It does not interpret visual meaning.

## Boundaries

The interpreter:

- accepts only supported vision Production Event types from the vision source
- treats `system_status_changed` conservatively and requires the vision adapter metadata marker
- creates only vision activity Observations
- preserves visual detection metadata as reported when present
- uses ED-0025 `ObservationLocation` anchors truthfully
- may produce zero Observations for unsupported or non-vision events

The interpreter does not perform OCR, interpret detected text, identify logos, identify faces, identify people, classify scene meaning, infer sessions, infer clips, infer production state, create reasoning artifacts, introduce persistence, create APIs, create queues, create workers, run AI, or introduce provider-specific behavior.

## Visual Phenomena

Vision is observable. Visual meaning is reasoning.

This interpreter may carry visual detection metadata as observed data, but it does not rewrite, summarize, normalize, or interpret that metadata as semantic meaning.

Generated Observations anchor to a recording block when one is available. If no recording block is known, they anchor to the source event's wall-clock occurrence time.
