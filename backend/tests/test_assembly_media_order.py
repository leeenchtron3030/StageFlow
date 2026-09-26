"""ED-0088 ordering, compatibility and migration behavior at real boundaries."""
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, dataclass, replace
from datetime import datetime, timedelta
from typing import Any, cast

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.contexts.assembly.contracts import (
    ApprovalAction,
    ApprovalState,
    CompletedMediaAssetContent,
    ExternalContent,
    PackagingAssetRole,
    RevisionContent,
)
from app.contexts.assembly.service import PackagingAssetService
from app.contexts.assembly.session_contracts import (
    AssemblyAction,
    AssemblyRevision,
    AssemblySlot,
    AssemblyTemplate,
    CompletionMember,
    MediaOrderSource,
    PlacementRole,
    SessionAssembly,
    SlotBinding,
    ValidationReason,
)
from app.contexts.assembly.session_repository import AssemblyConflictError
from app.contexts.assembly.session_service import SessionAssemblyService
from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.production.event_mode_kernel import DurableEventModeKernel
from app.contexts.production.event_mode_kernel.contracts import (
    MediaCandidate,
    MediaRegistrationState,
    RegisteredMediaAsset,
    StartSessionRequest,
)
from app.contexts.rendering.contracts import (
    FIRST_RENDER_PROFILE,
    RenderError,
    RenderPlan,
    RenderProfile,
    RenderReason,
    VideoInput,
)
from app.contexts.rendering.planning import build_render_plan
from app.infrastructure.postgres import PostgresEventModeKernelRepository
from app.infrastructure.postgres.migrations import PostgresMigrationRunner
from app.infrastructure.postgres.packaging_asset_repository import PostgresPackagingAssetRepository
from app.infrastructure.postgres.render_repository import PostgresRenderRepository
from app.infrastructure.postgres.session_assembly_repository import (
    Connection,
    PostgresSessionAssemblyRepository,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_packaging_asset_foundation import HEADERS
from tests.test_render_work_execution import render_postgres_dsn as render_postgres_dsn
from tests.test_rendering_phase_b import assembly
from tests.test_session_assembly_foundation import (
    ACTOR,
    EVENT,
    INPUT,
    MEDIA,
    NOW,
    SESSION,
    Harness,
    client_for,
)


def members_for(mode: str) -> tuple[CompletionMember, ...]:
    # Registration order deliberately differs from media order, with a key tie.
    members: list[CompletionMember] = []
    for index, seconds in enumerate((3, 1, 1)):
        registered = NOW + timedelta(seconds=seconds)
        started = (NOW + timedelta(seconds=4 - seconds)
                   if mode == "timed" or (mode == "mixed" and index == 0) else None)
        members.append(CompletionMember(
            EntityId.new(), 1, started, registered,
            MediaOrderSource.MEDIA_TIMING if started is not None
            else MediaOrderSource.REGISTRATION_TIME, started or registered,
        ))
    return tuple(members)


def expected_order(members: tuple[CompletionMember, ...]) -> tuple[CompletionMember, ...]:
    return tuple(sorted(members, key=lambda m: (
        m.media_started_at or m.registered_at, m.asset_id.value,
    )))


@pytest.mark.parametrize("mode", ["untimed", "mixed", "timed"])
def test_memory_order_sources_frozen_reload_replay_and_staleness(mode: str) -> None:
    harness = Harness()
    members = members_for(mode)
    harness.inputs = replace(INPUT, membership=members)
    original = harness.inputs
    operation = EntityId.new()
    revision = harness.propose(operation=operation)
    assert revision.validation.state == "valid"
    assert revision.membership == expected_order(members)
    assert all(m.order_key_at is not None for m in revision.membership)
    assert harness.inputs == original
    harness.decide()
    harness.inputs = replace(harness.inputs, membership=tuple(
        replace(m, registered_at=m.registered_at + timedelta(hours=1)) for m in reversed(members)
    ))
    assert harness.propose(operation=operation) == revision
    projected = harness.repository.list_revisions(EVENT, SESSION).items[0]
    assert projected.revision == revision and not projected.stale
    assert projected.approval_state == ApprovalState.APPROVED
    harness.inputs = replace(harness.inputs, package_revision=5)
    stale = harness.repository.list_revisions(EVENT, SESSION).items[0]
    assert stale.stale and stale.revision == revision
    with pytest.raises(AssemblyConflictError, match="assembly_not_approvable"):
        harness.decide(count=1)


@pytest.mark.parametrize("field", ["registered_at", "order_key_at", "media_started_at"])
def test_member_order_timestamps_require_awareness(field: str) -> None:
    with pytest.raises(ValueError):
        replace(MEDIA, **{field: NOW.replace(tzinfo=None)})


def test_member_order_closed_source_key_consistency_and_immutability() -> None:
    with pytest.raises(ValueError):
        replace(MEDIA, order_source=cast(Any, "invented"))
    with pytest.raises(ValueError, match="must equal"):
        replace(MEDIA, order_key_at=NOW + timedelta(seconds=1))
    with pytest.raises(ValueError, match="must equal"):
        replace(MEDIA, order_key_at=None)
    with pytest.raises(ValueError, match="requires an order key"):
        replace(MEDIA, order_source=MediaOrderSource.REGISTRATION_TIME, order_key_at=None)
    legacy = replace(MEDIA, media_started_at=None, order_key_at=None)
    assert legacy.order_source == MediaOrderSource.MEDIA_TIMING
    for field, value in (("registered_at", NOW), ("order_source", "registration_time"),
                         ("order_key_at", None)):
        with pytest.raises(FrozenInstanceError):
            setattr(MEDIA, field, value)


def test_proposal_derives_keys_from_source_facts_even_for_legacy_input() -> None:
    harness = Harness()
    timed = replace(MEDIA, registered_at=NOW + timedelta(seconds=10),
                    order_source=MediaOrderSource.REGISTRATION_TIME,
                    order_key_at=NOW + timedelta(seconds=10))
    legacy = replace(MEDIA, asset_id=EntityId.new(), media_started_at=None,
                     order_key_at=None, registered_at=NOW + timedelta(seconds=5))
    harness.inputs = replace(INPUT, membership=(legacy, timed))
    revision = harness.propose()
    assert revision.validation.state == "valid"
    assert revision.membership == (
        replace(timed, order_source=MediaOrderSource.MEDIA_TIMING, order_key_at=NOW),
        replace(legacy, order_source=MediaOrderSource.REGISTRATION_TIME,
                order_key_at=legacy.registered_at),
    )
    assert harness.inputs.membership == (legacy, timed)


@pytest.mark.parametrize("mode", ["untimed", "mixed", "timed"])
def test_render_intro_session_outro_uses_frozen_order(mode: str) -> None:
    source = assembly()
    members = members_for(mode)  # Deliberately not sorted: render must not resolve again.
    intro, outro = EntityId.new(), EntityId.new()
    source = replace(source, revision=replace(source.revision, membership=members, bindings=(
        SlotBinding("intro", intro, "bound"), SlotBinding("media", None, "session_media"),
        SlotBinding("optional", None, "unresolved"), SlotBinding("outro", outro, "bound"),
    )))
    packaging = {
        intro: VideoInput(ExternalContent("intro", "a" * 64, 10, "video/mp4"), "video/mp4"),
        outro: VideoInput(ExternalContent("outro", "b" * 64, 10, "video/mp4"), "video/mp4"),
    }
    media = {m.asset_id: VideoInput(CompletedMediaAssetContent(m.asset_id), "video/mp4")
             for m in members}
    plan = build_render_plan(source, FIRST_RENDER_PROFILE, packaging, media)
    assert plan.inputs == (
        packaging[intro], *(media[m.asset_id] for m in members), packaging[outro],
    )
    assert plan.manifest.metadata == source.revision.metadata
    with pytest.raises(RenderError) as failure:
        build_render_plan(source, FIRST_RENDER_PROFILE, packaging, {})
    assert failure.value.code == RenderReason.INPUT_MISSING
    with pytest.raises(RenderError) as failure:
        build_render_plan(source, FIRST_RENDER_PROFILE, {intro: packaging[intro]}, media)
    assert failure.value.code == RenderReason.INPUT_MISSING


def test_render_bound_binding_without_revision_and_template_without_session_media() -> None:
    source = assembly()
    members = members_for("timed")
    intro = EntityId.new()
    packaging = {
        intro: VideoInput(ExternalContent("intro", "a" * 64, 10, "video/mp4"), "video/mp4"),
    }
    media = {m.asset_id: VideoInput(CompletedMediaAssetContent(m.asset_id), "video/mp4")
             for m in members}
    broken = replace(source, revision=replace(source.revision, membership=members, bindings=(
        SlotBinding("intro", None, "bound"), SlotBinding("media", None, "session_media"),
    )))
    with pytest.raises(RenderError) as failure:
        build_render_plan(broken, FIRST_RENDER_PROFILE, packaging, media)
    assert failure.value.code == RenderReason.INPUT_MISSING
    # A template without a session-media slot renders exactly its bound packaging inputs.
    packaging_only = replace(source, revision=replace(
        source.revision, membership=members, bindings=(SlotBinding("intro", intro, "bound"),),
    ))
    plan = build_render_plan(packaging_only, FIRST_RENDER_PROFILE, packaging, media)
    assert plan.inputs == (packaging[intro],)


def test_api_exposes_member_order_source_and_key_without_paths() -> None:
    harness = Harness()
    harness.inputs = replace(INPUT, membership=members_for("mixed"))
    client = client_for(harness)
    response = client.post(f"/api/v1/assembly/sessions/{SESSION}/revisions", headers=HEADERS, json={
        "operation_id": EntityId.new().value, "actor_id": ACTOR.value, "confirmed": "confirmed",
        "template_id": harness.template.id.value, "expected_revision": 0,
        "expected_package_revision": 4,
    })
    assert response.status_code == 200
    page = client.get(f"/api/v1/assembly/events/{EVENT}/sessions/{SESSION}/revisions",
                      headers=HEADERS)
    assert page.status_code == 200
    for body in (response.json(), page.json()["items"][0]["revision"]):
        for actual, expected in zip(body["membership"], expected_order(harness.inputs.membership),
                                    strict=True):
            assert set(actual) == {"asset_id", "association_revision", "media_started_at",
                                   "order_source", "order_key_at"}
            assert actual["order_source"] == expected.order_source.value
            assert datetime.fromisoformat(actual["order_key_at"]) == expected.order_key_at


class IsolatedAssemblyRepository(PostgresSessionAssemblyRepository):
    @contextmanager
    def _transaction(self, *, read: bool = False) -> Generator[Connection]:
        # The fixture owns an outer rollback transaction: isolation cannot be reset
        # inside a savepoint. All queries, constraints and hydration still use PostgreSQL.
        with super()._transaction(read=False) as connection:
            yield connection


class IsolatedRenderRepository(PostgresRenderRepository):
    def load_plan(self, revision_id: EntityId, profile: RenderProfile) -> RenderPlan:
        # Same outer-transaction restriction as IsolatedAssemblyRepository.
        with self._connect() as connection:
            return self._plan(connection, revision_id, profile, lock=False)


@dataclass
class DatabaseAssembly:
    service: SessionAssemblyService
    kernel: DurableEventModeKernel
    kernel_repo: PostgresEventModeKernelRepository
    event_id: EntityId
    session_id: EntityId
    package_revision: int
    template: AssemblyTemplate
    members: tuple[CompletionMember, ...]

    def propose(self) -> AssemblyRevision:
        return self.service.propose(
            operation_id=EntityId.new(), actor_id=ACTOR, session_id=self.session_id,
            template_id=self.template.id, expected_revision=0,
            expected_package_revision=self.package_revision,
        )

    def read(self, dsn: str) -> SessionAssembly:
        return IsolatedAssemblyRepository(dsn).list_revisions(
            self.event_id, self.session_id,
        ).items[0]

    def approve(self) -> None:
        self.service.decide(operation_id=EntityId.new(), actor_id=ACTOR,
            session_id=self.session_id, revision_number=1, expected_revision=1,
            expected_decision_count=0, action=AssemblyAction.APPROVE, reason="Reviewed order")


def seed_assembly(dsn: str, mode: str, *, packaged: bool = False) -> DatabaseAssembly:
    repo = PostgresEventModeKernelRepository(dsn)
    kernel = DurableEventModeKernel(repository=repo, clock=FixedClock(NOW))
    source = "source-" + EntityId.new().value
    boot = kernel.bootstrap(EventStageBootstrapRequest(
        EntityId.new(), "event-" + EntityId.new().value, "Synthetic Event",
        (StageBootstrapDefinition("main", "Synthetic Stage", {source: "synthetic"}),), ACTOR, NOW,
    ))
    assert boot.event is not None
    event, stage = boot.event.id, boot.stages[0].id
    session = kernel.start_session(StartSessionRequest(
        EntityId.new(), event, stage, ACTOR, NOW, NOW,
    ))
    members: list[CompletionMember] = []
    for member in members_for(mode):
        candidate = EntityId.new()
        repo.register_candidate(MediaCandidate(candidate, member.asset_id, stage, source,
            "synthetic.mp4", NOW, NOW, MediaRegistrationState.READY, 1))
        repo.register_asset(RegisteredMediaAsset(member.asset_id, candidate, EntityId.new(),
            stage, source, member.registered_at, member.media_started_at, None))
        association = kernel.assign_asset(operation_id=EntityId.new(), asset_id=member.asset_id,
            session_id=session.id, actor_id=ACTOR, reason="Synthetic assignment")
        members.append(replace(member, association_revision=association.revision))
    kernel.correct_session_boundary(operation_id=EntityId.new(), session_id=session.id,
        boundary_kind="end", boundary_at=NOW + timedelta(minutes=1), actor_id=ACTOR,
        reason="Synthetic end")
    kernel.mark_package_ready(session.id)
    session = kernel.complete_package(operation_id=EntityId.new(), session_id=session.id,
        actor_id=ACTOR, approved=True, reason="Synthetic completion")
    service = SessionAssemblyService(PostgresSessionAssemblyRepository(dsn), FixedClock(NOW))
    slots = (AssemblySlot("media", PlacementRole.SESSION_MEDIA, True),)
    if packaged:
        packaging = PackagingAssetService(PostgresPackagingAssetRepository(dsn), FixedClock(NOW))
        for key, role in (("intro", PackagingAssetRole.OPENING_BUMPER),
                          ("outro", PackagingAssetRole.OUTRO)):
            asset = packaging.register(operation_id=EntityId.new(), actor_id=ACTOR, event_id=event,
                name=key, role=role)
            packaging.revise(operation_id=EntityId.new(), actor_id=ACTOR,
                packaging_asset_id=asset.id, expected_revision=0,
                content=RevisionContent(ExternalContent(key, "a" * 64, 10, "video/mp4")))
            packaging.decide(operation_id=EntityId.new(), actor_id=ACTOR,
                packaging_asset_id=asset.id, revision_number=1, expected_revision=1,
                action=ApprovalAction.APPROVE, reason="Synthetic approval")
        slots = (AssemblySlot("intro", PlacementRole.OPENING_BUMPER, True), *slots,
                 AssemblySlot("outro", PlacementRole.OUTRO, True))
    template = service.create_template(operation_id=EntityId.new(), actor_id=ACTOR, event_id=event,
        template_key="synthetic", expected_version=0, name="Synthetic",
        slots=slots)
    return DatabaseAssembly(service, kernel, repo, event, session.id, session.package_revision,
                            template, tuple(members))


@pytest.mark.parametrize("mode", ["untimed", "mixed", "timed"])
def test_postgres_order_sources_reload_approval_and_staleness(
    render_postgres_dsn: str, mode: str,
) -> None:
    db = seed_assembly(render_postgres_dsn, mode, packaged=True)
    upstream = db.kernel_repo.get_session(db.session_id)
    revision = db.propose()
    assert revision.validation.state == "valid"
    assert revision.membership == expected_order(db.members)
    db.approve()
    loaded = db.read(render_postgres_dsn)
    assert loaded.revision == revision and not loaded.stale
    assert loaded.approval_state == ApprovalState.APPROVED
    plan = IsolatedRenderRepository(render_postgres_dsn).load_plan(
        revision.id, FIRST_RENDER_PROFILE,
    )
    assert tuple(i.reference for i in plan.inputs) == (
        ExternalContent("intro", "a" * 64, 10, "video/mp4"),
        *(CompletedMediaAssetContent(m.asset_id) for m in revision.membership),
        ExternalContent("outro", "a" * 64, 10, "video/mp4"),
    )
    assert db.kernel_repo.get_session(db.session_id) == upstream
    db.kernel.correct_session_boundary(operation_id=EntityId.new(), session_id=db.session_id,
        boundary_kind="end", boundary_at=NOW + timedelta(minutes=2), actor_id=ACTOR,
        reason="Synthetic correction")
    stale = db.read(render_postgres_dsn)
    assert stale.stale and stale.revision == revision
    with pytest.raises(RenderError) as failure:
        build_render_plan(stale, FIRST_RENDER_PROFILE, {}, {})
    assert failure.value.code == RenderReason.STALE


@pytest.mark.parametrize("mode", ["untimed", "timed"])
def test_postgres_reverse_guard_and_allowed_timed_reverse_reapply(
    render_postgres_dsn: str, mode: str,
) -> None:
    db = seed_assembly(render_postgres_dsn, mode)
    revision = db.propose()
    runner = PostgresMigrationRunner(render_postgres_dsn)
    if mode == "untimed":
        with pytest.raises(psycopg.errors.RaiseException,
                           match="assembly_media_order_reverse_requires_no_registration_time"):
            runner.reverse_assembly_media_order_v1()
        assert db.read(render_postgres_dsn).revision == revision
    else:
        runner.reverse_assembly_media_order_v1()
        runner.apply_assembly_media_order_v1()
        assert db.read(render_postgres_dsn).revision == revision
        with psycopg.Connection[dict[str, Any]].connect(
            render_postgres_dsn, row_factory=dict_row,
        ) as conn:
            rows = conn.execute(
                "SELECT order_source,order_key_at FROM stageflow.assembly_member",
            ).fetchall()
            assert len(rows) == len(revision.membership)
            assert all(r["order_source"] is None and r["order_key_at"] is None for r in rows)
    runner.apply_assembly_media_order_v1()  # Idempotent forward.
    assert db.read(render_postgres_dsn).revision == revision
    with pytest.raises(psycopg.errors.RaiseException, match="assembly_history_is_immutable"):
        with psycopg.Connection[dict[str, Any]].connect(
            render_postgres_dsn, row_factory=dict_row,
        ) as conn:
            conn.execute("UPDATE stageflow.assembly_member SET order_key_at=order_key_at "
                         "WHERE revision_id=%s", (revision.id.value,))


@pytest.mark.parametrize("mode", ["untimed", "timed"])
def test_postgres_pre0016_null_rows_preserve_positions_and_invalid_validation(
    render_postgres_dsn: str, mode: str,
) -> None:
    runner = PostgresMigrationRunner(render_postgres_dsn)
    runner.reverse_assembly_media_order_v1()
    db = seed_assembly(render_postgres_dsn, mode)
    revision_id = EntityId.new()
    issues = ([{"code": "media_timing_unavailable", "subject": None}] if mode == "untimed" else [])
    with psycopg.Connection[dict[str, Any]].connect(
        render_postgres_dsn, row_factory=dict_row,
    ) as conn:
        completion = conn.execute("SELECT completion_decision_id FROM "
            "stageflow.session_completion_history WHERE session_id=%s AND approved",
            (db.session_id.value,)).fetchone()
        assert completion is not None
        conn.execute("""INSERT INTO stageflow.assembly_revision
            (revision_id,session_id,event_id,revision_number,template_id,package_revision,
             completion_decision_id,validation_state,validation_issues,actor_id,created_at)
            VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s)""",
            (revision_id.value, db.session_id.value, db.event_id.value, db.template.id.value,
             db.package_revision, completion["completion_decision_id"],
             "invalid" if issues else "valid", Jsonb(issues), ACTOR.value, NOW))
        for position, member in enumerate(db.members):
            conn.execute("""INSERT INTO stageflow.assembly_member
                (revision_id,position,completion_decision_id,asset_id,association_revision,
                 media_started_at) VALUES (%s,%s,%s,%s,%s,%s)""",
                (revision_id.value, position, completion["completion_decision_id"],
                 member.asset_id.value, member.association_revision, member.media_started_at))
        conn.execute("""INSERT INTO stageflow.assembly_binding
            (revision_id,position,slot_key,outcome) VALUES (%s,0,'media','session_media')""",
            (revision_id.value,))
    runner.apply_assembly_media_order_v1()
    loaded = db.read(render_postgres_dsn)
    assert tuple(m.asset_id for m in loaded.revision.membership) == tuple(
        m.asset_id for m in db.members
    )
    for actual, original in zip(loaded.revision.membership, db.members, strict=True):
        assert actual.registered_at == original.registered_at
        assert actual.order_source == MediaOrderSource.MEDIA_TIMING
        assert actual.order_key_at == original.media_started_at
    if mode == "untimed":
        assert loaded.revision.validation.state == "invalid"
        assert loaded.revision.validation.issues[0].code == (
            ValidationReason.MEDIA_TIMING_UNAVAILABLE
        )
        with pytest.raises(AssemblyConflictError, match="assembly_not_approvable"):
            db.approve()
        with pytest.raises(RenderError) as failure:
            build_render_plan(replace(loaded, approval_state=ApprovalState.APPROVED),
                              FIRST_RENDER_PROFILE, {}, {})
        assert failure.value.code == RenderReason.NOT_APPROVED
    else:
        assert loaded.revision.validation.state == "valid"
        db.approve()
        plan = IsolatedRenderRepository(render_postgres_dsn).load_plan(
            revision_id, FIRST_RENDER_PROFILE,
        )
        assert tuple(i.reference for i in plan.inputs) == tuple(
            CompletedMediaAssetContent(m.asset_id) for m in db.members
        )
    runner.reverse_assembly_media_order_v1()
    runner.apply_assembly_media_order_v1()
    assert db.read(render_postgres_dsn).revision == loaded.revision


@pytest.mark.parametrize(("source", "key", "started", "constraint"), [
    ("invented", NOW, NOW, "assembly_member_order_source_check"),
    ("media_timing", None, NOW, "assembly_member_order_pair_check"),
    (None, NOW, NOW, "assembly_member_order_pair_check"),
    ("media_timing", NOW, NOW + timedelta(seconds=1), "assembly_member_media_order_key_check"),
    ("media_timing", NOW, None, "assembly_member_media_order_key_check"),
])
def test_postgres_order_constraints_reject_invalid_inserts(
    render_postgres_dsn: str, source: str | None, key: datetime | None,
    started: datetime | None, constraint: str,
) -> None:
    db = seed_assembly(render_postgres_dsn, "timed")
    revision = db.propose()
    with pytest.raises(psycopg.errors.CheckViolation) as failure:
        with psycopg.Connection[dict[str, Any]].connect(
            render_postgres_dsn, row_factory=dict_row,
        ) as conn:
            revision_id = EntityId.new()
            conn.execute("""INSERT INTO stageflow.assembly_revision
                (revision_id,session_id,event_id,revision_number,template_id,package_revision,
                 completion_decision_id,validation_state,validation_issues,actor_id,created_at)
                SELECT %s,session_id,event_id,2,template_id,package_revision,completion_decision_id,
                       validation_state,validation_issues,actor_id,created_at
                FROM stageflow.assembly_revision WHERE revision_id=%s""",
                (revision_id.value, revision.id.value))
            conn.execute("""INSERT INTO stageflow.assembly_member
                (revision_id,position,completion_decision_id,asset_id,association_revision,
                 media_started_at,order_source,order_key_at)
                SELECT %s,position,completion_decision_id,asset_id,association_revision,%s,%s,%s
                FROM stageflow.assembly_member WHERE revision_id=%s AND position=0""",
                (revision_id.value, started, source, key, revision.id.value))
    assert failure.value.diag.constraint_name == constraint
    assert db.read(render_postgres_dsn).revision == revision
