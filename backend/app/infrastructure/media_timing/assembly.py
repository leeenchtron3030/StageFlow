"""Non-durable Assembly reader adapter for the in-memory MTE test repository."""
from app.contexts.assembly.timing_reader import AssemblyTimingEvidence
from app.contexts.production.media_timing_evidence.repository import (
    InMemoryMediaTimingEvidenceRepository,
)
from app.shared.ids import EntityId


class InMemoryAssemblyTimingReader:
    def __init__(self, repository: InMemoryMediaTimingEvidenceRepository) -> None:
        self._repository = repository

    def read(self, asset_ids: tuple[EntityId, ...]) -> tuple[AssemblyTimingEvidence, ...]:
        results: list[AssemblyTimingEvidence] = []
        for asset_id in dict.fromkeys(asset_ids):
            evidence = self._repository.get_active(asset_id)
            if evidence is None:
                continue
            matches = [d for d in evidence.result.derivations
                       if d.rule_id == "creation_time_plus_duration"]
            if len(matches) == 1:
                results.append(AssemblyTimingEvidence(
                    asset_id, evidence.id, evidence.revision,
                    evidence.result.qualification.status, matches[0].candidate_started_at,
                ))
        return tuple(results)
