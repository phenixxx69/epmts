# How to tag a media

A game never looks at a picture: it only reads its tags. A well-tagged media comes out exactly
when it should, and never when it should not. This guide explains which tags go together, and
the one idea that matters most: **who does what to whom**.

Tag ids come from [catalogue/TAGS.md](../../catalogue/TAGS.md). In the media manager, select a
thumbnail and click *Edit tags…*; type a word in *Filter* to find a tag (English or French).

## How games use your tags

A game asks for "a media that has **all** these tags, **none** of those tags, and no tag of
these types". Two consequences:

1. **A missing tag hides the media.** A request for *Kissing + M>F + bedroom* never finds a
   kissing scene tagged without *bedroom*.
2. **A missing tag also lets the media through where it should not appear.** A calm scene
   often asks for "no tag of type *Action*": a sexual picture tagged without its action would
   show up there.

Games ask in a few typical ways, and tags are organised the same way:

| The game wants… | It asks with… |
| --- | --- |
| a person alone (to introduce a character, a portrait, a pose) | gender + age + framing |
| someone doing something to someone | action + direction |
| a place or an object, nobody in it | `312 No person` + location / props |

So **tags depend on the context of the picture**: some only make sense together, and the same
information is never given twice.

## Context 1 — a person alone

A portrait, a pose, a person doing something on their own (bathing, walking, dancing, sleeping).

**Always together:**

- **Gender** (type 1): `1 Woman`, `2 Man` or `3 Trans woman`;
- **Age group** (type 17): the apparent age, `292` to `296`;
- **Framing** (type 3): `8 Upper-body portrait`, `9 Full-body view`, `37 Pelvis close-up`,
  `40 Back view`.

A person alone is the default: `313 One person` is optional.

Then, when they apply: an **intransitive** action (see below) such as `341 Bathing`,
`202 Walking`, `261 Dance`, `174 Self-display`; and the tags valid in every context.

> A woman taking a bath, seen whole: `1 Woman`, `293 Age 25 to 35`, `9 Full-body view`,
> `341 Bathing`, `196 Bathtub`, `167 Nude`.

Framing and age describe *one* person: they belong to this context. In a scene between
several people, they are not needed.

## Context 2 — someone does something to someone

### Transitive or intransitive?

Ask one question for each action: **is someone doing it to someone?**

- **Intransitive**: nobody receives it — bathing, walking, dancing, posing, sleeping. That is
  context 1 (or several people side by side, each doing it alone).
- **Transitive**: someone does it to someone — washing someone, massaging, kissing, licking,
  every sex act. That is this context.

#### The test: could it be done to someone else?

**Washing** and **bathing** look alike, but are not tagged the same way:

- **You can wash someone**: washing is transitive. You wash someone else *or yourself*, and in
  both cases someone receives the action, so there is a direction.
- **You do not bathe someone**: bathing is intransitive. You are simply in the water; nobody
  receives the action, so there is **never** a direction.

| Picture | Tags |
| --- | --- |
| A woman bathing | `341 Bathing` (+ gender, age, framing: context 1) |
| A woman washing herself | `297 wash` + `137 F>self` |
| A woman washing a man | `297 wash` + `70 F>M` |
| A woman washing another woman | `297 wash` + `120 F>F` |

Ask only: **could this action be done to someone else?** If yes, it is transitive — even when
the person does it to themselves (washing, caressing, masturbating), and its direction is then
`…>self`.

**And when an object acts?** Use **two directions**: the object's, saying what penetrates
(`300 item > F`, `301 item > M`, `302 item > T`), and the one of the person holding it, saying
who does it to whom. The second one is what tells the scenes apart:

| Picture | Tags |
| --- | --- |
| A woman inserting a dildo into herself | `56 Vaginal penetration`, `22 Dildo`, `300 item > F`, `137 F>self` |
| A woman penetrating another woman with a dildo | `56 Vaginal penetration`, `22 Dildo`, `300 item > F`, `120 F>F` |
| A man penetrating a woman with a dildo | `56 Vaginal penetration`, `22 Dildo`, `300 item > F`, `69 M>F` |

