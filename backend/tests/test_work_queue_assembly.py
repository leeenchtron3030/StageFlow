from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from importlib.util import resolve_name
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.router import router
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.assembly.contracts import ApprovalState
from app.contexts.assembly.session_contracts import AssemblyAction, SessionAssembly
from app.contexts.assembly.session_memory import InMemorySessionAssemblyRepository
from app.contexts.assembly.session_repository import AssemblyStorageUnavailableError
from app.contexts.assembly.session_service import SessionAssemblyService
from app.contexts.assembly.work_queue import assembly_work_queue_subject
from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
    KernelStorageUnavailableError,
    ProducerWorkQueuePosition,
    ProducerWorkQueueSubject,
    StartSessionRequest,
)
from app.contexts.production.work_queue import ProducerWorkQueueService
from app.core.config.deployment import EffectiveKernelConfiguration
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_assembly_metadata_overrides import record
from tests.test_producer_work_queue import SyncHttpClient
from tests.test_session_assembly_foundation import (
    ACTOR,
    EVENT,
    HEADERS,
    INPUT,
    NOW,
    SESSION,
    STAGE,
    Harness,
)


def test_pending_assembly_exact_projection_is_immutable_and_read_only() -> None:
    h = Harness()
    revision = h.propose()
    before = h.repository.list_revisions(EVENT, SESSION)
    items = h.repository.list_pending_approvals(EVENT)
    assert len(items) == 1
    item = items[0]
    assert item.projection_id == f"assembly:{SESSION}"
    assert item.decision_type.value == "assembly_approval_pending"
    assert item.subject_kind.value == "session_assembly"
    assert (item.subject_id, item.subject_revision) == (revision.id, 1)
    assert (item.event_id, item.stage_id, item.session_id) == (EVENT, STAGE, SESSION)
    assert item.priority == 5
    assert item.reason_codes == ("assembly_approval_pending",)
    assert item.action_reference == f"session:{SESSION}:assembly"
    assert item.created_at == item.updated_at == revision.created_at
    assert item.updated_at.utcoffset() is not None
    with pytest.raises(FrozenInstanceError):
        attribute = "priority"
        setattr(item, attribute, 1)
    with pytest.raises(ValueError):
        replace(item, updated_at=NOW.replace(tzinfo=None))
    assert h.repository.list_pending_approvals(EVENT) == items
    assert h.repository.list_revisions(EVENT, SESSION) == before
    assert h.repository.list_pending_approvals(EntityId.new()) == ()


@pytest.mark.parametrize("cause", [
    "approve", "reject", "package", "revoke", "packaging_reject", "override", "invalid",
])
def test_pending_assembly_disappears_for_existing_authority_changes(cause: str) -> None:
    h = Harness()
    original = h.propose()
    assert len(h.repository.list_pending_approvals(EVENT)) == 1
    if cause in ("approve", "reject"):
        h.decide(action=AssemblyAction(cause))
    elif cause == "package":
        h.inputs = replace(h.inputs, package_revision=5)
    elif cause in ("revoke", "packaging_reject"):
        h.candidates = (replace(h.candidates[0], approval_state=(
            ApprovalState.REVOKED if cause == "revoke" else ApprovalState.REJECTED
        )),)
    elif cause == "override":
        record(h.service)
    else:
        h.inputs = replace(h.inputs, package_complete=False)
        assert h.propose(1).validation.state == "invalid"
    assert h.repository.list_pending_approvals(EVENT) == ()
    assert h.repository.list_revisions(EVENT, SESSION).items[0].revision == original


def test_new_revision_replaces_subject_and_program_refresh_does_not_stale() -> None:
    h = Harness()
    original = h.propose()
    h.inputs = replace(h.inputs, metadata=tuple(
        replace(m, source_revision=m.source_revision + 1, values=("Updated display",))
        for m in h.inputs.metadata
    ))
    assert h.repository.list_pending_approvals(EVENT)[0].subject_id == original.id
    h.decide()
    assert h.repository.list_pending_approvals(EVENT) == ()
    latest = h.propose(1)
    item, = h.repository.list_pending_approvals(EVENT)
    assert item.subject_id == latest.id and item.subject_revision == 2


