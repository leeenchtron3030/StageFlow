"""Pure cue composition and immutable, first-class publication provenance."""
import re
from dataclasses import asdict, dataclass
from datetime import datetime

from app.contexts.editorial.derivation_contracts import word_tokens
from app.shared.human_commands import human_command_digest
from app.shared.ids import EntityId
from app.shared.time import require_aware_datetime

from .contracts import Reference
from .cue_catalog import BOUNDARY_CUE_CATALOG, BoundaryCueCatalog, CueRole, validate_phrases

START_KEY = "boundary-cues-start"
END_KEY = "boundary-cues-end"


class CueListSizeError(ValueError):
    def __init__(self, role: str, count: int) -> None:
        self.code = "cue_list_empty" if count == 0 else "cue_list_too_large"
        self.role, self.count = role, count
        super().__init__(f"{self.code}: {role} count={count}")


@dataclass(frozen=True, slots=True)
class PhraseChoice:
    group_key: str
    phrase: str


@dataclass(frozen=True, slots=True)
class CustomPhrase:
    text: str
    role: CueRole

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", CueRole(self.role))
        if self.role == CueRole.SEGMENT:
            raise ValueError("custom_segment_refused")
        validate_phrases((self.text,))
        object.__setattr__(self, "text", self.text.strip())


@dataclass(frozen=True, slots=True)
class CompositionRequest:
    catalog_version: int
    group_keys: tuple[str, ...]
    profile_key: str | None = None
    include: tuple[PhraseChoice, ...] = ()
    exclude: tuple[PhraseChoice, ...] = ()
    custom_phrases: tuple[CustomPhrase, ...] = ()

    def __post_init__(self) -> None:
        for name, limit in (("group_keys", 20), ("include", 400), ("exclude", 400),
                            ("custom_phrases", 400)):
            values = tuple(getattr(self, name))
            object.__setattr__(self, name, values)
            if len(values) > limit:
                raise ValueError(f"{name}_too_large")
            if name != "custom_phrases" and len(set(values)) != len(values):
                raise ValueError(f"duplicate_{name}")


@dataclass(frozen=True, slots=True)
class GroupReference:
    key: str
    version: int


@dataclass(frozen=True, slots=True)
class SegmentPhrase:
    text: str
    source_group: str


@dataclass(frozen=True, slots=True)
class ComposedCues:
    groups: tuple[GroupReference, ...]
    start: tuple[str, ...]
    end: tuple[str, ...]
    segments: tuple[SegmentPhrase, ...]

    def __post_init__(self) -> None:
        for name in ("groups", "start", "end", "segments"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


def compose(request: CompositionRequest,
            catalog: BoundaryCueCatalog = BOUNDARY_CUE_CATALOG) -> ComposedCues:
    if type(request.catalog_version) is not int or request.catalog_version != catalog.version:
        raise ValueError("unknown_catalog_version")
    if request.profile_key is not None and not any(
            p.key == request.profile_key for p in catalog.profiles):
        raise ValueError("unknown_profile")
    groups = {g.key: g for g in catalog.groups}
    if not set(request.group_keys) <= groups.keys():
        raise ValueError("unknown_group")
    for choices, expected_default in ((request.include, False), (request.exclude, True)):
        for choice in choices:
            group = groups.get(choice.group_key)
            if group is None or choice.group_key not in request.group_keys:
                raise ValueError("unknown_choice_group")
            phrase = next((p for p in group.phrases if p.text == choice.phrase), None)
            if phrase is None:
                raise ValueError("unknown_phrase_choice")
            if phrase.default != expected_default:
                raise ValueError("choice_default_mismatch")
    included, excluded = set(request.include), set(request.exclude)
    merged: dict[tuple[str, ...], tuple[str, set[CueRole]]] = {}
    segments: list[SegmentPhrase] = []
    selected: list[GroupReference] = []

    def add(text: str, role: CueRole) -> None:
        _, roles = merged.setdefault(word_tokens(text), (text, set()))
        roles.add(role)

    for group in catalog.groups:
        if group.key not in request.group_keys:
            continue
        selected.append(GroupReference(group.key, group.version))
        for phrase in group.phrases:
            choice = PhraseChoice(group.key, phrase.text)
            if (phrase.default and choice not in excluded) or choice in included:
                if phrase.role == CueRole.SEGMENT:
                    segments.append(SegmentPhrase(phrase.text, group.key))
                add(phrase.text, phrase.role)
    for custom in request.custom_phrases:
        add(custom.text, custom.role)
    start = tuple(text for text, roles in merged.values()
                  if roles & {CueRole.START, CueRole.CHANGEOVER})
    end = tuple(text for text, roles in merged.values()
                if roles & {CueRole.END, CueRole.CHANGEOVER})
    for role, phrases in (("start", start), ("end", end)):
        if not 1 <= len(phrases) <= 200:
            raise CueListSizeError(role, len(phrases))
        validate_phrases(phrases)
    return ComposedCues(tuple(selected), start, end, tuple(segments))


@dataclass(frozen=True, slots=True)
class BoundaryCueComposition:
    event_id: EntityId
    version: int
    command_id: EntityId
    request_digest: str
    catalog_id: str
    catalog_version: int
    catalog_digest: str
    profile_key: str | None
    groups: tuple[GroupReference, ...]
    include: tuple[PhraseChoice, ...]
    exclude: tuple[PhraseChoice, ...]
    custom_phrases: tuple[CustomPhrase, ...]
    segment_phrases: tuple[SegmentPhrase, ...]
    composed_by: EntityId
    composed_at: datetime
    start_cue_list: Reference
    end_cue_list: Reference

    def __post_init__(self) -> None:
        for name in ("groups", "include", "exclude", "custom_phrases", "segment_phrases"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        require_aware_datetime(self.composed_at, "composed_at")
        if not 1 <= self.version <= 2_147_483_647 or self.catalog_version < 1:
            raise ValueError("invalid composition version")
        if any(re.fullmatch(r"[0-9a-f]{64}", d) is None
               for d in (self.request_digest, self.catalog_digest)):
            raise ValueError("invalid composition digest")


def request_digest(event: EntityId, actor: EntityId, request: CompositionRequest) -> str:
    return human_command_digest({"event_id": event.value, "composed_by": actor.value,
                                 "request": asdict(request)})


def composition_document(value: BoundaryCueComposition) -> dict[str, object]:
    return {**asdict(value), "event_id": value.event_id.value,
            "command_id": value.command_id.value, "composed_by": value.composed_by.value,
            "start_cue_list": {"id": value.start_cue_list.id.value,
                               "version": value.start_cue_list.revision},
            "end_cue_list": {"id": value.end_cue_list.id.value,
                             "version": value.end_cue_list.revision}}
