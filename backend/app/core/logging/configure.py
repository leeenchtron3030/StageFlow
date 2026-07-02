import logging

from app.core.config.settings import Settings


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=settings.log_level)