def test_projection_excludes_superseded_stale_invalid_and_decided_revisions() -> None:
    h = Harness()
    revision = h.propose()
    valid = SessionAssembly(revision, 1, False, ApprovalState.UNREVIEWED, 0, None)
    for excluded in (
        replace(valid, current_revision_number=2), replace(valid, stale=True),
        replace(valid, decision_count=1), replace(valid, approval_state=ApprovalState.APPROVED),
    ):
        assert assembly_work_queue_subject(excluded, stage_id=STAGE) is None
    h.inputs = replace(h.inputs, package_complete=False)
    invalid = h.propose(1)
    assert assembly_work_queue_subject(
        replace(valid, revision=invalid, current_revision_number=2), stage_id=STAGE,
    ) is None


class QueueHarness:
    def __init__(self, event: EntityId = EVENT, count: int = 7) -> None:
        self.inputs = {EntityId(f"91000000-0000-0000-0000-{n:012d}"):
                       replace(INPUT, event_id=event) for n in range(count)}
        self.inputs = {sid: replace(value, session_id=sid) for sid, value in self.inputs.items()}
        self.repository = InMemorySessionAssemblyRepository(
            event_ids=frozenset((event,)), inputs=self.inputs.__getitem__, candidates=lambda: (),
        )
        self.service = SessionAssemblyService(self.repository, FixedClock(NOW))
        from app.contexts.assembly.session_contracts import AssemblySlot, PlacementRole
        template = self.service.create_template(
            operation_id=EntityId.new(), actor_id=ACTOR, event_id=event, template_key="media",
            expected_version=0, name="Example", slots=(
                AssemblySlot("media", PlacementRole.SESSION_MEDIA, True),
            ),
        )
        for sid in reversed(self.inputs):
            self.service.propose(
                operation_id=EntityId.new(), actor_id=ACTOR, session_id=sid,
                template_id=template.id, expected_revision=0, expected_package_revision=4,
            )


def test_bounded_read_continues_past_stale_pages_and_handles_equal_times() -> None:
    h = QueueHarness()
    sessions = list(h.inputs)
    for sid in sessions[:4]:
        h.inputs[sid] = replace(h.inputs[sid], package_revision=5)
    first = h.repository.list_pending_approvals(EVENT, limit=2)
    assert [item.session_id for item in first] == sessions[4:6]
    assert first == h.repository.list_pending_approvals(EVENT, limit=2)
    last = h.repository.list_pending_approvals(EVENT, after=first[-1].position, limit=2)
    assert [item.session_id for item in last] == sessions[6:]
    assert h.repository.list_pending_approvals(EVENT, after=last[-1].position, limit=2) == ()
    assert h.repository.list_pending_approvals(
        EVENT, after=ProducerWorkQueuePosition(6, NOW, "later"),
    ) == ()
    assert h.repository.list_pending_approvals(
        EVENT, after=ProducerWorkQueuePosition(4, NOW + timedelta(days=1), "package"), limit=2,
    ) == first
    for sid in sessions:
        h.inputs[sid] = replace(h.inputs[sid], package_revision=5)
    assert h.repository.list_pending_approvals(EVENT, limit=2) == ()


def test_repository_accepts_sentinel_bound_and_rejects_invalid_limits() -> None:
    h = QueueHarness(count=102)
    assert len(h.repository.list_pending_approvals(EVENT, limit=101)) == 101
    for limit in (0, 102, True):
        with pytest.raises(ValueError):
            h.repository.list_pending_approvals(EVENT, limit=limit)


def client_for_queue(
    kernel: InMemoryEventModeKernelRepository, assemblies: SessionAssemblyService,
) -> SyncHttpClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.state.kernel = KernelComponents(
        cast(EffectiveKernelConfiguration, None), kernel,
        DurableEventModeKernel(repository=kernel, clock=FixedClock(NOW)),
        session_assemblies=assemblies,
    )
    return cast(SyncHttpClient, TestClient(app))


def kernel_world() -> tuple[InMemoryEventModeKernelRepository, EntityId]:
    repository = InMemoryEventModeKernelRepository()
    kernel = DurableEventModeKernel(repository=repository, clock=FixedClock(NOW))
    boot = kernel.bootstrap(EventStageBootstrapRequest(
        EntityId.new(), "example-event", "Example Event", tuple(
            StageBootstrapDefinition(f"stage-{n}", f"Stage {n}", {}) for n in range(4)
        ), ACTOR, NOW,
    ))
    assert boot.event is not None
    for stage in boot.stages:
        session = repository.start_session(StartSessionRequest(
            EntityId.new(), boot.event.id, stage.id, ACTOR, NOW, NOW,
        ))
        repository.set_package_state(session.id, "ready_for_review", NOW)
    return repository, boot.event.id


