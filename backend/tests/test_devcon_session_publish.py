from __future__ import annotations

import json
from collections.abc import Mapping
from urllib.parse import parse_qs, urlsplit

import pytest

from app.infrastructure.devcon.session_publish import (
    DevconPublishContractError,
    DevconPublishError,
    DevconSessionPublishAdapter,
)


def test_session_publish_adapter_reads_identity_and_puts_only_approved_fields() -> None:
    requests: list[tuple[str, str, bytes | None]] = []

    def request(
        method: str,
        url: str,
        body: bytes | None,
        timeout: int,
        maximum_bytes: int,
    ) -> tuple[int, Mapping[str, object] | None]:
        requests.append((method, url, body))
        assert timeout == 5
        assert maximum_bytes == 2 * 1024 * 1024
        if method == "GET":
            return (
                200,
                {
                    "status": 200,
                    "data": {
                        "id": "target-session",
                        "eventId": "test-devcon-8",
                        "transcript_text": "read back",
                        "duration": 120,
                    },
                },
            )
        return 204, None

    adapter = DevconSessionPublishAdapter(timeout_seconds=5, requester=request)

    session = adapter.get_session("target-session")
    adapter.put_enrichment(
        session_id="target-session",
        api_key="credential-sentinel",
        transcript_text="normalized evidence",
        duration_seconds=120,
    )

    assert session.event_id == "test-devcon-8"
    assert session.transcript_text == "read back"
    assert requests[0][0] == "GET"
    assert requests[1][0] == "PUT"
    query = parse_qs(urlsplit(requests[1][1]).query)
    assert query == {"apiKey": ["credential-sentinel"]}
    assert requests[1][2] is not None
    assert json.loads(requests[1][2]) == {
        "transcript_text": "normalized evidence",
        "duration": 120,
    }


def test_session_publish_adapter_rejects_wrong_endpoint_and_invalid_contract() -> None:
    with pytest.raises(ValueError, match="official_endpoint"):
        DevconSessionPublishAdapter(base_url="https://example.invalid")

    def invalid(
        method: str,
        url: str,
        body: bytes | None,
        timeout: int,
        maximum_bytes: int,
    ) -> tuple[int, Mapping[str, object] | None]:
        del method, url, body, timeout, maximum_bytes
        return 200, {"status": 200, "data": {"id": "target-session"}}

    with pytest.raises(DevconPublishContractError):
        DevconSessionPublishAdapter(requester=invalid).get_session("target-session")


def test_session_publish_failures_do_not_include_credentials() -> None:
    def failed(
        method: str,
        url: str,
        body: bytes | None,
        timeout: int,
        maximum_bytes: int,
    ) -> tuple[int, Mapping[str, object] | None]:
        del method, url, body, timeout, maximum_bytes
        return 401, None

    adapter = DevconSessionPublishAdapter(requester=failed)

    with pytest.raises(DevconPublishError) as caught:
        adapter.put_enrichment(
            session_id="target-session",
            api_key="credential-sentinel",
            transcript_text="normalized evidence",
            duration_seconds=120,
        )

    assert "credential-sentinel" not in str(caught.value)
    assert "normalized evidence" not in str(caught.value)
