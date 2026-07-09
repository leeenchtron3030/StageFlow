from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ObservationInterpreterPolicy:
    """Small policy settings for Production Event to Observation translation."""

    allow_zero_observations: bool = True
    allow_multiple_observations: bool = True
    require_source_event_traceability: bool = True