@pytest.mark.parametrize("limit", [1, 4, 5, 100])
def test_mixed_source_api_pagination_truncation_replay_and_event_cursor(limit: int) -> None:
    kernel, event = kernel_world()
    h = QueueHarness(event)
    client = client_for_queue(kernel, h.service)
    url = f"/api/v1/producer/events/{event}/work-queue"
    expected = ProducerWorkQueueService(kernel, h.repository).list_items(event, limit=100)
    seen: list[str] = []
    cursor: str | None = None
    while True:
        page_url = f"{url}?limit={limit}" + (f"&cursor={cursor}" if cursor else "")
        response = client.get(page_url, headers=HEADERS)
        assert response.status_code == 200
        payload = cast(dict[str, Any], response.json())
        assert client.get(page_url, headers=HEADERS).json() == payload
        seen.extend(item["item_id"] for item in payload["items"])
        assert len(payload["items"]) <= limit
        assert payload["items_truncated"] == (len(seen) < len(expected))
        cursor = payload["next_cursor"]
        if cursor is None:
            break
        assert client.get(
            f"/api/v1/producer/events/{EntityId.new()}/work-queue?cursor={cursor}",
            headers=HEADERS,
        ).status_code == 422
    assert seen == [item.projection_id for item in expected]
    assert len(seen) == len(set(seen)) == 11
    assert [item.priority for item in expected] == [*([4] * 4), *([5] * 7)]


def test_application_fetches_limit_plus_one_from_both_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel, event = kernel_world()
    h = QueueHarness(event)
    calls: list[tuple[str, int, ProducerWorkQueuePosition | None]] = []
    after = kernel.list_producer_work_queue(event)[-1].position
    def kernel_read(event_id: EntityId, *, after: ProducerWorkQueuePosition | None = None,
                    limit: int = 50) -> tuple[ProducerWorkQueueSubject, ...]:
        calls.append(("kernel", limit, after))
        return ()
    original = h.repository.list_pending_approvals
    def assembly_read(event_id: EntityId, *, after: ProducerWorkQueuePosition | None = None,
                      limit: int = 50) -> tuple[ProducerWorkQueueSubject, ...]:
        calls.append(("assembly", limit, after))
        return original(event_id, after=after, limit=limit)
    monkeypatch.setattr(kernel, "list_producer_work_queue", kernel_read)
    monkeypatch.setattr(h.repository, "list_pending_approvals", assembly_read)
    items = ProducerWorkQueueService(kernel, h.repository).list_items(event, after=after, limit=1)
    assert len(items) == 2
    assert calls == [("kernel", 2, after), ("assembly", 2, after)]


@pytest.mark.parametrize("source", ["kernel", "assembly"])
def test_either_source_failure_returns_bounded_503(
    source: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel, event = kernel_world()
    h = QueueHarness(event)
    def unavailable(*args: object, **kwargs: object) -> object:
        error = (KernelStorageUnavailableError if source == "kernel"
                 else AssemblyStorageUnavailableError)
        raise error("private storage diagnostics")
    target, method = ((kernel, "list_producer_work_queue") if source == "kernel" else
                      (h.repository, "list_pending_approvals"))
    monkeypatch.setattr(target, method, unavailable)
    response = client_for_queue(kernel, h.service).get(
        f"/api/v1/producer/events/{event}/work-queue", headers=HEADERS,
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "postgresql_unavailable"}


def test_kernel_must_not_import_assembly() -> None:
    root = Path(__file__).parents[1] / "app" / "contexts" / "production" / "event_mode_kernel"
    paths = sorted(root.rglob("*.py"))
    # Guard against a vacuous pass if the Kernel package moves.
    assert any(path.name == "work_queue.py" for path in paths)
    for path in paths:
        package = "app.contexts.production.event_mode_kernel"
        parent = path.parent.relative_to(root).parts
        if parent:
            package += "." + ".".join(parent)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            imports: list[str] = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    module = resolve_name("." * node.level + module, package)
                imports = [module, *(f"{module}.{alias.name}" for alias in node.names)]
            assert not any(name == "app.contexts.assembly" or name.startswith(
                "app.contexts.assembly.",
            ) for name in imports), path
            assert not any(name == "app.contexts.production.session_suggestions" or name.startswith(
                "app.contexts.production.session_suggestions.",
            ) for name in imports), path
