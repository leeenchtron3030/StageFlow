from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import LiteralString, cast

import psycopg
from psycopg import sql


@dataclass(frozen=True, slots=True)
class PostgresMigrationRunner:
    """Explicit forward/reversal runner for the bounded StageFlow schema."""

    dsn: str

    def apply_ingress_v1(self) -> None:
        self._execute("0001_ingress_forward.sql")

    def reverse_ingress_v1(self) -> None:
        self._execute("0001_ingress_reverse.sql")

    def apply_event_mode_kernel_v1(self) -> None:
        self.apply_ingress_v1()
        self._execute("0002_event_mode_kernel_forward.sql")
        self._execute("0003_kernel_projections_forward.sql")
        self._execute_if_missing(
            "0004_kernel_review_corrections_forward.sql",
            version="0004_kernel_review_corrections",
        )
        self.apply_kernel_follow_up_closure()
        self.apply_media_timing_evidence_v1()
        self.apply_transcription_worker_v1()

    def apply_kernel_follow_up_closure(self) -> None:
        self._execute_if_missing(
            "0005_kernel_follow_up_closure_forward.sql",
            version="0005_kernel_follow_up_closure",
        )

    def apply_media_timing_evidence_v1(self) -> None:
        self._execute_if_missing(
            "0006_media_timing_evidence_forward.sql",
            version="0006_media_timing_evidence",
        )

    def apply_transcription_worker_v1(self) -> None:
        self._execute_if_missing(
            "0007_transcription_worker_forward.sql",
            version="0007_transcription_worker",
        )

    def reverse_event_mode_kernel_v1(self) -> None:
        self.reverse_transcription_worker_v1()
        self.reverse_media_timing_evidence_v1()
        self.reverse_kernel_follow_up_closure()
        self._execute("0004_kernel_review_corrections_reverse.sql")
        self._execute("0003_kernel_projections_reverse.sql")
        self._execute("0002_event_mode_kernel_reverse.sql")

    def reverse_kernel_follow_up_closure(self) -> None:
        self._execute_if_present(
            "0005_kernel_follow_up_closure_reverse.sql",
            version="0005_kernel_follow_up_closure",
        )

    def reverse_media_timing_evidence_v1(self) -> None:
        self.reverse_transcription_worker_v1()
        self._execute_if_present(
            "0006_media_timing_evidence_reverse.sql",
            version="0006_media_timing_evidence",
        )

    def reverse_transcription_worker_v1(self) -> None:
        self._execute_if_present(
            "0007_transcription_worker_reverse.sql",
            version="0007_transcription_worker",
        )

    def _execute(self, filename: str) -> None:
        statement = (
            Path(__file__).with_name("sql").joinpath(filename).read_text(encoding="utf-8")
        )
        with psycopg.connect(self.dsn) as connection:
            connection.execute(sql.SQL(cast(LiteralString, statement)))

    def _execute_if_missing(self, filename: str, *, version: str) -> None:
        statement = (
            Path(__file__).with_name("sql").joinpath(filename).read_text(encoding="utf-8")
        )
        with psycopg.connect(self.dsn) as connection:
            existing = connection.execute(
                "SELECT 1 FROM stageflow.schema_migration WHERE version = %s",
                (version,),
            ).fetchone()
            if existing is not None:
                return
            connection.execute(sql.SQL(cast(LiteralString, statement)))

    def _execute_if_present(self, filename: str, *, version: str) -> None:
        statement = (
            Path(__file__).with_name("sql").joinpath(filename).read_text(encoding="utf-8")
        )
        with psycopg.connect(self.dsn) as connection:
            existing = connection.execute(
                "SELECT 1 FROM stageflow.schema_migration WHERE version = %s",
                (version,),
            ).fetchone()
            if existing is None:
                return
            connection.execute(sql.SQL(cast(LiteralString, statement)))
