"""Contained local bytes; persisted identities are opaque keys and hashes only."""
import hashlib
import os
import re
import stat
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.contexts.assembly.contracts import ExternalContent
from app.contexts.rendering.contracts import RenderError, RenderReason


def safe_path(path: Path, *, directory: bool = False) -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise RenderError(RenderReason.INPUT_MISSING)
    try:
        for part in (*reversed(path.parents), path):
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise RenderError(RenderReason.INPUT_MISSING)
        resolved = path.resolve(strict=True)
        if (directory and not resolved.is_dir()) or (not directory and not resolved.is_file()):
            raise RenderError(RenderReason.INPUT_MISSING)
        return resolved
    except OSError:
        raise RenderError(RenderReason.INPUT_MISSING, retryable=True) from None


def digest_file(path: Path) -> tuple[str, int]:
    with safe_path(path).open("rb") as handle:
        before = os.fstat(handle.fileno())
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
        after = os.fstat(handle.fileno())
    current = safe_path(path).stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
    ) or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
        current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns
    ):
        raise RenderError(RenderReason.HASH_MISMATCH)
    return digest, after.st_size


class PackagingContentResolver:
    def __init__(self, root: Path) -> None:
        self.root = safe_path(root, directory=True)

    def resolve(self, content: ExternalContent) -> Path:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}", content.content_key) is None:
            raise RenderError(RenderReason.INPUT_MISSING)
        root = safe_path(self.root, directory=True)
        path = safe_path(root / content.content_key)
        if not path.is_relative_to(root):
            raise RenderError(RenderReason.INPUT_MISSING)
        if digest_file(path) != (content.sha256, content.byte_size):
            raise RenderError(RenderReason.HASH_MISMATCH)
        return path


@dataclass(frozen=True, slots=True)
class StoredContent:
    key: str
    sha256: str
    byte_size: int


class OutputStore:
    def __init__(self, root: Path) -> None:
        self.root = safe_path(root, directory=True)
        self.temp = self.root / ".tmp"
        self.temp.mkdir(exist_ok=True)
        safe_path(self.temp, directory=True)

    def validate(self) -> None:
        root = safe_path(self.root, directory=True)
        if not safe_path(self.temp, directory=True).is_relative_to(root):
            raise RenderError(RenderReason.STORE_UNAVAILABLE)

    @contextmanager
    def temporary(self, suffix: str) -> Generator[Path]:
        self.validate()
        path = self.temp / (uuid4().hex + suffix)
        try:
            with path.open("xb"):
                pass
            yield path
        finally:
            self.validate()
            path.unlink(missing_ok=True)

    def publish(self, temporary: Path) -> StoredContent:
        self.validate()
        path = safe_path(temporary)
        if path.parent != self.temp:
            raise RenderError(RenderReason.STORE_UNAVAILABLE)
        digest, size = digest_file(path)
        if not size:
            raise RenderError(RenderReason.OUTPUT_INVALID)
        descriptor = os.open(path, os.O_RDWR | getattr(os, "O_BINARY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        key = uuid4().hex
        self.validate()
        # UUID identity and rename (not replace) avoid overwriting prior Windows outputs.
        path.rename(self.root / key)
        return StoredContent(key, digest, size)

    def discard_unregistered(self, content: StoredContent) -> None:
        self.validate()
        if re.fullmatch(r"[a-f0-9]{32}", content.key) is None:
            raise RenderError(RenderReason.STORE_UNAVAILABLE)
        (self.root / content.key).unlink(missing_ok=True)
