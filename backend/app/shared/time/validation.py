from __future__ import annotations

from datetime import UTC, datetime


def require_aware_datetime(value: datetime, field_name: str) -> datetime:
    """Reject ambiguous wall-clock values at authoritative contract boundaries."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
    return value


def parse_aware_datetime(value: object) -> datetime | None:
    """Parse an already-zoned timestamp without inventing a source timezone."""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def normalize_utc_datetime(value: datetime, field_name: str) -> datetime:
    """Normalize a proven-aware timestamp to the canonical persistence timezone."""

    return require_aware_datetime(value, field_name).astimezone(UTC)
