"""ED-0091: advisory reads, frozen ordering and additive persistence boundaries."""
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, replace
from datetime import datetime, timedelta
from typing import Any, cast

import psycopg
import pytest
from psycopg.rows import dict_row

from app.contexts.assembly.contracts import ApprovalState, CompletedMediaAssetContent
from app.contexts.assembly.session_contracts import (
    AssemblyRevision,
    CompletionMember,
    MediaOrderSource,
    SessionAssembly,
)
from app.contexts.assembly.session_memory import InMemorySessionAssemblyRepository
from app.contexts.assembly.session_service import SessionAssemblyService
from app.contexts.assembly.timing_reader import AssemblyTimingEvidence
from app.contexts.production.media_timing_evidence.application import MediaTimingEvidenceApplication
from app.contexts.production.media_timing_evidence.contracts import (
    MediaTimingEvidence,
)
from app.contexts.production.media_timing_evidence.contracts import (
    RecorderProfileQualificationStatus as Qualification,
)
from app.contexts.production.media_timing_evidence.repository import (
    InMemoryMediaTimingEvidenceRepository,
    MediaTimingEvidenceRepository,
)
from app.contexts.rendering.contracts import FIRST_RENDER_PROFILE, VideoInput
from app.contexts.rendering.planning import build_render_plan
from app.infrastructure.media_timing.assembly import InMemoryAssemblyTimingReader
from app.infrastructure.postgres.assembly_timing_reader import PostgresAssemblyTimingReader
from app.infrastructure.postgres.media_timing_evidence_repository import (
    PostgresMediaTimingEvidenceRepository,
)
from app.infrastructure.postgres.migrations import PostgresMigrationRunner
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.media_timing_evidence_fixtures import evidence_request
from tests.test_assembly_media_order import IsolatedRenderRepository, members_for, seed_assembly
from tests.test_packaging_asset_foundation import HEADERS
from tests.test_render_work_execution import (
    render_postgres_dsn as render_postgres_dsn,
)
from tests.test_session_assembly_foundation import (
    ACTOR,
    EVENT,
    INPUT,
    NOW,
    SESSION,
    Harness,
    client_for,
)


def schema_contract(dsn: str) -> tuple[object, object]:
    with psycopg.connect(dsn) as conn:
        constraints = conn.execute("""SELECT conname,pg_get_constraintdef(oid)
            FROM pg_constraint WHERE conrelid='stageflow.assembly_member'::regclass
            ORDER BY conname""").fetchall()
        columns = conn.execute("""SELECT column_name,data_type,is_nullable,column_default
            FROM information_schema.columns
            WHERE table_schema='stageflow' AND table_name='assembly_member'
            ORDER BY ordinal_position""").fetchall()
    return constraints, columns


def append_evidence(
    repository: MediaTimingEvidenceRepository, member: CompletionMember,
    manifest: EntityId, start: datetime, *, matches: int = 1,
    qualification: Qualification = Qualification.UNQUALIFIED,
) -> MediaTimingEvidence:
    request = evidence_request(profile_id="synthetic-recorder")
    derivation = replace(request.result.derivations[0], rule_id="creation_time_plus_duration",
                         candidate_started_at=start,
                         candidate_ended_at=start + timedelta(seconds=60))
    # An unrelated derivation must neither qualify nor make a single match ambiguous.
    derivations = (replace(derivation, id=EntityId.new(), rule_id="unrelated_rule"),) + tuple(
        replace(derivation, id=EntityId.new()) for _ in range(matches)
    )
    return MediaTimingEvidenceApplication(repository).apply(replace(
        request, operation_id=EntityId.new(), asset_id=member.asset_id, manifest_id=manifest,
        result=replace(request.result, derivations=derivations, qualification=replace(
            request.result.qualification, status=qualification,
            qualification_record_id=EntityId.new() if qualification == Qualification.QUALIFIED
            else None,
        )),
    ))


