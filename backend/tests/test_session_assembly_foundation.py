from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from typing import cast

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.router import router
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.assembly.contracts import (
    ApprovalAction,
    ApprovalState,
    ExternalContent,
    PackagingAsset,
    PackagingAssetRevision,
    PackagingAssetRole,
    RevisionContent,
)
from app.contexts.assembly.resolution import resolve_bindings, validate_assembly
from app.contexts.assembly.service import PackagingAssetService
from app.contexts.assembly.session_contracts import (
    AssemblyAction,
    AssemblyInputs,
    AssemblySlot,
    AssemblyTemplate,
    CompletionMember,
    ExplicitBinding,
    MediaOrderSource,
    MetadataField,
    MetadataValue,
    PackagingCandidate,
    PlacementRole,
    ValidationReason,
)
from app.contexts.assembly.session_memory import InMemorySessionAssemblyRepository
from app.contexts.assembly.session_repository import (
    AssemblyConflictError,
    AssemblyNotFoundError,
    AssemblyStorageUnavailableError,
)
from app.contexts.assembly.session_service import SessionAssemblyService
from app.contexts.events import EventStageBootstrapRequest, StageBootstrapDefinition
from app.contexts.events.kernel_contracts import ProgramExpectation
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
)
from app.contexts.production.event_mode_kernel.contracts import (
    MediaCandidate,
    MediaRegistrationState,
    RegisteredMediaAsset,
    StartSessionRequest,
)
from app.core.config.deployment import EffectiveKernelConfiguration
from app.infrastructure.postgres import PostgresEventModeKernelRepository
from app.infrastructure.postgres.migrations import PostgresMigrationRunner
from app.infrastructure.postgres.packaging_asset_repository import PostgresPackagingAssetRepository
from app.infrastructure.postgres.session_assembly_repository import (
    PostgresSessionAssemblyRepository,
)
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_packaging_asset_foundation import HEADERS, SyncHttpClient

NOW = datetime(2026, 9, 25, 12, tzinfo=UTC)
EVENT, STAGE, SESSION, ACTOR, SOURCE = (EntityId.new() for _ in range(5))
MEDIA = CompletionMember(EntityId.new(), 3, NOW, NOW, MediaOrderSource.MEDIA_TIMING, NOW)
SLOTS = (AssemblySlot("intro", PlacementRole.OPENING_BUMPER, True),
         AssemblySlot("media", PlacementRole.SESSION_MEDIA, True))
METADATA = (
    MetadataValue(MetadataField.PARTICIPANT_NAMES, ("Speaker A", "Speaker B"), SOURCE, 2),
    MetadataValue(MetadataField.SESSION_TITLE, ("Example presentation",), SOURCE, 2),
)
INPUT = AssemblyInputs(SESSION, EVENT, STAGE, NOW, 4, True, EntityId.new(), (MEDIA,), METADATA)
TEMPLATE = AssemblyTemplate(EntityId.new(), EVENT, "example", 1, "Example", SLOTS,
                            (MetadataField.SESSION_TITLE, MetadataField.PARTICIPANT_NAMES), NOW)


def candidate(role: PackagingAssetRole = PackagingAssetRole.OPENING_BUMPER) -> PackagingCandidate:
    asset = PackagingAsset(EntityId.new(), EVENT, None, "Example content", role, NOW)
    revision = PackagingAssetRevision(EntityId.new(), asset.id, 1, RevisionContent(
        ExternalContent("example-content", "a" * 64, 100, "video/mp4"),
    ), NOW)
    return PackagingCandidate(asset, revision, ApprovalState.APPROVED)


