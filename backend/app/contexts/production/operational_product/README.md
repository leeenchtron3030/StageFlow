# Production Operational Product

## Purpose

This package contains the foundational operational product contracts introduced by ED-0011.

Operational products begin the execution layer. They are downstream outputs of verified reasoning and remain traceable to findings and verification decisions.

## Reasoning To Execution Boundary

- Timeline, observation, evidence, hypothesis, finding, and verification form the reasoning layer.
- Operational products begin the execution layer.
- Specialized products are implemented by future directives.

## What Belongs Here

- `OperationalProduct`
- `OperationalProductType`
- `OperationalProductStatus`
- `OperationalProductOrigin`
- `OperationalProductReference`
- `OperationalProductSummary`

## What Does Not Belong Here

- Specialized session window implementation.
- Specialized clip implementation.
- Specialized alert implementation.
- Specialized incident implementation.
- Specialized metadata record implementation.
- Specialized package task implementation.
- Persistence.
- APIs.
- Queues or workers.
- Frontend behavior.

## Traceability

Operational products reference finding IDs and verification decision IDs. They do not embed finding or verification decision objects.