def memory_harness(mode: str) -> tuple[Harness, InMemoryMediaTimingEvidenceRepository]:
    h = Harness()
    h.inputs = replace(INPUT, membership=members_for(mode))
    evidence = InMemoryMediaTimingEvidenceRepository()
    h.repository = InMemorySessionAssemblyRepository(
        event_ids=frozenset((EVENT,)), inputs=h.read_inputs, candidates=lambda: h.candidates,
        timing_reader=InMemoryAssemblyTimingReader(evidence),
    )
    h.service = SessionAssemblyService(h.repository, FixedClock(NOW))
    h.template = h.create_template()
    return h, evidence


@dataclass
class OrderingHarness:
    members: tuple[CompletionMember, ...]
    append: Callable[[CompletionMember, datetime, int], MediaTimingEvidence]
    propose: Callable[[int, EntityId], AssemblyRevision]
    read: Callable[[], SessionAssembly]
    approve: Callable[[], object]


@pytest.fixture(params=["memory", "postgres"])
def ordering(request: pytest.FixtureRequest) -> OrderingHarness:
    if request.param == "memory":
        h, repository = memory_harness("mixed")
        manifest = EntityId.new()
        for member in h.inputs.membership:
            repository.register_asset(member.asset_id, manifest)
        return OrderingHarness(
            h.inputs.membership,
            lambda m, at, count: append_evidence(repository, m, manifest, at, matches=count),
            lambda number, op: h.propose(number, op),
            lambda: h.repository.list_revisions(EVENT, SESSION).items[0],
            h.decide,
        )
    dsn = cast(str, request.getfixturevalue("render_postgres_dsn"))
    db = seed_assembly(dsn, "mixed")
    repo = PostgresMediaTimingEvidenceRepository(dsn)
    manifests: dict[EntityId, EntityId] = {}
    with psycopg.Connection[dict[str, Any]].connect(dsn, row_factory=dict_row) as conn:
        for m in db.members:
            row = conn.execute("SELECT manifest_id FROM stageflow.completed_media_asset_registry "
                               "WHERE asset_id=%s", (m.asset_id.value,)).fetchone()
            assert row is not None
            manifests[m.asset_id] = EntityId(str(row["manifest_id"]))
    return OrderingHarness(
        db.members,
        lambda m, at, count: append_evidence(repo, m, manifests[m.asset_id], at, matches=count),
        lambda number, op: db.service.propose(
            operation_id=op, actor_id=ACTOR, session_id=db.session_id, template_id=db.template.id,
            expected_revision=number, expected_package_revision=db.package_revision,
        ),
        lambda: db.read(dsn), db.approve,
    )


@pytest.mark.parametrize("matches", [0, 1, 2])
def test_latest_active_priority_fallback_freeze_replay_and_approval(
    ordering: OrderingHarness, matches: int,
) -> None:
    h = ordering
    active: dict[EntityId, MediaTimingEvidence] = {}
    for m in h.members:
        h.append(m, NOW - timedelta(seconds=30), 1)
        active[m.asset_id] = h.append(m, NOW - timedelta(seconds=10), matches)
    operation = EntityId.new()
    revision = h.propose(0, operation)
    assert revision.validation.state == "valid"
    expected: list[CompletionMember] = []
    for m in h.members:
        if m.media_started_at is not None:
            expected.append(m)
        elif matches == 1:
            e = active[m.asset_id]
            expected.append(replace(m, order_source=MediaOrderSource.TIMING_EVIDENCE,
                order_key_at=NOW - timedelta(seconds=10), order_evidence_id=e.id,
                order_evidence_revision=2, order_evidence_qualification=Qualification.UNQUALIFIED))
        else:
            expected.append(m)
    expected.sort(key=lambda m: (m.order_key_at or m.registered_at, m.asset_id.value))
    assert revision.membership == tuple(expected)
    assert h.read().revision == revision
    for m in h.members:
        h.append(m, NOW - timedelta(seconds=20), 1)
    assert h.propose(0, operation) == revision  # Exact replay never consults newer MTE.
    assert not h.read().stale
    h.approve()
    assert h.read().approval_state == ApprovalState.APPROVED
    assert h.read().revision == revision
    newer = h.propose(1, EntityId.new())
    assert all(m.order_evidence_revision == 3 for m in newer.membership
               if m.media_started_at is None)
    assert h.read().revision == revision and not h.read().stale


