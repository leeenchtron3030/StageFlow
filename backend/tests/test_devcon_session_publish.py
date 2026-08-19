from __future__ import annotations

import json
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import ClassVar
from urllib.parse import urlsplit

import pytest

from app.infrastructure.devcon import session_publish
from app.infrastructure.devcon.session_publish import (
    DevconPublishContractError,
    DevconPublishError,
    DevconSessionPublishAdapter,
)


@contextmanager
def _local_http_server(
    handler: type[BaseHTTPRequestHandler],
) -> Generator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


class CapturingHandler(BaseHTTPRequestHandler):
    observed: ClassVar[dict[str, object]] = {}

    def do_PUT(self) -> None:  # noqa: N802
        content_length = int(self.headers["Content-Length"])
        type(self).observed = {
            "path": self.path,
            "content_length": content_length,
            "content_type": self.headers["Content-Type"],
            "api_key": self.headers["x-api-key"],
            "body": self.rfile.read(content_length),
        }
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        del format, args


class RejectedHandler(BaseHTTPRequestHandler):
    calls: ClassVar[int] = 0

    def do_PUT(self) -> None:  # noqa: N802
        type(self).calls += 1
        response = json.dumps({"status": 400, "message": "No Body"}).encode(
            "utf-8"
        )
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


def test_session_publish_adapter_uses_sources_contract_and_only_approved_fields() -> None:
    requests: list[
        tuple[str, str, bytes | None, Mapping[str, str]]
    ] = []

    def request(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: int,
        maximum_bytes: int,
    ) -> tuple[int, Mapping[str, object] | None]:
        requests.append((method, url, body, headers))
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
    transcript = "Ol\u00e1, \u4e16\u754c \u2014 normalized evidence"

    session = adapter.get_session("target-session")
    adapter.put_enrichment(
        session_id="target-session",
        api_key="credential-sentinel",
        transcript_text=transcript,
        duration_seconds=120,
    )

    assert session.event_id == "test-devcon-8"
    assert session.transcript_text == "read back"
    assert requests[0][0] == "GET"
    method, url, body, headers = requests[1]
    parsed_url = urlsplit(url)
    assert method == "PUT"
    assert parsed_url.path == "/sessions/sources/target-session"
    assert parsed_url.query == ""
    assert headers["x-api-key"] == "credential-sentinel"
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert "credential-sentinel" not in url
    assert body is not None
    assert body.decode("utf-8") == json.dumps(
        {"transcript_text": transcript, "duration": 120},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert json.loads(body) == {
        "transcript_text": transcript,
        "duration": 120,
    }

def test_durable_session_reader_uses_exact_git_file_without_credentials() -> None:
    requests: list[
        tuple[str, str, bytes | None, Mapping[str, str]]
    ] = []

    def request(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: int,
        maximum_bytes: int,
    ) -> tuple[int, Mapping[str, object] | None]:
        requests.append((method, url, body, headers))
        assert timeout == 5
        assert maximum_bytes == 2 * 1024 * 1024
        return (
            200,
            {
                "id": "target-session",
                "eventId": "test-devcon-8",
                "transcript_text": "durable synthetic transcript",
                "duration": 120,
            },
        )

    adapter = DevconSessionPublishAdapter(timeout_seconds=5, requester=request)
    durable = adapter.get_durable_session(
        event_id="test-devcon-8",
        session_id="target-session",
    )

    assert durable.session_id == "target-session"
    assert durable.event_id == "test-devcon-8"
    assert durable.duration_seconds == 120
    method, url, body, headers = requests[0]
    parsed_url = urlsplit(url)
    assert method == "GET"
    assert parsed_url.path == (
        "/repos/efdevcon/monorepo/contents/"
        "devcon-api/data/sessions/test-devcon-8/target-session.json"
    )
    assert parsed_url.query == "ref=main"
    assert body is None
    assert headers["Accept"] == "application/vnd.github.raw+json"
    assert headers["Cache-Control"] == "no-cache"
    assert "x-api-key" not in headers



def test_urllib_request_sends_json_headers_content_length_and_unicode() -> None:
    CapturingHandler.observed = {}
    transcript = (
        "Za\u017c\u00f3\u0142\u0107 g\u0119\u015bl\u0105 "
        "ja\u017a\u0144 \u2014 \u3053\u3093\u306b\u3061\u306f"
    )
    body = json.dumps(
        {"transcript_text": transcript, "duration": 90},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    with _local_http_server(CapturingHandler) as base_url:
        status, payload = session_publish._request_json(  # pyright: ignore[reportPrivateUsage]
            "PUT",
            f"{base_url}/sessions/sources/unicode-session",
            body,
            {
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "x-api-key": "credential-sentinel",
            },
            5,
            1024,
        )

    assert status == 204
    assert payload is None
    assert CapturingHandler.observed == {
        "path": "/sessions/sources/unicode-session",
        "content_length": len(body),
        "content_type": "application/json; charset=utf-8",
        "api_key": "credential-sentinel",
        "body": body,
    }
    assert json.loads(body)["transcript_text"] == transcript


def test_devcon_no_body_response_maps_to_bounded_reason_without_retry() -> None:
    RejectedHandler.calls = 0
    requested_urls: list[str] = []

    with _local_http_server(RejectedHandler) as base_url:

        def request(
            method: str,
            url: str,
            body: bytes | None,
            headers: Mapping[str, str],
            timeout: int,
            maximum_bytes: int,
        ) -> tuple[int, Mapping[str, object] | None]:
            requested_urls.append(url)
            return session_publish._request_json(  # pyright: ignore[reportPrivateUsage]
                method,
                f"{base_url}/sessions/sources/target-session",
                body,
                headers,
                timeout,
                maximum_bytes,
            )

        adapter = DevconSessionPublishAdapter(requester=request)
        with pytest.raises(
            DevconPublishError,
            match=r"^devcon_publish_rejected:no_body$",
        ):
            adapter.put_enrichment(
                session_id="target-session",
                api_key="credential-sentinel",
                transcript_text="normalized evidence",
                duration_seconds=120,
            )

    assert requested_urls == [
        "https://api.devcon.org/sessions/sources/target-session"
    ]
    assert RejectedHandler.calls == 1


@pytest.mark.parametrize(
    ("status", "message", "reason"),
    [
        (401, "Unauthorized", "unauthorized"),
        (404, "Not Found", "not_found"),
        (500, "Internal Server Error", "internal_server_error"),
    ],
)
def test_publish_failure_statuses_remain_distinguishable(
    status: int, message: str, reason: str
) -> None:
    calls = 0

    def failed(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: int,
        maximum_bytes: int,
    ) -> tuple[int, Mapping[str, object] | None]:
        nonlocal calls
        del method, url, body, headers, timeout, maximum_bytes
        calls += 1
        return status, {"status": status, "message": message}

    adapter = DevconSessionPublishAdapter(requester=failed)
    with pytest.raises(
        DevconPublishError,
        match=rf"^devcon_publish_rejected:{reason}$",
    ):
        adapter.put_enrichment(
            session_id="target-session",
            api_key="credential-sentinel",
            transcript_text="normalized evidence",
            duration_seconds=120,
        )
    assert calls == 1


def test_session_publish_adapter_rejects_wrong_endpoint_and_invalid_contract() -> None:
    with pytest.raises(ValueError, match="official_endpoint"):
        DevconSessionPublishAdapter(base_url="https://example.invalid")

    def invalid(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: int,
        maximum_bytes: int,
    ) -> tuple[int, Mapping[str, object] | None]:
        del method, url, body, headers, timeout, maximum_bytes
        return 200, {"status": 200, "data": {"id": "target-session"}}

    with pytest.raises(DevconPublishContractError):
        DevconSessionPublishAdapter(requester=invalid).get_session("target-session")


def test_session_publish_failures_do_not_include_sensitive_values() -> None:
    def failed(
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout: int,
        maximum_bytes: int,
    ) -> tuple[int, Mapping[str, object] | None]:
        del method, url, body, headers, timeout, maximum_bytes
        return 400, {"status": 400, "message": "arbitrary upstream diagnostic"}

    adapter = DevconSessionPublishAdapter(requester=failed)

    with pytest.raises(DevconPublishError) as caught:
        adapter.put_enrichment(
            session_id="target-session",
            api_key="credential-sentinel",
            transcript_text="normalized evidence",
            duration_seconds=120,
        )

    assert str(caught.value) == "devcon_publish_http_status_400"
    assert "credential-sentinel" not in str(caught.value)
    assert "normalized evidence" not in str(caught.value)
    assert "arbitrary upstream diagnostic" not in str(caught.value)
