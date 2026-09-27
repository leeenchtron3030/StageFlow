"""Pure, deterministic phrase matching and advisory Session placement."""
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .contracts import EditorialCandidateLocation, EditorialLocationConflictReason
from .derivation_contracts import (
    EditorialPhraseList,
    EditorialSessionBasis,
    EditorialTimingBasis,
    EditorialTranscriptSegment,
    EditorialTranscriptWord,
    normalize_phrase,
    word_tokens,
)


@dataclass(frozen=True, slots=True)
class PhraseMatch:
    normalized_phrase: str
    first_word: EditorialTranscriptWord
    last_word: EditorialTranscriptWord


def match_phrases(
    phrases: EditorialPhraseList, segment: EditorialTranscriptSegment,
) -> Iterator[PhraseMatch]:
    tokens = tuple(
        (token, word) for word in segment.words for token in word_tokens(word.text)
    )
    for phrase in phrases.phrases:
        expected = word_tokens(phrase)
        if not expected:
            continue
        position = 0
        while position + len(expected) <= len(tokens):
            end = position + len(expected)
            if tuple(token for token, _ in tokens[position:end]) == expected:
                yield PhraseMatch(
                    normalize_phrase(phrase), tokens[position][1], tokens[end - 1][1],
                )
                position = end
            else:
                position += 1


def location_conflict_reason(
    location: EditorialCandidateLocation,
    authoritative_start: datetime,
    authoritative_end: datetime | None,
) -> EditorialLocationConflictReason | None:
    """The existing declared-candidate boundary evaluation, shared without change."""
    start = location.session_authoritative_start + timedelta(
        microseconds=location.timeline_start_microseconds,
    )
    end = location.session_authoritative_start + timedelta(
        microseconds=(location.timeline_start_microseconds
                      if location.timeline_end_microseconds is None
                      else location.timeline_end_microseconds),
    )
    if end < authoritative_start or (
        authoritative_end is not None and start > authoritative_end
    ):
        return EditorialLocationConflictReason.EXCLUDED
    if start < authoritative_start or (
        authoritative_end is not None and end > authoritative_end
    ):
        return EditorialLocationConflictReason.PARTIALLY_EXCLUDED
    return None


def place_match(
    match: PhraseMatch, timing: EditorialTimingBasis, session: EditorialSessionBasis,
) -> EditorialCandidateLocation | None:
    if session.authoritative_start is None:
        return None
    offset = (timing.candidate_started_at.astimezone(UTC)
              - session.authoritative_start.astimezone(UTC))
    microseconds = ((offset.days * 86400 + offset.seconds) * 1_000_000
                    + offset.microseconds)
    start = microseconds + match.first_word.asset_start_microseconds
    if start < 0:
        return None
    return EditorialCandidateLocation(
        session.revision, start,
        microseconds + match.last_word.asset_end_microseconds,
        session.authoritative_start, session.authoritative_end,
    )
