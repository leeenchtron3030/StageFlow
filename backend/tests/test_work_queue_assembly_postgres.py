from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from app.contexts.assembly.contracts import ApprovalAction, PackagingAssetRole
from app.contexts.assembly.service import PackagingAssetService
from app.contexts.assembly.session_contracts import (
    AssemblyAction,
    AssemblySlot,
    AssemblyTemplate,
    PlacementRole,
)
from app.contexts.assembly.session_service import SessionAssemblyService
from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.events.kernel_contracts import ProgramExpectation
from app.contexts.production.event_mode_kernel import DurableEventModeKernel
from app.contexts.production.event_mode_kernel.contracts import (
    MediaCandidate,
    MediaRegistrationState,
    RegisteredMediaAsset,
    Session,
    StartSessionRequest,
)
from app.infrastructure.postgres import PostgresEventModeKernelRepository
from app.infrastructure.postgres.migrations import PostgresMigrationRunner
from app.infrastructure.postgres.packaging_asset_repository import PostgresPackagingAssetRepository
from app.infrastructure.postgres.session_assembly_repository import (
    PostgresSessionAssemblyRepository,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_assembly_metadata_overrides import record
from tests.test_session_assembly_foundation import ACTOR, NOW, candidate
from tests.test_session_assembly_foundation import postgres_dsn as postgres_dsn


class PostgresQueueWorld:
    def __init__(self, dsn: str, count: int = 1) -> None:
        PostgresMigrationRunner(dsn).apply_event_mode_kernel_v1()
        self.kernel_repository = PostgresEventModeKernelRepository(dsn)
        self.kernel = DurableEventModeKernel(
            repository=self.kernel_repository, clock=FixedClock(NOW),
        )
        suffix = EntityId.new().value
        boot = self.kernel.bootstrap(EventStageBootstrapRequest(
            EntityId.new(), "queue-" + suffix, "Example Event", tuple(
                StageBootstrapDefinition(f"stage-{n}", f"Stage {n}", {
                    f"source-{suffix}-{n}": "synthetic-source",
                }) for n in range(count)
            ), ACTOR, NOW,
        ))
        assert boot.event is not None
        self.event = boot.event.id
        self.sessions: list[Session] = []
        self.programs: list[ProgramExpectation] = []
        for n, stage in enumerate(boot.stages):
            program = self.kernel_repository.put_program_expectation(ProgramExpectation(
                EntityId.new(), self.event, f"example-{n}", stage.id, "Example title",
                ("Speaker",), NOW, NOW + timedelta(hours=1), {}, 1, NOW,
            ))
            self.programs.append(program)
            session = self.kernel.start_session(StartSessionRequest(
                EntityId.new(), self.event, stage.id, ACTOR, NOW, NOW, program.id,
            ))
            asset, discovered = EntityId.new(), EntityId.new()
            self.kernel_repository.register_candidate(MediaCandidate(
                discovered, asset, stage.id, f"source-{suffix}-{n}", "synthetic-source", NOW, NOW,
                MediaRegistrationState.READY, 1,
            ))
            self.kernel_repository.register_asset(RegisteredMediaAsset(
                asset, discovered, EntityId.new(), stage.id, f"source-{suffix}-{n}", NOW, NOW,
                NOW + timedelta(minutes=1),
            ))
            self.kernel.assign_asset(operation_id=EntityId.new(), asset_id=asset,
                                     session_id=session.id, actor_id=ACTOR, reason="Example")
            self.kernel.correct_session_boundary(
                operation_id=EntityId.new(), session_id=session.id, boundary_kind="end",
                boundary_at=NOW + timedelta(minutes=1), actor_id=ACTOR, reason="Example",
            )
            self.kernel.mark_package_ready(session.id)
            self.sessions.append(self.kernel.complete_package(
                operation_id=EntityId.new(), session_id=session.id, actor_id=ACTOR,
                approved=True, reason="Example completion",
            ))
        self.repository = PostgresSessionAssemblyRepository(dsn)
        self.service = SessionAssemblyService(self.repository, FixedClock(NOW))
        self.template = self.service.create_template(
            operation_id=EntityId.new(), actor_id=ACTOR, event_id=self.event,
            template_key="media", expected_version=0, name="Example", slots=(
                AssemblySlot("media", PlacementRole.SESSION_MEDIA, True),
            ),
        )

    def propose(self, index: int = 0, expected: int = 0,
                template: AssemblyTemplate | None = None):
        session = self.sessions[index]
        return self.service.propose(
            operation_id=EntityId.new(), actor_id=ACTOR, session_id=session.id,
            template_id=(template or self.template).id, expected_revision=expected,
            expected_package_revision=session.package_revision,
        )

    def decide(self, index: int, action: AssemblyAction) -> None:
        self.service.decide(
            operation_id=EntityId.new(), actor_id=ACTOR, session_id=self.sessions[index].id,
            revision_number=1, expected_revision=1, expected_decision_count=0,
            action=action, reason="Example review",
        )


def test_postgres_pending_read_pages_past_stale_and_excludes_decided_superseded_invalid(
    postgres_dsn: str,
) -> None:
    world = PostgresQueueWorld(postgres_dsn, 7)
    # Equal timestamps exercise the projection-ID tie breaker in PostgreSQL.
    for index in reversed(range(7)):
        world.propose(index)
    original = world.repository.list_pending_approvals(world.event)
    assert len(original) == 7
    assert [i.projection_id for i in original] == sorted(i.projection_id for i in original)
    assert world.repository.list_pending_approvals(EntityId.new()) == ()
    for item in original[:4]:
        assert item.session_id is not None
        record(world.service, session=item.session_id)
    restarted = PostgresSessionAssemblyRepository(postgres_dsn)
    first = restarted.list_pending_approvals(world.event, limit=2)
    assert first == original[4:6]
    assert restarted.list_pending_approvals(world.event, limit=2) == first
    final = restarted.list_pending_approvals(world.event, after=first[-1].position, limit=2)
    assert final == original[6:]
    assert restarted.list_pending_approvals(world.event, after=final[-1].position) == ()
    remaining = [next(n for n, s in enumerate(world.sessions) if s.id == item.session_id)
                 for item in original[4:]]
    world.decide(remaining[0], AssemblyAction.APPROVE)
    world.decide(remaining[1], AssemblyAction.REJECT)
    index = remaining[2]
    replacement = world.propose(index, 1)
    pending, = restarted.list_pending_approvals(world.event)
    assert pending.subject_id == replacement.id and pending.subject_revision == 2
    invalid_template = world.service.create_template(
        operation_id=EntityId.new(), actor_id=ACTOR, event_id=world.event,
        template_key="unbound", expected_version=0, name="Example", slots=(
            AssemblySlot("intro", PlacementRole.OPENING_BUMPER, True),
        ),
    )
    assert world.propose(index, 2, invalid_template).validation.state == "invalid"
    assert restarted.list_pending_approvals(world.event, limit=2) == ()


@pytest.mark.parametrize("cause", ["package", "revoke", "reject", "override", "program"])
def test_postgres_pending_read_uses_existing_staleness_inputs(
    postgres_dsn: str, cause: str,
) -> None:
    world = PostgresQueueWorld(postgres_dsn)
    packaging = PackagingAssetService(PostgresPackagingAssetRepository(postgres_dsn),
                                      FixedClock(NOW))
    asset = packaging.register(
        operation_id=EntityId.new(), actor_id=ACTOR, event_id=world.event, name="Example intro",
        role=PackagingAssetRole.OPENING_BUMPER,
    )
    packaging.revise(operation_id=EntityId.new(), actor_id=ACTOR, packaging_asset_id=asset.id,
                     expected_revision=0, content=candidate().revision.content)
    packaging.decide(operation_id=EntityId.new(), actor_id=ACTOR, packaging_asset_id=asset.id,
                     revision_number=1, expected_revision=1, action=ApprovalAction.APPROVE,
                     reason="Example approval")
    template = world.service.create_template(
        operation_id=EntityId.new(), actor_id=ACTOR, event_id=world.event,
        template_key="with-intro", expected_version=0, name="Example", slots=(
            AssemblySlot("intro", PlacementRole.OPENING_BUMPER, True),
            AssemblySlot("media", PlacementRole.SESSION_MEDIA, True),
        ),
    )
    revision = world.propose(template=template)
    initial = world.repository.list_pending_approvals(world.event)
    assert len(initial) == 1 and initial[0].subject_id == revision.id
    session = world.sessions[0]
    if cause == "package":
        world.kernel.correct_session_boundary(
            operation_id=EntityId.new(), session_id=session.id, boundary_kind="end",
            boundary_at=NOW + timedelta(minutes=2), actor_id=ACTOR, reason="Example correction",
        )
    elif cause in ("revoke", "reject"):
        packaging.decide(
            operation_id=EntityId.new(), actor_id=ACTOR, packaging_asset_id=asset.id,
            revision_number=1, expected_revision=1, action=ApprovalAction(cause),
            reason="Example withdrawal",
        )
    elif cause == "override":
        record(world.service, session=session.id)
    else:
        program = world.programs[0]
        world.kernel_repository.put_program_expectation(replace(
            program, title="Updated display", revision=program.revision + 1,
        ))
    assert world.repository.list_pending_approvals(world.event) == (
        initial if cause == "program" else ()
    )
    assert world.repository.list_revisions(world.event, session.id).items[0].revision == revision
