# Cue phrase catalog v1 (proposal)

## Status

**Accepted v1.0** (owner, 2026-09-29), with the decisions recorded under *Owner decisions*.

- This is the proposed content for the ADR-0034 Phase 2d-1 preset catalog
  ([plan](../plans/session-boundary-suggestions.md)).
- It replaces the short example table in that plan section.
- It does not implement anything. The catalog ships in code under ED-0107.

## Purpose

- A producer builds the boundary cue lists for an Event by choosing an **event profile**,
  which is a starter set of phrase groups.
- They can then add or remove **groups**, remove individual phrases, and add **custom
  phrases**.
- The result feeds Session suggestions:
  - **Today:** cue support and tie-breaks in policy v3.
  - **Later:** cue edges in policy v4 (Phase 2d-2).

## How a producer uses it

1. **Pick a profile** on the Event page, for example *Conference stage* or *Press
   conference*. Its default groups are pre-ticked.
2. **Adjust groups:**
   - Tick or untick any group from any category. Profiles are only starting points.
   - Groups marked **opt-in** are never pre-ticked, because they are noisy in other
     contexts.
3. **Review the aggregate:**
   - Phrases are grouped by role (start, end, changeover, segment).
   - Each phrase shows a source badge (the group, or *custom*) and an evidence badge (see
     below).
   - Duplicates across groups are merged.
4. **Refine:**
   - Remove individual phrases.
   - Add custom phrases to any role: a speaker's catch-phrase, a sponsor line, a local
     greeting.
5. **Publish:**
   - Start and changeover phrases go into the Event's start cue list, and end and
     changeover phrases go into its end cue list. These are ED-0092 phrase lists, at most
     200 phrases each.
   - The composition is recorded as provenance.

## Roles

| Role | Meaning | Used as |
| --- | --- | --- |
| `start` | Said at, or just after, the start of a Session: a speaker's greeting | a start cue |
| `end` | Said at, or just before, the end of a Session: a speaker's closing thanks | an end cue |
| `changeover` | Said **between** Sessions, typically by an MC. It closes one Session and introduces the next | both a start and an end cue for the same changeover |
| `segment` | Marks a part **inside** a Session (owner decision 2026-09-29: a studio take is a segment inside a Session, and a series of takes is repeated passes at the same content) | stored for later Segment work. **Never a Session edge**, so it is not published to the start or end lists in v1 |

## Evidence badges

- **M a/b: measured on the conference corpus.**
  - What was measured: 112 transcribed recorder blocks, three days, one main stage, and
    27 distinct talks with editor-accurate edges.
  - *b* is the phrase's total hits.
  - *a* is the hits in the expected zone:
    - near a talk start (−120 to +180 s) for `start`;
    - near a talk end (−180 to +60 s) for `end`;
    - near either for `changeover`.
  - Only anonymous counts were recorded. The media, transcripts and ground truth stay
    outside the repository.
- **R [n]: from published scripts and guides.** Source *n* is listed at the end. These
  phrases have not been measured, because the corpus has no such events.
- **Noisy:** in the measurements, most hits fell deep inside talks. Such phrases are
  **opt-in** only, and marked ⚠.

## What the measurements show

- **MC handoffs are the most precise signal.** Every hit landed at a changeover:
  - "please join me in welcoming": M 10/10, covering 10 of 27 talk starts;
  - "please welcome": M 10/10;
  - "next speaker": M 13/13, covering 12 starts.
- **"good morning" is precise** (M 7/7). Generic greetings such as "hi everyone" (3/3)
  and "hello everyone" (2/2) are precise but rare.
- **Closing thanks straddle the changeover.** "thank you so much" is M 24/26: 11 hits near
  starts and 13 near ends, the speaker's closing followed by the MC's thanks. It
  covers 18 of 27 talk ends, so it is a `changeover` phrase.
- **Some intuitive phrases are noisy:**
  - "thank you" alone: 476 hits, 35 deep inside talks and 265 elsewhere outside the edge
    windows;
  - "questions": 25 of 50 hits deep inside talks;
  - "any questions": 6 of 11 deep inside talks;
  - "i'm going to talk about": 0 of 5 near a start;
  - "see you": 3 of 9 deep inside talks.
