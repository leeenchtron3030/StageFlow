"""Composition persistence on the enclosing suggestion transaction's connection."""
from typing import Any

import psycopg

from app.contexts.editorial.derivation_contracts import EditorialPhraseList
from app.contexts.production.session_suggestions.contracts import (
    Reference,
    SuggestionConflictError,
    SuggestionNotFoundError,
)
from app.contexts.production.session_suggestions.cue_composition import (
    BoundaryCueComposition,
    CustomPhrase,
    GroupReference,
    PhraseChoice,
    SegmentPhrase,
)
from app.infrastructure.postgres.editorial_derivation_repository import (
    PostgresEditorialDerivationTransaction,
)
from app.shared.ids import EntityId

type Row = dict[str, Any]


class PostgresBoundaryCueTransaction:
    connection: psycopg.Connection[Row]

    def cue_event_scope(self, event_id: EntityId) -> None:
        if self.connection.execute("SELECT 1 FROM stageflow.business_event WHERE event_id=%s",
                                   (event_id.value,)).fetchone() is None:
            raise SuggestionNotFoundError("event_not_found")

    def _composition(self, row: Row) -> BoundaryCueComposition:
        args = (row["event_id"], row["version"])
        groups = self.connection.execute(
            """SELECT group_key, group_version FROM stageflow.boundary_cue_group
               WHERE event_id=%s AND version=%s ORDER BY ordinal""", args).fetchall()
        choices = self.connection.execute(
            """SELECT kind, group_key, phrase FROM stageflow.boundary_cue_choice
               WHERE event_id=%s AND version=%s ORDER BY ordinal""", args).fetchall()
        customs = self.connection.execute(
            """SELECT phrase, role FROM stageflow.boundary_cue_custom_phrase
               WHERE event_id=%s AND version=%s ORDER BY ordinal""", args).fetchall()
        segments = self.connection.execute(
            """SELECT phrase, source_group FROM stageflow.boundary_cue_segment_phrase
               WHERE event_id=%s AND version=%s ORDER BY ordinal""", args).fetchall()
        return BoundaryCueComposition(
            EntityId(str(row["event_id"])), row["version"], EntityId(str(row["command_id"])),
            row["request_digest"], row["catalog_id"], row["catalog_version"], row["catalog_digest"],
            row["profile_key"], tuple(GroupReference(g["group_key"], g["group_version"])
                                      for g in groups),
            tuple(PhraseChoice(c["group_key"], c["phrase"])
                  for c in choices if c["kind"] == "include"),
            tuple(PhraseChoice(c["group_key"], c["phrase"])
                  for c in choices if c["kind"] == "exclude"),
            tuple(CustomPhrase(c["phrase"], c["role"]) for c in customs),
            tuple(SegmentPhrase(s["phrase"], s["source_group"]) for s in segments),
            EntityId(str(row["composed_by"])), row["composed_at"],
            Reference(EntityId(str(row["start_phrase_list_id"])), row["start_phrase_list_version"]),
            Reference(EntityId(str(row["end_phrase_list_id"])), row["end_phrase_list_version"]))

    def current_composition(self, event_id: EntityId) -> BoundaryCueComposition | None:
        row = self.connection.execute(
            """SELECT * FROM stageflow.boundary_cue_composition WHERE event_id=%s
               ORDER BY version DESC LIMIT 1""", (event_id.value,)).fetchone()
        return None if row is None else self._composition(row)

    def replay_composition(self, command_id: EntityId, digest: str
                           ) -> BoundaryCueComposition | None:
        self.connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                                ("boundary_cue_command:" + command_id.value,))
        row = self.connection.execute(
            "SELECT * FROM stageflow.boundary_cue_composition WHERE command_id=%s",
            (command_id.value,)).fetchone()
        if row is not None and row["request_digest"] != digest:
            raise SuggestionConflictError("cue_composition_command_id_conflict")
        return None if row is None else self._composition(row)

    def publish_cue_list(self, value: EditorialPhraseList) -> EditorialPhraseList:
        return PostgresEditorialDerivationTransaction(self.connection).publish(value)

    def save_composition(self, value: BoundaryCueComposition) -> None:
        self.connection.execute(
            """INSERT INTO stageflow.boundary_cue_composition
               (event_id, version, command_id, request_digest, catalog_id, catalog_version,
                catalog_digest, profile_key, composed_by, composed_at,
                start_phrase_list_id, start_phrase_list_version,
                end_phrase_list_id, end_phrase_list_version,
                group_count, choice_count, custom_count, segment_count)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (value.event_id.value, value.version, value.command_id.value, value.request_digest,
             value.catalog_id, value.catalog_version, value.catalog_digest, value.profile_key,
             value.composed_by.value, value.composed_at, value.start_cue_list.id.value,
             value.start_cue_list.revision, value.end_cue_list.id.value,
             value.end_cue_list.revision,
             len(value.groups), len(value.include) + len(value.exclude),
             len(value.custom_phrases), len(value.segment_phrases)))
        owner = (value.event_id.value, value.version)
        for ordinal, group in enumerate(value.groups):
            self.connection.execute(
                """INSERT INTO stageflow.boundary_cue_group
                   (event_id, version, ordinal, group_key, group_version)
                   VALUES (%s,%s,%s,%s,%s)""",
                (*owner, ordinal, group.key, group.version))
        choices = [("include", c) for c in value.include] + [("exclude", c) for c in value.exclude]
        for ordinal, (kind, choice) in enumerate(choices):
            self.connection.execute(
                """INSERT INTO stageflow.boundary_cue_choice
                   (event_id, version, ordinal, kind, group_key, phrase)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (*owner, ordinal, kind, choice.group_key, choice.phrase))
        for ordinal, custom in enumerate(value.custom_phrases):
            self.connection.execute(
                """INSERT INTO stageflow.boundary_cue_custom_phrase
                   (event_id, version, ordinal, phrase, role) VALUES (%s,%s,%s,%s,%s)""",
                (*owner, ordinal, custom.text, custom.role.value))
        for ordinal, segment in enumerate(value.segment_phrases):
            self.connection.execute(
                """INSERT INTO stageflow.boundary_cue_segment_phrase
                   (event_id, version, ordinal, phrase, source_group) VALUES (%s,%s,%s,%s,%s)""",
                (*owner, ordinal, segment.text, segment.source_group))

    def composition_history(self, event_id: EntityId, after: int, limit: int
                            ) -> tuple[BoundaryCueComposition, ...]:
        rows = self.connection.execute(
            """SELECT * FROM stageflow.boundary_cue_composition
               WHERE event_id=%s AND version>%s ORDER BY version LIMIT %s""",
            (event_id.value, after, limit)).fetchall()
        return tuple(self._composition(row) for row in rows)
