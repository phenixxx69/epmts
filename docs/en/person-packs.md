# Person packs: keep the same person through a story

A game that draws media by tags shows a **different** person every time: "a woman with red
hair" is never the same woman twice. For a story, that breaks the continuity — the character
met in the tavern does not look like the one in the next scene.

A **person pack** solves it: it gathers several media of **one same person**. The game
introduces a character with a portrait, then draws the following scenes **only among that
person's media**. The character keeps the same face and body from scene to scene.

## What a person pack is

Inside a pack, a person pack is a folder `medias/<portrait sha256>/`, itself a small pack with
the person's media:

```
my-pack/
├── tags.sqlite              the portrait is a media here, like any other
└── medias/
    ├── 81bd…07e             ordinary media
    └── 5c0e…9aa/            person pack — named by the fingerprint of the portrait
        ├── tags.sqlite      the person's media only
        └── medias/
            ├── 5c0e…9aa     the portrait
            ├── a41f…2c3     the same person, alone
            └── 9d07…e18     the same person, in a scene
```

The portrait belongs to both: in the main pack, it is drawn like any media (that is how a game
picks a character); in the person pack, it is the person's first media. Its fingerprint is the
person's **reference**.

The person's other media are **only** in the person pack: an ordinary draw never returns them,
only a draw carrying the reference does. Put in a person pack the media you want to keep for
that character; a media meant for any scene stays in the main pack.

## Creating one

In the media manager:

1. *Person › New person pack from a portrait…* and choose the portrait (a still picture).
2. Tag the portrait (see below). The manager creates the person pack and opens it.
3. In the *Import* tab, import the media of that person: they go into the person pack.
4. Tag each media (*Edit tags…*). Click *BACK* to return to the main pack, where the person
   appears as an orange card.

From the command line: `php tools/php/pack_add_person.php <pack> <folder> <portrait file>`
creates the person pack from a folder holding the pictures of one person
([php-tools.md](php-tools.md)).

## Tagging a person pack

- **The portrait** is how the game finds the character: tag it as a person alone — gender, age
  group, framing — and above all **what makes the person recognisable**: hair colour, clothing
  style, distinctive clothing, state of dress, class or race for an RPG. A game introducing "a
  red-haired gothic mage" looks for exactly these tags. Details:
  [How to tag a media › Portraits](tagging.md#portraits-and-person-packs).
- **The other media** are tagged by their own context, exactly as in the main pack: a solo
  picture with gender, age and framing; a scene with action + direction, and no gender tags.
- **Variety pays off**: portraits, solo poses, different outfits and states of dress, scenes.
  The more contexts the person covers, the more often the story finds a media of *that*
  person instead of falling back on someone else.

## How a game uses it

The same flow works over HTTP and in a browser pack:

1. **Pick a character**: draw a portrait with the character's criteria, for example
   `1 Woman` + `8 Upper-body portrait` + `27 Red hair`.
2. **Learn whether it is a person**: the answer says so (see below). Keep the reference with
   your character — in the save game, for instance.
3. **Next scenes**: send the same kind of request **with the reference**. Only that person's
   media can come out.
4. **When the person has nothing matching**, the answer is empty. The game decides: draw again
   without the reference (another person), or show nothing. EPMTS never switches person
   silently.

**Over HTTP** ([server.md](server.md)): a portrait answer carries `referenceHash`; send it back
in the next requests:

```json
{"format": "img", "includeTagImg": [15, 137], "referenceHash": "5c0e…9aa"}
```

**In a browser game** ([web-games.md](web-games.md)):

```js
var portrait = pack.select({include: [1, 8, 27], format: 'img'});
pack.person(portrait).then(function (person) {
    // person is null when this portrait has no person pack
    var next = (person && person.select({include: [15, 137]})) || pack.select({include: [15, 137]});
});
```

The rule is in the [standard](../../standard/EPMTS-HTTP.md), section 9 (PR-1).

## Sharing and merging

- **Creating a pack** (*File › Create a pack from…*) includes a person pack whenever its
  portrait is part of the pack.
- **Importing or merging**: person packs with the same portrait are merged, their media
  united, like the rest of the pack.

## Good to know

- The reference is the **fingerprint of the portrait file**: another file, even a very similar
  one, is another person. Keep the portrait unchanged once games use it.
- A person pack cannot contain another person pack.
- Person packs live in packs: the server handles them with its default SQLite backend, not with
  the MySQL backend.
- A portrait cannot be deleted while its person pack exists: delete the person's folder first.
- Editing the portrait's tags updates it in both places (main pack and person pack).
