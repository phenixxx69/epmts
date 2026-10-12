# The tag catalogue

`catalogue.json` is **the reference of every EPMTS tag id**. Packs, servers and games all use
these ids; a tag is identified by its number, never by its name.

## The one rule: tags are created here, and only here

- A tag or a tag type is created **only in this repository**, with the scripts below.
  A tool, a pack or a server never creates one: the same number would end up meaning two
  different things in two places, and packs could no longer be merged.
- An id is **never renumbered** and **never reused**. Removed ids are listed in
  `retired_tag_ids` / `retired_type_ids` and stay unused forever.
- Names and descriptions may be improved; the meaning of a tag must not change.

To propose a new tag for everyone, open a pull request on this repository with the change made
by the script (`catalogue.json`, `TAGS.md`, `empty-pack/`).

How to choose the tags of a media: [docs/en/tagging.md](../docs/en/tagging.md)
([français](../docs/fr/guide-tagage.md)).

## Files

| File | Role |
| --- | --- |
| `catalogue.json` | The reference: `type_tag` (types), `tag_media` (tags), retired ids. |
| `logos/<tagId>.png` | Optional tag icons (PNG, at most 100 × 100). |
| `TAGS.md` | The readable list, **generated**. |
| `../empty-pack/` | An empty pack holding the whole catalogue, **generated**. |

A tag has: `id`, `name`, `type_tag` (its type id), `subcategory_name`, `description` (English
keywords), `description_fr` (French keywords), `ia_text` (a sentence for text generators),
`porn` (1 only for sexually explicit action tags, type 6), `logo` (`logos/<id>.png` or null).

## Adding a tag or a type

Needs PHP 7.4+ with the sqlite3 extension.

```
php tools/php/catalogue_add_tag.php "Tag name" --type=6 --description="english keywords" --description-fr="mots clés" [--subcategory=...] [--porn]
php tools/php/catalogue_add_type.php "Type name" [--position=0] [--color=black]
```

Both scripts take the next free id, update `catalogue.json` and rebuild `TAGS.md` and
`empty-pack/`. After editing `catalogue.json` by hand (a description, a logo), rebuild with:

```
php tools/php/catalogue_build.php
```

Existing packs get the new tags with *File › Update the tag catalogue* in the editor, or
`php tools/php/pack_update_catalogue.php <pack>`; their media and tags are kept.

## Special tags

- **Default exclusions** (47, 48, 66, 135, 143, 163, 168): left out of every draw unless one of
  them is asked for. See the standard, section 4.1.
- **291 "Age other"**: protected tag, see the standard, sections 4.2 and 12.
