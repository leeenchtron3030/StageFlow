from enum import StrEnum


class VerificationReason(StrEnum):
    OPERATOR_CONFIRMATION = "operator_confirmation"
    SCHEDULE_ALIGNMENT = "schedule_alignment"
    EDITORIAL_REVIEW = "editorial_review"
    TECHNICAL_REVIEW = "technical_review"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    DUPLICATE_FINDING = "duplicate_finding"
    MANUAL_ADJUSTMENT = "manual_adjustment"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    QUALITY_ISSUE = "quality_issue"
    OTHER = "other"