@pytest.mark.parametrize("role", list(PackagingAssetRole))
@pytest.mark.parametrize("count", [0, 1, 2])
def test_each_packaging_role_conservative_deterministic_resolution(
    role: PackagingAssetRole, count: int,
) -> None:
    template = replace(TEMPLATE, slots=(AssemblySlot("slot", PlacementRole(role.value), True),))
    candidates = tuple(candidate(role) for _ in range(count))
    bindings = resolve_bindings(template, INPUT, candidates)
    assert bindings == resolve_bindings(template, INPUT, reversed(candidates))
    assert bindings[0].outcome == ("unresolved", "bound", "ambiguous")[count]
    assert (bindings[0].packaging_revision_id is not None) == (count == 1)
    assert validate_assembly(template, INPUT, bindings).state == (
        "valid" if count == 1 else "invalid"
    )


@pytest.mark.parametrize("state", list(ApprovalState))
def test_only_approved_candidates(state: ApprovalState) -> None:
    result = resolve_bindings(TEMPLATE, INPUT, (replace(candidate(), approval_state=state),))
    assert (result[0].outcome == "bound") == (state == ApprovalState.APPROVED)


@pytest.mark.parametrize("scope", ["event", "other_event", "stage", "other_stage", "role"])
def test_event_stage_role_applicability(scope: str) -> None:
    c = candidate()
    if scope == "other_event":
        c = replace(c, asset=replace(c.asset, event_id=EntityId.new()))
    if scope in ("stage", "other_stage"):
        c = replace(c, asset=replace(
            c.asset, stage_id=STAGE if scope == "stage" else EntityId.new(),
        ))
    if scope == "role":
        c = replace(c, asset=replace(c.asset, role=PackagingAssetRole.OUTRO))
    assert (resolve_bindings(TEMPLATE, INPUT, (c,))[0].outcome == "bound") == (
        scope in ("event", "stage")
    )


@pytest.mark.parametrize(("start", "end", "eligible"), [
    (None, None, True), (-1, None, True), (0, None, True), (1, None, False),
    (None, -1, False), (None, 0, False), (None, 1, True), (-1, 1, True),
])
def test_effective_interval_is_start_inclusive_end_exclusive(
    start: int | None, end: int | None, eligible: bool,
) -> None:
    c = candidate()
    c = replace(c, revision=replace(c.revision, content=replace(
        c.revision.content,
        effective_from=None if start is None else NOW + timedelta(seconds=start),
        effective_until=None if end is None else NOW + timedelta(seconds=end),
    )))
    assert (resolve_bindings(TEMPLATE, INPUT, (c,))[0].outcome == "bound") == eligible


@pytest.mark.parametrize("valid", [True, False])
def test_explicit_binding_must_be_eligible_even_for_optional_slot(valid: bool) -> None:
    a, b = candidate(), candidate()
    template = replace(TEMPLATE, slots=(replace(SLOTS[0], required=False),))
    binding = ExplicitBinding("intro", a.revision.id if valid else EntityId.new())
    result = resolve_bindings(template, INPUT, (a, b), (binding,))
    assert result[0].outcome == ("bound" if valid else "invalid_explicit")
    assert validate_assembly(template, INPUT, result).state == ("valid" if valid else "invalid")


@pytest.mark.parametrize("key", ["unknown", "media", "duplicate"])
def test_bad_explicit_slot_keys_are_rejected(key: str) -> None:
    bindings = (ExplicitBinding(key, EntityId.new()),) if key != "duplicate" else (
        ExplicitBinding("intro", EntityId.new()), ExplicitBinding("intro", EntityId.new()),
    )
    with pytest.raises(ValueError):
        resolve_bindings(TEMPLATE, INPUT, (), bindings)


@pytest.mark.parametrize("count", [0, 2])
def test_optional_unresolved_or_ambiguous_slots_do_not_block(count: int) -> None:
    template = replace(TEMPLATE, slots=(replace(SLOTS[0], required=False),))
    bindings = resolve_bindings(template, INPUT, tuple(candidate() for _ in range(count)))
    assert validate_assembly(template, INPUT, bindings).state == "valid"


