from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row

from app.contexts.production.media_timing_evidence import (
    MediaTimingDerivation,
    MediaTimingEvidence,
    MediaTimingEvidenceConflictError,
    MediaTimingEvidenceNotFoundError,
    MediaTimingEvidenceRepository,
    MediaTimingEvidenceStorageUnavailableError,
    MediaTimingInspectionProvenance,
    MediaTimingInspectionResult,
    MediaTimingObservation,
    PendingMediaTimingEvidence,
    RecorderProfileQualification,
    RecorderProfileQualificationStatus,
    TimingTimezoneKind,
)
from app.shared.ids import EntityId

Row = dict[str, Any]


class PostgresMediaTimingEvidenceRepository(MediaTimingEvidenceRepository):
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def _connect(self) -> psycopg.Connection[Row]:
        return psycopg.Connection[Row].connect(self._dsn, row_factory=dict_row)

    def append(self, pending: PendingMediaTimingEvidence) -> MediaTimingEvidence:
        request = pending.request
        try:
            with self._connect() as connection:
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (request.operation_id.value,),
                )
                replay = connection.execute(
                    """
                    SELECT request_digest, evidence_id
                    FROM stageflow.media_timing_evidence_application
                    WHERE operation_id = %s
                    """,
                    (request.operation_id.value,),
                ).fetchone()
                if replay is not None:
                    if cast(str, replay["request_digest"]) != pending.request_digest:
                        raise MediaTimingEvidenceConflictError(
                            "application_identity_conflict"
                        )
                    return self._load_one(connection, EntityId.parse(str(replay["evidence_id"])))

                asset = connection.execute(
                    """
                    SELECT asset_id, manifest_id
                    FROM stageflow.completed_media_asset_registry
                    WHERE asset_id = %s FOR UPDATE
                    """,
                    (request.asset_id.value,),
                ).fetchone()
                if asset is None:
                    raise MediaTimingEvidenceNotFoundError(
                        "completed_media_asset_not_found"
                    )
                if str(asset["manifest_id"]) != request.manifest_id.value:
                    raise MediaTimingEvidenceConflictError(
                        "asset_manifest_identity_conflict"
                    )
                predecessor = connection.execute(
                    """
                    SELECT evidence_id, evidence_revision
                    FROM stageflow.media_timing_evidence
                    WHERE asset_id = %s
                    ORDER BY evidence_revision DESC LIMIT 1
                    """,
                    (request.asset_id.value,),
                ).fetchone()
                revision = (
                    1
                    if predecessor is None
                    else cast(int, predecessor["evidence_revision"]) + 1
                )
                predecessor_id = None if predecessor is None else str(predecessor["evidence_id"])
                result = request.result
                connection.execute(
                    """
                    INSERT INTO stageflow.media_timing_evidence (
                        evidence_id, asset_id, manifest_id, manifest_version,
                        evidence_revision, predecessor_evidence_id,
                        provider_id, provider_version, tool_id, tool_version,
                        recorder_profile_id, recorder_profile_revision, inspected_at,
                        qualification_status, qualification_evaluated_at,
                        qualification_record_id, qualification_limitations,
                        limitations, applied_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        pending.id.value,
                        request.asset_id.value,
                        request.manifest_id.value,
                        request.manifest_version,
                        revision,
                        predecessor_id,
                        result.provenance.provider_id,
                        result.provenance.provider_version,
                        result.provenance.tool_id,
                        result.provenance.tool_version,
                        result.provenance.recorder_profile_id,
                        result.provenance.recorder_profile_revision,
                        result.provenance.inspected_at,
                        result.qualification.status.value,
                        result.qualification.evaluated_at,
                        None
                        if result.qualification.qualification_record_id is None
                        else result.qualification.qualification_record_id.value,
                        list(result.qualification.limitations),
                        list(result.limitations),
                        request.applied_at,
                    ),
                )
                self._insert_observations(connection, pending)
                self._insert_derivations(connection, pending)
                connection.execute(
                    """
                    INSERT INTO stageflow.media_timing_evidence_application (
                        operation_id, request_digest, evidence_id, recorded_at
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    (
                        request.operation_id.value,
                        pending.request_digest,
                        pending.id.value,
                        request.applied_at,
                    ),
                )
                return MediaTimingEvidence(
                    id=pending.id,
                    asset_id=request.asset_id,
                    manifest_id=request.manifest_id,
                    manifest_version=request.manifest_version,
                    revision=revision,
                    predecessor_evidence_id=(
                        None if predecessor_id is None else EntityId.parse(predecessor_id)
                    ),
                    operation_id=request.operation_id,
                    request_digest=pending.request_digest,
                    applied_at=request.applied_at,
                    result=request.result,
                )
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise MediaTimingEvidenceStorageUnavailableError(
                "postgresql_media_timing_evidence_unavailable"
            ) from exc

    def _insert_observations(
        self,
        connection: psycopg.Connection[Row],
        pending: PendingMediaTimingEvidence,
    ) -> None:
        for item in pending.request.result.observations:
            connection.execute(
                """
                INSERT INTO stageflow.media_timing_observation (
                    evidence_id, observation_id, observation_kind, source_field,
                    original_representation, observed_at, timezone_kind,
                    normalized_timestamp, normalized_duration_microseconds,
                    normalized_value, precision, stream_selector, limitations
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    pending.id.value,
                    item.id.value,
                    item.kind,
                    item.source_field,
                    item.original_representation,
                    item.observed_at,
                    item.timezone_kind.value,
                    item.normalized_timestamp,
                    _duration_microseconds(item.normalized_duration),
                    item.normalized_value,
                    item.precision,
                    item.stream_selector,
                    list(item.limitations),
                ),
            )

    def _insert_derivations(
        self,
        connection: psycopg.Connection[Row],
        pending: PendingMediaTimingEvidence,
    ) -> None:
        for item in pending.request.result.derivations:
            connection.execute(
                """
                INSERT INTO stageflow.media_timing_derivation (
                    evidence_id, derivation_id, rule_id, rule_version,
                    candidate_started_at, candidate_ended_at, derived_at, limitations
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    pending.id.value,
                    item.id.value,
                    item.rule_id,
                    item.rule_version,
                    item.candidate_started_at,
                    item.candidate_ended_at,
                    item.derived_at,
                    list(item.limitations),
                ),
            )
            for observation_id in item.input_observation_ids:
                connection.execute(
                    """
                    INSERT INTO stageflow.media_timing_derivation_input (
                        evidence_id, derivation_id, observation_id
                    ) VALUES (%s, %s, %s)
                    """,
                    (pending.id.value, item.id.value, observation_id.value),
                )

    def get_active(self, asset_id: EntityId) -> MediaTimingEvidence | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT evidence_id FROM stageflow.media_timing_evidence
                    WHERE asset_id = %s
                    ORDER BY evidence_revision DESC LIMIT 1
                    """,
                    (asset_id.value,),
                ).fetchone()
                return None if row is None else self._load_one(
                    connection, EntityId.parse(str(row["evidence_id"]))
                )
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise MediaTimingEvidenceStorageUnavailableError(
                "postgresql_media_timing_evidence_unavailable"
            ) from exc

    def history(self, asset_id: EntityId) -> tuple[MediaTimingEvidence, ...]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT evidence_id FROM stageflow.media_timing_evidence
                    WHERE asset_id = %s ORDER BY evidence_revision
                    """,
                    (asset_id.value,),
                ).fetchall()
                return tuple(
                    self._load_one(connection, EntityId.parse(str(row["evidence_id"])))
                    for row in rows
                )
        except (psycopg.InterfaceError, psycopg.OperationalError) as exc:
            raise MediaTimingEvidenceStorageUnavailableError(
                "postgresql_media_timing_evidence_unavailable"
            ) from exc

    def _load_one(
        self,
        connection: psycopg.Connection[Row],
        evidence_id: EntityId,
    ) -> MediaTimingEvidence:
        parent = connection.execute(
            """
            SELECT evidence.*, application.operation_id, application.request_digest
            FROM stageflow.media_timing_evidence evidence
            JOIN stageflow.media_timing_evidence_application application
              ON application.evidence_id = evidence.evidence_id
            WHERE evidence.evidence_id = %s
            """,
            (evidence_id.value,),
        ).fetchone()
        if parent is None:
            raise MediaTimingEvidenceNotFoundError("media_timing_evidence_not_found")
        observation_rows = connection.execute(
            """
            SELECT * FROM stageflow.media_timing_observation
            WHERE evidence_id = %s ORDER BY observation_id
            """,
            (evidence_id.value,),
        ).fetchall()
        derivation_rows = connection.execute(
            """
            SELECT derivation.*,
                   array_agg(input.observation_id ORDER BY input.observation_id) AS input_ids
            FROM stageflow.media_timing_derivation derivation
            JOIN stageflow.media_timing_derivation_input input
              ON input.evidence_id = derivation.evidence_id
             AND input.derivation_id = derivation.derivation_id
            WHERE derivation.evidence_id = %s
            GROUP BY derivation.evidence_id, derivation.derivation_id
            ORDER BY derivation.derivation_id
            """,
            (evidence_id.value,),
        ).fetchall()
        provenance = MediaTimingInspectionProvenance(
            provider_id=cast(str, parent["provider_id"]),
            provider_version=cast(str, parent["provider_version"]),
            tool_id=cast(str, parent["tool_id"]),
            tool_version=cast(str, parent["tool_version"]),
            recorder_profile_id=cast(str, parent["recorder_profile_id"]),
            recorder_profile_revision=cast(int, parent["recorder_profile_revision"]),
            inspected_at=cast(datetime, parent["inspected_at"]),
        )
        qualification = RecorderProfileQualification(
            profile_id=provenance.recorder_profile_id,
            profile_revision=provenance.recorder_profile_revision,
            status=RecorderProfileQualificationStatus(cast(str, parent["qualification_status"])),
            evaluated_at=cast(datetime, parent["qualification_evaluated_at"]),
            qualification_record_id=(
                None
                if parent["qualification_record_id"] is None
                else EntityId.parse(str(parent["qualification_record_id"]))
            ),
            limitations=_text_array(parent, "qualification_limitations"),
        )
        result = MediaTimingInspectionResult(
            provenance=provenance,
            observations=tuple(_observation(row) for row in observation_rows),
            derivations=tuple(_derivation(row) for row in derivation_rows),
            qualification=qualification,
            limitations=_text_array(parent, "limitations"),
        )
        return MediaTimingEvidence(
            id=evidence_id,
            asset_id=EntityId.parse(str(parent["asset_id"])),
            manifest_id=EntityId.parse(str(parent["manifest_id"])),
            manifest_version=cast(str, parent["manifest_version"]),
            revision=cast(int, parent["evidence_revision"]),
            predecessor_evidence_id=(
                None
                if parent["predecessor_evidence_id"] is None
                else EntityId.parse(str(parent["predecessor_evidence_id"]))
            ),
            operation_id=EntityId.parse(str(parent["operation_id"])),
            request_digest=cast(str, parent["request_digest"]),
            applied_at=cast(datetime, parent["applied_at"]),
            result=result,
        )


