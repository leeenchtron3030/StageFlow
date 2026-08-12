from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest

from app.contexts.production.ingress import (
    IngressRegistrationResult,
    IngressRegistrationStatus,
)
from app.infrastructure.postgres import PostgresIngressRepository, PostgresMigrationRunner
from tests.test_durable_ingress_contracts import make_ingress_request


def test_forward_and_reversal_migrations_are_explicit_and_bounded() -> None:
    sql_directory = Path(__file__).parents[1] / "app" / "infrastructure" / "postgres" / "sql"
    forward = (sql_directory / "0001_ingress_forward.sql").read_text(encoding="utf-8")
    reverse = (sql_directory / "0001_ingress_reverse.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS stageflow.production_event_ingress" in forward
    assert "production_event_ingress_identity_unique" in forward
    assert "timestamptz" in forward
    assert "DROP TABLE IF EXISTS stageflow.production_event_ingress" in reverse
    assert "DROP SCHEMA" not in reverse


def test_database_unavailability_is_typed_without_in_memory_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*args: object, **kwargs: object) -> None:
        raise psycopg.OperationalError("offline")

    monkeypatch.setattr(psycopg, "connect", unavailable)

    result = PostgresIngressRepository("postgresql://unavailable").register(
        make_ingress_request()
    )

    assert result.status is IngressRegistrationStatus.STORAGE_UNAVAILABLE
    assert result.record is None
    assert result.failure_code == "postgresql_ingress_unavailable"


_POSTGRES_DSN = os.getenv("STAGEFLOW_TEST_POSTGRES_DSN")


@pytest.mark.skipif(
    not _POSTGRES_DSN,
    reason="STAGEFLOW_TEST_POSTGRES_DSN is required for real PostgreSQL durability checks.",
)
def test_real_postgres_restart_and_concurrent_replay() -> None:
    assert _POSTGRES_DSN is not None
    PostgresMigrationRunner(_POSTGRES_DSN).apply_ingress_v1()
    key = f"test-{datetime.now(UTC).isoformat()}"
    request = make_ingress_request(source_event_key=key)
    first_repository = PostgresIngressRepository(_POSTGRES_DSN)
    created = first_repository.register(request)

    reconstructed_repository = PostgresIngressRepository(_POSTGRES_DSN)
    def register_replay(index: int) -> IngressRegistrationResult:
        return reconstructed_repository.register(
            make_ingress_request(
                source_event_key=key,
                received_at=request.received_at + timedelta(seconds=index + 1),
            )
        )

    with ThreadPoolExecutor(max_workers=6) as executor:
        replays = tuple(
            executor.map(register_replay, range(12))
        )

    assert created.status is IngressRegistrationStatus.CREATED
    assert all(item.status is IngressRegistrationStatus.REPLAYED for item in replays)
    assert created.record is not None
    assert all(item.record is not None for item in replays)
    assert {item.record.production_event_id for item in replays if item.record} == {
        created.record.production_event_id
    }