@pytest.mark.parametrize("field", list(MetadataField))
@pytest.mark.parametrize("values", [(), ("",), (" ",)])
def test_metadata_required_only_by_template(field: MetadataField, values: tuple[str, ...]) -> None:
    inputs = replace(INPUT, metadata=(MetadataValue(field, values, SOURCE, 2),))
    template = replace(TEMPLATE, required_metadata=(field,))
    bindings = resolve_bindings(template, inputs, (candidate(),))
    assert ValidationReason.MISSING_REQUIRED_METADATA in {
        i.code for i in validate_assembly(template, inputs, bindings).issues
    }
    optional = replace(template, required_metadata=())
    assert validate_assembly(optional, inputs, bindings).state == "valid"
    assert inputs.package_complete and inputs.package_revision == INPUT.package_revision


@pytest.mark.parametrize("case", ["ineligible", "missing_completion", "empty", "timing"])
def test_package_and_membership_validation(case: str) -> None:
    inputs = INPUT
    code = ValidationReason.COMPLETION_MEMBERSHIP_UNAVAILABLE
    if case == "ineligible":
        inputs = replace(inputs, package_complete=False, completion_decision_id=None, membership=())
        code = ValidationReason.INELIGIBLE_PACKAGE
    elif case == "missing_completion":
        inputs = replace(inputs, completion_decision_id=None)
    elif case == "empty":
        inputs = replace(inputs, membership=())
    else:
        inputs = replace(inputs, membership=(replace(
            MEDIA, media_started_at=None, order_source=MediaOrderSource.REGISTRATION_TIME,
        ),))
        harness = Harness()
        harness.inputs = inputs
        revision = harness.propose()
        assert revision.validation.state == "valid"
        assert revision.membership[0].order_source == MediaOrderSource.REGISTRATION_TIME
        return
    bindings = resolve_bindings(TEMPLATE, inputs, (candidate(),))
    assert code in {i.code for i in validate_assembly(TEMPLATE, inputs, bindings).issues}


class Harness:
    def __init__(self) -> None:
        self.inputs = INPUT
        self.candidates: tuple[PackagingCandidate, ...] = (candidate(),)
        self.repository = InMemorySessionAssemblyRepository(
            event_ids=frozenset((EVENT,)), inputs=self.read_inputs,
            candidates=lambda: self.candidates,
        )
        self.service = SessionAssemblyService(self.repository, FixedClock(NOW))
        self.template_operation = EntityId.new()
        self.template = self.create_template()

    def read_inputs(self, session_id: EntityId) -> AssemblyInputs:
        if session_id != SESSION:
            raise AssemblyNotFoundError("session_not_found")
        return self.inputs

    def create_template(
        self, expected: int = 0, operation: EntityId | None = None,
    ) -> AssemblyTemplate:
        return self.service.create_template(
            operation_id=operation or self.template_operation, actor_id=ACTOR, event_id=EVENT,
            template_key="example", expected_version=expected, name="Example", slots=SLOTS,
            required_metadata=TEMPLATE.required_metadata,
        )

    def propose(self, expected: int = 0, operation: EntityId | None = None):
        return self.service.propose(
            operation_id=operation or EntityId.new(), actor_id=ACTOR, session_id=SESSION,
            template_id=self.template.id, expected_revision=expected,
            expected_package_revision=self.inputs.package_revision,
        )

    def decide(self, expected: int = 1, count: int = 0, operation: EntityId | None = None,
               action: AssemblyAction = AssemblyAction.APPROVE):
        return self.service.decide(
            operation_id=operation or EntityId.new(), actor_id=ACTOR, session_id=SESSION,
            revision_number=expected, expected_revision=expected, expected_decision_count=count,
            action=action, reason="Human review",
        )


@pytest.fixture
def harness() -> Harness:
    return Harness()


