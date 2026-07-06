from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class CorrelationId:
    """Generic UUID-compatible workflow tracing identifier."""

    value: str

    def __post_init__(self) -> None:
        UUID(self.value)

    @classmethod
    def new(cls) -> CorrelationId:
        return cls(str(uuid4()))

    @classmethod
    def parse(cls, value: str) -> CorrelationId:
        return cls(value)

    def __str__(self) -> str:
        return self.value

    def to_json(self) -> str:
        return self.value
