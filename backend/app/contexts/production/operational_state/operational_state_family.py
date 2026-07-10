from enum import StrEnum


class OperationalStateFamily(StrEnum):
    DIRECTLY_OBSERVABLE = "directly_observable"
    EVIDENCE_DERIVED = "evidence_derived"
    STAGEFLOW_READINESS = "stageflow_readiness"
    ENVIRONMENTAL_CONTEXT = "environmental_context"
    UNKNOWN = "unknown"
