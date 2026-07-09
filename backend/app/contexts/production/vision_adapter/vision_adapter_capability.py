from enum import StrEnum


class VisionAdapterCapability(StrEnum):
    REPORTS_TEXT_REGIONS = "reports_text_regions"
    REPORTS_SLIDE_CHANGES = "reports_slide_changes"
    REPORTS_IMAGE_CHANGES = "reports_image_changes"
    REPORTS_FACES = "reports_faces"
    REPORTS_MOTION = "reports_motion"
    REPORTS_SCREEN_TRANSITIONS = "reports_screen_transitions"
    REPORTS_CONFIDENCE = "reports_confidence"
    UNKNOWN = "unknown"
