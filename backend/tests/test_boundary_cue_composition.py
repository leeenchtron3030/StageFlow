from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from unittest.mock import patch

import pytest

from app.contexts.editorial.derivation_contracts import EditorialPhraseList
from app.contexts.editorial.derivation_service import EditorialDerivationService
from app.contexts.production.session_suggestions.contracts import (
    Reference,
    SuggestionConflictError,
    SuggestionNotFoundError,
)
from app.contexts.production.session_suggestions.cue_catalog import (
    BOUNDARY_CUE_CATALOG as CATALOG,
)
from app.contexts.production.session_suggestions.cue_catalog import CueRole
from app.contexts.production.session_suggestions.cue_composition import (
    BoundaryCueComposition,
    CompositionRequest,
    CueListSizeError,
    CustomPhrase,
    PhraseChoice,
    compose,
)
from app.contexts.production.session_suggestions.cue_service import BoundaryCueService
from app.shared.ids import EntityId
from tests.test_derived_editorial_candidates import segment
from tests.test_durable_event_mode_kernel import ACTOR_ID
from tests.test_session_suggestion_policy import NOW, asset
from tests.test_session_suggestions import Harness

CONFERENCE = CompositionRequest(1, CATALOG.profiles[0].group_keys, "conference")


def publish(h: Harness, request: CompositionRequest = CONFERENCE,
            command: EntityId | None = None) -> BoundaryCueComposition:
    return BoundaryCueService(h.repository, h.service.clock).publish(
        event_id=h.event, actor_id=ACTOR_ID, command_id=command or EntityId.new(), request=request)


def test_defaults_choices_custom_union_dedupe_and_order() -> None:
    result = compose(CONFERENCE)
    assert result.start[:2] == ("please join me in welcoming", "please welcome")
    assert "ladies and gentlemen" not in result.start
    assert "welcome to" not in result.start and "any questions" not in result.end
    assert "thank you so much" in result.start and "thank you so much" in result.end
    request = replace(CONFERENCE, group_keys=CONFERENCE.group_keys[::-1] + ("interviews",),
                      include=(PhraseChoice("conference.mc-handoffs", "ladies and gentlemen"),),
                      exclude=(PhraseChoice("conference.mc-handoffs", "please welcome"),),
                      custom_phrases=(CustomPhrase("GOOD MORNING!", CueRole.END),
                                      CustomPhrase("A synthetic farewell", CueRole.END)))
    result = compose(request)
    assert result.start.count("thanks for having me") == 1
    assert "ladies and gentlemen" in result.start and "ladies and gentlemen" in result.end
    assert "please welcome" not in result.start
    assert "good morning" in result.start and "good morning" in result.end
    assert "GOOD MORNING!" not in result.end
    assert result.end[-1] == "A synthetic farewell"
    assert result == compose(replace(request, group_keys=request.group_keys[::-1]))
    # Profile is provenance, not an implicit addition of its groups.
    assert compose(replace(CONFERENCE, group_keys=("press",))).groups[0].key == "press"


def test_studio_profile_defaults_publish_setup_wraps_and_store_takes() -> None:
    h = Harness()
    profile = next(p for p in CATALOG.profiles if p.key == "studio")
    value = publish(h, CompositionRequest(1, profile.group_keys, profile.key))
    start = h.repository.editorial.phrase_list(
        value.start_cue_list.id, value.start_cue_list.revision)
    end = h.repository.editorial.phrase_list(
        value.end_cue_list.id, value.end_cue_list.revision)
    assert start.phrases == ("picture's up",)
    assert end.phrases == ("moving on", "that's a wrap", "that's lunch", "we're wrapped")
    assert tuple(g.key for g in value.groups) == (
        "studio.setups", "studio.takes", "studio.wraps")
    takes = next(g for g in CATALOG.groups if g.key == "studio.takes")
    assert tuple(p.text for p in value.segment_phrases) == tuple(p.text for p in takes.phrases)
    assert len(value.segment_phrases) == 92
    assert {p.source_group for p in value.segment_phrases} == {"studio.takes"}
    assert all(p.text not in start.phrases + end.phrases for p in value.segment_phrases)
    assert BoundaryCueService(h.repository, h.service.clock).current(h.event) == value


