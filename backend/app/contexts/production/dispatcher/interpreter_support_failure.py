from __future__ import annotations

from dataclasses import dataclass

from app.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class InterpreterSupportFailure:
    """Sanitized failure while evaluating whether an interpreter supports an Event."""

    interpreter_id: EntityId
    failure_code: str
    warning: str

    def __post_init__(self) -> None:
        if not self.failure_code.strip():
            raise ValueError("InterpreterSupportFailure failure_code must not be empty.")
        if not self.warning.strip():
            raise ValueError("InterpreterSupportFailure warning must not be empty.")


__all__ = ["InterpreterSupportFailure"]
