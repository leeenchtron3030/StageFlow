"""Infrastructure-local inference values; importing these needs no optional runtime."""
from dataclasses import dataclass


@dataclass
class Word:
    word: str
    start: float
    end: float
    probability: float


@dataclass
class Segment:
    text: str
    start: float
    end: float
    words: list[Word] | None
