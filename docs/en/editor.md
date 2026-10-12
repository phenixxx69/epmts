# The editor

Open it from the home window (*Open the media manager*), or directly with `quickstart.cmd editor`
(Windows) / `./quickstart.sh editor` (Linux/macOS); an optional folder opens a given pack:
`./quickstart.sh editor path/to/pack`. It reopens the last pack used.

## Menus

| Menu | Action |
| --- | --- |
| File › Open pack folder… | Opens a pack (a folder holding `tags.sqlite`). Older packs are upgraded on open. |
| File › New empty pack… | Creates a pack with the whole catalogue in an empty folder. |
| File › Import a downloaded pack (.zip)… | Checks the zip fully, then merges it into the open pack. |
| File › Import a pack folder… | Same for an unzipped pack. |
| File › Update the tag catalogue | Replaces the tag list of the pack (and its person packs) with the repository one. Ids never change, media keep their tags. |
| File › Check the pack | Validates the open pack, re-hashing every file. |
| File › Show the pack folder | Opens the folder in your file manager. |
| File › Create a pack from my local media… | Asks name, author, version, date and description, then saves a shareable `.zip` with the media you added yourself (origin *local*). |
| File › Create a pack from all media… | Same with every media, imported ones included (they keep their origin). |
| Person › New person pack from a portrait… | Asks a portrait picture and its tags, creates `medias/<portrait sha256>/`, and enters it so you can import that person's media ([Person packs](person-packs.md)). |

## Import checks

An import is refused **as a whole** when any of these fails:

- the zip is unsafe (a path leaving the folder, a link, an absurd size) or unreadable;
- the folder holds no `tags.sqlite`, or extra files besides the pack files;
- the database is not SQLite, lacks a table or column, or has broken references;
- a media file is missing, is not referenced, or **does not match its SHA-256**;
- a media type is not allowed, or `media.path` is not empty;
- a media uses a tag id unknown to the catalogue;
- a media breaks the tagging rules (standard, section 12);
- a person pack has one of these problems, or has no portrait row.

An older catalogue in the source is accepted (it is replaced by the current one), and missing
`tags.sql` / `tags.sql.js` are accepted (they are regenerated).

Archive junk (`__MACOSX/`, `.DS_Store`, `Thumbs.db`) is ignored. A zip may hold the pack at its
root or inside one folder.

## Origin of the media

Every media remembers where it comes from (`media.origin`): *local* when you added it yourself,
or the name of the pack it was imported from (the `name` of its `pack.json`, or the zip name
when the pack has none). Filter by origin with the *Origin* list; each card shows it.

When you create a pack, the zip holds `pack.json` (name, author, version, date, description,
media count, and the link to the original project, https://github.com/phenixxx69/epmts, which
every pack must carry: a pack without it is refused on import). The local media you exported then take the new pack name as origin, so that the
next "local media" pack only holds what you add afterwards.

## Tagging

What to tag and how: [How to tag a media](tagging.md).


- Tags can only be **chosen** from the catalogue; creating a tag is done in this repository
  ([catalogue/README.md](../../catalogue/README.md)).
- The tag window marks porn action tags with 🔞 and shows a red warning, then refuses to save,
  when tag 291 is combined with one of them.
- A portrait exists in the main pack and in its person pack; editing its tags updates both.
- A portrait cannot be deleted while its person pack exists (delete the person folder first).

## Imported files

Files are cleaned before entering the pack: EXIF, XMP, IPTC, comments and container metadata
are removed (a JPEG that relied on EXIF rotation is rotated for real), the file is named by
the SHA-256 of the cleaned content, and no original name or path is stored. Videos need ffmpeg.

## Video playback

Without extra packages, a video shows a still frame and *Open in system viewer* plays it. To play
videos inside the editor, install the optional packages (they need a Python version for which
PyAV 9 has wheels, e.g. Python 3.10):

```
.venv/bin/python -m pip install -r tools/python/editor/requirements-video.txt
```

## Command line

The same import and checks without the window:

```
.venv/bin/python tools/python/epmts_cli.py import packs/main downloaded-pack.zip
.venv/bin/python tools/python/epmts_cli.py check packs/main
.venv/bin/python tools/python/epmts_cli.py update-catalogue packs/main
.venv/bin/python tools/python/epmts_cli.py create-pack packs/main my-pack.zip --name "My pack" --author Me --version 1.0 --local-only
```

(Windows: `.venv\Scripts\python tools\python\epmts_cli.py …`)
