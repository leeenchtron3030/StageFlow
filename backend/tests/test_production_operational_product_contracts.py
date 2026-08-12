from dataclasses import fields
from datetime import UTC, datetime

import pytest

from app.contexts.production.operational_product import (
    OperationalProduct,
    OperationalProductOrigin,
    OperationalProductReference,
    OperationalProductReferenceType,
    OperationalProductStatus,
    OperationalProductSummary,
    OperationalProductType,
)
from app.shared.ids import CorrelationId, EntityId
from tests.timestamp_fixtures import AWARE_TIMESTAMP


def _product(
    origin: OperationalProductOrigin = OperationalProductOrigin.VERIFIED_FINDING,
) -> OperationalProduct:
    return OperationalProduct(
               created_at=AWARE_TIMESTAMP,

        id=EntityId.new(),
        product_type=OperationalProductType.SESSION_WINDOW,
        status=OperationalProductStatus.CREATED,
        origin=origin,
        originating_finding_ids=[EntityId.new()],
        originating_verification_decision_ids=[EntityId.new()],
        correlation_id=CorrelationId.new(),
    )


def test_operational_product_creation() -> None:
    finding_id = EntityId.new()
    decision_id = EntityId.new()
    created_at = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    product = OperationalProduct(
        id=EntityId.new(),
        product_type=OperationalProductType.ALERT,
        status=OperationalProductStatus.ACTIVE,
        origin=OperationalProductOrigin.VERIFIED_FINDING,
        originating_finding_ids=[finding_id],
        originating_verification_decision_ids=[decision_id],
        references=[
            OperationalProductReference(
                reference_type=OperationalProductReferenceType.FINDING,
                referenced_id=finding_id,
                label="source finding",
            )
        ],
        correlation_id=CorrelationId.new(),
        created_at=created_at,
        metadata={"priority": "review"},
        notes="Generic operational product only.",
    )

    assert product.product_type is OperationalProductType.ALERT
    assert product.status is OperationalProductStatus.ACTIVE
    assert product.origin is OperationalProductOrigin.VERIFIED_FINDING
    assert product.originating_finding_ids == (finding_id,)
    assert product.originating_verification_decision_ids == (decision_id,)
    assert len(product.references) == 1
    assert dict(product.metadata) == {"priority": "review"}
    assert product.created_at == created_at


def test_operational_product_type_allowed_values() -> None:
    assert {product_type.value for product_type in OperationalProductType} == {
        "session_window",
        "editorial_moment",
        "technical_incident",
        "metadata_record",
        "alert",
        "package_task",
        "unknown",
    }


def test_operational_product_status_allowed_values() -> None:
    assert {status.value for status in OperationalProductStatus} == {
        "created",
        "active",
        "completed",
        "cancelled",
        "superseded",
        "archived",
    }


def test_operational_product_origin_allowed_values() -> None:
    assert {origin.value for origin in OperationalProductOrigin} == {
        "verified_finding",
        "human_created",
        "system_created",
        "imported",
        "unknown",
    }


def test_operational_product_reference_creation() -> None:
    referenced_id = EntityId.new()
    reference = OperationalProductReference(
        reference_type=OperationalProductReferenceType.VERIFICATION_DECISION,
        referenced_id=referenced_id,
        label="accepted decision",
        metadata={"order": 1},
    )

    assert reference.reference_type is OperationalProductReferenceType.VERIFICATION_DECISION
    assert reference.referenced_id == referenced_id
    assert reference.label == "accepted decision"
    assert dict(reference.metadata) == {"order": 1}


