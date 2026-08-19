from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class DevconPublishError(RuntimeError):
    """A bounded Devcon Session publication operation failed."""


class DevconPublishContractError(DevconPublishError):
    """A Devcon Session response did not satisfy the required contract."""


@dataclass(frozen=True, slots=True)
class RemoteDevconSession:
    session_id: str
    event_id: str
    transcript_text: str | None
    duration_seconds: int | None


SessionRequester = Callable[
    [str, str, bytes | None, int, int],
    tuple[int, Mapping[str, object] | None],
]


def _request_json(
    method: str,
    url: str,
    body: bytes | None,
    timeout_seconds: int,
    maximum_bytes: int,
) -> tuple[int, Mapping[str, object] | None]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "StageFlow-Demo-Devcon-Publish/1.0",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            status = response.status
            declared_length = response.headers.get("Content-Length")
            if declared_length is not None and int(declared_length) > maximum_bytes:
                raise DevconPublishError("devcon_publish_response_too_large")
            payload_bytes = response.read(maximum_bytes + 1)
    except HTTPError as exc:
        raise DevconPublishError(f"devcon_publish_http_status_{exc.code}") from None
    except (OSError, TimeoutError, URLError, ValueError):
        raise DevconPublishError("devcon_publish_unavailable") from None
    if len(payload_bytes) > maximum_bytes:
        raise DevconPublishError("devcon_publish_response_too_large")
    if not payload_bytes:
        return status, None
    try:
        payload = json.loads(payload_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DevconPublishContractError(
            "devcon_publish_response_invalid_json"
        ) from None
    if not isinstance(payload, dict):
        raise DevconPublishContractError("devcon_publish_response_not_object")
    return status, cast(Mapping[str, object], payload)


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DevconPublishContractError(f"devcon_publish_{field}_invalid")
    return value.strip()


def _optional_duration(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DevconPublishContractError("devcon_publish_duration_invalid")
    duration = int(value)
    if duration < 0 or float(duration) != float(value):
        raise DevconPublishContractError("devcon_publish_duration_invalid")
    return duration


class DevconSessionPublishAdapter:
    _maximum_response_bytes = 2 * 1024 * 1024

    def __init__(
        self,
        *,
        base_url: str = "https://api.devcon.org",
        timeout_seconds: int = 10,
        requester: SessionRequester = _request_json,
    ) -> None:
        if base_url.rstrip("/") != "https://api.devcon.org":
            raise ValueError("devcon_publish_official_endpoint_required")
        if timeout_seconds < 1 or timeout_seconds > 30:
            raise ValueError("devcon_publish_timeout_out_of_bounds")
        self._base_url = "https://api.devcon.org"
        self._timeout_seconds = timeout_seconds
        self._requester = requester

    def get_session(self, session_id: str) -> RemoteDevconSession:
        normalized_id = session_id.strip()
        if not normalized_id:
            raise ValueError("devcon_publish_session_id_required")
        status, payload = self._requester(
            "GET",
            f"{self._base_url}/sessions/{quote(normalized_id, safe='')}",
            None,
            self._timeout_seconds,
            self._maximum_response_bytes,
        )
        if status != 200 or payload is None:
            raise DevconPublishError(f"devcon_publish_http_status_{status}")
        if payload.get("status") != 200 or not isinstance(payload.get("data"), dict):
            raise DevconPublishContractError("devcon_publish_envelope_invalid")
        data = cast(Mapping[str, object], payload["data"])
        transcript = data.get("transcript_text")
        if transcript is not None and not isinstance(transcript, str):
            raise DevconPublishContractError("devcon_publish_transcript_text_invalid")
        return RemoteDevconSession(
            session_id=_required_text(data.get("id"), "session_id"),
            event_id=_required_text(data.get("eventId"), "event_id"),
            transcript_text=transcript,
            duration_seconds=_optional_duration(data.get("duration")),
        )

    def put_enrichment(
        self,
        *,
        session_id: str,
        api_key: str,
        transcript_text: str,
        duration_seconds: int,
    ) -> None:
        normalized_id = session_id.strip()
        if not normalized_id:
            raise ValueError("devcon_publish_session_id_required")
        if not api_key.strip():
            raise ValueError("devcon_publish_credential_required")
        if not transcript_text.strip():
            raise ValueError("devcon_publish_transcript_required")
        if duration_seconds <= 0:
            raise ValueError("devcon_publish_duration_required")
        body = json.dumps(
            {
                "transcript_text": transcript_text,
                "duration": duration_seconds,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        query = urlencode({"apiKey": api_key})
        status, _ = self._requester(
            "PUT",
            f"{self._base_url}/sessions/{quote(normalized_id, safe='')}?{query}",
            body,
            self._timeout_seconds,
            self._maximum_response_bytes,
        )
        if status != 204:
            raise DevconPublishError(f"devcon_publish_http_status_{status}")


__all__ = [
    "DevconPublishContractError",
    "DevconPublishError",
    "DevconSessionPublishAdapter",
    "RemoteDevconSession",
    "SessionRequester",
]
