from enum import StrEnum


class EvidenceContextSource(StrEnum):
    """Describes where one resolved Evidence context value originated."""

    OBSERVATION_FIRST_CLASS = "observation_first_class"
    EVIDENCE_FIRST_CLASS = "evidence_first_class"
    STRUCTURED_LEGACY_FIELD = "structured_legacy_field"
    STRUCTURED_METADATA_FALLBACK = "structured_metadata_fallback"
    COMPOSED_FROM_SOURCES = "composed_from_sources"
    EXPLICIT_BUILDER_INPUT = "explicit_builder_input"
    UNKNOWN = "unknown"