def test_template_immutability_versions_and_replay(harness: Harness) -> None:
    assert harness.create_template() == harness.template
    second = harness.create_template(1, EntityId.new())
    assert second.version == 2 and harness.template.version == 1
    with pytest.raises(AssemblyConflictError):
        harness.create_template(0, EntityId.new())
    with pytest.raises(AssemblyConflictError):
        harness.create_template(1)
    def assert_frozen(value: object, name: str, replacement: object) -> None:
        with pytest.raises(FrozenInstanceError):
            setattr(value, name, replacement)
    assert_frozen(harness.template.slots[0], "required", False)
    assert_frozen(harness.template, "name", "Changed")
    slots = list(SLOTS)
    template = replace(TEMPLATE, slots=cast(tuple[AssemblySlot, ...], slots))
    slots.clear()
    assert template.slots == SLOTS
    with pytest.raises(ValueError):
        replace(template, slots=(SLOTS[0], SLOTS[0]))
    with pytest.raises(ValueError):
        replace(template, created_at=NOW.replace(tzinfo=None))


def test_proposal_freezes_membership_metadata_and_supersedes(harness: Harness) -> None:
    later = replace(MEDIA, asset_id=EntityId.new(), media_started_at=NOW + timedelta(seconds=2),
                    order_key_at=NOW + timedelta(seconds=2))
    harness.inputs = replace(INPUT, membership=(later, MEDIA))
    original_inputs, original_candidates = harness.inputs, harness.candidates
    operation = EntityId.new()
    first = harness.propose(operation=operation)
    assert first.membership == (MEDIA, later) and first.validation.state == "valid"
    assert first.package_revision == 4
    assert first.completion_decision_id == INPUT.completion_decision_id
    assert first.metadata == METADATA
    assert harness.inputs == original_inputs and harness.candidates == original_candidates
    harness.inputs = replace(harness.inputs, metadata=())
    second = harness.propose(1)
    assert second.supersedes_id == first.id and second.revision_number == 2
    assert second.validation.state == "invalid" and first.metadata == METADATA
    assert harness.propose(operation=operation) == first
    with pytest.raises(AssemblyConflictError):
        harness.propose(1, operation)
    with pytest.raises(AssemblyConflictError):
        harness.decide()
    with pytest.raises(AssemblyConflictError):
        harness.decide(2)
    assert harness.repository.list_revisions(EVENT, SESSION).items[0].revision == first


@pytest.mark.parametrize("cause", ["package", "revoke", "reject", "new_content", "metadata"])
def test_read_time_staleness_preserves_decisions_and_rows(harness: Harness, cause: str) -> None:
    first = harness.propose()
    decision_op = EntityId.new()
    decision = harness.decide(operation=decision_op)
    if cause == "package":
        harness.inputs = replace(INPUT, package_revision=5, package_complete=False)
    elif cause in ("revoke", "reject"):
        harness.candidates = (replace(harness.candidates[0], approval_state=(
            ApprovalState.REVOKED if cause == "revoke" else ApprovalState.REJECTED
        )),)
    elif cause == "new_content":
        harness.candidates += (candidate(),)
    else:
        harness.inputs = replace(INPUT, metadata=())
    item = harness.repository.list_revisions(EVENT, SESSION).items[0]
    assert item.stale == (cause in ("package", "revoke", "reject"))
    assert item.revision == first and item.latest_decision == decision
    assert item.approval_state == ApprovalState.APPROVED
    assert harness.decide(operation=decision_op) == decision
    if item.stale:
        with pytest.raises(AssemblyConflictError):
            harness.decide(count=1)


def test_ineligible_proposal_is_recorded_and_decisions_require_fresh_count(
    harness: Harness,
) -> None:
    harness.inputs = replace(
        INPUT, package_complete=False, completion_decision_id=None, membership=(),
    )
    revision = harness.propose()
    assert ValidationReason.INELIGIBLE_PACKAGE in {i.code for i in revision.validation.issues}
    with pytest.raises(AssemblyConflictError):
        harness.decide()
    harness.inputs = INPUT
    harness.propose(1)
    first = harness.decide(2)
    with pytest.raises(AssemblyConflictError):
        harness.decide(2)
    second = harness.decide(2, 1, action=AssemblyAction.REJECT)
    assert second.sequence == 2 and first.authority_kind == "human"
    assert harness.repository.list_revisions(EVENT, SESSION).items[1].approval_state == (
        ApprovalState.REJECTED
    )


