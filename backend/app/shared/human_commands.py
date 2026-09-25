"""Canonical digest used by synchronous human-command idempotency."""

import hashlib
import json


def human_command_digest(document: dict[str, object]) -> str:
    serialized = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
