from enum import StrEnum


class ScheduledActivityType(StrEnum):
    PRESENTATION = "presentation"
    PANEL = "panel"
    WORKSHOP = "workshop"
    ANNOUNCEMENT = "announcement"
    MUSIC = "music"
    FILM = "film"
    CEREMONY = "ceremony"
    NETWORKING = "networking"
    MEAL = "meal"
    BREAK = "break"
    CUSTOM = "custom"
    UNKNOWN = "unknown"