@pytest.mark.parametrize("qualification", list(Qualification))
def test_qualification_is_disclosed_without_authority_promotion(
    qualification: Qualification,
) -> None:
    h, repo = memory_harness("untimed")
    member = h.inputs.membership[0]
    manifest = EntityId.new()
    repo.register_asset(member.asset_id, manifest)
    e = append_evidence(repo, member, manifest, NOW, qualification=qualification)
    revision = h.propose()
    selected = next(m for m in revision.membership if m.asset_id == member.asset_id)
    assert selected.order_evidence_qualification == qualification
    assert selected.order_evidence_id == e.id
    assert selected.media_started_at is None
    assert h.inputs.membership[0] == member
    with pytest.raises(FrozenInstanceError):
        cast(Any, selected).order_evidence_revision = 9
    projection = InMemoryAssemblyTimingReader(repo).read((member.asset_id,))[0]
    with pytest.raises(FrozenInstanceError):
        cast(Any, projection).candidate_started_at = NOW
    h.decide()


@pytest.mark.parametrize("field", ["order_evidence_id", "order_evidence_revision",
                                  "order_evidence_qualification"])
def test_member_requires_evidence_fields_iff_timing_evidence(field: str) -> None:
    member = members_for("untimed")[0]
    fields: dict[str, Any] = dict(order_evidence_id=EntityId.new(), order_evidence_revision=1,
                                 order_evidence_qualification=Qualification.UNQUALIFIED)
    valid = replace(member, order_source=MediaOrderSource.TIMING_EVIDENCE, **fields)
    with pytest.raises(ValueError):
        replace(valid, **{field: None})
    for source in (MediaOrderSource.MEDIA_TIMING, MediaOrderSource.REGISTRATION_TIME):
        baseline = replace(member, order_source=source, order_key_at=None
                           if source == MediaOrderSource.MEDIA_TIMING else NOW)
        with pytest.raises(ValueError):
            replace(baseline, **{field: fields[field]})


def test_timing_contract_rejects_naive_keys_invalid_revision_and_qualification() -> None:
    member = replace(members_for("untimed")[0], order_source=MediaOrderSource.TIMING_EVIDENCE,
                     order_evidence_id=EntityId.new(), order_evidence_revision=1,
                     order_evidence_qualification=Qualification.UNQUALIFIED)
    for field in ("order_key_at", "registered_at", "media_started_at"):
        with pytest.raises(ValueError):
            replace(member, **{field: NOW.replace(tzinfo=None)})
    for changes in ({"order_key_at": None}, {"order_evidence_revision": 0},
                    {"order_evidence_qualification": "invented"}):
        with pytest.raises(ValueError):
            replace(member, **changes)
    with pytest.raises(ValueError):
        AssemblyTimingEvidence(member.asset_id, EntityId.new(), 1, Qualification.UNQUALIFIED,
                               NOW.replace(tzinfo=None))


