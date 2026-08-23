"""Compatibility exports for the original Demo Editorial Moment module."""

from .contracts import DeclareEditorialMoment, EditorialCandidateMoment
from .repository import (
    EditorialMomentConflictError,
    EditorialMomentNotFoundError,
    EditorialMomentRepository,
    EditorialMomentStorageUnavailableError,
)
from .service import EditorialMomentService

__all__ = [
    "DeclareEditorialMoment",
    "EditorialCandidateMoment",
    "EditorialMomentConflictError",
    "EditorialMomentNotFoundError",
    "EditorialMomentRepository",
    "EditorialMomentService",
    "EditorialMomentStorageUnavailableError",
]
