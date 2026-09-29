"""Accepted, offline boundary vocabulary. No evidence counts imply a guarantee."""
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.contexts.editorial.derivation_contracts import EditorialPhraseList
from app.shared.human_commands import human_command_digest
from app.shared.ids import EntityId


class CueRole(StrEnum):
    START = "start"
    END = "end"
    CHANGEOVER = "changeover"
    SEGMENT = "segment"


def validate_phrases(phrases: tuple[str, ...]) -> None:
    """Reuse the published-list rules without generating identity or reading a clock."""
    identity = EntityId("00000000-0000-0000-0000-000000000000")
    EditorialPhraseList(identity, identity, "validation", 1, "Validation", phrases,
                        identity, datetime(2000, 1, 1, tzinfo=UTC))


@dataclass(frozen=True, slots=True)
class CuePhrase:
    text: str
    role: CueRole
    default: bool
    evidence: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", CueRole(self.role))
        validate_phrases((self.text,))
        if type(self.default) is not bool or not self.evidence.strip():
            raise ValueError("invalid cue phrase attributes")


@dataclass(frozen=True, slots=True)
class CueGroup:
    key: str
    name: str
    category: str
    phrases: tuple[CuePhrase, ...]
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "phrases", tuple(self.phrases))
        if not self.key or not self.name or not self.category or self.version != 1:
            raise ValueError("invalid cue group")
        validate_phrases(tuple(p.text for p in self.phrases))


@dataclass(frozen=True, slots=True)
class EventProfile:
    key: str
    name: str
    group_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "group_keys", tuple(self.group_keys))
        if not self.key or not self.name or len(set(self.group_keys)) != len(self.group_keys):
            raise ValueError("invalid event profile")


@dataclass(frozen=True, slots=True)
class BoundaryCueCatalog:
    groups: tuple[CueGroup, ...]
    profiles: tuple[EventProfile, ...]
    id: str = "boundary-cue-catalog"
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "groups", tuple(self.groups))
        object.__setattr__(self, "profiles", tuple(self.profiles))
        keys = {g.key for g in self.groups}
        if len(keys) != len(self.groups):
            raise ValueError("duplicate group key")
        if len({p.key for p in self.profiles}) != len(self.profiles):
            raise ValueError("duplicate profile key")
        if any(not set(p.group_keys) <= keys for p in self.profiles):
            raise ValueError("unknown profile group")

    @property
    def digest(self) -> str:
        return human_command_digest(asdict(self))


_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
          "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
          "eighteen", "nineteen", "twenty")


def _phrases(rows: tuple[tuple[str, str, bool, str], ...]) -> tuple[CuePhrase, ...]:
    result: list[CuePhrase] = []
    for text, role, default, evidence in rows:
        texts = (text,) if "{n}" not in text else tuple(
            text.replace("{n}", n) for digit, word in enumerate(_WORDS, 1)
            for n in (str(digit), word))
        result.extend(CuePhrase(t, CueRole(role), default, evidence) for t in texts)
    return tuple(result)