def test_exclusion_is_local_to_source_group() -> None:
    request = CompositionRequest(1, ("conference.breaks", "broadcast"),
                                 exclude=(PhraseChoice("conference.breaks", "welcome back"),))
    assert compose(request).start.count("welcome back") == 1
    removed = compose(replace(request, exclude=request.exclude + (
        PhraseChoice("broadcast", "welcome back"),)))
    assert "welcome back" not in removed.start + removed.end


def test_segments_are_stored_with_sources_and_never_published() -> None:
    result = compose(replace(CONFERENCE, group_keys=("panels", "studio.takes", "studio.wraps")))
    assert len(result.segments) == 94
    assert all(p.text not in result.start + result.end for p in result.segments)
    assert {p.source_group for p in result.segments} == {"panels", "studio.takes"}
    with pytest.raises(ValueError, match="custom_segment_refused"):
        CustomPhrase("synthetic segment", CueRole.SEGMENT)


def test_segment_and_explicit_boundary_role_union_retains_first_literal_and_order() -> None:
    request = CompositionRequest(1, ("panels", "studio.takes", "studio.wraps"),
                                 custom_phrases=(CustomPhrase("ACTION!", CueRole.END),))
    result = compose(request)
    assert "action" in result.end and "ACTION!" not in result.end
    assert "action" not in result.start
    assert result.end.index("action") < result.end.index("that's a wrap")
    assert any(s.text == "action" and s.source_group == "studio.takes" for s in result.segments)


@pytest.mark.parametrize("composition_request, reason", [
    (replace(CONFERENCE, catalog_version=2), "unknown_catalog_version"),
    (replace(CONFERENCE, profile_key="unknown"), "unknown_profile"),
    (replace(CONFERENCE, group_keys=("unknown",)), "unknown_group"),
    (replace(CONFERENCE, include=(PhraseChoice("unknown", "unknown"),)), "unknown_choice_group"),
    (replace(CONFERENCE, include=(PhraseChoice("press", "last question"),)),
     "unknown_choice_group"),
    (replace(CONFERENCE, include=(PhraseChoice("conference.mc-handoffs", "unknown"),)),
     "unknown_phrase_choice"),
    (replace(CONFERENCE, include=(PhraseChoice("conference.mc-handoffs", "please welcome"),)),
     "choice_default_mismatch"),
    (replace(CONFERENCE, exclude=(PhraseChoice("conference.mc-handoffs", "ladies and gentlemen"),)),
     "choice_default_mismatch"),
])
def test_invalid_choices_are_refused(composition_request: CompositionRequest, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        compose(composition_request)


@pytest.mark.parametrize("count", [0, 200, 201])
def test_list_size_is_counted_after_merge_and_never_truncated(count: int) -> None:
    request = CompositionRequest(1, (), custom_phrases=tuple(
        CustomPhrase(f"Synthetic cue {n}", CueRole.CHANGEOVER) for n in range(count)))
    if count == 200:
        result = compose(request)
        assert len(result.start) == len(result.end) == 200
        assert compose(replace(request, custom_phrases=request.custom_phrases + (
            CustomPhrase("SYNTHETIC CUE 0!", CueRole.START),))) == result
    else:
        with pytest.raises(CueListSizeError) as caught:
            compose(request)
        assert caught.value.count == count
        assert caught.value.code == ("cue_list_empty" if count == 0 else "cue_list_too_large")
    with pytest.raises(CueListSizeError) as caught:
        compose(CompositionRequest(1, (), custom_phrases=(CustomPhrase("start", CueRole.START),)))
    assert caught.value.role == "end" and caught.value.count == 0


def test_publication_replay_conflict_history_provenance_and_no_authority() -> None:
    h, command = Harness(), EntityId.new()
    svc = BoundaryCueService(h.repository, h.service.clock)
    assert svc.current(h.event) is None
    request = replace(CONFERENCE, group_keys=CONFERENCE.group_keys + ("panels",),
                      custom_phrases=(CustomPhrase("Synthetic greeting", CueRole.START),))
    first = publish(h, request, command)
    second = publish(h, request)
    assert first.version == 1 and second.version == 2
    assert first.start_cue_list.id == second.start_cue_list.id
    assert first.start_cue_list.revision == 1 and second.start_cue_list.revision == 2
    assert first.catalog_digest == CATALOG.digest and first.composed_by == ACTOR_ID
    assert first.composed_at == h.service.clock.now() and first.segment_phrases
    assert svc.current(h.event) == second
    assert publish(h, request, command) == first
    assert svc.history(h.event, limit=1) == ((first,), 1)
    assert svc.history(h.event, after=1) == ((second,), None)
    assert not h.kernel_repo.list_sessions_for_stage(h.stage)
    with pytest.raises(SuggestionConflictError, match="command_id_conflict"):
        publish(h, CONFERENCE, command)
    with pytest.raises(FrozenInstanceError):
        first.groups[0].version = 2  # type: ignore[misc]
    with pytest.raises(SuggestionNotFoundError):
        svc.current(EntityId.new())
    with pytest.raises(ValueError):
        svc.publish(event_id=h.event, actor_id=ACTOR_ID, command_id=EntityId.new(),
                    request=CONFERENCE, authority_kind="automatic")


@pytest.mark.parametrize("failure", ["second_list", "composition"])
def test_atomic_publication_rolls_back_every_insert(failure: str) -> None:
    h = Harness()
    original = h.repository.publish_cue_list
    calls = 0

    def fail_second(value: EditorialPhraseList) -> EditorialPhraseList:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected failure")
        return original(value)

    target = "publish_cue_list" if failure == "second_list" else "save_composition"
    effect = fail_second if failure == "second_list" else RuntimeError("injected failure")
    with patch.object(h.repository, target, side_effect=effect):
        with pytest.raises(RuntimeError, match="injected failure"):
            publish(h)
    assert not h.repository.compositions and not h.repository.editorial.phrases
    assert publish(h).version == 1


def test_concurrent_commands_have_contiguous_versions_and_replay() -> None:
    h, command = Harness(), EntityId.new()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(publish, h, command=command) for _ in range(4)]
        values = tuple(f.result() for f in futures)
    assert all(v == values[0] for v in values)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(publish, h) for _ in range(4)]
        values = tuple(f.result() for f in futures)
    assert sorted(v.version for v in values) == [2, 3, 4, 5]


