from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from app.shared.errors import StageFlowError

_UNSET = object()


@dataclass(frozen=True, slots=True)
class Result[T]:
    """Explicit success/failure result for expected control flow."""

    _value: T | object = _UNSET
    _error: StageFlowError | None = None

    @staticmethod
    def ok[TValue](value: TValue) -> Result[TValue]:
        return Result(_value=value)

    @classmethod
    def fail(cls, error: StageFlowError) -> Result[T]:
        return cls(_error=error)

    @property
    def is_success(self) -> bool:
        return self._error is None and self._value is not _UNSET

    @property
    def is_failure(self) -> bool:
        return self._error is not None

    @property
    def value(self) -> T:
        if self._error is not None:
            raise RuntimeError("Cannot access value from a failed Result.")
        if self._value is _UNSET:
            raise RuntimeError("Cannot access value from an unset Result.")
        return cast(T, self._value)

    @property
    def error(self) -> StageFlowError:
        if self._error is None:
            raise RuntimeError("Cannot access error from a successful Result.")
        return self._error
