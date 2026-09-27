from datetime import UTC

from app.shared.human_commands import human_command_digest
from app.shared.ids import EntityId
from app.shared.time import Clock

from .contracts import (
    EditorialCandidateMoment,
    EditorialCandidateOrigin,
    EditorialCandidateSourceKind,
)
from .derivation import location_conflict_reason, match_phrases, place_match
from .derivation_contracts import (
    EditorialCandidateProvenance,
    EditorialDerivationInput,
    EditorialDerivationRun,
    EditorialPhraseList,
    EditorialSkipCounts,
)
from .derivation_repository import EditorialDerivationRepository
from .repository import EditorialMomentConflictError


def input_identity(item: EditorialDerivationInput) -> dict[str, object]:
    return {
        "asset_id": item.asset_id.value,
        "transcript_evidence_id": (None if item.transcript_evidence_id is None
                                   else item.transcript_evidence_id.value),
        "timing_evidence_id": (None if item.timing is None
                               else item.timing.evidence_id.value),
        "timing_revision": None if item.timing is None else item.timing.revision,
    }


class EditorialDerivationService:
    def __init__(self, repository: EditorialDerivationRepository, clock: Clock) -> None:
        self.repository = repository
        self.clock = clock

    def publish_phrase_list(
        self, *, event_id: EntityId, key: str, version: int, name: str,
        phrases: tuple[str, ...], actor_id: EntityId, command_id: EntityId,
        authority_kind: str = "human",
    ) -> EditorialPhraseList:
        self._human(authority_kind)
        phrase_list = EditorialPhraseList(
            EntityId.new(), event_id, key, version, name, phrases, actor_id,
            self.clock.now().astimezone(UTC),
        )
        digest = human_command_digest({
            "kind": "editorial_phrase_list", "event_id": event_id.value,
            "key": phrase_list.key, "version": version, "name": phrase_list.name,
            "phrases": list(phrase_list.phrases), "actor_id": actor_id.value,
        })
        with self.repository.transaction() as transaction:
            replay = transaction.replay(command_id, digest)
            if replay is not None:
                assert isinstance(replay, EditorialPhraseList)
                return replay
            result = transaction.publish(phrase_list)
            transaction.record_command(command_id, digest, result)
            return result

    def versions(
        self, event_id: EntityId, key: str, *, after: int = 0, limit: int = 100,
    ) -> tuple[EditorialPhraseList, ...]:
        if after < 0 or not 1 <= limit <= 101:
            raise ValueError("invalid phrase-list page bounds")
        with self.repository.transaction() as transaction:
            return transaction.versions(event_id, key.strip(), after, limit)

    def derive_candidates(
        self, *, session_id: EntityId, phrase_list_id: EntityId, version: int,
        actor_id: EntityId, command_id: EntityId, authority_kind: str = "human",
    ) -> EditorialDerivationRun:
        self._human(authority_kind)
        if version < 1:
            raise ValueError("version must be positive")
        digest = human_command_digest({
            "kind": "editorial_derivation", "session_id": session_id.value,
            "phrase_list_id": phrase_list_id.value, "version": version,
            "actor_id": actor_id.value,
        })
        with self.repository.transaction() as transaction:
            replay = transaction.replay(command_id, digest)
            if replay is not None:
                assert isinstance(replay, EditorialDerivationRun)
                return replay
            session = transaction.session_basis(session_id)
            phrases = transaction.phrase_list(phrase_list_id, version)
            if phrases.event_id != session.event_id:
                raise EditorialMomentConflictError("phrase_list_event_mismatch")
            inputs = transaction.associated_inputs(session_id)
            input_digest = human_command_digest({
                "session_id": session_id.value, "phrase_list_id": phrase_list_id.value,
                "version": version, "inputs": [input_identity(item) for item in inputs],
            })
            existing = transaction.find_run(input_digest)
            if existing is not None:
                transaction.record_command(command_id, digest, existing)
                return existing
            run_id, now = EntityId.new(), self.clock.now().astimezone(UTC)
            candidates: list[EditorialCandidateMoment] = []
            skips = dict.fromkeys(EditorialSkipCounts.__dataclass_fields__, 0)
            for item in inputs:
                if item.transcript_evidence_id is None:
                    skips["no_transcript"] += 1
                    continue
                if item.timing is None:
                    skips["no_timing_evidence"] += 1
                    continue
                if session.authoritative_start is None:
                    skips["no_session_start"] += 1
                    continue
                assert item.transcript_revision is not None
                for segment in transaction.transcript_segments(item.transcript_evidence_id):
                    for match in match_phrases(phrases, segment):
                        location = place_match(match, item.timing, session)
                        if location is None:
                            skips["outside_session"] += 1
                            continue
                        if len(candidates) == 500:
                            skips["limit_reached"] += 1
                            continue
                        provenance = EditorialCandidateProvenance(
                            run_id, phrases.id, version, match.normalized_phrase,
                            item.asset_id, item.transcript_evidence_id,
                            item.transcript_revision, segment.id, match.first_word.id,
                            match.last_word.id, match.first_word.asset_start_microseconds,
                            match.last_word.asset_end_microseconds, item.timing.evidence_id,
                            item.timing.revision, item.timing.qualification,
                        )
                        candidates.append(EditorialCandidateMoment(
                            id=EntityId.new(), session_id=session_id,
                            expected_session_revision=session.revision,
                            timeline_start_microseconds=location.timeline_start_microseconds,
                            timeline_end_microseconds=location.timeline_end_microseconds,
                            session_authoritative_start=session.authoritative_start,
                            session_authoritative_end=session.authoritative_end,
                            actor_id=actor_id, operation_id=None, note=None, declared_at=now,
                            origin=EditorialCandidateOrigin.DERIVED,
                            epistemic_kind=EditorialCandidateOrigin.DERIVED,
                            reason_code="transcript_phrase_match",
                            source_kind=EditorialCandidateSourceKind.TRANSCRIPT_PHRASE_MATCH,
                            provenance=provenance,
                            location_conflict_reason=location_conflict_reason(
                                location, session.authoritative_start, session.authoritative_end,
                            ),
                        ))
            run = EditorialDerivationRun(
                run_id, session_id, phrases.id, version, inputs, input_digest, actor_id,
                now, tuple(candidate.id for candidate in candidates), EditorialSkipCounts(**skips),
            )
            transaction.save_run(run, tuple(candidates))
            transaction.record_command(command_id, digest, run)
            return run

    @staticmethod
    def _human(authority_kind: str) -> None:
        if authority_kind != "human":
            raise ValueError("Editorial derivation commands require human authority")
