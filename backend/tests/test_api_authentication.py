from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast

import pytest
from fastapi.testclient import TestClient
from httpx import Response

import app.api.v1.demo as demo_api
from app.api.authentication import API_SECRET_HEADER
from app.core.config.settings import get_settings
from app.main import create_app

TEST_SECRET = "stageflow-test-only-shared-secret-0123456789"
AUTH_HEADERS = {API_SECRET_HEADER: TEST_SECRET}


class SyncHttpClient(Protocol):
    def get(self, url: str, *, headers: Mapping[str, str] | None = None) -> Response: ...

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: object | None = None,
    ) -> Response: ...

    def options(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> Response: ...


def test_health_stays_public_while_all_operational_routers_require_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = cast(SyncHttpClient, TestClient(create_app()))

    assert client.get("/api/v1/health").status_code == 200
    for path in (
        "/api/v1/kernel/status",
        "/api/v1/media-assets/10000000-0000-4000-8000-000000000001/timing-evidence",
    ):
        assert client.get(path).status_code == 401
        assert client.get(path, headers={API_SECRET_HEADER: "incorrect-secret"}).status_code == 401
    assert client.get("/api/v1/kernel/status", headers=AUTH_HEADERS).status_code == 200
    assert "incorrect-secret" not in caplog.text


def test_unauthorized_mutation_is_rejected_before_handler_logic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def must_not_run(request: object) -> object:
        del request
        raise AssertionError("handler logic ran before authentication")

    monkeypatch.setattr(demo_api, "_components", must_not_run)
    client = cast(SyncHttpClient, TestClient(create_app()))

    response = client.post("/api/v1/demo/program/refresh", json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_cors_uses_explicit_allow_list_and_api_header() -> None:
    client = cast(SyncHttpClient, TestClient(create_app()))
    allowed = client.options(
        "/api/v1/kernel/status",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": API_SECRET_HEADER,
        },
    )
    denied = client.options(
        "/api/v1/kernel/status",
        headers={
            "Origin": "http://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
    assert API_SECRET_HEADER.casefold() in allowed.headers[
        "access-control-allow-headers"
    ].casefold()
    assert "access-control-allow-origin" not in denied.headers


def test_startup_fails_closed_when_shared_secret_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("STAGEFLOW_API_SHARED_SECRET")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="stageflow_api_shared_secret_required"):
            with TestClient(create_app()):
                pass
    finally:
        monkeypatch.setenv("STAGEFLOW_API_SHARED_SECRET", TEST_SECRET)
        get_settings.cache_clear()


def test_invalid_security_configuration_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STAGEFLOW_API_SHARED_SECRET", "too-short")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="at least 32 characters"):
        create_app()

    monkeypatch.setenv("STAGEFLOW_API_SHARED_SECRET", TEST_SECRET)
    monkeypatch.setenv("STAGEFLOW_CORS_ALLOWED_ORIGINS", "*")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="invalid origin"):
        create_app()
    get_settings.cache_clear()
