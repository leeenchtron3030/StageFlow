from enum import StrEnum


class VisualDetectionType(StrEnum):
    TEXT_REGION = "text_region"
    IMAGE_CHANGE = "image_change"
    SLIDE_CHANGE = "slide_change"
    FACE_REGION = "face_region"
    PERSON_REGION = "person_region"
    SCREEN_TRANSITION = "screen_transition"
    CAMERA_OBSTRUCTION = "camera_obstruction"
    CAMERA_MOTION = "camera_motion"
    BRIGHTNESS_CHANGE = "brightness_change"
    COLOR_CHANGE = "color_change"
    GRAPHIC_REGION = "graphic_region"
    UNKNOWN = "unknown"
