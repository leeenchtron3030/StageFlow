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

    def reverse_event_mode_kernel_v1(self) -> None:
        self._execute("0002_event_mode_kernel_reverse.sql")

    def _execute(self, filename: str) -> None:
        statement = (
            Path(__file__).with_name("sql").joinpath(filename).read_text(encoding="utf-8")
        )
        with psycopg.connect(self.dsn) as connection:
            connection.execute(sql.SQL(cast(LiteralString, statement)))
