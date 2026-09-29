"""Human publication: both lists and their provenance share one transaction."""
from app.contexts.editorial.derivation_contracts import EditorialPhraseList
from app.shared.ids import EntityId
from app.shared.time import Clock

from .contracts import Reference
from .cue_catalog import BOUNDARY_CUE_CATALOG
from .cue_composition import (
    END_KEY,
    START_KEY,
    BoundaryCueComposition,
    CompositionRequest,
    compose,
    request_digest,
)
from .repository import SuggestionRepository


class BoundaryCueService:
    def __init__(self, repository: SuggestionRepository, clock: Clock) -> None:
        self.repository, self.clock = repository, clock

    def publish(self, *, event_id: EntityId, actor_id: EntityId, command_id: EntityId,
                request: CompositionRequest, authority_kind: str = "human"
                ) -> BoundaryCueComposition:
        if authority_kind != "human":
            raise ValueError("boundary_cues_require_human")
        cues = compose(request)
        digest = request_digest(event_id, actor_id, request)
        with self.repository.transaction(self.clock) as tx:
            tx.lock_event(event_id)
            tx.cue_event_scope(event_id)
            prior = tx.replay_composition(command_id, digest)
            if prior is not None:
                return prior
            current = tx.current_composition(event_id)
            version = 1 if current is None else current.version + 1
            now = self.clock.now()
            start = tx.publish_cue_list(EditorialPhraseList(
                EntityId.new(), event_id, START_KEY, version, "Boundary cues — start",
                cues.start, actor_id, now))
            end = tx.publish_cue_list(EditorialPhraseList(
                EntityId.new(), event_id, END_KEY, version, "Boundary cues — end",
                cues.end, actor_id, now))
            catalog = BOUNDARY_CUE_CATALOG
            value = BoundaryCueComposition(
                event_id, version, command_id, digest, catalog.id, catalog.version,
                catalog.digest, request.profile_key, cues.groups, request.include,
                request.exclude, request.custom_phrases, cues.segments, actor_id, now,
                Reference(start.id, start.version), Reference(end.id, end.version))
            tx.save_composition(value)
            return value

    def current(self, event_id: EntityId) -> BoundaryCueComposition | None:
        with self.repository.transaction(self.clock) as tx:
            tx.cue_event_scope(event_id)
            return tx.current_composition(event_id)

    def history(self, event_id: EntityId, *, after: int = 0, limit: int = 50
                ) -> tuple[tuple[BoundaryCueComposition, ...], int | None]:
        if (type(after) is not int or not 0 <= after <= 2_147_483_647
                or type(limit) is not int or not 1 <= limit <= 100):
            raise ValueError("invalid cue composition history page")
        with self.repository.transaction(self.clock) as tx:
            tx.cue_event_scope(event_id)
            values = tx.composition_history(event_id, after, limit + 1)
            return values[:limit], values[limit - 1].version if len(values) > limit else None