def test_concurrent_proposals_and_decisions_have_one_winner(harness: Harness) -> None:
    def propose(_: int) -> str:
        try:
            harness.propose()
            return "created"
        except AssemblyConflictError:
            return "conflict"
    def decide(_: int) -> str:
        try:
            harness.decide()
            return "created"
        except AssemblyConflictError:
            return "conflict"
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sorted(pool.map(propose, range(4))) == ["conflict"] * 3 + ["created"]
        assert sorted(pool.map(decide, range(4))) == ["conflict"] * 3 + ["created"]
    operation = EntityId.new()
    def replay(_: int):
        return harness.propose(1, operation)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(replay, range(4)))
    assert all(r == results[0] for r in results)


def test_current_revision_read_supplies_approval_concurrency_guard(harness: Harness) -> None:
    harness.propose()
    harness.decide()
    harness.propose(1)
    current = harness.repository.list_revisions(EVENT, SESSION, after=1).items[0]
    assert current.decision_count == 0
    decision = harness.decide(current.current_revision_number, current.decision_count)
    assert decision.sequence == 2


def test_event_scoping_pagination_counts_and_stale_package_guard(harness: Harness) -> None:
    for n in range(3):
        harness.propose(n)
    page = harness.repository.list_revisions(EVENT, SESSION, limit=1)
    assert page.total_count == 3 and page.next_after == 1
    assert page.items[0].current_revision_number == 3
    assert harness.repository.list_revisions(EVENT, SESSION, after=3).items == ()
    harness.create_template(1, EntityId.new())
    templates = harness.repository.list_templates(EVENT, limit=1)
    assert templates.total_count == 2 and templates.next_after is not None
    assert len(harness.repository.list_templates(EVENT, after=templates.next_after).items) == 1
    assert harness.repository.list_templates(EntityId.new()).total_count == 0
    with pytest.raises(AssemblyNotFoundError):
        harness.repository.list_revisions(EntityId.new(), SESSION)
    with pytest.raises(AssemblyConflictError, match="package_revision"):
        harness.service.propose(operation_id=EntityId.new(), actor_id=ACTOR, session_id=SESSION,
                                template_id=harness.template.id, expected_revision=3,
                                expected_package_revision=3)
    for limit in (0, 101):
        with pytest.raises(ValueError):
            harness.repository.list_revisions(EVENT, SESSION, limit=limit)


def client_for(harness: Harness) -> SyncHttpClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    repo = InMemoryEventModeKernelRepository()
    app.state.kernel = KernelComponents(
        configuration=cast(EffectiveKernelConfiguration, None), repository=repo,
        kernel=DurableEventModeKernel(repository=repo, clock=FixedClock(NOW)),
        session_assemblies=harness.service,
    )
    return cast(SyncHttpClient, TestClient(app))


