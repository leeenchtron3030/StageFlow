"""Non-durable test double; never a runtime fallback for PostgreSQL."""
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import replace
from threading import RLock

from app.shared.ids import EntityId

from .contracts import EditorialCandidateMoment
from .derivation_contracts import (
    EditorialDerivationInput,
    EditorialDerivationRun,
    EditorialPhraseList,
    EditorialSessionBasis,
    EditorialTranscriptSegment,
)
from .derivation_repository import EditorialDerivationTransaction
from .repository import EditorialMomentConflictError, EditorialMomentNotFoundError


class InMemoryEditorialDerivationRepository:
    def __init__(self) -> None:
        self.events: set[EntityId] = set()
        self.sessions: dict[EntityId, EditorialSessionBasis] = {}
        self.inputs: dict[EntityId, tuple[EditorialDerivationInput, ...]] = {}
        self.segments: dict[EntityId, tuple[EditorialTranscriptSegment, ...]] = {}
        self.phrases: dict[tuple[EntityId, int], EditorialPhraseList] = {}
        self.runs: dict[str, EditorialDerivationRun] = {}
        self.commands: dict[EntityId, tuple[str, EditorialPhraseList | EditorialDerivationRun]] = {}
        self.candidates: dict[EntityId, EditorialCandidateMoment] = {}
        self._lock = RLock()

    @contextmanager
    def transaction(self) -> Generator[EditorialDerivationTransaction]:
        with self._lock:
            snapshot = (self.phrases.copy(), self.runs.copy(), self.commands.copy(),
                        self.candidates.copy())
            try:
                yield self
            except BaseException:
                self.phrases, self.runs, self.commands, self.candidates = snapshot
                raise

    def replay(
        self, command_id: EntityId, digest: str,
    ) -> EditorialPhraseList | EditorialDerivationRun | None:
        replay = self.commands.get(command_id)
        if replay is None:
            return None
        if replay[0] != digest:
            raise EditorialMomentConflictError("human_command_operation_id_conflict")
        return replay[1]

    def record_command(
        self, command_id: EntityId, digest: str,
        result: EditorialPhraseList | EditorialDerivationRun,
    ) -> None:
        self.commands[command_id] = (digest, result)

    def publish(self, phrase_list: EditorialPhraseList) -> EditorialPhraseList:
        if phrase_list.event_id not in self.events:
            raise EditorialMomentNotFoundError("event_not_found")
        for prior in self.phrases.values():
            if prior.event_id == phrase_list.event_id and prior.key == phrase_list.key:
                phrase_list = replace(phrase_list, id=prior.id)
                break
        if (phrase_list.id, phrase_list.version) in self.phrases:
            raise EditorialMomentConflictError("phrase_list_version_exists")
        self.phrases[phrase_list.id, phrase_list.version] = phrase_list
        return phrase_list

    def phrase_list(self, phrase_list_id: EntityId, version: int) -> EditorialPhraseList:
        try:
            return self.phrases[phrase_list_id, version]
        except KeyError as exc:
            raise EditorialMomentNotFoundError("phrase_list_not_found") from exc

    def versions(
        self, event_id: EntityId, key: str, after: int, limit: int,
    ) -> tuple[EditorialPhraseList, ...]:
        return tuple(sorted((p for p in self.phrases.values()
                             if p.event_id == event_id and p.key == key and p.version > after),
                            key=lambda p: p.version))[:limit]

    def session_basis(self, session_id: EntityId) -> EditorialSessionBasis:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise EditorialMomentNotFoundError("session_not_found") from exc

    def associated_inputs(self, session_id: EntityId) -> tuple[EditorialDerivationInput, ...]:
        return tuple(sorted(self.inputs.get(session_id, ()), key=lambda item: item.asset_id.value))

    def transcript_segments(self, evidence_id: EntityId) -> Iterator[EditorialTranscriptSegment]:
        return iter(self.segments.get(evidence_id, ()))

    def find_run(self, input_digest: str) -> EditorialDerivationRun | None:
        return self.runs.get(input_digest)

    def save_run(
        self, run: EditorialDerivationRun, candidates: tuple[EditorialCandidateMoment, ...],
    ) -> None:
        self.runs[run.input_digest] = run
        self.candidates.update((candidate.id, candidate) for candidate in candidates)
