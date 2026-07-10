from dataclasses import fields
from datetime import UTC, datetime, timedelta
from inspect import getmembers, isfunction

from app.contexts.production.evidence import (
    EvidenceRole,
    EvidenceSignal,
    EvidenceStrength,
)
from app.contexts.production.evidence_builder import (
    EvidenceBuilderContextKey,
    EvidenceBuilderInputClassification,
    EvidenceBuilderInputReport,
    EvidenceBuilderSemanticRule,
    ObservationSemanticSelectionStatus,
    ObservationSemanticSelector,
    deduplicate_observations,
    observation_ordering_key,
    order_observations,
    timeline_order_value,
)
from app.contexts.production.observation import (
    Observation,
    ObservationConfidence,
    ObservationLocation,
    ObservationSource,
    ObservationType,
)
from app.contexts.production.timeline import TimelinePosition, TimelineRange
from app.shared.ids import CorrelationId, EntityId


def _observation(
    observation_type: ObservationType,
    *,
    observation_id: EntityId | None = None,
    observed_at: datetime | None = None,
    location: ObservationLocation | None = None,
    metadata: dict[str, object] | None = None,
) -> Observation:
    return Observation(
        id=observation_id or EntityId.new(),
        recording_block_id=location.recording_block_id if location is not None else None,
        observation_type=observation_type,
        observation_source=ObservationSource.SYSTEM,
        location=location
        or ObservationLocation.at_wall_clock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC)),
        confidence=ObservationConfidence(1.0),
        correlation_id=CorrelationId.new(),
        observed_at=observed_at or datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        metadata=metadata or {},
    )


def test_observation_semantic_selector_creation() -> None:
    selector = ObservationSemanticSelector(
        accepted_observation_types=(ObservationType.RECORDING_ACTIVITY,),
        semantic_keys=("recording_activity", "recording_event_kind"),
    )

    assert selector.accepted_observation_types == (ObservationType.RECORDING_ACTIVITY,)
    assert selector.semantic_keys == ("recording_activity", "recording_event_kind")


def test_prioritized_semantic_key_lookup() -> None:
    selector = ObservationSemanticSelector(
        accepted_observation_types=(ObservationType.RECORDING_ACTIVITY,),
        semantic_keys=("recording_activity", "recording_event_kind"),
    )
    observation = _observation(
        ObservationType.RECORDING_ACTIVITY,
        metadata={
            "recording_activity": " began ",
            "recording_event_kind": "paused",
        },
    )

    selection = selector.select(observation, supported_values={"began", "paused"})

    assert selection.status is ObservationSemanticSelectionStatus.SELECTED
    assert selection.matched_semantic_key == "recording_activity"
    assert selection.normalized_semantic_value == "began"


def test_ignored_observation_type_result() -> None:
    selector = ObservationSemanticSelector(
        accepted_observation_types=(ObservationType.TRANSCRIPT_ACTIVITY,),
        semantic_keys=("transcript_lifecycle",),
    )
    observation = _observation(
        ObservationType.RECORDING_ACTIVITY,
        metadata={"recording_activity": "began"},
    )

    selection = selector.select(observation, supported_values={"segment_available"})

    assert selection.status is ObservationSemanticSelectionStatus.IGNORED_OBSERVATION_TYPE
    assert selection.normalized_semantic_value is None


def test_missing_semantic_value_result() -> None:
    selector = ObservationSemanticSelector(
        accepted_observation_types=(ObservationType.TRANSCRIPT_ACTIVITY,),
        semantic_keys=("transcript_lifecycle",),
    )

    selection = selector.select(
        _observation(ObservationType.TRANSCRIPT_ACTIVITY),
        supported_values={"segment_available"},
    )

    assert selection.status is ObservationSemanticSelectionStatus.MISSING_SEMANTIC_VALUE


