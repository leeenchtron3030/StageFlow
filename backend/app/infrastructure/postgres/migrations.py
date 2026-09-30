from __future__ import annotations

from contextlib import ExitStack, nullcontext
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import LiteralString, cast

import psycopg
from psycopg import sql


@dataclass
class _ReversalTransaction:
    """Open lazily so migration registration remains independent of a database."""
    stack: ExitStack
    connection: psycopg.Connection | None = None

    def borrow(self, dsn: str) -> nullcontext[psycopg.Connection]:
        if self.connection is None:
            self.connection = self.stack.enter_context(psycopg.connect(dsn))
        return nullcontext(self.connection)


@dataclass(frozen=True, slots=True)
class PostgresMigrationRunner:
    """Explicit forward/reversal runner for the bounded StageFlow schema."""

    dsn: str
    _reversal: _ReversalTransaction | None = field(default=None, repr=False, compare=False)

    def apply_ingress_v1(self) -> None:
        self._execute("0001_ingress_forward.sql")

    def reverse_ingress_v1(self) -> None:
        self._execute("0001_ingress_reverse.sql")

    def apply_event_mode_kernel_v1(self) -> None:
        self.apply_ingress_v1()
        self._execute("0002_event_mode_kernel_forward.sql")
        self._execute("0003_kernel_projections_forward.sql")
        self._execute_if_missing(
            "0004_kernel_review_corrections_forward.sql",
            version="0004_kernel_review_corrections",
        )
        self.apply_kernel_follow_up_closure()
        self.apply_media_timing_evidence_v1()
        self.apply_transcription_worker_v1()
        self.apply_demo_vertical_slice_v1()
        self.apply_program_expectation_reconciliation_v1()
        self.apply_editorial_candidate_moment_v1()

    def apply_kernel_follow_up_closure(self) -> None:
        self._execute_if_missing(
            "0005_kernel_follow_up_closure_forward.sql",
            version="0005_kernel_follow_up_closure",
        )

    def apply_media_timing_evidence_v1(self) -> None:
        self._execute_if_missing(
            "0006_media_timing_evidence_forward.sql",
            version="0006_media_timing_evidence",
        )

    def apply_transcription_worker_v1(self) -> None:
        self._execute_if_missing(
            "0007_transcription_worker_forward.sql",
            version="0007_transcription_worker",
        )

    def apply_demo_vertical_slice_v1(self) -> None:
        self._execute_if_missing(
            "0008_demo_vertical_slice_forward.sql",
            version="0008_demo_vertical_slice",
        )

    def apply_program_expectation_reconciliation_v1(self) -> None:
        self._execute_if_missing(
            "0009_program_expectation_reconciliation_forward.sql",
            version="0009_program_expectation_reconciliation",
        )

    def apply_editorial_candidate_moment_v1(self) -> None:
        self._execute_if_missing(
            "0010_editorial_candidate_moment_forward.sql",
            version="0010_editorial_candidate_moment",
        )
        self.apply_editorial_review_foundation_v1()

    def apply_editorial_review_foundation_v1(self) -> None:
        self._execute_if_missing(
            "0011_editorial_review_foundation_forward.sql",
            version="0011_editorial_review_foundation",
        )
        self.apply_packaging_asset_foundation_v1()

    def apply_packaging_asset_foundation_v1(self) -> None:
        self._execute_if_missing(
            "0012_packaging_asset_foundation_forward.sql",
            version="0012_packaging_asset_foundation",
        )
        self.apply_session_assembly_foundation_v1()

    def apply_session_assembly_foundation_v1(self) -> None:
        self._execute_if_missing(
            "0013_session_assembly_foundation_forward.sql",
            version="0013_session_assembly_foundation",
        )
        self.apply_assembly_metadata_overrides_v1()

    def apply_assembly_metadata_overrides_v1(self) -> None:
        self._execute_if_missing(
            "0014_assembly_metadata_overrides_forward.sql",
            version="0014_assembly_metadata_overrides",
        )

        self.apply_render_durable_operation_v1()

    def apply_render_durable_operation_v1(self) -> None:
        self._execute_if_missing(
            "0015_render_durable_operation_forward.sql",
            version="0015_render_durable_operation",
        )

        self.apply_assembly_media_order_v1()

    def apply_assembly_media_order_v1(self) -> None:
        self._execute_if_missing(
            "0016_assembly_media_order_forward.sql",
            version="0016_assembly_media_order",
        )

        self.apply_media_timing_operation_v1()

    def apply_media_timing_operation_v1(self) -> None:
        self._execute_if_missing(
            "0017_media_timing_operation_forward.sql",
            version="0017_media_timing_operation",
        )

        self.apply_assembly_timing_evidence_v1()

    def apply_assembly_timing_evidence_v1(self) -> None:
        self._execute_if_missing(
            "0018_assembly_timing_evidence_forward.sql",
            version="0018_assembly_timing_evidence",
        )
        self.apply_derived_editorial_candidates_v1()

    def apply_derived_editorial_candidates_v1(self) -> None:
        self._execute_if_missing(
            "0019_derived_editorial_candidates_forward.sql",
            version="0019_derived_editorial_candidates",
        )

        self.apply_event_render_setting_v1()

    def apply_event_render_setting_v1(self) -> None:
        self._execute_if_missing(
            "0020_event_render_setting_forward.sql", version="0020_event_render_setting",
        )

        self.apply_media_segmentation_v1()

    def apply_media_segmentation_v1(self) -> None:
        self._execute_if_missing(
            "0021_media_segmentation_forward.sql", version="0021_media_segmentation",
        )
        self.apply_session_suggestions_v1()

    def apply_session_suggestions_v1(self) -> None:
        self._execute_if_missing(
            "0022_session_suggestions_forward.sql", version="0022_session_suggestions",
        )

        self.apply_session_suggestions_policy_v2()

    def apply_session_suggestions_policy_v2(self) -> None:
        self._execute_if_missing(
            "0023_session_suggestions_policy_v2_forward.sql",
            version="0023_session_suggestions_policy_v2",
        )

        self.apply_session_suggestions_policy_v3()

    def apply_session_suggestions_policy_v3(self) -> None:
        self._execute_if_missing(
            "0024_session_suggestions_policy_v3_forward.sql",
            version="0024_session_suggestions_policy_v3",
        )

        self.apply_boundary_cue_composition_v1()

    def apply_boundary_cue_composition_v1(self) -> None:
        self._execute_if_missing(
            "0025_boundary_cue_composition_forward.sql", version="0025_boundary_cue_composition",
        )
        self.apply_session_suggestions_already_realized()

    def apply_session_suggestions_already_realized(self) -> None:
        self._execute_if_missing(
            "0026_session_suggestions_already_realized_forward.sql",
            version="0026_session_suggestions_already_realized",
        )
        self.apply_boundary_proposal_decisions()

    def apply_boundary_proposal_decisions(self) -> None:
        self._execute_if_missing(
            "0027_boundary_proposal_decisions_forward.sql",
            version="0027_boundary_proposal_decisions",
        )

    def reverse_event_mode_kernel_v1(self) -> None:
        self.reverse_demo_vertical_slice_v1()
        self.reverse_transcription_worker_v1()
        self.reverse_media_timing_evidence_v1()
        self.reverse_kernel_follow_up_closure()
        self._execute("0004_kernel_review_corrections_reverse.sql")
        self._execute("0003_kernel_projections_reverse.sql")
        self._execute("0002_event_mode_kernel_reverse.sql")

    def reverse_kernel_follow_up_closure(self) -> None:
        self._execute_if_present(
            "0005_kernel_follow_up_closure_reverse.sql",
            version="0005_kernel_follow_up_closure",
        )

    def reverse_media_timing_evidence_v1(self) -> None:
        self.reverse_transcription_worker_v1()
        self._execute_if_present(
            "0006_media_timing_evidence_reverse.sql",
            version="0006_media_timing_evidence",
        )

    def reverse_transcription_worker_v1(self) -> None:
        self.reverse_render_durable_operation_v1()
        self._execute_if_present(
            "0007_transcription_worker_reverse.sql",
            version="0007_transcription_worker",
        )

    def reverse_demo_vertical_slice_v1(self) -> None:
        self.reverse_editorial_candidate_moment_v1()
        self.reverse_program_expectation_reconciliation_v1()
        self._execute_if_present(
            "0008_demo_vertical_slice_reverse.sql",
            version="0008_demo_vertical_slice",
        )

    def reverse_program_expectation_reconciliation_v1(self) -> None:
        self._execute_if_present(
            "0009_program_expectation_reconciliation_reverse.sql",
            version="0009_program_expectation_reconciliation",
        )

    def reverse_editorial_candidate_moment_v1(self) -> None:
        self.reverse_editorial_review_foundation_v1()
        self._execute_if_present(
            "0010_editorial_candidate_moment_reverse.sql",
            version="0010_editorial_candidate_moment",
        )

    def reverse_editorial_review_foundation_v1(self) -> None:
        self.reverse_packaging_asset_foundation_v1()
        self._execute_if_present(
            "0011_editorial_review_foundation_reverse.sql",
            version="0011_editorial_review_foundation",
        )

    def reverse_packaging_asset_foundation_v1(self) -> None:
        self.reverse_session_assembly_foundation_v1()
        self._execute_if_present(
            "0012_packaging_asset_foundation_reverse.sql",
            version="0012_packaging_asset_foundation",
        )

    def reverse_session_assembly_foundation_v1(self) -> None:
        self.reverse_assembly_metadata_overrides_v1()
        self._execute_if_present(
            "0013_session_assembly_foundation_reverse.sql",
            version="0013_session_assembly_foundation",
        )

    def reverse_assembly_metadata_overrides_v1(self) -> None:
        self.reverse_render_durable_operation_v1()
        self._execute_if_present(
            "0014_assembly_metadata_overrides_reverse.sql",
            version="0014_assembly_metadata_overrides",
        )

    def reverse_render_durable_operation_v1(self) -> None:
        self.reverse_assembly_media_order_v1()
        self._execute_if_present(
            "0015_render_durable_operation_reverse.sql",
            version="0015_render_durable_operation",
        )

    def reverse_assembly_media_order_v1(self) -> None:
        self.reverse_media_timing_operation_v1()
        self._execute_if_present(
            "0016_assembly_media_order_reverse.sql",
            version="0016_assembly_media_order",
        )

    def reverse_media_timing_operation_v1(self) -> None:
        self.reverse_assembly_timing_evidence_v1()
        self._execute_if_present(
            "0017_media_timing_operation_reverse.sql",
            version="0017_media_timing_operation",
        )

    def reverse_assembly_timing_evidence_v1(self) -> None:
        self.reverse_derived_editorial_candidates_v1()
        self._execute_if_present(
            "0018_assembly_timing_evidence_reverse.sql",
            version="0018_assembly_timing_evidence",
        )

    def reverse_derived_editorial_candidates_v1(self) -> None:
        self.reverse_event_render_setting_v1()
        self._execute_if_present(
            "0019_derived_editorial_candidates_reverse.sql",
            version="0019_derived_editorial_candidates",
        )

    def reverse_event_render_setting_v1(self) -> None:
        self.reverse_media_segmentation_v1()
        self._execute_if_present(
            "0020_event_render_setting_reverse.sql", version="0020_event_render_setting",
        )

    def reverse_media_segmentation_v1(self) -> None:
        self.reverse_session_suggestions_v1()
        self._execute_if_present(
            "0021_media_segmentation_reverse.sql", version="0021_media_segmentation",
        )

    def reverse_session_suggestions_v1(self) -> None:
        self.reverse_session_suggestions_policy_v2()
        self._execute_if_present(
            "0022_session_suggestions_reverse.sql", version="0022_session_suggestions",
        )

    def reverse_session_suggestions_policy_v2(self) -> None:
        self.reverse_session_suggestions_policy_v3()
        self._execute_if_present(
            "0023_session_suggestions_policy_v2_reverse.sql",
            version="0023_session_suggestions_policy_v2",
        )

    def reverse_session_suggestions_policy_v3(self) -> None:
        # If 0024's existing guard refuses, retain later migrations too.
        with ExitStack() as stack:
            runner = replace(self, _reversal=_ReversalTransaction(stack))
            runner.reverse_boundary_cue_composition_v1()
            runner._execute_if_present(
                "0024_session_suggestions_policy_v3_reverse.sql",
                version="0024_session_suggestions_policy_v3",
            )

    def reverse_boundary_cue_composition_v1(self) -> None:
        # Retain 0026 if the composition guard refuses reversal.
        with ExitStack() as stack:
            runner = (self if self._reversal is not None
                      else replace(self, _reversal=_ReversalTransaction(stack)))
            runner.reverse_session_suggestions_already_realized()
            runner._execute_if_present(
                "0025_boundary_cue_composition_reverse.sql",
                version="0025_boundary_cue_composition",
            )

    def reverse_session_suggestions_already_realized(self) -> None:
        self.reverse_boundary_proposal_decisions()
        self._execute_if_present(
            "0026_session_suggestions_already_realized_reverse.sql",
            version="0026_session_suggestions_already_realized",
        )

    def reverse_boundary_proposal_decisions(self) -> None:
        self._execute_if_present(
            "0027_boundary_proposal_decisions_reverse.sql",
            version="0027_boundary_proposal_decisions",
        )

    def _execute(self, filename: str) -> None:
        statement = (
            Path(__file__).with_name("sql").joinpath(filename).read_text(encoding="utf-8")
        )
        with psycopg.connect(self.dsn) as connection:
            connection.execute(sql.SQL(cast(LiteralString, statement)))

    def _execute_if_missing(self, filename: str, *, version: str) -> None:
        statement = (
            Path(__file__).with_name("sql").joinpath(filename).read_text(encoding="utf-8")
        )
        with psycopg.connect(self.dsn) as connection:
            existing = connection.execute(
                "SELECT 1 FROM stageflow.schema_migration WHERE version = %s",
                (version,),
            ).fetchone()
            if existing is not None:
                return
            connection.execute(sql.SQL(cast(LiteralString, statement)))

    def _execute_if_present(self, filename: str, *, version: str) -> None:
        statement = (
            Path(__file__).with_name("sql").joinpath(filename).read_text(encoding="utf-8")
        )
        scope = (psycopg.connect(self.dsn) if self._reversal is None
                 else self._reversal.borrow(self.dsn))
        with scope as connection:
            existing = connection.execute(
                "SELECT 1 FROM stageflow.schema_migration WHERE version = %s",
                (version,),
            ).fetchone()
            if existing is None:
                return
            connection.execute(sql.SQL(cast(LiteralString, statement)))