- **Studio words misfire on a conference stage:** "action" had 9 of 10 hits deep inside
  talks, "speed" 5 of 6, and "cut" 3 of 4. Studio groups are therefore opt-in and
  profile-specific.
- **Many plausible phrases never occurred** in this corpus, for example "thank you for
  having me", "give it up for", "that's all the time we have" and "last question". They
  stay in the catalog on research evidence. Other events and cultures will differ.

## Event profiles (starter bundles)

| Profile | Pre-ticked groups |
| --- | --- |
| Conference stage | Conference: MC handoffs; Speaker openings; Speaker closings; Breaks and returns |
| Tech conference and meetup | Conference profile, plus Tech: pitch and demo day handoffs |
| Panel or moderated session | Panels; Conference: MC handoffs; Speaker closings |
| Civic or government meeting | Civic: opening and adjournment; Civic: agenda items |
| Arena, sports or large public event | Arena and public address; Anthem and ceremonies |
| Community and cultural event (Commonwealth/South Asian formal English) | Community: dignitaries and anchoring; Conference: MC handoffs; Speaker closings |
| Press conference or media briefing | Press conference |
| Interview, junket or podcast | Interviews and junkets |
| Broadcast or live stream | Broadcast and live stream |
| Film or studio set | Studio: setups; Studio: slate and takes (segment); Studio: wraps |
| Webinar or virtual event | Webinar and virtual |

**Regional add-on groups** (Australia and New Zealand; UK and Ireland; South Asian English)
are never pre-ticked. Producers add them to any profile.

## Catalog groups

Phrases are written as the literal matcher sees them. Case and punctuation are ignored,
and the whole phrase must match in order. The **Default** column says whether a phrase
is included when its group is ticked; ⚠ phrases need the producer to include them
explicitly.

### Conference and keynote stage