def test_operational_product_summary_generation() -> None:
    created_at = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    product = OperationalProduct(
        id=EntityId.new(),
        product_type=OperationalProductType.PACKAGE_TASK,
        status=OperationalProductStatus.CREATED,
        origin=OperationalProductOrigin.VERIFIED_FINDING,
        originating_finding_ids=[EntityId.new(), EntityId.new()],
        originating_verification_decision_ids=[EntityId.new()],
        references=[
            OperationalProductReference(
                OperationalProductReferenceType.RECORDING_BLOCK,
                EntityId.new(),
            )
        ],
        correlation_id=CorrelationId.new(),
        created_at=created_at,
    )

    summary = OperationalProductSummary.from_operational_product(product)

    assert summary.operational_product_id == product.id
    assert summary.product_type is OperationalProductType.PACKAGE_TASK
    assert summary.status is OperationalProductStatus.CREATED
    assert summary.origin is OperationalProductOrigin.VERIFIED_FINDING
    assert summary.originating_finding_count == 2
    assert summary.originating_verification_decision_count == 1
    assert summary.reference_count == 1
    assert summary.created_at == created_at


def test_product_references_finding_ids_by_id_only() -> None:
    product = _product()
    field_names = {field.name for field in fields(OperationalProduct)}

    assert len(product.originating_finding_ids) == 1
    assert "originating_finding_ids" in field_names
    assert "findings" not in field_names


def test_product_references_verification_decision_ids_by_id_only() -> None:
    product = _product()
    field_names = {field.name for field in fields(OperationalProduct)}

    assert len(product.originating_verification_decision_ids) == 1
    assert "originating_verification_decision_ids" in field_names
    assert "verification_decisions" not in field_names


def test_product_status_does_not_modify_reasoning_artifacts() -> None:
    product_fields = {field.name for field in fields(OperationalProduct)}
    forbidden_terms = {
        "_".join(("finding", "status")),
        "_".join(("verification", "status")),
        "_".join(("update", "finding")),
        "_".join(("update", "verification")),
    }

    assert not any(term in field_name for field_name in product_fields for term in forbidden_terms)


def test_product_requires_reasoning_lineage_unless_origin_allows_otherwise() -> None:
    with pytest.raises(ValueError, match="requires Finding or Verification Decision lineage"):
        OperationalProduct(
            created_at=AWARE_TIMESTAMP,

            id=EntityId.new(),
            product_type=OperationalProductType.UNKNOWN,
            status=OperationalProductStatus.CREATED,
            origin=OperationalProductOrigin.VERIFIED_FINDING,
            originating_finding_ids=[],
            originating_verification_decision_ids=[],
            correlation_id=CorrelationId.new(),
        )

    imported_product = OperationalProduct(
                           created_at=AWARE_TIMESTAMP,

        id=EntityId.new(),
        product_type=OperationalProductType.UNKNOWN,
        status=OperationalProductStatus.CREATED,
        origin=OperationalProductOrigin.IMPORTED,
        originating_finding_ids=[],
        originating_verification_decision_ids=[],
        correlation_id=CorrelationId.new(),
    )

    assert imported_product.origin is OperationalProductOrigin.IMPORTED


def test_no_specialized_product_behavior_exists() -> None:
    product_fields = {field.name for field in fields(OperationalProduct)}
    summary_fields = {field.name for field in fields(OperationalProductSummary)}
    forbidden_terms = {
        "render",
        "publish",
        "assemble",
        "deliver",
        "execute",
        "workflow",
        "queue",
        "worker",
    }

    assert not any(
        term in field_name
        for field_name in product_fields | summary_fields
        for term in forbidden_terms
    )


def test_no_provider_specific_names_appear() -> None:
    enum_values = (
        {product_type.value for product_type in OperationalProductType}
        | {status.value for status in OperationalProductStatus}
        | {origin.value for origin in OperationalProductOrigin}
        | {reference_type.value for reference_type in OperationalProductReferenceType}
    )
    forbidden_terms = {
        "provider",
        "vendor",
        "tool",
        "brand",
        "conference",
    }

    assert not any(term in value for value in enum_values for term in forbidden_terms)


def test_no_api_persistence_or_frontend_behavior_exists() -> None:
    product_fields = {field.name for field in fields(OperationalProduct)}
    forbidden_terms = {
        "api",
        "database",
        "repository",
        "frontend",
        "endpoint",
    }

    assert not any(term in field_name for field_name in product_fields for term in forbidden_terms)