def test_api_authentication_commands_reads_and_validation(harness: Harness) -> None:
    client = client_for(harness)
    base = "/api/v1/assembly"
    human = {"operation_id": EntityId.new().value, "actor_id": ACTOR.value,
             "confirmed": "confirmed"}
    body = {**human, "template_id": harness.template.id.value,
            "expected_revision": 0, "expected_package_revision": 4}
    url = base + f"/sessions/{SESSION}/revisions"
    assert client.post(url, json=body).status_code == 401
    response = client.post(url, json=body, headers=HEADERS)
    assert response.status_code == 200 and response.json()["validation"]["state"] == "valid"
    assert client.post(url, json=body, headers=HEADERS).json() == response.json()
    assert client.post(url, json={**body, "metadata": {}}, headers=HEADERS).status_code == 422
    assert client.post(url, json={**body, "operation_id": EntityId.new().value},
                       headers=HEADERS).status_code == 409
    decision = {**human, "operation_id": EntityId.new().value, "revision_number": 1,
                "expected_revision": 1, "expected_decision_count": 0,
                "action": "approve", "reason": "Reviewed"}
    approval_url = base + f"/sessions/{SESSION}/approvals"
    assert client.post(approval_url, json=decision).status_code == 401
    assert client.post(approval_url, json=decision, headers=HEADERS).status_code == 200
    assert client.post(approval_url, json={**decision, "action": "revoke"},
                       headers=HEADERS).status_code == 422
    assert client.post(approval_url, json={**decision, "authority_kind": "automatic"},
                       headers=HEADERS).status_code == 422
    history = base + f"/events/{EVENT}/sessions/{SESSION}/revisions"
    assert client.get(history).status_code == 401
    item = client.get(history, headers=HEADERS).json()["items"][0]
    assert not item["stale"] and item["approval_state"] == "approved"
    assert client.get(history + "?limit=101", headers=HEADERS).status_code == 422
    assert client.get(history.replace(EVENT.value, EntityId.new().value),
                      headers=HEADERS).status_code == 404
    templates = base + f"/events/{EVENT}/templates"
    assert client.get(templates).status_code == 401
    assert client.get(templates, headers=HEADERS).json()["total_count"] == 1
    template_body = {**human, "operation_id": EntityId.new().value,
                     "event_id": EVENT.value, "template_key": "second",
                     "expected_version": 0, "name": "Second", "slots": [
                         {"key": "media", "role": "session_media", "required": True}]}
    assert client.post(base + "/templates", json=template_body).status_code == 401
    assert client.post(base + "/templates", json=template_body, headers=HEADERS).status_code == 200


def test_storage_error_does_not_leak_diagnostics(harness: Harness) -> None:
    class Unavailable(InMemorySessionAssemblyRepository):
        def list_templates(self, event_id: EntityId, *, after: EntityId | None = None,
                           limit: int = 50):
            raise AssemblyStorageUnavailableError("private diagnostics")
    harness.service.repository = Unavailable(event_ids=frozenset(), inputs=harness.read_inputs,
                                              candidates=lambda: ())
    response = client_for(harness).get(
        f"/api/v1/assembly/events/{EVENT}/templates", headers=HEADERS,
    )
    assert response.status_code == 503 and response.json() == {"detail": "postgresql_unavailable"}


def test_migration_registration_order(monkeypatch: pytest.MonkeyPatch) -> None:
    applied: list[str] = []
    def record(self: PostgresMigrationRunner, filename: str, *, version: str) -> None:
        applied.append(version)
    monkeypatch.setattr(PostgresMigrationRunner, "_execute_if_missing", record)
    monkeypatch.setattr(PostgresMigrationRunner, "_execute_if_present", record)
    runner = PostgresMigrationRunner("unused")
    runner.apply_packaging_asset_foundation_v1()
    assert applied == ["0012_packaging_asset_foundation", "0013_session_assembly_foundation",
                       "0014_assembly_metadata_overrides", "0015_render_durable_operation",
                       "0016_assembly_media_order"]
    applied.clear()
    runner.reverse_packaging_asset_foundation_v1()
    assert applied == ["0016_assembly_media_order", "0015_render_durable_operation",
                       "0014_assembly_metadata_overrides",
                       "0013_session_assembly_foundation",
                       "0012_packaging_asset_foundation"]