def test_api_discloses_frozen_provenance_and_render_preserves_order() -> None:
    h, repo = memory_harness("untimed")
    for i, m in enumerate(h.inputs.membership):
        manifest = EntityId.new()
        repo.register_asset(m.asset_id, manifest)
        append_evidence(repo, m, manifest, NOW - timedelta(seconds=i))
    client = client_for(h)
    response = client.post(f"/api/v1/assembly/sessions/{SESSION}/revisions", headers=HEADERS, json={
        "operation_id": EntityId.new().value, "actor_id": ACTOR.value, "confirmed": "confirmed",
        "template_id": h.template.id.value, "expected_revision": 0, "expected_package_revision": 4,
    })
    assert response.status_code == 200
    page = client.get(f"/api/v1/assembly/events/{EVENT}/sessions/{SESSION}/revisions",
                      headers=HEADERS)
    assert page.status_code == 200
    frozen = h.repository.list_revisions(EVENT, SESSION).items[0].revision
    for body in (response.json(), page.json()["items"][0]["revision"]):
        for actual, m in zip(body["membership"], frozen.membership, strict=True):
            assert set(actual) == {"asset_id", "association_revision", "media_started_at",
                                   "order_source", "order_key_at", "order_evidence_id",
                                   "order_evidence_revision", "order_evidence_qualification"}
            assert actual["order_source"] == "timing_evidence"
            assert actual["order_evidence_id"] == str(m.order_evidence_id)
            assert actual["order_evidence_revision"] == 1
            assert actual["order_evidence_qualification"] == "unqualified"
            assert datetime.fromisoformat(actual["order_key_at"]) == m.order_key_at
    h.decide()
    source = h.repository.list_revisions(EVENT, SESSION).items[0]
    packaging = {c.revision.id: VideoInput(c.revision.content.reference, "video/mp4")
                 for c in h.candidates}
    media = {m.asset_id: VideoInput(CompletedMediaAssetContent(m.asset_id), "video/mp4")
             for m in frozen.membership}
    plan = build_render_plan(source, FIRST_RENDER_PROFILE, packaging, media)
    assert plan.inputs == (*packaging.values(), *(media[m.asset_id] for m in frozen.membership))


def test_postgres_reader_one_bounded_query_and_reverse_refused(render_postgres_dsn: str) -> None:
    dsn = render_postgres_dsn
    db = seed_assembly(dsn, "untimed")
    with psycopg.Connection[dict[str, Any]].connect(dsn, row_factory=dict_row) as conn:
        row = conn.execute("SELECT manifest_id FROM stageflow.completed_media_asset_registry "
                           "WHERE asset_id=%s", (db.members[0].asset_id.value,)).fetchone()
        assert row is not None
        e = append_evidence(PostgresMediaTimingEvidenceRepository(dsn), db.members[0],
                            EntityId(str(row["manifest_id"])), NOW)
        class CountingConnection:
            calls = 0

            def execute(self, *args: Any, **kwargs: Any) -> Any:
                self.calls += 1
                return conn.execute(*args, **kwargs)

        counted = CountingConnection()
        reader = PostgresAssemblyTimingReader(cast(psycopg.Connection[dict[str, Any]], counted))
        result = reader.read(tuple(m.asset_id for m in db.members))
        assert counted.calls == 1 and len(result) == 1 and result[0].evidence_id == e.id
        assert reader.read((EntityId.new(),)) == ()
    revision = db.propose()
    before = schema_contract(dsn)
    with pytest.raises(psycopg.errors.RaiseException, match="requires_no_timing_evidence_members"):
        PostgresMigrationRunner(dsn).reverse_assembly_timing_evidence_v1()
    assert schema_contract(dsn) == before
    assert db.read(dsn).revision == revision
    db.approve()
    plan = IsolatedRenderRepository(dsn).load_plan(revision.id, FIRST_RENDER_PROFILE)
    assert tuple(i.reference for i in plan.inputs) == tuple(
        CompletedMediaAssetContent(m.asset_id) for m in revision.membership
    )
    with psycopg.connect(dsn) as conn:
        with pytest.raises(psycopg.errors.RaiseException, match="assembly_history_is_immutable"):
            with conn.transaction():
                conn.execute("UPDATE stageflow.assembly_member SET order_evidence_revision=99 "
                             "WHERE revision_id=%s", (revision.id.value,))


