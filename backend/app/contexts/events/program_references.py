"""Read compatibility for persisted program references (ADR-0031).

Remove legacy aliases only when retained current and historical records no longer
depend on them and all writers use neutral keys. No persisted history is rewritten.
"""

from collections.abc import Mapping
from typing import Literal

_LEGACY_KEYS = {
    "external_session_id": "devcon_session_id",
    "external_event_id": "devcon_event_id",
    "external_room_id": "devcon_room_id",
}


def program_reference(
    references: Mapping[str, str],
    key: Literal["external_session_id", "external_event_id", "external_room_id"],
) -> str | None:
    return references.get(key, references.get(_LEGACY_KEYS[key]))