@pytest.fixture
def postgres_dsn() -> str:
    dsn = os.getenv("STAGEFLOW_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("STAGEFLOW_TEST_POSTGRES_DSN is required for real PostgreSQL validation")
    try:
        with psycopg.connect(dsn, connect_timeout=3):
            pass
    except psycopg.OperationalError:
        pytest.skip("Real PostgreSQL is unreachable from this sandbox")
    return dsn


def test_postgres_restart_lineage_replay_staleness_and_reverse_reapply(postgres_dsn: str) -> None:
    # This test requires the same explicitly isolated database as the existing durability tests.
    runner = PostgresMigrationRunner(postgres_dsn)
    runner.apply_event_mode_kernel_v1()
    kernel_repo = PostgresEventModeKernelRepository(postgres_dsn)
    kernel = DurableEventModeKernel(repository=kernel_repo, clock=FixedClock(NOW))
    source_key = "source-" + EntityId.new().value
    boot = kernel.bootstrap(EventStageBootstrapRequest(
        EntityId.new(), "assembly-" + EntityId.new().value, "Example Event",
        (StageBootstrapDefinition("main", "Example Stage", {source_key: "synthetic-source"}),),
        ACTOR, NOW,
    ))
    assert boot.event is not None
    event, stage = boot.event.id, boot.stages[0].id
    program = kernel_repo.put_program_expectation(ProgramExpectation(
        EntityId.new(), event, "example-program", stage, "Example title",
        ("Speaker B", "Speaker A"),
        NOW, NOW + timedelta(hours=1), {}, 1, NOW,
    ))
    session = kernel.start_session(StartSessionRequest(
        EntityId.new(), event, stage, ACTOR, NOW, NOW, program.id,
    ))
    media_id, candidate_id = EntityId.new(), EntityId.new()
    kernel_repo.register_candidate(MediaCandidate(candidate_id, media_id, stage, source_key,
                                                  "synthetic-source", NOW, NOW,
                                                  MediaRegistrationState.READY, 1))
    kernel_repo.register_asset(RegisteredMediaAsset(
        media_id, candidate_id, EntityId.new(), stage,
        source_key, NOW, NOW, NOW + timedelta(minutes=1),
    ))
    association = kernel.assign_asset(operation_id=EntityId.new(), asset_id=media_id,
                                      session_id=session.id, actor_id=ACTOR,
                                      reason="Example review")
    kernel.correct_session_boundary(operation_id=EntityId.new(), session_id=session.id,
                                    boundary_kind="end", boundary_at=NOW + timedelta(minutes=1),
                                    actor_id=ACTOR, reason="Example end")
    kernel.mark_package_ready(session.id)
    session = kernel.complete_package(operation_id=EntityId.new(), session_id=session.id,
                                       actor_id=ACTOR, approved=True, reason="Example completion")
    packaging = PackagingAssetService(
        PostgresPackagingAssetRepository(postgres_dsn), FixedClock(NOW),
    )
    asset = packaging.register(operation_id=EntityId.new(), actor_id=ACTOR, event_id=event,
                                name="Example bumper", role=PackagingAssetRole.OPENING_BUMPER)
    packaging_revision = packaging.revise(operation_id=EntityId.new(), actor_id=ACTOR,
                                           packaging_asset_id=asset.id, expected_revision=0,
                                           content=candidate().revision.content)
    packaging.decide(operation_id=EntityId.new(), actor_id=ACTOR, packaging_asset_id=asset.id,
                     revision_number=1, expected_revision=1, action=ApprovalAction.APPROVE,
                     reason="Example approval")
    service = SessionAssemblyService(
        PostgresSessionAssemblyRepository(postgres_dsn), FixedClock(NOW),
    )
    template_op, proposal_op, decision_op = EntityId.new(), EntityId.new(), EntityId.new()
    try:
        template = service.create_template(
            operation_id=template_op, actor_id=ACTOR, event_id=event, template_key="example",
            expected_version=0, name="Example", slots=SLOTS,
            required_metadata=TEMPLATE.required_metadata,
        )
        def propose(service: SessionAssemblyService, expected: int = 0,
                    operation: EntityId = proposal_op):
            return service.propose(operation_id=operation, actor_id=ACTOR, session_id=session.id,
                                   template_id=template.id, expected_revision=expected,
                                   expected_package_revision=session.package_revision)
        revision = propose(service)
        assert revision.validation.state == "valid"
        assert revision.membership == (CompletionMember(
            media_id, association.revision, NOW, NOW, MediaOrderSource.MEDIA_TIMING, NOW,
        ),)
        assert revision.bindings[0].packaging_revision_id == packaging_revision.id
        assert revision.metadata[0].source_revision == program.revision
        assert revision.metadata[0].values == ("Speaker A", "Speaker B")
        decision = service.decide(
            operation_id=decision_op, actor_id=ACTOR, session_id=session.id, revision_number=1,
            expected_revision=1, expected_decision_count=0, action=AssemblyAction.APPROVE,
            reason="Example approval",
        )
        restarted = SessionAssemblyService(PostgresSessionAssemblyRepository(postgres_dsn),
                                            FixedClock(NOW + timedelta(hours=1)))
        assert propose(restarted) == revision
        assert restarted.repository.list_revisions(
            event, session.id,
        ).items[0].latest_decision == decision
        assert kernel_repo.get_session(session.id) == session
        updated_program = kernel_repo.put_program_expectation(replace(
            program, title="New example title", revision=program.revision + 1,
        ))
        assert updated_program.title != revision.metadata[1].values[0]
        assert propose(restarted) == revision
        packaging.decide(operation_id=EntityId.new(), actor_id=ACTOR, packaging_asset_id=asset.id,
                         revision_number=1, expected_revision=1, action=ApprovalAction.REVOKE,
                         reason="Example revoke")
        projected = restarted.repository.list_revisions(event, session.id).items[0]
        assert projected.stale and projected.revision == revision
        with pytest.raises(AssemblyConflictError):
            restarted.decide(operation_id=EntityId.new(), actor_id=ACTOR, session_id=session.id,
                             revision_number=1, expected_revision=1, expected_decision_count=1,
                             action=AssemblyAction.REJECT, reason="Stale")
        assert restarted.decide(
            operation_id=decision_op, actor_id=ACTOR, session_id=session.id, revision_number=1,
            expected_revision=1, expected_decision_count=0, action=AssemblyAction.APPROVE,
            reason="Example approval",
        ) == decision
        def append(_: int) -> str:
            independent = SessionAssemblyService(PostgresSessionAssemblyRepository(postgres_dsn),
                                                   FixedClock(NOW))
            try:
                propose(independent, 1, EntityId.new())
                return "created"
            except AssemblyConflictError:
                return "conflict"
        with ThreadPoolExecutor(max_workers=3) as pool:
            assert sorted(pool.map(append, range(3))) == ["conflict", "conflict", "created"]
        page = restarted.repository.list_revisions(event, session.id, limit=1)
        assert page.total_count == 2 and page.next_after == 1
        assert page.items[0].current_revision_number == 2
        # Trigger behavior, not merely the presence of trigger names.
        with pytest.raises(psycopg.errors.RaiseException, match="assembly_history_is_immutable"):
            with psycopg.connect(postgres_dsn) as conn:
                conn.execute("UPDATE stageflow.assembly_revision "
                             "SET package_revision=package_revision "
                             "WHERE revision_id=%s", (revision.id.value,))
        with pytest.raises(psycopg.errors.RaiseException, match="assembly_history_is_immutable"):
            with psycopg.connect(postgres_dsn) as conn:
                conn.execute("DELETE FROM stageflow.assembly_template WHERE template_id=%s",
                             (template.id.value,))
        runner.reverse_session_assembly_foundation_v1()
        with psycopg.connect(postgres_dsn) as conn:
            assert conn.execute(
                "SELECT to_regclass('stageflow.assembly_revision')",
            ).fetchone() == (None,)
            assert conn.execute("SELECT count(*) FROM stageflow.packaging_asset_revision "
                                "WHERE revision_id=%s",
                                (packaging_revision.id.value,)).fetchone() == (1,)
        assert kernel_repo.get_session(session.id) == session
        runner.apply_session_assembly_foundation_v1()
        assert restarted.repository.list_revisions(event, session.id).total_count == 0
    finally:
        # Preserve upstream authoritative fixture history; only reverse this slice in the
        # explicitly isolated durability database. No deletions of Kernel or Packaging history.
        runner.reverse_session_assembly_foundation_v1()
        runner.apply_session_assembly_foundation_v1()
