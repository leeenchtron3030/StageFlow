from enum import StrEnum


class CompletedMediaAssetKind(StrEnum):
    RECORDING_SEGMENT = "recording_segment"
    COMPLETE_RECORDING = "complete_recording"
    MEDIA_CLIP = "media_clip"
    AUDIO_RECORDING = "audio_recording"
    VIDEO_RECORDING = "video_recording"
    OTHER_SUPPORTED_MEDIA = "other_supported_media"
    UNKNOWN = "unknown"