def test_unsupported_semantic_value_result() -> None:
    selector = ObservationSemanticSelector(
        accepted_observation_types=(ObservationType.RECORDING_ACTIVITY,),
        semantic_keys=("recording_activity",),
    )

    selection = selector.select(
        _observation(
            ObservationType.RECORDING_ACTIVITY,
            metadata={"recording_activity": "device_reconfigured"},
        ),
        supported_values={"began"},
    )

    assert selection.status is ObservationSemanticSelectionStatus.UNSUPPORTED_SEMANTIC_VALUE
    assert selection.normalized_semantic_value == "device_reconfigured"


def test_deterministic_normalization() -> None:
    selector = ObservationSemanticSelector(
        accepted_observation_types=(ObservationType.TRANSCRIPT_ACTIVITY,),
        semantic_keys=("status",),
    )
    observation = _observation(
        ObservationType.TRANSCRIPT_ACTIVITY,
        metadata={"status": "Transcript Activity-Interrupted"},
    )

    selection = selector.select(observation)

    assert selection.normalized_semantic_value == "transcript_activity_interrupted"


def test_generic_semantic_rule_creation() -> None:
    rule = EvidenceBuilderSemanticRule(
        id=EntityId.new(),
        normalized_semantic_value="began",
        target_signal=EvidenceSignal.RECORDING_CONTINUITY_ESTABLISHED,
    )

    assert rule.evidence_role is EvidenceRole.SUPPORTS
    assert rule.evidence_strength is EvidenceStrength.STRONG
    assert "recording_continuity_established" in rule.rationale()


def test_context_key_equality_and_hashing() -> None:
    first = EvidenceBuilderContextKey.from_components(
        recording_block_id="block-1",
        stage_id="stage-1",
    )
    second = EvidenceBuilderContextKey.from_components(
        recording_block_id="block-1",
        stage_id="stage-1",
    )
    third = EvidenceBuilderContextKey.from_components(
        recording_block_id="block-2",
        stage_id="stage-1",
    )

    assert first == second
    assert hash(first) == hash(second)
    assert first != third
    assert first.as_dict()["recording_block_id"] == "block-1"


def test_input_classification_values() -> None:
    assert {classification.value for classification in EvidenceBuilderInputClassification} == {
        "recognized",
        "ignored",
        "unsupported",
        "missing_semantic_value",
        "duplicate",
        "unknown",
    }


def test_input_report_creation_and_id_only_reporting() -> None:
    selector = ObservationSemanticSelector(
        accepted_observation_types=(ObservationType.RECORDING_ACTIVITY,),
        semantic_keys=("recording_activity",),
    )
    recognized = selector.select(
        _observation(
            ObservationType.RECORDING_ACTIVITY,
            metadata={"recording_activity": "began"},
        ),
        supported_values={"began"},
    )
    ignored = selector.select(_observation(ObservationType.TRANSCRIPT_ACTIVITY))
    unsupported = selector.select(
        _observation(
            ObservationType.RECORDING_ACTIVITY,
            metadata={"recording_activity": "unsupported"},
        ),
        supported_values={"began"},
    )

    report = EvidenceBuilderInputReport.from_selections(
        (recognized, ignored, unsupported),
        applied_rule_ids=(EntityId.new(),),
    )

    assert report.recognized_observation_ids == (recognized.observation_id,)
    assert report.ignored_observation_ids == (ignored.observation_id,)
    assert report.unsupported_observation_ids == (unsupported.observation_id,)
    assert "observations" not in {field.name for field in fields(EvidenceBuilderInputReport)}


def test_deterministic_ordering_with_timeline_offset_fallback() -> None:
    recording_block_id = EntityId.new()
    same_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    later_offset = _observation(
        ObservationType.RECORDING_ACTIVITY,
        observed_at=same_time,
        location=ObservationLocation.at_point(
            TimelinePosition(recording_block_id, timedelta(seconds=20))
        ),
    )
    earlier_offset = _observation(
        ObservationType.RECORDING_ACTIVITY,
        observed_at=same_time,
        location=ObservationLocation.at_point(
            TimelinePosition(recording_block_id, timedelta(seconds=10))
        ),
    )

    ordered = order_observations((later_offset, earlier_offset))

    assert [item.observation.id for item in ordered] == [earlier_offset.id, later_offset.id]
    assert timeline_order_value(earlier_offset) == 10.0


