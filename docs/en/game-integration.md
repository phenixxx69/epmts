# Games and mods using the API

Any game that can send an HTTP request can use EPMTS through the server: it posts the tags it
wants and downloads the file it gets back. The server converts media into formats game engines
read (JPEG/PNG pictures, VP8 IVF video with an OGG sound track).

## Example: connecting a game or mod

1. Import your pack into `packs/main` ([getting-started.md](getting-started.md)).
2. On the computer that runs the game, double-click `quickstart.cmd` and click *Start the
   server*. Answer *No* to the private key question if you play alone on this computer. Leave
   the window open; it shows the address (and the key, if you chose one).
3. In the media settings of your game or mod, fill in:

   | Setting | Value |
   | --- | --- |
   | Media address | `http://127.0.0.1:5055/select` (the tag catalogue is at `/tags` beside it) |
   | Key | empty without a private key; otherwise the key shown |
   | Conversion | what the engine displays: `jpg`/`png` pictures, `ivf` (VP8) videos, or `auto` |
   | Maximum file size | 32 MB or more, for converted videos |
   | Maximum video length | e.g. 60 seconds |

The first video of each media takes a few seconds to convert; later ones come from the server
cache.

**Server on another computer**: set `"host": "0.0.0.0"` in `tools/python/server/config.json`,
allow port 5055 in that computer's firewall, and use its address in the game
(e.g. `http://192.168.x.y:5055/select`).

**In your story or event files**, refer to tags by id (for example `56`). The ids are those of
[catalogue/TAGS.md](../../catalogue/TAGS.md) — the same in every EPMTS pack, which is why a
story written once works with anyone's pack. Tags can also be looked up by name in `/tags`
(for example the actor directions `M>F`, `F>F`…), to adapt a request to the player's character.

## Any other engine

The protocol is small; the whole specification is [standard/EPMTS-HTTP.md](../../standard/EPMTS-HTTP.md).

1. `GET /tags` once, with `Authorization: Bearer <key>` when the server requires a key, to show
   or check tag names (optional).
2. `POST /select` with JSON:

   ```json
   {"format": "img", "includeTagImg": [1, 56], "excludeTagImg": [], "excludeTypeTag": [], "convert": "jpg"}
   ```

3. Read the answer:
   - `{"found": false}` → nothing matches: show your fallback;
   - `"converted": true` → download `url` (and `audioUrl` for a video sound track) — the links
     expire, download them at once;
   - `"converted": false` with `statusUrl` → wait `retryAfterSeconds`, then `POST` the same body
     to `statusUrl`; meanwhile `posterUrl` is a still picture you may show;
   - `"converted": false` with `error` → give up, show your fallback.
4. Keep `mediaId` to show the same media again later: `POST /media/{mediaId}`.
5. Person continuity: if an answer has `referenceHash`, send it back in the next `/select` to
   stay with the same person; on `{"found": false}`, retry without it if you want
   ([Person packs](person-packs.md)).

Pick `convert` for your engine: `none` (stored file, for browsers and engines that read
WebP/GIF/MP4), `jpg`/`png` (still pictures), `ivf` (VP8 video), `auto` (pictures for `img`,
VP8 for moving formats).

Engines that cannot do HTTP can read `tags.sqlite` directly: copy the pack into the game and
query it with the rules of the standard (section 11.4), as `tools/python/epmts/rules.py` does.