def _duration_microseconds(value: timedelta | None) -> int | None:
    if value is None:
        return None
    return value.days * 86_400_000_000 + value.seconds * 1_000_000 + value.microseconds


def _text_array(row: Mapping[str, Any], key: str) -> tuple[str, ...]:
    return tuple(cast(list[str], row[key]))


def _observation(row: Mapping[str, Any]) -> MediaTimingObservation:
    microseconds = cast(int | None, row["normalized_duration_microseconds"])
    return MediaTimingObservation(
        id=EntityId.parse(str(row["observation_id"])),
        kind=cast(str, row["observation_kind"]),
        source_field=cast(str, row["source_field"]),
        original_representation=cast(str, row["original_representation"]),
        observed_at=cast(datetime, row["observed_at"]),
        timezone_kind=TimingTimezoneKind(cast(str, row["timezone_kind"])),
        normalized_timestamp=cast(datetime | None, row["normalized_timestamp"]),
        normalized_duration=(
            None if microseconds is None else timedelta(microseconds=microseconds)
        ),
        normalized_value=cast(str | None, row["normalized_value"]),
        precision=cast(str | None, row["precision"]),
        stream_selector=cast(str | None, row["stream_selector"]),
        limitations=_text_array(row, "limitations"),
    )


def _derivation(row: Mapping[str, Any]) -> MediaTimingDerivation:
    return MediaTimingDerivation(
        id=EntityId.parse(str(row["derivation_id"])),
        rule_id=cast(str, row["rule_id"]),
        rule_version=cast(str, row["rule_version"]),
        input_observation_ids=tuple(
            EntityId.parse(str(value)) for value in cast(list[object], row["input_ids"])
        ),
        candidate_started_at=cast(datetime, row["candidate_started_at"]),
        candidate_ended_at=cast(datetime, row["candidate_ended_at"]),
        derived_at=cast(datetime, row["derived_at"]),
        limitations=_text_array(row, "limitations"),
    )


__all__ = ["PostgresMediaTimingEvidenceRepository"]