### A transitive action always has a direction

This is **mandatory**: every transitive action goes with a direction tag (type 10, *Actor
relationship*) saying who acts on whom, **the one who acts first**:

| Tag | Meaning |
| --- | --- |
| `69 M>F` | a man does it to a woman |
| `70 F>M` | a woman does it to a man |
| `120 F>F` | a woman does it to a woman |
| `125 M>M` | a man does it to a man |
| `71 M>T`, `72 T>M`, `139 F>T`, `140 T>F`, `257 T>T` | the same with a trans woman |
| `137 F>self`, `138 M>self`, `136 T>self` | someone does it to themselves (masturbation, self-touching) |
| `80 M=F` | a man and a woman do it to each other, neither leading |
| `300 item > F`, `301 item > M`, `302 item > T` | an object or a machine acts on someone (plus the direction of whoever holds it) |

### No gender tags here

The direction already says who is there: `69 M>F` means a man and a woman. **Do not add the
gender tags** (`1 Woman`, `2 Man`…): they would repeat the direction, and would make the
scene come out for "a woman alone" requests. The same goes for doing it to oneself:
`137 F>self` says it is a woman.

> A woman washing a man: `297 wash`, `70 F>M`, `196 Bathtub`.
>
> A woman masturbating: `15 female masturbation`, `137 F>self`, `199 bed`.

The direction separates pictures that nothing else can: `193 cunny` with `69 M>F` (a man licks
a woman) and `193 cunny` with `120 F>F` (a woman licks a woman) are two very different media.
Without the direction, a game asking for one gets the other — or nothing at all.

### Also in this context

- **Position** (type 18), when one is recognisable: `422 Cowgirl`, `425 Doggy style`…
- **Several actions**: tag each, with **every direction that is true**. A man penetrating a
  woman who licks another woman: `56 Vaginal penetration`, `69 M>F`, `193 cunny`, `120 F>F`.
- **Groups** (three people or more): add the participant count (`250 Three people`,
  `251 Four people`…) and, when one sex clearly dominates, `47 Male-majority group` or
  `48 Female-majority group`.

## Context 3 — nobody in the picture

`312 No person`, with the location, props and ambiance: an empty tavern, a dungeon, a sex toy.

## Tags valid in every context

Add them to any picture when they are true and visible:

- **Location** (type 12), only when it is recognisable and matters to the scene (see below):
  `376 bedroom`, `383 bathroom`, `245 woods`, `486 Medieval tavern`…
- **Ambiance** (type 7): `17 Gothic`, `85 Middle Ages`, `39 Wet`, `203 sleeping`…
- **Clothing** (type 19): one level, from `167 Nude` to `456 Fully covered`.
- **Body traits** (type 4): `4 Visible penis`, `5 Visible breasts`, `27 Red hair`, `23 Tattoo`…
- **Props and accessories** (type 5): rope, collar, high heels, dildo…
- **Point of view** (type 11): `106 male pov`, `107 female pov`… when the camera is the eyes of
  someone in the scene.
- **Fantasy race** (type 14) and **character role** (type 16): `244 Elf`, `228 Succubus`,
  `267 Mage`, `266 Warrior`…
- **Kink status** (type 8): `51 domination`, `46 Submission`, when the picture shows it.
- **Consent** (type 13): one level, as the scene presents it, from `217 Enthusiastic consent`
  to `222 No consent`. Players and games rely on it to avoid content they do not want: tag it
  honestly whenever the scene suggests something other than plain consent.
- **Hypnosis** (type 9): only for hypnosis-themed media.

### Generic media: sometimes, no location

A game can exclude a **whole type** of tags. It uses this to get a *neutral* picture, one that
does not give a particular colour to a scene that does not need it. For example, a scene where
the place does not matter asks for the action and the direction **with the Location type (12)
excluded**: only media without a location can come out.

