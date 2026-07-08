from enum import StrEnum


class MediaArtifactType(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    CAPTION = "caption"
    TRANSCRIPT = "transcript"
    METADATA = "metadata"
    LOG = "log"
    MANIFEST = "manifest"
    UNKNOWN = "unknown"
