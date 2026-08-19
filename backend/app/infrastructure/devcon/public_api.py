from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import cast
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.contexts.integration.devcon import ExternalProgramItem
from app.core.config.deployment import DevconReadConfiguration


class DevconReadError(RuntimeError):
    """The bounded public Devcon read could not complete."""


class DevconContractError(DevconReadError):
    """The public Devcon response did not satisfy the expected contract."""


JsonFetcher = Callable[[str, int, int], Mapping[str, object]]


def _fetch_json(url: str, timeout_seconds: int, maximum_bytes: int) -> Mapping[str, object]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "StageFlow-Demo-Program-Read/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            if response.status != 200:
                raise DevconReadError(f"devcon_http_status_{response.status}")
            declared_length = response.headers.get("Content-Length")
            if declared_length is not None and int(declared_length) > maximum_bytes:
                raise DevconReadError("devcon_response_too_large")
            body = response.read(maximum_bytes + 1)
    except DevconReadError:
        raise
    except (OSError, TimeoutError, ValueError) as exc:
        raise DevconReadError("devcon_read_unavailable") from exc
    if len(body) > maximum_bytes:
        raise DevconReadError("devcon_response_too_large")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DevconContractError("devcon_response_invalid_json") from exc
    if not isinstance(payload, dict):
        raise DevconContractError("devcon_response_not_object")
    return cast(Mapping[str, object], payload)


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DevconContractError(f"devcon_session_{field}_invalid")
    return value.strip()


def _timestamp(value: object, field: str) -> datetime:
    if isinstance(value, bool):
        raise DevconContractError(f"devcon_session_{field}_invalid")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000, tz=UTC)
    if isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise DevconContractError(f"devcon_session_{field}_invalid") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise DevconContractError(f"devcon_session_{field}_naive")
        return parsed
    raise DevconContractError(f"devcon_session_{field}_invalid")


def _speaker_names(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise DevconContractError("devcon_session_speakers_invalid")
    speakers = cast(list[object], value)
    names: list[str] = []
    for speaker_value in speakers:
        if not isinstance(speaker_value, dict):
            raise DevconContractError("devcon_session_speaker_invalid")
        speaker = cast(Mapping[str, object], speaker_value)
        name = speaker.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return tuple(names)


class DevconPublicProgramAdapter:
    _maximum_page_bytes = 8 * 1024 * 1024

    def __init__(
        self,
        configuration: DevconReadConfiguration,
        *,
        fetch_json: JsonFetcher = _fetch_json,
    ) -> None:
        self._configuration = configuration
        self._fetch_json = fetch_json

    def fetch_program(self) -> tuple[ExternalProgramItem, ...]:
        offset = 0
        total: int | None = None
        selected: dict[str, ExternalProgramItem] = {}
        while total is None or offset < total:
            query = urlencode(
                {
                    "from": offset,
                    "size": self._configuration.page_size,
                    "event": self._configuration.event_id,
                    "room": self._configuration.room_id,
                }
            )
            payload = self._fetch_json(
                f"{self._configuration.base_url}/sessions?{query}",
                self._configuration.timeout_seconds,
                self._maximum_page_bytes,
            )
            status = payload.get("status")
            data_value = payload.get("data")
            if status != 200 or not isinstance(data_value, dict):
                raise DevconContractError("devcon_response_envelope_invalid")
            data = cast(Mapping[str, object], data_value)
            raw_total = data.get("total")
            raw_items_value = data.get("items")
            if (
                isinstance(raw_total, bool)
                or not isinstance(raw_total, int)
                or raw_total < 0
                or not isinstance(raw_items_value, list)
            ):
                raise DevconContractError("devcon_session_page_invalid")
            raw_items = cast(list[object], raw_items_value)
            if raw_total > self._configuration.maximum_catalog_sessions:
                raise DevconReadError("devcon_catalog_exceeds_configured_bound")
            if total is not None and raw_total != total:
                raise DevconContractError("devcon_catalog_changed_during_read")
            total = raw_total
            if not raw_items and offset < total:
                raise DevconContractError("devcon_session_page_empty_before_total")

            for raw_item_value in raw_items:
                if not isinstance(raw_item_value, dict):
                    raise DevconContractError("devcon_session_item_invalid")
                raw_item = cast(Mapping[str, object], raw_item_value)
                if raw_item.get("eventId") != self._configuration.event_id:
                    continue
                room_id = raw_item.get("slot_roomId")
                room_value = raw_item.get("slot_room")
                if room_id != self._configuration.room_id:
                    continue
                if not isinstance(room_value, dict):
                    raise DevconContractError("devcon_session_room_invalid")
                room = cast(Mapping[str, object], room_value)
                item = ExternalProgramItem(
                    event_id=_required_text(raw_item.get("eventId"), "event_id"),
                    session_id=_required_text(raw_item.get("id"), "id"),
                    room_id=_required_text(room_id, "room_id"),
                    room_name=_required_text(room.get("name"), "room_name"),
                    title=_required_text(raw_item.get("title"), "title"),
                    speakers=_speaker_names(raw_item.get("speakers")),
                    planned_start=_timestamp(raw_item.get("slot_start"), "slot_start"),
                    planned_end=_timestamp(raw_item.get("slot_end"), "slot_end"),
                )
                existing = selected.get(item.session_id)
                if existing is not None and existing != item:
                    raise DevconContractError("devcon_session_identity_conflict")
                selected[item.session_id] = item

            offset += len(raw_items)
            if not raw_items:
                break
        return tuple(
            sorted(
                selected.values(),
                key=lambda item: (item.planned_start, item.session_id),
            )
        )


__all__ = [
    "DevconContractError",
    "DevconPublicProgramAdapter",
    "DevconReadError",
    "JsonFetcher",
]