def test_run_defaults_explicit_lists_no_mixing_and_input_digest() -> None:
    h = Harness()
    transcript = EntityId.new()
    h.repository.editorial.segments[transcript] = (segment("Please welcome"),)
    h.repository.assets[h.stage] = (
        replace(asset(0, 1800), transcript=Reference(transcript, 1)),)
    uncued = h.run()
    assert uncued.start_cue_list is None and uncued.end_cue_list is None
    assert not uncued.assets[0].start_cues and not uncued.assets[0].end_cues
    first = publish(h)
    default = h.run()
    assert default.start_cue_list == first.start_cue_list
    assert default.end_cue_list == first.end_cue_list
    assert default.assets[0].start_cues == default.assets[0].end_cues == (NOW,)
    assert not h.repository.editorial.candidates
    assert default.input_digest != uncued.input_digest
    for named in ("start_cue_list", "end_cue_list"):
        reference = getattr(first, named)
        run = h.service.run(event_id=h.event, stage_id=h.stage, actor_id=ACTOR_ID,
                            **{named: reference})
        assert getattr(run, named) == reference
        other = "end_cue_list" if named == "start_cue_list" else "start_cue_list"
        assert getattr(run, other) is None
    second = publish(h)
    changed = h.run()
    assert changed.start_cue_list == second.start_cue_list
    assert changed.input_digest != default.input_digest


@pytest.mark.parametrize("key", ["boundary-cues-start", "boundary-cues-end"])
def test_manual_reserved_keys_refused_and_ordinary_publication_unchanged(key: str) -> None:
    h = Harness()
    h.repository.editorial.events.add(h.event)
    svc = EditorialDerivationService(h.repository.editorial, h.service.clock)
    with pytest.raises(ValueError, match="reserved_boundary_cue_list_key"):
        svc.publish_phrase_list(event_id=h.event, key=f" {key} ", version=1, name="Manual",
                                phrases=("synthetic",), actor_id=ACTOR_ID,
                                command_id=EntityId.new())
    command = EntityId.new()
    first = svc.publish_phrase_list(event_id=h.event, key="ordinary", version=1, name="Ordinary",
                                    phrases=("synthetic",), actor_id=ACTOR_ID, command_id=command)
    assert svc.publish_phrase_list(event_id=h.event, key="ordinary", version=1, name="Ordinary",
                                   phrases=("synthetic",), actor_id=ACTOR_ID,
                                   command_id=command) == first
