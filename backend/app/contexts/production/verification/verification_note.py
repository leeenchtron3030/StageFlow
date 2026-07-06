from dataclasses import dataclass
from enum import StrEnum


class VerificationNoteVisibility(StrEnum):
    INTERNAL = "internal"
    REVIEWER = "reviewer"
    OPERATOR = "operator"
    PUBLIC = "public"


@dataclass(frozen=True, slots=True)
class VerificationNote:
    """Human-readable context attached to a verification decision."""

    text: str
    visibility: VerificationNoteVisibility | None = None

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("VerificationNote text must not be empty.")
