from typing import Protocol, cast

from fastapi.testclient import TestClient
from httpx import Response

from app.main import create_app


class SyncHttpClient(Protocol):
    def get(self, url: str) -> Response: ...


def test_health_endpoint_returns_ok() -> None:
    client = cast(SyncHttpClient, TestClient(create_app()))

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "stageflow-backend",
    }
