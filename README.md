# EPMTS — Easy Porn Media Tag System

*[Version française : README.fr.md](README.fr.md)*

EPMTS is a ready-to-use system to **tag adult media and draw them by tags** in your own
projects: browser games, desktop games and mods, or any program that can read SQLite or call
an HTTP API.

You get:

| Part | What it does | Where |
| --- | --- | --- |
| **Tag catalogue** | 475 tags in 19 types, with stable ids. This repository is the reference: tags are created **only here**. | [`catalogue/`](catalogue/) · [tag list](catalogue/TAGS.md) |
| **Pack format** | A media pack is a folder: `tags.sqlite` + `tags.sql` + `tags.sql.js` + `medias/<sha256>`. | [`empty-pack/`](empty-pack/) (empty pack) |
| **Home window** | One window for beginners: media count, import a pack (.zip), start the server, preview. | `quickstart` |
| **Media manager** | Browse, tag, add your own media, person packs, create a shareable pack (.zip with `pack.json`). Every media remembers its origin. | home window |
| **Person packs** | Group the media of one same person, so that a story keeps the same character from scene to scene: the game picks a portrait, then draws only that person's media. | [guide](docs/en/person-packs.md) |
| **Server** | Local HTTP server for games: draws media by tags, converts for game engines (PNG/JPEG, VP8 IVF). Works on a pack (SQLite) or MySQL; private key optional. | home window |
| **Preview** | Web page to try tag requests, with or without the server. | [`web/preview.html`](web/preview.html) |
| **Browser reader** | One JavaScript file to draw media from a pack in a browser game, without any server. | [`web/epmts-pack.js`](web/epmts-pack.js) |
| **PHP scripts** | Command-line tools: create a pack, add media, add a person, merge, validate, manage the catalogue. | [`tools/php/`](tools/php/) |
| **Standard** | The normative specification of the API, the pack format and the tagging rules. | [`standard/EPMTS-HTTP.md`](standard/EPMTS-HTTP.md) |

No media is included in this repository.

## Quick start

1. **Download** this repository (green *Code* button › *Download ZIP*, or `git clone`) and unzip it.
2. **Double-click `quickstart.cmd`** (Windows) or run `./quickstart.sh` (Linux/macOS). The first
   start offers to install what is missing (Python, ffmpeg), then the home window opens.
3. **Import your downloaded media pack**: *Import a media pack (.zip)…*. Every file is checked
   against its SHA-256 before anything is imported.
4. **Use it** in your project:
   - a **browser game** → copy the pack folder next to your game and use
     [`web/epmts-pack.js`](web/epmts-pack.js) ([guide](docs/en/web-games.md));
   - a **game or mod that calls an API** →
     *Start the server* and give the game the address shown ([guide](docs/en/game-integration.md));
   - **anything else** → read `tags.sqlite` directly with the SQL of the [standard](standard/EPMTS-HTTP.md).

New to all this? Follow the **[getting started guide](docs/en/getting-started.md)** step by step.

## Documentation

- [Getting started](docs/en/getting-started.md) — from a downloaded pack to your game
- [How to tag a media](docs/en/tagging.md) — who does what to whom
- [Person packs](docs/en/person-packs.md) — keep the same person through a story
- [The editor](docs/en/editor.md)
- [The server](docs/en/server.md) — configuration, SQLite or MySQL, API keys, network
- [Browser games](docs/en/web-games.md) — `epmts-pack.js`, the preview page
- [Games and mods using the API](docs/en/game-integration.md)
- [PHP command-line tools](docs/en/php-tools.md)
- [The tag catalogue and how to add a tag](catalogue/README.md)
- [The standard](standard/EPMTS-HTTP.md)
- [Guide du débutant (français)](docs/fr/guide-debutant.md)
- [Guide de tagage (français)](docs/fr/guide-tagage.md)
- [Packs personnage (français)](docs/fr/packs-personnage.md)

## Repository layout

```
catalogue/      catalogue.json (the reference), logos/<tagId>.png, TAGS.md (generated)
empty-pack/     an empty pack holding the whole catalogue (generated)
standard/       EPMTS-HTTP.md, the normative specification
tools/python/   epmts/ (shared core), home/, editor/, server/, epmts_cli.py, tests/
tools/php/      command-line scripts and their library
tools/setup/    what quickstart runs (Python, ffmpeg and packages installation)
web/            preview page, epmts-pack.js, browser game example, vendor/sql.js
docs/           guides (en, fr)
packs/          your packs (not versioned)
```

## License

EPMTS is free for any **noncommercial** use under the
[PolyForm Noncommercial License 1.0.0](LICENSE): use it, change it, share it and build packs with
it, keeping the [NOTICE](NOTICE) file and its link to the original project
(https://github.com/phenixxx69/epmts). **Making money with EPMTS needs a commercial license**:
see [COMMERCIAL.md](COMMERCIAL.md). Tag ids stay those of this repository's catalogue. Every
distributed pack names the original project in its `pack.json`.

## Development

```
# Python tests (core, packs, import, server)
.venv/bin/python -m unittest discover -s tools/python/tests
# Rebuild TAGS.md and empty-pack/ after a catalogue change
php tools/php/catalogue_build.php
```

The Python core (`tools/python/epmts`) and the PHP library (`tools/php/lib/epmts.php`) write
byte-identical packs; keep them in step when the format changes.
