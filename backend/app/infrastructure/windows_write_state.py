from __future__ import annotations

import ctypes
import ntpath
import sys
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from app.contexts.production.asset_readiness import (
    AssetWriteStateObservation,
    AssetWriteStateStatus,
)
from app.contexts.production.media_collection import (
    MediaObservationCollectionOutcome,
    MediaObservationCollectionRequest,
    MediaObservationCollectionResult,
)
from app.contexts.production.media_collection.ports import WriteStateObservationCollectionPort
from app.contexts.production.runtime import RuntimeObservationType
from app.shared.ids import EntityId
from app.shared.time import Clock

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080
ERROR_SHARING_VIOLATION = 32
DRIVE_REMOTE = 4
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
ASSESSMENT_MECHANISM = "windows-share-deny-write"


def write_state_supported() -> bool:
    return sys.platform == "win32"


class _WindowsCtypes(Protocol):
    """Platform-specific ctypes surface, accessed only on a supported host."""

    def WinDLL(self, name: str, *, use_last_error: bool) -> ctypes.CDLL: ...

    def get_last_error(self) -> int: ...

    def WinError(self, code: int) -> OSError: ...


_windows_ctypes = cast(_WindowsCtypes, ctypes)


class WindowsFileApi(Protocol):
    """Narrow injectable seam; a successful open transfers handle ownership."""

    def drive_type(self, root: str) -> int: ...

    def open_read_deny_write(self, path: str) -> int: ...

    def close(self, handle: int) -> None: ...


class CtypesWindowsFileApi:
    def __init__(self) -> None:
        if not write_state_supported():
            raise RuntimeError("windows_write_state_unsupported")
        kernel32 = _windows_ctypes.WinDLL("kernel32", use_last_error=True)
        self._open = kernel32.CreateFileW
        self._open.argtypes = (
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        )
        self._open.restype = wintypes.HANDLE
        self._close = kernel32.CloseHandle
        self._close.argtypes = (wintypes.HANDLE,)
        self._close.restype = wintypes.BOOL
        self._drive_type = kernel32.GetDriveTypeW
        self._drive_type.argtypes = (wintypes.LPCWSTR,)
        self._drive_type.restype = wintypes.UINT

    def drive_type(self, root: str) -> int:
        return int(self._drive_type(root))

    def open_read_deny_write(self, path: str) -> int:
        handle = self._open(
            path, GENERIC_READ, FILE_SHARE_READ, None,
            OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None,
        )
        if handle is None or handle == INVALID_HANDLE_VALUE:
            raise _windows_ctypes.WinError(_windows_ctypes.get_last_error())
        return int(handle)

    def close(self, handle: int) -> None:
        if not self._close(handle):
            raise _windows_ctypes.WinError(_windows_ctypes.get_last_error())


@dataclass(frozen=True, slots=True)
class WriteStateProbeResult:
    status: AssetWriteStateStatus
    limitations: tuple[str, ...] = ()


class WindowsWriteStateProbe:
    """One read-only open/close, with no content access, waiting, or retained handle."""

    def __init__(self, api: WindowsFileApi | None = None) -> None:
        if not write_state_supported():
            raise RuntimeError("windows_write_state_unsupported")
        self._api = api if api is not None else CtypesWindowsFileApi()

    def probe(self, resolved_path: Path) -> WriteStateProbeResult:
        path = str(resolved_path).replace("/", "\\")
        # Extended local paths also start with two slashes; distinguish UNC first.
        extended = path.startswith("\\\\?\\")
        if path.upper().startswith("\\\\?\\UNC\\") or (
            path.startswith("\\\\") and not extended
        ):
            return WriteStateProbeResult(
                AssetWriteStateStatus.UNKNOWN, ("write_state_network_path",)
            )
        drive, _ = ntpath.splitdrive(path[4:] if extended else path)
        if not drive:
            return WriteStateProbeResult(
                AssetWriteStateStatus.UNKNOWN, ("write_state_drive_unknown",)
            )
        try:
            drive_type = self._api.drive_type(drive + "\\")
            if drive_type == DRIVE_REMOTE:
                return WriteStateProbeResult(
                    AssetWriteStateStatus.UNKNOWN, ("write_state_network_path",)
                )
            if drive_type in (0, 1):
                return WriteStateProbeResult(
                    AssetWriteStateStatus.UNKNOWN, ("write_state_drive_unknown",)
                )
            try:
                handle = self._api.open_read_deny_write(path)
            except OSError as exc:
                if getattr(exc, "winerror", None) == ERROR_SHARING_VIOLATION:
                    return WriteStateProbeResult(AssetWriteStateStatus.ACTIVE)
                raise
            try:
                result = WriteStateProbeResult(AssetWriteStateStatus.INACTIVE)
            finally:
                self._api.close(handle)
            return result
        except OSError:
            # Never expose paths, OS messages, or unbounded error codes in facts.
            return WriteStateProbeResult(
                AssetWriteStateStatus.UNKNOWN, ("write_state_os_error",)
            )


class WindowsWriteStateObservationAdapter(WriteStateObservationCollectionPort):
    def __init__(
        self,
        *,
        probe: WindowsWriteStateProbe,
        resolve_path: Callable[[MediaObservationCollectionRequest], Path],
        observer_id: EntityId,
        clock: Clock,
    ) -> None:
        self._probe = probe
        self._resolve_path = resolve_path
        self._observer_id = observer_id
        self._clock = clock

    def collect_write_state_observation(
        self, request: MediaObservationCollectionRequest
    ) -> MediaObservationCollectionResult:
        if request.observation_type is not RuntimeObservationType.WRITE_STATE:
            raise ValueError("write_state_observation_type_required")
        started_at = self._clock.now()
        try:
            result = self._probe.probe(self._resolve_path(request))
        except OSError:
            result = WriteStateProbeResult(
                AssetWriteStateStatus.UNKNOWN, ("write_state_path_unavailable",)
            )
        observed_at = self._clock.now()
        observation = AssetWriteStateObservation(
            id=EntityId.new(),
            candidate_id=request.candidate_id,
            resource_id=request.resource_id,
            observed_at=observed_at,
            status=result.status,
            assessment_mechanism_id=ASSESSMENT_MECHANISM,
            observer_id=self._observer_id,
            source_runtime_id=request.runtime_id,
            limitations=result.limitations,
        )
        return MediaObservationCollectionResult(
            collection_request_id=request.collection_request_id,
            cycle_id=request.collection_cycle_id,
            candidate_id=request.candidate_id,
            resource_id=request.resource_id,
            observation_type=request.observation_type,
            port_id=self._observer_id,
            outcome=MediaObservationCollectionOutcome.COLLECTED,
            observations=(observation,),
            limitations=result.limitations,
            started_at=started_at,
            completed_at=observed_at,
        )