def test_postgres_0018_forward_reverse_reapply_preserves_0016(render_postgres_dsn: str) -> None:
    dsn = render_postgres_dsn
    runner = PostgresMigrationRunner(dsn)
    db = seed_assembly(dsn, "mixed")
    revision = db.propose()
    runner.reverse_assembly_timing_evidence_v1()
    original = schema_contract(dsn)
    runner.apply_assembly_timing_evidence_v1()
    runner.apply_assembly_timing_evidence_v1()
    assert db.read(dsn).revision == revision
    runner.reverse_assembly_timing_evidence_v1()
    assert schema_contract(dsn) == original
    runner.apply_assembly_timing_evidence_v1()
    assert db.read(dsn).revision == revision


@pytest.mark.parametrize("case", ["missing_id", "missing_revision", "missing_qualification",
                                 "all_missing", "foreign_asset", "unknown_evidence",
                                 "qualification", "source", "legacy_id", "registration_revision",
                                 "media_qualification"])
def test_postgres_0018_negative_inserts(render_postgres_dsn: str, case: str) -> None:
    dsn = render_postgres_dsn
    db = seed_assembly(dsn, "timed")
    revision = db.propose()
    with psycopg.Connection[dict[str, Any]].connect(dsn, row_factory=dict_row) as conn:
        member = revision.membership[0]
        row = conn.execute("SELECT manifest_id FROM stageflow.completed_media_asset_registry "
                           "WHERE asset_id=%s", (member.asset_id.value,)).fetchone()
        assert row is not None
        e = append_evidence(PostgresMediaTimingEvidenceRepository(dsn), member,
                            EntityId(str(row["manifest_id"])), NOW)
        source, eid, number, qualification = "timing_evidence", e.id.value, 1, "unqualified"
        values: list[Any] = [source, eid, number, qualification]
        constraint = "assembly_member_order_evidence_set_check"
        if case.startswith("missing_"):
            index = {"missing_id": 1, "missing_revision": 2, "missing_qualification": 3}[case]
            values[index] = None
        elif case == "all_missing":
            values[1:] = [None, None, None]
        elif case == "qualification":
            values[3] = "invented"
            constraint = "assembly_member_order_evidence_qualification_check"
        elif case == "source":
            values = ["invented", None, None, None]
            constraint = "assembly_member_order_source_check"
        elif case == "legacy_id":
            values = [None, eid, None, None]
        elif case == "registration_revision":
            values = ["registration_time", None, 1, None]
        elif case == "media_qualification":
            values = ["media_timing", None, None, "unqualified"]
        else:
            values[1] = EntityId.new().value if case == "unknown_evidence" else eid
            constraint = "assembly_member_order_evidence_fk"
        position = 1 if case == "foreign_asset" else 0
        error = psycopg.errors.ForeignKeyViolation if case in (
            "foreign_asset", "unknown_evidence",
        ) else psycopg.errors.CheckViolation
        with pytest.raises(error) as failure:
            with conn.transaction():
                new_revision = EntityId.new()
                conn.execute("""INSERT INTO stageflow.assembly_revision
                    (revision_id,session_id,event_id,revision_number,template_id,package_revision,
                     completion_decision_id,validation_state,validation_issues,actor_id,created_at)
                    SELECT %s,session_id,event_id,2,template_id,package_revision,
                           completion_decision_id,validation_state,validation_issues,actor_id,created_at
                    FROM stageflow.assembly_revision WHERE revision_id=%s""",
                    (new_revision.value, revision.id.value))
                conn.execute("""INSERT INTO stageflow.assembly_member
                    (revision_id,position,completion_decision_id,asset_id,association_revision,
                     media_started_at,order_source,order_key_at,order_evidence_id,
                     order_evidence_revision,order_evidence_qualification)
                    SELECT %s,99,completion_decision_id,asset_id,association_revision,
                           media_started_at,%s,%s,%s,%s,%s
                    FROM stageflow.assembly_member WHERE revision_id=%s AND position=%s""",
                    (new_revision.value, values[0],
                     None if values[0] is None else revision.membership[position].order_key_at,
                     *values[1:], revision.id.value, position))
        assert failure.value.diag.constraint_name == constraint