**Conference: MC handoffs** (`conference.mc-handoffs`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| please join me in welcoming | changeover | M 10/10 | yes |
| please welcome | changeover | M 10/10 | yes |
| next speaker | changeover | M 13/13 | yes |
| please give a warm welcome | changeover | M 2/2 | yes |
| warm welcome | changeover | M 2/2 | yes |
| welcome to the stage | changeover | M 2/2 | yes |
| round of applause | changeover | M 3/3 | yes |
| let's hear it for | changeover | M 2/2 | yes |
| thank you so much | changeover | M 24/26 | yes |
| thank you very much | changeover | M 9/10 | yes |
| thanks so much | changeover | M 2/2 | yes |
| give it up for | changeover | R [14] | yes |
| put your hands together | changeover | R [14] | yes |
| without further ado | changeover | M 0/2 (said earlier in the changeover), R [14] | yes |
| please join me in thanking | changeover | R [15] | yes |
| ladies and gentlemen | changeover | M 1/3 ⚠ | opt-in |

**Conference: Speaker openings** (`conference.speaker-openings`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| good morning | start | M 7/7 | yes |
| good afternoon | start | R [14] | yes |
| good evening | start | M 1/1 | yes |
| hi everyone | start | M 3/3 | yes |
| hello everyone | start | M 2/2 | yes |
| welcome everyone | start | M 1/1 | yes |
| my name is | start | M 4/5 | yes |
| a pleasure to be here | start | M 2/2 | yes |
| great to be here | start | M 1/1 | yes |
| excited to be here | start | M 1/1 | yes |
| it's an honor | start | M 1/1 | yes |
| thank you for having me | start | R [13] | yes |
| thanks for having me | start | R [13] | yes |
| today i want to talk | start | M 1/1 | yes |
| today i'm going to | start | M 1/1 | yes |
| let's get started | start | M 1/1, R [12] | yes |
| welcome to | start | M 7/8 ⚠ (short, generic) | opt-in |

**Conference: Speaker closings** (`conference.speaker-closings`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| thanks everyone | end | M 2/2 | yes |
| thank you all | end | M 3/4 | yes |
| thank you everyone | end | M 0/1 | yes |
| thank you for your attention | end | M 0/1, R | yes |
| thank you for listening | end | R | yes |
| in conclusion | end | M 1/1 | yes |
| to conclude | end | M 1/1 | yes |
| wrapping up | end | M 1/1 | yes |
| key takeaways | end | M 1/1 | yes |
| that's all i have | end | R | yes |
| that's it for me | end | R | yes |
| find me afterwards | end | R | yes |
| any questions | end | M 4/11 ⚠ | opt-in |
| see you | end | M 5/9 ⚠ | opt-in |

**Conference: Breaks and returns** (`conference.breaks`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| welcome back | start | M 4/5 | yes |
| lunch break | end | M 1/1 | yes |
| short break | end | M 1/1 | yes |
| coffee break | end | R | yes |
| we'll be back | end | R | yes |
| enjoy your lunch | end | R | yes |

### Panels and moderated sessions (`panels`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| our panelists | start | M 1/1, R [15] | yes |
| our moderator | start | M 1/1 | yes |
| please welcome our panel | changeover | R [15] | yes |
| let me introduce our panelists | start | R [15] | yes |
| open it up to the audience | segment | R [15] | yes |
| time for a few audience questions | segment | R [15] | yes |
| please join me in thanking our panel | end | R [15] | yes |
| thank our panelists | end | R [15] | yes |

### Civic and government meetings

**Civic: opening and adjournment** (`civic.open-close`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| call this meeting to order | start | R [2] | yes |
| called to order | start | R [2] | yes |
| roll call | start | R [2] | yes |
| pledge of allegiance | start | R [2] | yes |
| we are in recess | end | R [2] | yes |
| reconvene | start | R [2] | yes |
| meeting is adjourned | end | R [2] | yes |
| meeting stands adjourned | end | R [2] | yes |
| motion to adjourn | end | R [2] | yes |

**Civic: agenda items** (`civic.agenda`). Each agenda item is its own Session (owner decision,
2026-09-29). This group is pre-ticked in the civic profile.

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| next item on the agenda | changeover | R [2] | yes |
| moving on to item | changeover | R [2] | yes |
| public comment | segment | R [2] | yes |
| state your name and address | segment | R [2] | yes |
| all those in favor | segment | R [2] | yes |
| the motion carries | segment | R [2] | yes |

### Ceremonies and awards (`ceremonies.awards`), deferred from v1 by the owner

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| please welcome our presenter | changeover | R [8] | yes |
| our next award | changeover | R [8] | yes |
| the nominees are | segment | R [8] | yes |
| and the award goes to | segment | R [8] | yes |
| and the winner is | segment | R [8] | yes |
| accepting the award | segment | R [8] | yes |

### Arena, sports and public address

**Arena and public address** (`arena.pa`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| good evening ladies and gentlemen | start | R [6] | yes |
| welcome to | start | R [6] ⚠ | opt-in |
| starting lineups | segment | R [6] | yes |
| halftime | segment | R [6] | yes |
| final score | end | R [6] | yes |
| thank you for coming | end | R [6] | yes |
| drive home safely | end | R [6] | yes |

**Anthem and ceremonies** (`arena.anthem`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| please rise | start | R [6] | yes |
| remove your hats | start | R [6] | yes |
| national anthem | segment | R [6] | yes |
| moment of silence | segment | R [6] | yes |

### Community and cultural events

**Community: dignitaries and anchoring** (`community.anchoring`), common in formal
Commonwealth and South Asian English

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| respected dignitaries | start | R [4] | yes |
| esteemed guests | start | R [4] | yes |
| chief guest | segment | R [4] | yes |
| lighting of the lamp | segment | R [4] | yes |
| light the ceremonial lamp | segment | R [4] | yes |
| i now call upon | changeover | R [4] | yes |
| i would like to invite | changeover | R [4] | yes |
| may i request | changeover | R [4] | yes |
| vote of thanks | end | R [4] | yes |
| felicitation | segment | R [4] | yes |

### Press conferences and media briefings (`press`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| thank you all for coming | start | R [3] | yes |
| open the floor to questions | segment | R [3] | yes |
| we'll take a few questions | segment | R [3] | yes |
| last question | end | R [3] | yes |
| that's all the time we have | end | R [3] | yes |
| thank you everyone for attending | end | R [3] | yes |

### Interviews, junkets and podcasts (`interviews`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| welcome to the show | start | R [13] | yes |
| my guest today | start | R [13] | yes |
| joining me today | start | R [13] | yes |
| thanks for joining us | start | R [13] | yes |
| thanks for having me | start | R [13] | yes |
| where can people find you | end | R [13] | yes |
| thanks for coming in | end | R [13] | yes |
| thanks for coming on | end | R [13] | yes |
| thanks for talking with us | end | R [13] | yes |
| that's all the time we have | end | R [3] [13] | yes |

### Broadcast and live stream (`broadcast`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| we're live | start | R [5] | yes |
| welcome back | start | M 4/5 | yes |
| stand by | segment | R [5] | yes |
| we'll be right back | end | R [5] | yes |
| stay with us | end | R [5] | yes |
| after the break | end | R [5] | yes |
| we're clear | end | R [5] | yes |
| we're off air | end | R [5] | yes |

### Film and studio set

**Studio: setups** (`studio.setups`). Added by the owner on 2026-09-29, so that the studio profile has
a Session-start phrase. A Session is a setup; takes are segments inside it.

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| picture's up | start | R [16] | yes |

**Studio: slate and takes** (`studio.takes`). All `segment`: takes are passes within a
Session (owner decision). Opt-in outside the *Film or studio set* profile: on a
conference stage, "action" landed deep inside talks in 9 of 10 hits.

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| quiet on set | segment | R [1] | yes |
| roll sound | segment | R [1] | yes |
| sound speed | segment | R [1] | yes |
| camera speed | segment | R [1] | yes |
| rolling | segment | R [1], M 0/2 on stage ⚠ | yes (studio profile only) |
| speed | segment | R [1], M 0/6 on stage ⚠ | yes (studio profile only) |
| mark it | segment | R [1] | yes |
| take {n}, for n = 1–20, as digits and as words ("take 3", "take three") | segment | R [1] | yes |
| scene {n} | segment | R [1] | yes |
| action | segment | R [1], M 1/10 on stage ⚠ | yes (studio profile only) |
| cut | segment | R [1], M 1/4 on stage ⚠ | yes (studio profile only) |
| back to one | segment | R [1] | yes |
| reset | segment | R [1], M 0/4 on stage ⚠ | yes (studio profile only) |
| check the gate | segment | R [1] | yes |

**Studio: wraps** (`studio.wraps`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| moving on | end | R [1], M 1/6 on stage ⚠ | yes (studio profile only) |
| that's a wrap | end | R [1] | yes |
| that's lunch | end | R [1] | yes |
| we're wrapped | end | R [1] | yes |

### Webinar and virtual (`virtual`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| a few minutes for people to join | changeover | R [12] | yes |
| let's get started | start | M 1/1, R [12] | yes |
| can everyone see my screen | start | R [12] | yes |
| can you see my screen | start | R [12] | yes |
| the recording will be shared | end | R [12] | yes |
| thank you for joining | end | R [12] | yes |
| you're on mute | segment | R [12] ⚠ (said at any time) | opt-in |

### Worship and faith services (`worship`), deferred from v1 by the owner

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| please be seated | segment | R [9] | yes |
| you may be seated | segment | R [9] | yes |
| please stand | segment | R [9] | yes |
| let us pray | segment | R [9] | yes |
| go in peace | end | R [9] | yes |
| let us go forth | end | R [9] | yes |

### Tech: pitch and demo day (`tech.pitch`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| our next team | changeover | R [10] | yes |
| next up we have | changeover | R [10] | yes |
| you have three minutes | start | R [10] | yes |
| time's up | end | R [10] | yes |
| questions from the judges | segment | R [10] | yes |
| live demo | segment | R [10], M 0 | yes |
| let me show you | segment | R [10], M 0 ⚠ | opt-in |
| demo | segment | M 1/14 ⚠ | opt-in |

### Regional add-ons (never pre-ticked)

**Australia and New Zealand** (`regional.au-nz`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| traditional custodians | start | R [7] | yes |
| traditional owners | start | R [7] | yes |
| elders past and present | start | R [7] | yes |
| kia ora | start | R | yes |
| g'day | start | R | yes |

An Acknowledgement of Country usually opens an **event or a day**, not each Session. It
supports the first Session's start.

**UK and Ireland** (`regional.uk-ie`)

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| cheers everyone | end | R | yes |
| lovely to be here | start | R | yes |
| cheers | end | R ⚠ (said at any time) | opt-in |
| brilliant | end | M 2/5 ⚠ | opt-in |

**South Asian English** (`regional.south-asia`): see *Community: dignitaries and anchoring*,
plus:

| Phrase | Role | Evidence | Default |
| --- | --- | --- | --- |
| good morning to one and all | start | R [4] | yes |
| a very warm welcome | changeover | R [4] | yes |
| namaste | start | R [4] | yes |

## Excluded from v1

These phrases were measured as too noisy to ship even as opt-in. A producer can still add
any of them as custom phrases.

- **"thank you"**: 476 hits, mostly outside edges. The precise longer forms above cover
  the useful cases.
- **"questions"**: 25 of 50 hits deep inside talks.
- **"i'm going to talk about"** and **"i want to talk about"**: 0 of 9 near a start.
- **"slides"**, **"next slide"** and **"to wrap up"**: mostly deep inside talks.

## Matching notes (for ED-0107)

- **Matcher:** the ED-0092 matcher is literal. Tokens are NFKC-normalized, casefolded, and
  split on anything that is not a letter or digit. "that's" matches "That’s" with a curly
  apostrophe, because both split into the tokens *that* and *s*.
- **Numbers:** transcripts render them as digits or as words, so the `{n}` templates
  expand to both forms at catalog build time. "take {n}" for n = 1–20 gives 40 phrases.
- **Size:** the largest realistic composition is a profile plus two add-ons, which is
  about 60–90 phrases per list, well under the 200 cap.
- **Language:** English only in v1, by owner decision. Regional groups cover English
  variants, not other languages.
- **Measurement limits:** one English-language conference, one stage, and one
  transcription model. Phrase precision differs by speaker population, MC style and
  transcriber. The catalog should be re-measured when other corpora exist.

## Owner decisions (2026-09-29)

1. **Profiles, groups and phrases:** accepted as proposed, with the changes below. v1
   ships 11 profiles and 18 groups, plus 3 regional add-ons.
2. **`segment` phrases:** stored in the composition and kept out of the published start
   and end cue lists until Segment work exists.
3. **Civic meetings:** each agenda item is its own Session. The `civic.agenda` changeover
   phrases split them.
4. **Worship and ceremonies:** deferred from v1. Their groups (`worship`,
   `ceremonies.awards`) and profiles stay documented above as deferred, and do not ship in
   the ED-0107 catalog.
5. **Noisy phrases:** available as opt-in, never pre-ticked. The *Excluded from v1*
   phrases can be added only as custom phrases.
6. **Studio Session start (2026-09-29, from the ED-0107 review):**
   - The *Film or studio set* profile had no `start` phrase, so it could never publish a
     start list.
   - The owner added the `studio.setups` group with "picture's up", which marks the first
     real take of a setup, and pre-ticks it in that profile.
   - The rule that both published lists need 1–200 phrases is unchanged.

## Sources

1. StudioBinder, "The Film Slate Explained"
   (<https://www.studiobinder.com/blog/how-to-use-a-film-slate/>); SetHero, "What does
   'Speed' mean on a film set?"
   (<https://sethero.com/blog/article/speed-film-set-terminology/>); No Film School,
   "Need-to-know terms for film sets"
   (<https://nofilmschool.com/what-are-the-need-to-know-terms-for-film-sets>).
2. Tucson City Clerk, "Chair's script"
   (<https://www.tucsonaz.gov/files/sharedassets/public/v/1/government/city-clerks-office/documents/sample_script_for_chairperson.pdf>);
   League of Oregon Cities, "Model Rules of Procedure for Council Meetings"
   (<https://www.orcities.org/application/files/3417/1693/7124/ModelRulesofProcedureforCouncilMeetings-updated8-15-23.pdf>);
   Greater Minnesota Cities, "Virtual meeting script"
   (<https://greatermncities.org/wp-content/uploads/2020/04/SAMPLE-virtual-meeting-script.pdf>).
3. SkillsYouNeed, "Managing a Press Conference"
   (<https://www.skillsyouneed.com/present/press-conference.html>); Community Tool Box,
   "Arranging a Press Conference"
   (<https://ctb.ku.edu/en/table-of-contents/participation/promoting-interest/press-conference/main>).
4. Testbook, "Lighting of the Lamp anchoring script"
   (<https://testbook.com/articles/lighting-of-the-lamp-anchoring-script>); TalkDrill,
   "Anchoring script in English"
   (<https://www.talkdrill.com/blog/anchoring-script-english/>).
5. ScreenSkills, "Floor manager"
   (<https://www.screenskills.com/job-profiles/browse/unscripted-tv/floor-or-location/floor-manager/>);
   MediaCollege, "The Television Floor Manager"
   (<https://www.mediacollege.com/employment/television/floor-manager.html>).
6. NCAA, "Public address announcer script template"
   (<https://ncaaorg.s3.amazonaws.com/championships/sports/football/d2/2021-22D2MFB_PAScripts.pdf>);
   Little League, "Public address announcer: responsibilities and suggested practices"
   (<https://www.littleleague.org/university/articles/public-address-announcer-responsibilities-and-suggested-practices/>).
7. UNSW, "Acknowledgement of Country"
   (<https://www.unsw.edu.au/indigenous/strategy/resources/acknowledgement-country-and-welcome-country>);
   Victorian Government, "Acknowledgement of Traditional Owners"
   (<https://www.firstpeoplesrelations.vic.gov.au/acknowledgement-traditional-owners>).
8. Awards ceremony scripts
   (<https://scriptforanchoringawards.blogspot.com/>), plus common broadcast-awards usage.
9. Discipleship Ministries (UMC), "An Order of Sunday Worship"
   (<https://www.umcdiscipleship.org/book-of-worship/an-order-of-sunday-worship-using-the-basic-pattern>);
   Church of England, "A Service of the Word"
   (<https://www.churchofengland.org/prayer-and-worship/worship-texts-and-resources/common-worship/service-word/service-word-morning-and>).
10. Technical presentation and demo guides
    (<https://www.youngju.dev/blog/english/2026-03-07-english-technical-presentation-demo-pitch-communication.en>,
    <https://developerrelations.com/talks/how-to-rock-a-technical-keynote/>).
11. Toastmasters, "When You Are the Emcee"
    (<https://www.toastmasters.org/magazine/articles/when-you-are-the-emcee>).
12. English Interconnect, "Essential vocabulary for Zoom and virtual meetings"
    (<https://www.englishinterconnect.com/mastering-online-meetings/>); Vimeo, "Webinar
    welcome speech" (<https://vimeo.com/blog/post/welcome-speech-for-a-webinar>).
13. Resound, "Podcast script templates"
    (<https://www.resound.fm/blog/podcast-script-templates>); Buzzsprout, "How to write a
    podcast script" (<https://www.buzzsprout.com/blog/write-podcast-script-examples>).
14. Emcee script guides (<https://expertmc.com/emcee-script/>,
    <https://adamchristing.com/blog/great-opening-lines-for-emcee/>).
15. Powerful Panels, "Sample script for a panel discussion"
    (<https://www.powerfulpanels.com/sample-script-for-a-panel-discussion/>);
    Toastmasters, "A Panel Moderator's Guide to Success"
    (<https://www.toastmasters.org/magazine/magazine-issues/2023/june/panel-moderators>).
16. SetHero, "What does 'Picture's up' mean on a film set?"
    (<https://sethero.com/blog/article/pictures-up-film-set-terminology/>);
    HowToFilmSchool, "Picture's Up" (<https://howtofilmschool.com/dictionary/pictures-up/>).