So when the background is neutral or indistinct (plain backdrop, blur, close-up where nothing
around is visible), **do not tag a location**. The media becomes a generic one, usable
wherever the place does not matter.

> A woman giving a blowjob against a neutral background: `6 Blowjob`, `70 F>M`, no location.
> It comes out for "a blowjob, place irrelevant" (Location type excluded), and never forces a
> bedroom or a forest onto a scene set elsewhere.

Same logic for the ambiance (type 7): tag it only when it really shows. A location or ambiance
tag added "just in case" removes the media from generic requests.

Some tags are **excluded by default** (47, 48, 66, 135, 143, 163, 168): a media carrying one
of them is only drawn when a request explicitly asks for it. Tag them when they are true; the
media then simply stays out of ordinary requests.

Tag 291 of the age group is a protected tag with its own rules (standard, section 12): the
tools refuse it where it does not belong.

## Portraits and person packs

A **portrait** is the picture a game shows to introduce a person, and the entry of a person
pack. It is context 1, without any transitive action:

- **always**: gender, age group, framing (`313 One person` is optional: alone is the default);
- **what makes the person recognisable**, since a game introducing "a red-haired gothic woman
  in a corset" looks for exactly these tags:
  - **hair** (type 4): colour (`27 Red hair`, `448 Blonde hair`, `449 Brown hair`) and cut
    (`481 Long hair`, `482 Shaved head`);
  - **clothing style** (type 7): `17 Gothic`, `50 steampunk`, `61 vintage`…;
  - **distinctive clothing** (type 5): `49 Corset`, `43 Dress`, `153 Latex`, `33 Leather`,
    `118 Maid outfit`, `398 Nurse outfit`, `473 Suit and tie`, `28 High heels`, `334 Boots`…;
  - **state of dress** (type 19), one level: `456 Fully covered`, `457 Normally dressed`,
    `458 Revealing outfit`, `459 Highly revealing outfit` or `167 Nude`;
  - **character class**, for an RPG (type 16): `266 Warrior`, `267 Mage`, `268 Priest`,
    `269 Archer`, `274 Rogue`, `272 Barbarian`, `276 Shaman or druid`…;
  - **fantasy race** (type 14): `244 Elf`, `228 Succubus`, `229 Demon`…;
  - and when the picture shows it: kink status (type 8), tattoos (`23 Tattoo`).

A hair colour or a piece of clothing is missing? It is created in this repository, like any
tag ([catalogue/README.md](../../catalogue/README.md)).

What person packs are for and how games use them: [Person packs](person-packs.md).

Inside a person pack, tag every media by its own context: the portraits and solo pictures like
context 1, the scenes with someone else like context 2.

## Common mistakes

| Mistake | Consequence | Fix |
| --- | --- | --- |
| Transitive action without direction | The wrong pairing comes out, or nothing | Always add the type 10 direction |
| Gender tags on a scene with a direction | The scene comes out for "a person alone" requests | Remove them: the direction says who is there |
| A direction on an intransitive action | Bathing alone no longer matches single-person requests | Directions only for actions done to someone |
| Framing or age missing on a portrait | The portrait never comes out to introduce a character | Gender + age + framing, always together |
| No action tag on a sexual picture | It appears in calm scenes that exclude the *Action* type | Always tag the action |
| Tagging what is implied but not visible | Disappointing results | Tag only what the picture shows |
| A location on a neutral background, "just in case" | The media no longer comes out for generic requests (Location type excluded) | No location when the setting cannot be told |
| No consent tag on a non-consensual scene | Players who exclude it still see it | Tag the consent level honestly |

## Check your work

Open the **preview** (home window › *Preview the media in your browser*): include the tags a
game would ask for and draw a few times. Your media should come out for its tags, and stay out
when you exclude one of them. In the media manager, the *Tag* filter shows every media carrying
a tag, which is a quick way to spot one that was forgotten.
