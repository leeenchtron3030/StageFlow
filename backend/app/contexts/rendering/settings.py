"""Pure Event render setting commands and version checks."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.shared.human_commands import human_command_digest
from app.shared.ids import EntityId
from app.shared.time import Clock
from app.shared.time.validation import require_aware_datetime

from .contracts import (
    RenderActor,
    RenderAdjustments,
    RenderError,
    RenderReason,
    normalize_adjustments,
    render_preset,
)


@dataclass(frozen=True, slots=True)
class EventRenderSetting:
    event_id: EntityId
    version: int
    profile_id: str
    profile_version: str
    adjustments: RenderAdjustments
    command_id: EntityId
    request_digest: str
    selected_by: EntityId
    selected_at: datetime

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version <= 0:
            raise ValueError("render_setting_version_invalid")
        require_aware_datetime(self.selected_at, "selected_at")
        object.__setattr__(self, "adjustments", normalize_adjustments(
            render_preset(self.profile_id, self.profile_version), self.adjustments))


@dataclass(frozen=True, slots=True)
class ChooseRenderSetting:
    event_id: EntityId
    profile_id: str
    profile_version: str
    adjustments: RenderAdjustments
    actor: RenderActor
    command_id: EntityId
    expected_version: int | None

    def __post_init__(self) -> None:
        if self.actor.authority_kind != "human":
            raise RenderError(RenderReason.HUMAN_REQUIRED)
        if self.expected_version is not None and (
            type(self.expected_version) is not int or self.expected_version <= 0
        ):
            raise ValueError("render_setting_version_invalid")
        object.__setattr__(self, "adjustments", normalize_adjustments(
            render_preset(self.profile_id, self.profile_version), self.adjustments))

    @property
    def digest(self) -> str:
        return human_command_digest({
            "kind": "choose_render_setting", "event_id": self.event_id.value,
            "profile_id": self.profile_id, "profile_version": self.profile_version,
            "video_bit_rate": self.adjustments.video_bit_rate,
            "audio_bit_rate": self.adjustments.audio_bit_rate,
            "actor_id": self.actor.id.value, "authority": self.actor.authority_kind,
            "expected_version": self.expected_version,
        })


class RenderSettingsRepository(Protocol):
    def choose_setting(self, command: ChooseRenderSetting, now: datetime) -> EventRenderSetting: ...

    def setting_history(self, event_id: EntityId) -> tuple[EventRenderSetting, ...]: ...


@dataclass(slots=True)
class RenderSettingsService:
    repository: RenderSettingsRepository
    clock: Clock

    def choose(self, command: ChooseRenderSetting) -> EventRenderSetting:
        return self.repository.choose_setting(command, self.clock.now())

    def history(self, event_id: EntityId) -> tuple[EventRenderSetting, ...]:
        return self.repository.setting_history(event_id)
