from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import psycopg

from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.production.event_mode_kernel.repository import (
    KernelStorageUnavailableError,
)
from app.contexts.work_execution import WorkExecutionStorageUnavailableError
from app.demo.service import DemoApplication, ReconcileMediaRequest
from app.infrastructure.devcon import DevconReadError


@dataclass(frozen=True, slots=True)
class AutonomousEventNodeStatus:
    enabled: bool
    state: Literal["disabled", "starting", "running", "standby", "degraded", "stopping", "stopped"]
    owner: bool
    media_reconciliation_interval_seconds: float
    program_refresh_interval_seconds: float
    media_cycle_count: int
    media_last_attempt_at: datetime | None
    media_last_success_at: datetime | None
    media_last_failure_code: str | None
    media_candidates_seen: int
    media_assets_registered: int
    transcription_operations_enqueued: int
    transcription_enqueue_failures: int
    program_refresh_count: int
    program_last_attempt_at: datetime | None
    program_last_success_at: datetime | None
    program_last_failure_code: str | None


class AutonomousEventNodeCoordinator:
    """One process-owned bounded reconciliation loop with PostgreSQL singleton ownership."""

    def __init__(self, components: KernelComponents) -> None:
        self.components = components
        configuration = components.configuration.deployment.autonomous_event_node
        self.configuration = configuration
        self._state_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False
        self._state: AutonomousEventNodeStatus = self._initial_status()

    def _initial_status(self) -> AutonomousEventNodeStatus:
        media_last_success_at: datetime | None = None
        program_last_success_at: datetime | None = None
        try:
            event = self.components.repository.get_event_by_key(self.components.event_key)
            if event is not None:
                latest_media = self.components.repository.get_latest_reconciliation(event.id)
                if latest_media is not None:
                    media_last_success_at = latest_media.completed_at
                stages = self.components.repository.list_stages(event.id)
                if len(stages) == 1:
                    latest_program = (
                        self.components.repository.get_latest_program_reconciliation(
                            event.id, stages[0].id
                        )
                    )
                    if latest_program is not None:
                        program_last_success_at = latest_program.synchronized_at
        except KernelStorageUnavailableError:
            pass
        return AutonomousEventNodeStatus(
            enabled=self.configuration.enabled,
            state="starting" if self.configuration.enabled else "disabled",
            owner=False,
            media_reconciliation_interval_seconds=(
                self.configuration.media_reconciliation_interval_seconds
            ),
            program_refresh_interval_seconds=(
                self.configuration.program_refresh_interval_seconds
            ),
            media_cycle_count=0,
            media_last_attempt_at=None,
            media_last_success_at=media_last_success_at,
            media_last_failure_code=None,
            media_candidates_seen=0,
            media_assets_registered=0,
            transcription_operations_enqueued=0,
            transcription_enqueue_failures=0,
            program_refresh_count=0,
            program_last_attempt_at=None,
            program_last_success_at=program_last_success_at,
            program_last_failure_code=None,
        )

    def status(self) -> AutonomousEventNodeStatus:
        with self._state_lock:
            return self._state

    def _update(self, **changes: object) -> None:
        with self._state_lock:
            values = {
                field: getattr(self._state, field)
                for field in self._state.__dataclass_fields__
            }
            values.update(changes)
            self._state = AutonomousEventNodeStatus(**values)

    def start(self) -> None:
        if not self.configuration.enabled:
            return
        with self._state_lock:
            if self._started:
                return
            self._started = True
            self._thread = threading.Thread(
                target=self._run,
                name="stageflow-autonomous-event-node",
                daemon=False,
            )
            thread = self._thread
        thread.start()

    def stop(self, *, timeout_seconds: float = 10.0) -> None:
        if not self.configuration.enabled:
            return
        self._update(state="stopping")
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=max(0.1, min(timeout_seconds, 30.0)))
        if thread is not None and thread.is_alive():
            self._update(
                state="degraded",
                owner=False,
                media_last_failure_code="coordinator_stop_timeout",
            )
            return
        self._update(state="stopped", owner=False)

    def _run(self) -> None:
        lock_key = (
            "stageflow:autonomous-event-node:"
            f"{self.components.configuration.deployment.deployment_id}"
        )
        while not self._stop.is_set():
            try:
                with psycopg.connect(
                    self.components.configuration.postgres_dsn,
                    autocommit=True,
                ) as connection:
                    row = connection.execute(
                        "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
                        (lock_key,),
                    ).fetchone()
                    if row is None or not bool(row[0]):
                        self._update(state="standby", owner=False)
                        self._stop.wait(5.0)
                        continue
                    self._update(state="running", owner=True)
                    try:
                        self._run_owned(connection)
                    finally:
                        try:
                            connection.execute(
                                "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                                (lock_key,),
                            )
                        except psycopg.Error:
                            pass
                        self._update(owner=False)
            except psycopg.Error:
                if self._stop.is_set():
                    break
                self._update(
                    state="degraded",
                    owner=False,
                    media_last_failure_code="postgresql_unavailable",
                )
                self._stop.wait(5.0)
        if self.status().state != "degraded":
            self._update(state="stopped", owner=False)

    def _run_owned(self, connection: psycopg.Connection[object]) -> None:
        next_media = (
            time.monotonic()
            + self.configuration.media_reconciliation_interval_seconds
        )
        next_program = time.monotonic()
        while not self._stop.is_set():
            connection.execute("SELECT 1")
            now = time.monotonic()
            if now >= next_program:
                self.run_program_refresh()
                next_program = (
                    time.monotonic()
                    + self.configuration.program_refresh_interval_seconds
                )
            if now >= next_media:
                self.run_media_cycle()
                next_media = (
                    time.monotonic()
                    + self.configuration.media_reconciliation_interval_seconds
                )
            wait_seconds = max(
                0.0,
                min(next_media, next_program) - time.monotonic(),
            )
            self._stop.wait(wait_seconds)

    def run_media_cycle(self) -> None:
        attempted_at = self.components.kernel.clock.now()
        self._update(media_last_attempt_at=attempted_at)
        try:
            result = DemoApplication.from_components(
                self.components
            ).reconcile_media(
                ReconcileMediaRequest(
                    scope="autonomous_event_node",
                    requested_at=attempted_at,
                )
            )
        except (KernelStorageUnavailableError, WorkExecutionStorageUnavailableError):
            self._update(media_last_failure_code="postgresql_unavailable")
            return
        except (OSError, RuntimeError, ValueError):
            self._update(media_last_failure_code="media_reconciliation_failed")
            return
        current = self.status()
        self._update(
            media_cycle_count=current.media_cycle_count + 1,
            media_last_success_at=self.components.kernel.clock.now(),
            media_last_failure_code=None,
            media_candidates_seen=result.candidates_seen,
            media_assets_registered=result.assets_registered,
            transcription_operations_enqueued=(
                current.transcription_operations_enqueued
                + result.operations_enqueued
            ),
            transcription_enqueue_failures=(
                current.transcription_enqueue_failures
                + len(result.enqueue_failures)
            ),
        )

    def run_program_refresh(self) -> None:
        attempted_at = self.components.kernel.clock.now()
        self._update(program_last_attempt_at=attempted_at)
        try:
            result = self.components.sync_devcon_program()
        except DevconReadError:
            self._update(program_last_failure_code="provider_refresh_unavailable")
            return
        except KernelStorageUnavailableError:
            self._update(program_last_failure_code="postgresql_unavailable")
            return
        except (OSError, RuntimeError, ValueError):
            self._update(program_last_failure_code="program_refresh_failed")
            return
        current = self.status()
        self._update(
            program_refresh_count=current.program_refresh_count + 1,
            program_last_success_at=result.synchronized_at,
            program_last_failure_code=None,
        )


__all__ = [
    "AutonomousEventNodeCoordinator",
    "AutonomousEventNodeStatus",
]