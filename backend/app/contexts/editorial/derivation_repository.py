from collections.abc import Iterator
from contextlib import AbstractContextManager
from typing import Protocol

from app.shared.ids import EntityId

from .contracts import EditorialCandidateMoment
from .derivation_contracts import (
    EditorialDerivationInput,
    EditorialDerivationRun,
    EditorialPhraseList,
    EditorialSessionBasis,
    EditorialTranscriptSegment,
)


class EditorialDerivationReader(Protocol):
    def session_basis(self, session_id: EntityId) -> EditorialSessionBasis: ...

    def associated_inputs(
        self, session_id: EntityId,
    ) -> tuple[EditorialDerivationInput, ...]: ...

    def transcript_segments(
        self, evidence_id: EntityId,
    ) -> Iterator[EditorialTranscriptSegment]: ...


class EditorialDerivationTransaction(EditorialDerivationReader, Protocol):
    def replay(
        self, command_id: EntityId, digest: str,
    ) -> EditorialPhraseList | EditorialDerivationRun | None: ...

    def record_command(
        self, command_id: EntityId, digest: str,
        result: EditorialPhraseList | EditorialDerivationRun,
    ) -> None: ...

    def publish(self, phrase_list: EditorialPhraseList) -> EditorialPhraseList: ...

    def phrase_list(self, phrase_list_id: EntityId, version: int) -> EditorialPhraseList: ...

    def versions(
        self, event_id: EntityId, key: str, after: int, limit: int,
    ) -> tuple[EditorialPhraseList, ...]: ...

    def find_run(self, input_digest: str) -> EditorialDerivationRun | None: ...

    def save_run(
        self, run: EditorialDerivationRun, candidates: tuple[EditorialCandidateMoment, ...],
    ) -> None: ...


class EditorialDerivationRepository(Protocol):
    def transaction(self) -> AbstractContextManager[EditorialDerivationTransaction]: ...
