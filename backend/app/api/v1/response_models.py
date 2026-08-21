from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, cast

from pydantic import AfterValidator, BaseModel, ConfigDict, PlainSerializer

from app.contexts.events import ProgramExpectationChange
from app.shared.metadata import freeze_metadata


def _freeze_json_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return cast(Mapping[str, object], freeze_metadata(value))


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {
            str(key): _json_value(nested) for key, nested in mapping.items()
        }
    if isinstance(value, tuple | frozenset):
        items = cast(tuple[object, ...] | frozenset[object], value)
        return [_json_value(nested) for nested in items]
    return value


def _serialize_json_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return {key: _json_value(nested) for key, nested in value.items()}


ImmutableJsonMapping = Annotated[
    Mapping[str, object],
    AfterValidator(_freeze_json_mapping),
    PlainSerializer(_serialize_json_mapping, return_type=dict[str, object]),
]


def _freeze_int_mapping(value: Mapping[str, int]) -> Mapping[str, int]:
    return cast(Mapping[str, int], freeze_metadata(value))


ImmutableIntMapping = Annotated[
    Mapping[str, int],
    AfterValidator(_freeze_int_mapping),
    PlainSerializer(dict, return_type=dict[str, int]),
]


class ProgramFieldChangeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    previous: str | None
    current: str | None


class ProgramChangeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    expectation_id: str
    expectation_key: str
    title: str
    external_session_id: str | None
    fields: tuple[ProgramFieldChangeResponse, ...]


def program_change_responses(
    changes: Sequence[ProgramExpectationChange],
) -> tuple[ProgramChangeResponse, ...]:
    return tuple(
        ProgramChangeResponse(
            kind=change.kind.value,
            expectation_id=change.expectation_id.value,
            expectation_key=change.expectation_key,
            title=change.title,
            external_session_id=change.external_session_id,
            fields=tuple(
                ProgramFieldChangeResponse(
                    field=field.field,
                    previous=field.previous,
                    current=field.current,
                )
                for field in change.fields
            ),
        )
        for change in changes
    )


__all__ = [
    "ImmutableIntMapping",
    "ImmutableJsonMapping",
    "ProgramChangeResponse",
    "ProgramFieldChangeResponse",
    "program_change_responses",
]