def test_observation_id_and_input_index_fallbacks_are_stable() -> None:
    same_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    first = _observation(ObservationType.RECORDING_ACTIVITY, observed_at=same_time)
    second = _observation(ObservationType.RECORDING_ACTIVITY, observed_at=same_time)

    ordered_once = order_observations((second, first))
    ordered_twice = order_observations((second, first))

    assert [item.observation.id for item in ordered_once] == [
        item.observation.id for item in ordered_twice
    ]
    assert observation_ordering_key(ordered_once[0]) == observation_ordering_key(
        ordered_twice[0]
    )


def test_timeline_range_ordering_uses_range_start() -> None:
    recording_block_id = EntityId.new()
    observation = _observation(
        ObservationType.TRANSCRIPT_ACTIVITY,
        location=ObservationLocation.over_range(
            TimelineRange(
                TimelinePosition(recording_block_id, timedelta(seconds=5)),
                TimelinePosition(recording_block_id, timedelta(seconds=15)),
            )
        ),
    )

    assert timeline_order_value(observation) == 5.0


def test_deterministic_duplicate_handling_and_conflicting_duplicate_report() -> None:
    observation_id = EntityId.new()
    first = _observation(
        ObservationType.RECORDING_ACTIVITY,
        observation_id=observation_id,
        observed_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        metadata={"recording_activity": "began"},
    )
    conflicting_duplicate = _observation(
        ObservationType.RECORDING_ACTIVITY,
        observation_id=observation_id,
        observed_at=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
        metadata={"recording_activity": "paused"},
    )

    result = deduplicate_observations((conflicting_duplicate, first))

    assert result.retained_observations == (first,)
    assert result.duplicate_observation_ids == (observation_id,)
    assert result.duplicate_selections[0].status is ObservationSemanticSelectionStatus.DUPLICATE


def test_generic_mechanics_do_not_mutate_input_or_create_evidence() -> None:
    observation = _observation(
        ObservationType.TRANSCRIPT_ACTIVITY,
        metadata={"transcript_lifecycle": "segment_available"},
    )
    original_metadata = dict(observation.metadata)
    selector = ObservationSemanticSelector(
        accepted_observation_types=(ObservationType.TRANSCRIPT_ACTIVITY,),
        semantic_keys=("transcript_lifecycle",),
    )

    selection = selector.select(observation)
    deduplicate_observations((observation,))

    assert dict(observation.metadata) == original_metadata
    assert not hasattr(selection, "evidence_set")


def test_selector_does_not_know_evidence_concern_or_signal_mapping() -> None:
    selector_fields = {field.name for field in fields(ObservationSemanticSelector)}
    selection_fields = {field.name for field in fields(type(ObservationSemanticSelector(
        accepted_observation_types=(ObservationType.UNKNOWN,),
        semantic_keys=("semantic",),
    ).select(_observation(ObservationType.UNKNOWN))))}

    assert "concern" not in selector_fields
    assert "target_signal" not in selector_fields
    assert "evidence_signal" not in selection_fields


def test_architectural_boundaries_no_runtime_rules_engine_or_infrastructure() -> None:
    names = {
        field.name
        for contract in (
            ObservationSemanticSelector,
            EvidenceBuilderSemanticRule,
            EvidenceBuilderContextKey,
            EvidenceBuilderInputReport,
        )
        for field in fields(contract)
    } | {
        name
        for name, value in getmembers(ObservationSemanticSelector)
        if isfunction(value)
    }
    forbidden_terms = {
        "session_boundary",
        "session_transition",
        "operational_state",
        "transition_evaluation",
        "repository",
        "persist",
        "plugin",
        "json_rule",
        "yaml",
        "ai",
        "api",
        "queue",
        "worker",
        "frontend",
    }

    assert not any(term in name for name in names for term in forbidden_terms)
