"""Transaction-bound, member-bounded advisory MTE read for Assembly proposals."""
from typing import Any

import psycopg

from app.contexts.assembly.timing_reader import AssemblyTimingEvidence
from app.contexts.production.media_timing_evidence.contracts import (
    RecorderProfileQualificationStatus,
)
from app.shared.ids import EntityId


class PostgresAssemblyTimingReader:
    def __init__(self, connection: psycopg.Connection[dict[str, Any]]) -> None:
        self._connection = connection

    def read(self, asset_ids: tuple[EntityId, ...]) -> tuple[AssemblyTimingEvidence, ...]:
        rows = self._connection.execute(
            """SELECT e.asset_id,e.evidence_id,e.evidence_revision,e.qualification_status,
                      d.candidate_started_at
               FROM (SELECT DISTINCT ON (asset_id)
                         asset_id,evidence_id,evidence_revision,qualification_status
                     FROM stageflow.media_timing_evidence
                     WHERE asset_id=ANY(%s::uuid[])
                     ORDER BY asset_id,evidence_revision DESC) e
               JOIN LATERAL (
                   SELECT min(candidate_started_at) AS candidate_started_at
                   FROM stageflow.media_timing_derivation
                   WHERE evidence_id=e.evidence_id AND rule_id='creation_time_plus_duration'
                   HAVING count(*)=1
               ) d ON TRUE""", ([asset.value for asset in asset_ids],),
        ).fetchall()
        return tuple(AssemblyTimingEvidence(
            EntityId(str(r["asset_id"])), EntityId(str(r["evidence_id"])),
            r["evidence_revision"], RecorderProfileQualificationStatus(r["qualification_status"]),
            r["candidate_started_at"],
        ) for r in rows)
