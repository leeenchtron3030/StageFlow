from enum import StrEnum


class RuntimeProfile(StrEnum):
    AGENT = "agent"
    NODE = "node"
    EXTERNAL_COMPATIBLE = "external_compatible"
    DEVELOPMENT = "development"
    UNKNOWN = "unknown"