BOUNDARY_CUE_CATALOG = BoundaryCueCatalog(
    groups=(
        CueGroup('conference.mc-handoffs', 'Conference: MC handoffs',
                 'Conference and keynote stage', _phrases((
                     ('please join me in welcoming', 'changeover', True, 'M 10/10'),
                     ('please welcome', 'changeover', True, 'M 10/10'),
                     ('next speaker', 'changeover', True, 'M 13/13'),
                     ('please give a warm welcome', 'changeover', True, 'M 2/2'),
                     ('warm welcome', 'changeover', True, 'M 2/2'),
                     ('welcome to the stage', 'changeover', True, 'M 2/2'),
                     ('round of applause', 'changeover', True, 'M 3/3'),
                     ("let's hear it for", 'changeover', True, 'M 2/2'),
                     ('thank you so much', 'changeover', True, 'M 24/26'),
                     ('thank you very much', 'changeover', True, 'M 9/10'),
                     ('thanks so much', 'changeover', True, 'M 2/2'),
                     ('give it up for', 'changeover', True, 'R [14]'),
                     ('put your hands together', 'changeover', True, 'R [14]'),
                     ('without further ado', 'changeover', True,
                      'M 0/2 (said earlier in the changeover), R [14]'),
                     ('please join me in thanking', 'changeover', True, 'R [15]'),
                     ('ladies and gentlemen', 'changeover', False, 'M 1/3 ⚠'),
                 ))),
        CueGroup('conference.speaker-openings', 'Conference: Speaker openings',
                 'Conference and keynote stage', _phrases((
                     ('good morning', 'start', True, 'M 7/7'),
                     ('good afternoon', 'start', True, 'R [14]'),
                     ('good evening', 'start', True, 'M 1/1'),
                     ('hi everyone', 'start', True, 'M 3/3'),
                     ('hello everyone', 'start', True, 'M 2/2'),
                     ('welcome everyone', 'start', True, 'M 1/1'),
                     ('my name is', 'start', True, 'M 4/5'),
                     ('a pleasure to be here', 'start', True, 'M 2/2'),
                     ('great to be here', 'start', True, 'M 1/1'),
                     ('excited to be here', 'start', True, 'M 1/1'),
                     ("it's an honor", 'start', True, 'M 1/1'),
                     ('thank you for having me', 'start', True, 'R [13]'),
                     ('thanks for having me', 'start', True, 'R [13]'),
                     ('today i want to talk', 'start', True, 'M 1/1'),
                     ("today i'm going to", 'start', True, 'M 1/1'),
                     ("let's get started", 'start', True, 'M 1/1, R [12]'),
                     ('welcome to', 'start', False, 'M 7/8 ⚠ (short, generic)'),
                 ))),
        CueGroup('conference.speaker-closings', 'Conference: Speaker closings',
                 'Conference and keynote stage', _phrases((
                     ('thanks everyone', 'end', True, 'M 2/2'),
                     ('thank you all', 'end', True, 'M 3/4'),
                     ('thank you everyone', 'end', True, 'M 0/1'),
                     ('thank you for your attention', 'end', True, 'M 0/1, R'),
                     ('thank you for listening', 'end', True, 'R'),
                     ('in conclusion', 'end', True, 'M 1/1'),
                     ('to conclude', 'end', True, 'M 1/1'),
                     ('wrapping up', 'end', True, 'M 1/1'),
                     ('key takeaways', 'end', True, 'M 1/1'),
                     ("that's all i have", 'end', True, 'R'),
                     ("that's it for me", 'end', True, 'R'),
                     ('find me afterwards', 'end', True, 'R'),
                     ('any questions', 'end', False, 'M 4/11 ⚠'),
                     ('see you', 'end', False, 'M 5/9 ⚠'),
                 ))),
        CueGroup('conference.breaks', 'Conference: Breaks and returns',
                 'Conference and keynote stage', _phrases((
                     ('welcome back', 'start', True, 'M 4/5'),
                     ('lunch break', 'end', True, 'M 1/1'),
                     ('short break', 'end', True, 'M 1/1'),
                     ('coffee break', 'end', True, 'R'),
                     ("we'll be back", 'end', True, 'R'),
                     ('enjoy your lunch', 'end', True, 'R'),
                 ))),
        CueGroup('panels', 'Panels and moderated sessions',
                 'Panels and moderated sessions', _phrases((
                     ('our panelists', 'start', True, 'M 1/1, R [15]'),
                     ('our moderator', 'start', True, 'M 1/1'),
                     ('please welcome our panel', 'changeover', True, 'R [15]'),
                     ('let me introduce our panelists', 'start', True, 'R [15]'),
                     ('open it up to the audience', 'segment', True, 'R [15]'),
                     ('time for a few audience questions', 'segment', True, 'R [15]'),
                     ('please join me in thanking our panel', 'end', True, 'R [15]'),
                     ('thank our panelists', 'end', True, 'R [15]'),
                 ))),
        CueGroup('civic.open-close', 'Civic: opening and adjournment',
                 'Civic and government meetings', _phrases((
                     ('call this meeting to order', 'start', True, 'R [2]'),
                     ('called to order', 'start', True, 'R [2]'),
                     ('roll call', 'start', True, 'R [2]'),
                     ('pledge of allegiance', 'start', True, 'R [2]'),
                     ('we are in recess', 'end', True, 'R [2]'),
                     ('reconvene', 'start', True, 'R [2]'),
                     ('meeting is adjourned', 'end', True, 'R [2]'),
                     ('meeting stands adjourned', 'end', True, 'R [2]'),
                     ('motion to adjourn', 'end', True, 'R [2]'),
                 ))),
        CueGroup('civic.agenda', 'Civic: agenda items',
                 'Civic and government meetings', _phrases((
                     ('next item on the agenda', 'changeover', True, 'R [2]'),
                     ('moving on to item', 'changeover', True, 'R [2]'),
                     ('public comment', 'segment', True, 'R [2]'),
                     ('state your name and address', 'segment', True, 'R [2]'),
                     ('all those in favor', 'segment', True, 'R [2]'),
                     ('the motion carries', 'segment', True, 'R [2]'),
                 ))),
        CueGroup('arena.pa', 'Arena and public address',
                 'Arena, sports and public address', _phrases((
                     ('good evening ladies and gentlemen', 'start', True, 'R [6]'),
                     ('welcome to', 'start', False, 'R [6] ⚠'),
                     ('starting lineups', 'segment', True, 'R [6]'),
                     ('halftime', 'segment', True, 'R [6]'),
                     ('final score', 'end', True, 'R [6]'),
                     ('thank you for coming', 'end', True, 'R [6]'),
                     ('drive home safely', 'end', True, 'R [6]'),
                 ))),
        CueGroup('arena.anthem', 'Anthem and ceremonies',
                 'Arena, sports and public address', _phrases((
                     ('please rise', 'start', True, 'R [6]'),
                     ('remove your hats', 'start', True, 'R [6]'),
                     ('national anthem', 'segment', True, 'R [6]'),
                     ('moment of silence', 'segment', True, 'R [6]'),
                 ))),
        CueGroup('community.anchoring', 'Community: dignitaries and anchoring',
                 'Community and cultural events', _phrases((
                     ('respected dignitaries', 'start', True, 'R [4]'),
                     ('esteemed guests', 'start', True, 'R [4]'),
                     ('chief guest', 'segment', True, 'R [4]'),
                     ('lighting of the lamp', 'segment', True, 'R [4]'),
                     ('light the ceremonial lamp', 'segment', True, 'R [4]'),
                     ('i now call upon', 'changeover', True, 'R [4]'),
                     ('i would like to invite', 'changeover', True, 'R [4]'),
                     ('may i request', 'changeover', True, 'R [4]'),
                     ('vote of thanks', 'end', True, 'R [4]'),
                     ('felicitation', 'segment', True, 'R [4]'),
                 ))),
        CueGroup('press', 'Press conferences and media briefings',
                 'Press conferences and media briefings', _phrases((
                     ('thank you all for coming', 'start', True, 'R [3]'),
                     ('open the floor to questions', 'segment', True, 'R [3]'),
                     ("we'll take a few questions", 'segment', True, 'R [3]'),
                     ('last question', 'end', True, 'R [3]'),
                     ("that's all the time we have", 'end', True, 'R [3]'),
                     ('thank you everyone for attending', 'end', True, 'R [3]'),
                 ))),
        CueGroup('interviews', 'Interviews, junkets and podcasts',
                 'Interviews, junkets and podcasts', _phrases((
                     ('welcome to the show', 'start', True, 'R [13]'),
                     ('my guest today', 'start', True, 'R [13]'),
                     ('joining me today', 'start', True, 'R [13]'),
                     ('thanks for joining us', 'start', True, 'R [13]'),
                     ('thanks for having me', 'start', True, 'R [13]'),
                     ('where can people find you', 'end', True, 'R [13]'),
                     ('thanks for coming in', 'end', True, 'R [13]'),
                     ('thanks for coming on', 'end', True, 'R [13]'),
                     ('thanks for talking with us', 'end', True, 'R [13]'),
                     ("that's all the time we have", 'end', True, 'R [3] [13]'),
                 ))),
        CueGroup('broadcast', 'Broadcast and live stream',
                 'Broadcast and live stream', _phrases((
                     ("we're live", 'start', True, 'R [5]'),
                     ('welcome back', 'start', True, 'M 4/5'),
                     ('stand by', 'segment', True, 'R [5]'),
                     ("we'll be right back", 'end', True, 'R [5]'),
                     ('stay with us', 'end', True, 'R [5]'),
                     ('after the break', 'end', True, 'R [5]'),
                     ("we're clear", 'end', True, 'R [5]'),
                     ("we're off air", 'end', True, 'R [5]'),
                 ))),
        CueGroup('studio.setups', 'Studio: setups',
                 'Film and studio set', _phrases((
                     ("picture's up", 'start', True, 'R [16]'),
                 ))),
        CueGroup('studio.takes', 'Studio: slate and takes',
                 'Film and studio set', _phrases((
                     ('quiet on set', 'segment', True, 'R [1]'),
                     ('roll sound', 'segment', True, 'R [1]'),
                     ('sound speed', 'segment', True, 'R [1]'),
                     ('camera speed', 'segment', True, 'R [1]'),
                     ('rolling', 'segment', True, 'R [1], M 0/2 on stage ⚠'),
                     ('speed', 'segment', True, 'R [1], M 0/6 on stage ⚠'),
                     ('mark it', 'segment', True, 'R [1]'),
                     ('take {n}', 'segment', True, 'R [1]'),
                     ('scene {n}', 'segment', True, 'R [1]'),
                     ('action', 'segment', True, 'R [1], M 1/10 on stage ⚠'),
                     ('cut', 'segment', True, 'R [1], M 1/4 on stage ⚠'),
                     ('back to one', 'segment', True, 'R [1]'),
                     ('reset', 'segment', True, 'R [1], M 0/4 on stage ⚠'),
                     ('check the gate', 'segment', True, 'R [1]'),
                 ))),
        CueGroup('studio.wraps', 'Studio: wraps',
                 'Film and studio set', _phrases((
                     ('moving on', 'end', True, 'R [1], M 1/6 on stage ⚠'),
                     ("that's a wrap", 'end', True, 'R [1]'),
                     ("that's lunch", 'end', True, 'R [1]'),
                     ("we're wrapped", 'end', True, 'R [1]'),
                 ))),
        CueGroup('virtual', 'Webinar and virtual',
                 'Webinar and virtual', _phrases((
                     ('a few minutes for people to join', 'changeover', True, 'R [12]'),
                     ("let's get started", 'start', True, 'M 1/1, R [12]'),
                     ('can everyone see my screen', 'start', True, 'R [12]'),
                     ('can you see my screen', 'start', True, 'R [12]'),
                     ('the recording will be shared', 'end', True, 'R [12]'),
                     ('thank you for joining', 'end', True, 'R [12]'),
                     ("you're on mute", 'segment', False, 'R [12] ⚠ (said at any time)'),
                 ))),
        CueGroup('tech.pitch', 'Tech: pitch and demo day',
                 'Tech: pitch and demo day', _phrases((
                     ('our next team', 'changeover', True, 'R [10]'),
                     ('next up we have', 'changeover', True, 'R [10]'),
                     ('you have three minutes', 'start', True, 'R [10]'),
                     ("time's up", 'end', True, 'R [10]'),
                     ('questions from the judges', 'segment', True, 'R [10]'),
                     ('live demo', 'segment', True, 'R [10], M 0'),
                     ('let me show you', 'segment', False, 'R [10], M 0 ⚠'),
                     ('demo', 'segment', False, 'M 1/14 ⚠'),
                 ))),
        CueGroup('regional.au-nz', 'Australia and New Zealand',
                 'Regional add-ons (never pre-ticked)', _phrases((
                     ('traditional custodians', 'start', True, 'R [7]'),
                     ('traditional owners', 'start', True, 'R [7]'),
                     ('elders past and present', 'start', True, 'R [7]'),
                     ('kia ora', 'start', True, 'R'),
                     ("g'day", 'start', True, 'R'),
                 ))),
        CueGroup('regional.uk-ie', 'UK and Ireland',
                 'Regional add-ons (never pre-ticked)', _phrases((
                     ('cheers everyone', 'end', True, 'R'),
                     ('lovely to be here', 'start', True, 'R'),
                     ('cheers', 'end', False, 'R ⚠ (said at any time)'),
                     ('brilliant', 'end', False, 'M 2/5 ⚠'),
                 ))),
        CueGroup('regional.south-asia', 'South Asian English',
                 'Regional add-ons (never pre-ticked)', _phrases((
                     ('good morning to one and all', 'start', True, 'R [4]'),
                     ('a very warm welcome', 'changeover', True, 'R [4]'),
                     ('namaste', 'start', True, 'R [4]'),
                 ))),
    ),
    profiles=(
        EventProfile('conference',
                     'Conference stage',
                     ('conference.mc-handoffs', 'conference.speaker-openings',
                      'conference.speaker-closings', 'conference.breaks')),
        EventProfile('tech',
                     'Tech conference and meetup',
                     ('conference.mc-handoffs', 'conference.speaker-openings',
                      'conference.speaker-closings', 'conference.breaks',
                      'tech.pitch')),
        EventProfile('panels',
                     'Panel or moderated session',
                     ('panels', 'conference.mc-handoffs', 'conference.speaker-closings')),
        EventProfile('civic',
                     'Civic or government meeting',
                     ('civic.open-close', 'civic.agenda')),
        EventProfile('arena',
                     'Arena, sports or large public event',
                     ('arena.pa', 'arena.anthem')),
        EventProfile('community',
                     'Community and cultural event (Commonwealth/South Asian formal English)',
                     ('community.anchoring', 'conference.mc-handoffs',
                      'conference.speaker-closings')),
        EventProfile('press',
                     'Press conference or media briefing',
                     ('press',)),
        EventProfile('interviews',
                     'Interview, junket or podcast',
                     ('interviews',)),
        EventProfile('broadcast',
                     'Broadcast or live stream',
                     ('broadcast',)),
        EventProfile('studio',
                     'Film or studio set',
                     ('studio.setups', 'studio.takes', 'studio.wraps')),
        EventProfile('virtual',
                     'Webinar or virtual event',
                     ('virtual',)),
    ),
)
