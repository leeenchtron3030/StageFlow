"""Synthetic phrase evidence only; no real event text or provider execution."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.editorial import EditorialDerivationRunResponse
from app.api.v1.router import router as api_router
from app.bootstrap.event_mode_kernel import KernelComponents
from app.contexts.editorial import (
    EditorialCandidateOrigin,
    EditorialMomentConflictError,
    EditorialMomentReviewAction,
    EditorialMomentService,
)
from app.contexts.editorial.derivation import location_conflict_reason, match_phrases, place_match
from app.contexts.editorial.derivation_contracts import (
    EditorialCandidateProvenance,
    EditorialDerivationInput,
    EditorialDerivationRun,
    EditorialPhraseList,
    EditorialSessionBasis,
    EditorialSkipCounts,
    EditorialTimingBasis,
    EditorialTranscriptSegment,
    EditorialTranscriptWord,
    TimingQualification,
)
from app.contexts.editorial.derivation_memory import InMemoryEditorialDerivationRepository
from app.contexts.editorial.derivation_service import EditorialDerivationService
from app.contexts.production.event_mode_kernel import (
    DurableEventModeKernel,
    InMemoryEventModeKernelRepository,
)
from app.core.config.deployment import EffectiveKernelConfiguration
from app.shared.ids import EntityId
from app.shared.time import FixedClock
from tests.test_editorial_review_foundation import (
    AUTH_HEADERS,
    MemoryEditorialReviewRepository,
    SyncHttpClient,
)

NOW = datetime(2026, 9, 26, tzinfo=UTC)


def eid(number: int) -> EntityId:
    return EntityId(f"92000000-0000-0000-0000-{number:012d}")


EVENT, SESSION, ACTOR = eid(1), eid(2), eid(3)


def phrase_list(phrases: tuple[str, ...] = ("silver lantern",)) -> EditorialPhraseList:
    return EditorialPhraseList(
        eid(4), EVENT, "highlights", 1, "Synthetic phrases", phrases, ACTOR, NOW,
    )


def segment(text: str, *, number: int = 100) -> EditorialTranscriptSegment:
    return EditorialTranscriptSegment(eid(number), tuple(
        EditorialTranscriptWord(eid(number + i + 1), word, i * 1_000_000, (i + 1) * 1_000_000)
        for i, word in enumerate(text.split())
    ))


class Harness:
    def __init__(self, phrases: tuple[str, ...] = ("silver lantern",)) -> None:
        self.repository = InMemoryEditorialDerivationRepository()
        self.repository.events.add(EVENT)
        self.repository.sessions[SESSION] = EditorialSessionBasis(
            SESSION, EVENT, 1, NOW, NOW + timedelta(seconds=30),
        )
        self.timing = EditorialTimingBasis(eid(7), 1, TimingQualification.UNQUALIFIED, NOW)
        self.input = EditorialDerivationInput(eid(5), eid(6), 1, self.timing)
        self.repository.inputs[SESSION] = (self.input,)
        self.repository.segments[eid(6)] = (segment("Silver lantern glows silver lantern"),)
        self.service = EditorialDerivationService(self.repository, FixedClock(NOW))
        self.phrases = self.service.publish_phrase_list(
            event_id=EVENT, key="highlights", version=1, name="Synthetic phrases", phrases=phrases,
            actor_id=ACTOR, command_id=eid(8),
        )

    def derive(self, command_id: EntityId | None = None) -> EditorialDerivationRun:
        return self.service.derive_candidates(
            session_id=SESSION, phrase_list_id=self.phrases.id, version=1,
            actor_id=ACTOR, command_id=command_id or EntityId.new(),
        )


def test_phrase_normalization_bounds_and_recursive_immutability() -> None:
    phrases = ["  ＳＩＬＶＥＲ\tLantern  ", "Straße"]
    result = phrase_list(cast(tuple[str, ...], phrases))
    phrases.append("changed")
    assert result.phrases == ("ＳＩＬＶＥＲ\tLantern", "Straße")
    with pytest.raises(FrozenInstanceError):
        result.name = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="duplicate normalized"):
        phrase_list((" ＳＩＬＶＥＲ\tLantern ", "silver lantern"))
    with pytest.raises(ValueError, match="duplicate normalized"):
        phrase_list(("Straße", "STRASSE"))
    assert len(phrase_list(tuple(str(i) for i in range(200))).phrases) == 200
    assert phrase_list(("x" * 100,)).phrases == ("x" * 100,)


@pytest.mark.parametrize(("phrases", "reason"), [
    (("a, b", "a b"), "duplicate normalized"),
    (("!",), "at least one word token"),
])
def test_phrase_publish_rejects_duplicate_token_sequences_and_empty_tokens(
    phrases: tuple[str, ...], reason: str,
) -> None:
    h = Harness()
    with pytest.raises(ValueError, match=reason):
        h.service.publish_phrase_list(
            event_id=EVENT, key="invalid", version=1, name="Synthetic invalid phrases",
            phrases=phrases, actor_id=ACTOR, command_id=eid(90),
        )
    assert h.service.versions(EVENT, "invalid") == ()
    assert eid(90) not in h.repository.commands


def test_declared_candidate_requires_operation_and_rejects_derived_provenance() -> None:
    h = Harness()
    run = h.derive()
    candidate = h.repository.candidates[run.candidate_ids[0]]
    provenance = candidate.provenance
    assert provenance is not None
    declared = replace(
        candidate, origin="declared", epistemic_kind="declared",
        source_kind="producer_declaration", reason_code="human_mark_moment",
        operation_id=eid(91), provenance=None,
    )
    with pytest.raises(ValueError, match="declared candidate requires a human command only"):
        replace(declared, operation_id=None)
    with pytest.raises(ValueError, match="declared candidate requires a human command only"):
        replace(declared, provenance=provenance)


@pytest.mark.parametrize("phrases", [(), (" ",), ("x" * 101,), tuple(str(i) for i in range(201))])
def test_phrase_list_rejects_out_of_bounds(phrases: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        phrase_list(phrases)


def test_matching_unicode_tokens_occurrences_overlaps_and_segment_boundaries() -> None:
    phrases = phrase_list(("silver lantern", "STRASSE", "go go", "lantern", "café", "猫 42"))
    words = segment("ＳＩＬＶＥＲ, lantern Straße go go go go CAFÉ 猫_42 silver-lantern")
    matches = tuple(match_phrases(phrases, words))
    assert [m.normalized_phrase for m in matches] == [
        "silver lantern", "silver lantern", "strasse", "go go", "go go",
        "lantern", "lantern", "café", "猫 42",
    ]
    assert [m.first_word.asset_start_microseconds for m in matches
            if m.normalized_phrase == "go go"] == [3_000_000, 5_000_000]
    assert tuple(match_phrases(phrase_list(), segment("silver"))) == ()
    assert tuple(match_phrases(phrase_list(), segment("lantern"))) == ()
    assert tuple(match_phrases(phrase_list(("silver",)), segment("silvery"))) == ()
    assert tuple(match_phrases(phrase_list(), EditorialTranscriptSegment(eid(100), ()))) == ()


@pytest.mark.parametrize(("offset", "end", "reason"), [
    (0, 2, None), (1, 2, "partially_excluded_by_session_boundary"),
    (3, 2, "excluded_by_session_boundary"), (2, 2, "partially_excluded_by_session_boundary"),
    (0, None, None),
])
def test_placement_uses_exact_microseconds_and_declared_end_conflicts(
    offset: int, end: int | None, reason: str | None,
) -> None:
    session = EditorialSessionBasis(
        SESSION, EVENT, 1, NOW, None if end is None else NOW + timedelta(seconds=end),
    )
    timing = EditorialTimingBasis(eid(7), 1, TimingQualification.EXPIRED,
                                  NOW + timedelta(seconds=offset))
    match = next(match_phrases(phrase_list(), segment("silver lantern")))
    location = place_match(match, timing, session)
    assert location is not None
    assert location.timeline_start_microseconds == offset * 1_000_000
    assert location.timeline_end_microseconds == (offset + 2) * 1_000_000
    assert location_conflict_reason(location, NOW, session.authoritative_end) == reason
    fine = place_match(match, replace(timing, candidate_started_at=NOW + timedelta(microseconds=1)),
                       session)
    assert fine is not None and fine.timeline_start_microseconds == 1
    assert place_match(match, replace(timing, candidate_started_at=NOW - timedelta(microseconds=1)),
                       session) is None


def test_service_replay_input_identity_changed_inputs_and_provenance() -> None:
    h = Harness()
    original = h.derive(eid(10))
    assert len(original.candidate_ids) == 2
    assert h.derive(eid(10)) == h.derive(eid(11)) == original
    assert len(h.repository.candidates) == 2
    candidate = h.repository.candidates[original.candidate_ids[0]]
    assert candidate.origin == EditorialCandidateOrigin.DERIVED
    assert candidate.operation_id is None
    assert candidate.provenance is not None
    assert candidate.provenance.normalized_phrase == "silver lantern"
    assert candidate.provenance.transcript_evidence_id == eid(6)
    assert candidate.provenance.timing_evidence_id == eid(7)
    assert candidate.provenance.timing_qualification == TimingQualification.UNQUALIFIED
    assert candidate.review_state.value == "unreviewed"
    with pytest.raises(ValueError):
        replace(candidate, operation_id=eid(10))
    with pytest.raises(ValueError):
        replace(candidate, provenance=None)
    with pytest.raises(EditorialMomentConflictError):
        h.service.derive_candidates(session_id=SESSION, phrase_list_id=h.phrases.id, version=2,
                                    actor_id=ACTOR, command_id=eid(10))
    h.repository.inputs[SESSION] = (replace(h.input, timing=replace(h.timing, evidence_id=eid(12),
                                                                  revision=2)),)
    changed = h.derive()
    assert changed.id != original.id
    # Exact command replay remains the old immutable result even after new evidence.
    assert h.derive(eid(11)) == original
    h.repository.inputs[SESSION] = (replace(h.input, transcript_evidence_id=eid(13),
                                           transcript_revision=2),)
    h.repository.segments[eid(13)] = h.repository.segments[eid(6)]
    assert h.derive().id not in (original.id, changed.id)
    h.repository.inputs[SESSION] = ()
    assert h.derive().candidate_ids == ()


def test_phrase_publish_replay_versions_event_scope_and_human_authority() -> None:
    h = Harness()
    assert h.service.publish_phrase_list(
        event_id=EVENT, key="highlights", version=1, name="Synthetic phrases",
        phrases=("silver lantern",), actor_id=ACTOR, command_id=eid(8),
    ) == h.phrases
    next_version = h.service.publish_phrase_list(
        event_id=EVENT, key="highlights", version=2, name="Second",
        phrases=("lantern",), actor_id=ACTOR, command_id=eid(20),
    )
    assert next_version.id == h.phrases.id
    assert h.service.versions(EVENT, "highlights", after=1) == (next_version,)
    with pytest.raises(EditorialMomentConflictError, match="operation_id_conflict"):
        h.service.publish_phrase_list(
            event_id=EVENT, key="highlights", version=2, name="Changed",
            phrases=("lantern",), actor_id=ACTOR, command_id=eid(8),
        )
    with pytest.raises(EditorialMomentConflictError, match="version_exists"):
        h.service.publish_phrase_list(
            event_id=EVENT, key="highlights", version=1, name="Changed",
            phrases=("lantern",), actor_id=ACTOR, command_id=eid(21),
        )
    for authority in ("automatic", "model"):
        with pytest.raises(ValueError, match="human authority"):
            h.service.derive_candidates(session_id=SESSION, phrase_list_id=h.phrases.id, version=1,
                                       actor_id=ACTOR, command_id=EntityId.new(),
                                       authority_kind=authority)
        with pytest.raises(ValueError, match="human authority"):
            h.service.publish_phrase_list(event_id=EVENT, key="another", version=1, name="Test",
                                          phrases=("lantern",), actor_id=ACTOR,
                                          command_id=EntityId.new(), authority_kind=authority)
    h.repository.sessions[SESSION] = replace(h.repository.sessions[SESSION], event_id=eid(99))
    with pytest.raises(EditorialMomentConflictError, match="event_mismatch"):
        h.derive()


def test_skip_counts_candidate_bound_and_deterministic_selection() -> None:
    h = Harness(("lantern",))
    h.repository.segments[eid(6)] = (segment(" ".join(["lantern"] * 503)),)
    h.repository.inputs[SESSION] = (
        replace(h.input, asset_id=eid(30), transcript_evidence_id=None, transcript_revision=None),
        replace(h.input, asset_id=eid(31), timing=None), h.input,
    )
    run = h.derive()
    assert run.skips == EditorialSkipCounts(no_transcript=1, no_timing_evidence=1, limit_reached=3)
    assert len(run.candidate_ids) == 500
    assert h.repository.candidates[run.candidate_ids[-1]].timeline_start_microseconds == 499_000_000
    assert h.repository.candidates[run.candidate_ids[-1]].location_conflict is True
    assert tuple(i.asset_id for i in run.inputs) == (eid(5), eid(30), eid(31))
    h.repository.inputs[SESSION] = (replace(h.input, timing=replace(
        h.timing, evidence_id=eid(40), candidate_started_at=NOW - timedelta(seconds=1))),)
    assert h.derive().skips == EditorialSkipCounts(outside_session=1, limit_reached=2)
    h.repository.sessions[SESSION] = replace(
        h.repository.sessions[SESSION], authoritative_start=None,
    )
    h.repository.inputs[SESSION] = (replace(h.input, asset_id=eid(41)),)
    assert h.derive().skips == EditorialSkipCounts(no_session_start=1)


def test_transaction_failure_rolls_back_run_candidates_and_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = Harness()
    original = h.repository.record_command

    def fail(command_id: EntityId, digest: str,
             result: EditorialPhraseList | EditorialDerivationRun) -> None:
        original(command_id, digest, result)
        raise RuntimeError("synthetic storage failure")

    monkeypatch.setattr(h.repository, "record_command", fail)
    with pytest.raises(RuntimeError, match="synthetic"):
        h.derive(eid(50))
    assert not h.repository.runs and not h.repository.candidates
    assert eid(50) not in h.repository.commands


def test_concurrent_runs_create_one_input_result() -> None:
    h = Harness()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = tuple(pool.map(h.derive, (eid(60), eid(60), eid(61), eid(62))))
    assert all(run == results[0] for run in results)
    assert len(h.repository.candidates) == 2


@pytest.mark.parametrize("action", tuple(EditorialMomentReviewAction))
def test_derived_candidates_use_unchanged_review_actions_and_clip_creation(
    action: EditorialMomentReviewAction,
) -> None:
    h = Harness()
    run = h.derive()
    candidate = h.repository.candidates[run.candidate_ids[0]]
    repository = MemoryEditorialReviewRepository((candidate,), event_id=EVENT)
    service = EditorialMomentService(repository, FixedClock(NOW))
    kwargs: dict[str, Any] = {}
    if action == EditorialMomentReviewAction.REVISE_RANGE:
        kwargs = {
            "adjusted_timeline_start_microseconds": 1, "adjusted_timeline_end_microseconds": 2,
        }
    result = service.review_moment(
        operation_id=eid(70), candidate_moment_id=candidate.id, expected_candidate_revision=1,
        actor_id=ACTOR, action=action, reason="Synthetic human review", **kwargs,
    )
    assert result.decision.review_state == action.projected_state
    assert (result.clip is not None) == (
        action == EditorialMomentReviewAction.APPROVE_AND_CREATE_CLIP
    )
    if result.clip is not None:
        assert result.clip.candidate_moment_id == candidate.id
        assert result.clip.approved_range.timeline_end_microseconds == 2_000_000
    queue = service.list_review_queue(EVENT)
    assert queue.items[0].candidate.provenance == candidate.provenance
    assert queue.items[0].candidate.origin == EditorialCandidateOrigin.DERIVED


def test_api_authentication_bounds_idempotency_and_additive_reads() -> None:
    h = Harness()
    candidates = h.derive().candidate_ids
    review_repository = MemoryEditorialReviewRepository(
        tuple(h.repository.candidates[i] for i in candidates), event_id=EVENT,
    )
    kernel_repository = InMemoryEventModeKernelRepository()
    kernel = DurableEventModeKernel(repository=kernel_repository, clock=FixedClock(NOW))
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.state.kernel = KernelComponents(
        configuration=cast(EffectiveKernelConfiguration, SimpleNamespace()),
        repository=kernel_repository, kernel=kernel,
        editorial_moments=EditorialMomentService(review_repository, FixedClock(NOW)),
        editorial_derivation=h.service,
    )
    client = cast(SyncHttpClient, TestClient(app))
    publish_url = f"/api/v1/editorial/events/{EVENT.value}/phrase-lists"
    derive_url = f"/api/v1/editorial/sessions/{SESSION.value}/derivations"
    publish = {"command_id": eid(80).value, "actor_id": ACTOR.value, "confirmed": "confirmed",
               "key": "highlights", "version": 2, "name": "Synthetic", "phrases": ["lantern"]}
    derive = {"command_id": eid(81).value, "actor_id": ACTOR.value, "confirmed": "confirmed",
              "phrase_list_id": h.phrases.id.value, "version": 1}
    assert client.post(publish_url, json=publish).status_code == 401
    assert client.post(derive_url, json=derive).status_code == 401
    assert client.get(publish_url + "?key=highlights").status_code == 401
    assert client.post(publish_url, headers=AUTH_HEADERS, json=publish).status_code == 200
    assert client.post(derive_url, headers=AUTH_HEADERS, json=derive).status_code == 200
    page = client.get(publish_url + "?key=highlights&limit=1", headers=AUTH_HEADERS).json()
    assert page["items_truncated"] is True and page["next_after"] == 1
    assert client.get(
        publish_url + "?key=highlights&limit=101", headers=AUTH_HEADERS,
    ).status_code == 422
    invalid_commands: tuple[dict[str, object], ...] = (
        {"phrases": []}, {"phrases": ["x" * 101]}, {"phrases": ["x"] * 201},
        {"confirmed": "automatic"}, {"path": "synthetic-path"},
    )
    for invalid in invalid_commands:
        assert client.post(publish_url, headers=AUTH_HEADERS,
                           json={**publish, **invalid}).status_code == 422
    assert client.post(derive_url, headers=AUTH_HEADERS,
                       json={**derive, "confirmed": "automatic"}).status_code == 422
    padded = client.post(publish_url, headers=AUTH_HEADERS, json={
        **publish, "command_id": eid(82).value, "version": 3, "phrases": ["  " + "x" * 100 + "  "],
    })
    assert padded.status_code == 200 and padded.json()["phrases"] == ["x" * 100]
    queue = client.get(f"/api/v1/editorial/events/{EVENT.value}/review-queue", headers=AUTH_HEADERS)
    assert queue.status_code == 200
    candidate = queue.json()["items"][0]["candidate"]
    assert candidate["origin"] == "derived" and candidate["operation_id"] is None
    assert candidate["provenance"]["timing_qualification"] == "unqualified"
    assert "path" not in candidate and "transcript_text" not in candidate
    response = EditorialDerivationRunResponse.model_validate(
        client.post(derive_url, headers=AUTH_HEADERS, json=derive).json(),
    )
    with pytest.raises(TypeError):
        response.skip_counts["no_transcript"] = 3  # type: ignore[index]


def test_new_timestamp_and_provenance_contracts_reject_invalid_values() -> None:
    h = Harness()
    run = h.derive()
    candidate = h.repository.candidates[run.candidate_ids[0]]
    assert isinstance(candidate.provenance, EditorialCandidateProvenance)
    for value, field in ((h.phrases, "created_at"), (run, "created_at"),
                         (h.timing, "candidate_started_at")):
        with pytest.raises(ValueError, match="timezone-aware"):
            replace(value, **{field: datetime(2026, 9, 26)})
    with pytest.raises(ValueError):
        replace(candidate.provenance, transcript_revision=0)
    with pytest.raises(ValueError):
        replace(candidate.provenance, normalized_phrase="SILVER LANTERN")
    with pytest.raises(FrozenInstanceError):
        candidate.provenance.asset_id = eid(1000)  # type: ignore[misc]
