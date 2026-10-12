# The server

The server implements the [EPMTS-HTTP standard](../../standard/EPMTS-HTTP.md): a game asks for
"a media with these tags" and gets a temporary link to a file it can display.

## Starting

The simplest way is the home window (*Start the server*): it asks whether a private key is
needed and shows the address and key to give your game. Without the home window:

```
quickstart.cmd server                          (Windows)
./quickstart.sh server                         (Linux / macOS)
./quickstart.sh server path/to/pack --no-key   another pack, no key required
```

On first start it creates `tools/python/server/config.json` with a random **API key**, and an
empty pack in `packs/main` if there is none. The console shows the game address, the key, the
preview address and whether ffmpeg was found. Stop it with Ctrl+C.

## Configuration (`tools/python/server/config.json`)

| Key | Default | Meaning |
| --- | --- | --- |
| `backend` | `sqlite` | `sqlite` serves a pack; `mysql` serves a MySQL database. |
| `pack_dir` | `packs/main` | The pack served by the `sqlite` backend (relative to the repository). |
| `host` | `127.0.0.1` | Listening address. `127.0.0.1` = this computer only; `0.0.0.0` = your local network too. |
| `port` | `5055` | Listening port. |
| `public_base_url` | empty | Base of the links handed out, when the server is behind a proxy (e.g. `https://media.example.net`). Empty = the address the client used. |
| `require_api_key` | `true` | `false` = requests need no key (fine when only this computer can reach the server). `--no-key` / `--key` override it. |
| `api_keys` | generated | Accepted keys. Give each game or friend its own key; remove one to revoke it. |
| `link_secret` | generated | Signs the temporary file links. Changing it invalidates links handed out. |
| `link_ttl_seconds` | `3600` | Lifetime of a file link. |
| `video_wait_seconds` | `2` | How long a request waits for a video conversion before answering "converting, retry". |
| `cache_dir` | `cache` | Converted files and media ids. Safe to delete when the server is stopped. |
| `logos_dir` | catalogue logos | Where tag logos are read (`<id>.png`). |
| `mysql`, `media_root`, `media_storage` | — | Only for `backend: mysql`, see below. |

## Routes

| Route | Key | Purpose |
| --- | --- | --- |
| `GET /specification` | no | The standard, as Markdown. |
| `GET /tags` | yes | The tag catalogue with logos. |
| `POST /select` | yes | Draws one media. Body: `format`, `includeTagImg`, `excludeTagImg`, `excludeTypeTag`, `convert`, `max_video_time`, `referenceHash`. |
| `POST /media/{mediaId}` | yes | Describes a media again; also the status address of a running conversion. |
| `GET /file/…` | no (signed) | Temporary link to a file. |
| `GET /preview/` | no | The preview page (asks the key, keeps it in your browser). |
| `GET /health` | no | `{"status": "ok"}`. |

Example:

```
curl -X POST http://127.0.0.1:5055/select \
     -H "Authorization: Bearer YOUR_KEY" -H "Content-Type: application/json" \
     -d '{"format": "img", "includeTagImg": [1, 56], "convert": "jpg"}'
```

## Conversions

| `convert` | Result |
| --- | --- |
| `none` | The stored file (what a browser shows best). |
| `auto` | JPEG/PNG pictures for `img`; VP8 IVF video (+ OGG sound) for `gif`, `video`, `animated`. |
| `png`, `jpg` | A still picture (the first usable image of an animation). |
| `ivf` | VP8 video, 30 fps, at most 1280 px wide and 60 s: what game engines that decode VP8 only can play. |

Pictures are converted while the client waits. Videos are converted in the background: the
answer says `"converted": false` with a `statusUrl` to poll and a `posterUrl` still picture.
Video conversion needs ffmpeg (the launchers offer to install it).

## Person packs (PR-1)

When the drawn media is the portrait of a person pack, the answer carries `referenceHash`. A
following `/select` with the same `referenceHash` draws only among that person's media. If the
person has nothing matching, the answer is `{"found": false}`: the game decides whether to try
again without the reference.

## MySQL backend

For a large shared catalogue kept in MySQL, with the same four tables as a pack
(`type_tag`, `tag_media`, `media`, `media_has_tag_media`):

```json
"backend": "mysql",
"mysql": {"host": "127.0.0.1", "port": 3306, "user": "reader", "password": "…", "database": "media"},
"media_root": "/srv/media",
"media_storage": "hash"
```

`media_storage`: `hash` = file named `<sha256>` in `media_root`; `path` = `media.path` relative to
`media_root`; `auto` = both. Files outside `media_root` are never served. Install the driver
once: `.venv/bin/python -m pip install -r tools/python/server/requirements-mysql.txt`. Give the
server a MySQL user that can only read those four tables. Person packs are not available with
MySQL.

## Opening the server to other computers

- On your local network: set `"host": "0.0.0.0"` and allow the port in your firewall; clients use
  `http://<this computer's address>:5055`.
- On the internet: put it behind a reverse proxy with HTTPS (nginx, Caddy…), set
  `public_base_url`, and keep one key per user. The built-in server is meant for local use.

The server never lists folders and never exposes file names or paths: media are reached only
through opaque ids and signed, expiring links.
