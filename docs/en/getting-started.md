# Getting started

This guide takes you from "I downloaded a media pack" to "my game shows those media". No
programming knowledge is needed until the last step.

## 1. Start EPMTS

1. Download this repository (green *Code* button › *Download ZIP*) and unzip it anywhere —
   avoid protected folders such as `C:\Program Files`.
2. **Windows**: double-click **`quickstart.cmd`**.
   **Linux / macOS**: open a terminal in the folder and run `./quickstart.sh`.
3. The first time, it checks your computer and **asks before installing** anything missing:
   - **Python** (the tools are written in it). On Windows it is downloaded from python.org and
     installed for you; on Linux your package manager is used (it may ask your password).
   - **ffmpeg** (to read videos). Optional: pictures work without it.
   Then it prepares a private environment in `.venv/` (about a minute, only once).
4. The **EPMTS home window** opens. Next time, double-clicking `quickstart.cmd` opens it at once.

The home window tells you how many media you have — *No media found* at first — and where they
come from, and offers four buttons.

## 2. Import the pack you downloaded

Click **Import a media pack (.zip)…** and choose the zip. Before importing anything, EPMTS
checks the whole pack:

- every expected file and folder is there, and nothing else;
- the database is valid;
- **every media file matches its SHA-256 fingerprint** (no corrupted or replaced file);
- the tagging rules of the [standard](../../standard/EPMTS-HTTP.md) are respected.

If anything is wrong, nothing is imported and the problems are listed. Otherwise you are back
on the home window, which now shows, for example, *1 250 media found — 1 250 from "Pack name"*.
Import as many packs as you like: a media present in two packs appears once, with all its tags,
and each media remembers the pack it came from.

## 3. Use the media in a game

### A game that asks a server (a game mod, Ren'Py, Unity…)

Click **Start the server**. EPMTS asks whether games need a **private key**:

- **No** — any program on this computer can ask for media. Simplest when you play alone.
- **Yes** — only programs that know the key. Choose this when other people can reach your
  computer.

The home window then shows the **address to give your game** (and the key, if any), with
*Copy* buttons. Keep the window open while you play; *Stop the server* or closing the window
stops it. What to fill in the game: [game-integration.md](game-integration.md).

The server converts media for game engines: pictures to JPEG/PNG, animations to VP8 IVF video
with an OGG sound track. The first video of a media takes a few seconds.

### A browser game (HTML/JavaScript)

Copy your pack folder (`packs/main`) next to your game and add two script files: see
[web-games.md](web-games.md). `web/example-browser-game.html` is a working demo.

### Any other program

`packs/main/tags.sqlite` is a normal SQLite database. The selection rules are in the
[standard](../../standard/EPMTS-HTTP.md) (sections 4 and 11).

## 4. Look at your media

**Preview the media in your browser** opens a page where you click tags to include or exclude
them and draw media exactly as a game would — no server needed.

## 5. Manage your media and make your own packs

**Open the media manager** to:

- browse your media with filters by tag, type and **origin** (*Local* = added by you, or the
  name of an imported pack);
- **edit the tags** of a media (tags marked 🔞 are porn actions) — read
  [How to tag a media](tagging.md) first;
- **add your own files** in the *Import* tab: they are cleaned of their metadata (camera, GPS,
  names…), renamed by fingerprint, and marked *local*;
- create **person packs** (*Person › New person pack from a portrait…*): several media of the
  same person, so that a story keeps the same character from scene to scene
  ([Person packs](person-packs.md));
- **share your work**: *File › Create a pack from my local media…* (only what you added) or
  *File › Create a pack from all media…* (everything, imported packs included). EPMTS asks the
  pack name, author, version and date, and saves a ready-to-share `.zip` holding a `pack.json`
  with these details. Your local media in it are then marked as coming from that pack, so a
  later "local media" pack holds only what you add afterwards.

Everything is saved at once.

## 6. Keep the tag catalogue up to date

When this repository gets new tags, download it again (or `git pull`), then in the media
manager *File › Update the tag catalogue*. Your media and their tags are kept.

## Troubleshooting

| Problem | Solution |
| --- | --- |
| Windows says "Windows protected your PC" | *More info › Run anyway* (the scripts are plain text you can read). |
| "Your Python has no tcl/tk" | Windows: answer *y*, quickstart adds it to your Python (or installs a separate Python for EPMTS if that is impossible). Linux: accept the proposed install. |
| Videos show no thumbnail | ffmpeg is missing: run `quickstart` again and accept the download. |
| The import is refused | Read the listed problems: the pack is damaged or incomplete. Download it again. |
| The server does not start | Another program uses port 5055: change `port` in `tools/python/server/config.json`. |
| The game gets nothing | Check the address (it ends with `/select`), the key, that the server is running, and the tags in the preview. |

Advanced use: `quickstart.cmd editor` or `quickstart.cmd server` start the media manager or the
server directly ([editor.md](editor.md), [server.md](server.md)).
