"""EPMTS media server: the EPMTS-HTTP standard over an EPMTS pack (SQLite) or a MySQL catalogue.

Routes (see standard/EPMTS-HTTP.md):
  GET  /specification      the standard, public
  GET  /tags               the tag catalogue
  POST /select             draws one media
  POST /media/<mediaId>    describes a media again (and polls a conversion)
  GET  /file/<token>       temporary signed link to a file, no key needed
  GET  /preview/           the preview page
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import sys
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, Response, abort, jsonify, request, send_file  # noqa: E402

from epmts import REPO_ROOT, STANDARD_PATH, rules  # noqa: E402
from epmts import media as media_tools  # noqa: E402
from epmts.catalogue import logo_path  # noqa: E402

from backends import MysqlBackend, SqliteBackend  # noqa: E402
from conversion import FAILED, PROFILES, READY, Converter  # noqa: E402

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(SERVER_DIR, "config.json")
WEB_DIR = os.path.join(REPO_ROOT, "web")
PREVIEW_FILES = {
    "preview.html": "text/html",
    "preview.js": "application/javascript",
    "preview.css": "text/css",
    "epmts-pack.js": "application/javascript",
    "vendor/sql.js/sql-asm.js": "application/javascript",
}

CONVERT_VALUES = ("auto", "none", "png", "jpg", "ivf")
HASH_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
MEDIA_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,255}$")
RETRY_AFTER_SECONDS = 1


class BadRequest(ValueError):
    """A request value outside the standard (answered with 400)."""


# Reads the JSON configuration and resolves its relative paths from the repository root.
def load_config(path):
    with open(path, "r", encoding="utf-8") as handle:
        config = json.load(handle)
    for key in ("pack_dir", "cache_dir", "media_root", "logos_dir"):
        if config.get(key) and not os.path.isabs(config[key]):
            config[key] = os.path.abspath(os.path.join(REPO_ROOT, config[key]))
    return config


class MediaIdRegistry:
    """Opaque, stable media ids: random strings mapped to (context, hash) in a small SQLite file."""

    # Opens or creates the registry database.
    def __init__(self, cache_dir):
        self.path = os.path.join(cache_dir, "media_ids.sqlite")
        self.lock = threading.Lock()
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS media_id (media_id TEXT PRIMARY KEY, context TEXT NOT NULL, hash TEXT NOT NULL, UNIQUE (context, hash))"
            )

    # Opens a connection on the registry.
    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    # Returns the media id of (context, hash), creating it once.
    def get(self, context, media_hash):
        with self.lock, self._connect() as connection:
            row = connection.execute("SELECT media_id FROM media_id WHERE context = ? AND hash = ?", (context, media_hash)).fetchone()
            if row:
                return row[0]
            media_id = secrets.token_urlsafe(18)
            connection.execute("INSERT INTO media_id VALUES (?, ?, ?)", (media_id, context, media_hash))
            return media_id

    # Returns (context, hash) for a media id, or None.
    def resolve(self, media_id):
        with self._connect() as connection:
            row = connection.execute("SELECT context, hash FROM media_id WHERE media_id = ?", (media_id,)).fetchone()
        return (row[0], row[1]) if row else None


class LinkSigner:
    """Expiring links: /file/<payload>.<signature>.<extension>."""

    # Keeps the signing secret and the link lifetime.
    def __init__(self, secret, ttl_seconds):
        self.secret = secret.encode("utf-8")
        self.ttl = int(ttl_seconds)

    # Signs a payload with HMAC-SHA256.
    def _sign(self, payload):
        return base64.urlsafe_b64encode(hmac.new(self.secret, payload.encode("ascii"), hashlib.sha256).digest()[:24]).decode("ascii").rstrip("=")

    # Builds the token of a file: media id, variant (native, png, jpg, ivf, ogg) and expiry.
    def token(self, media_id, variant, extension):
        raw = json.dumps([media_id, variant, int(time.time()) + self.ttl], separators=(",", ":"))
        payload = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
        return "{}.{}.{}".format(payload, self._sign(payload), extension)

    # Returns (media_id, variant) of a valid unexpired token, or None.
    def verify(self, token):
        parts = token.split(".")
        if len(parts) != 3 or not hmac.compare_digest(self._sign(parts[0]), parts[1]):
            return None
        try:
            media_id, variant, expires = json.loads(base64.urlsafe_b64decode(parts[0] + "=" * (-len(parts[0]) % 4)))
        except (ValueError, TypeError):
            return None
        if expires < time.time():
            return None
        return media_id, variant


# Builds the Flask application from a loaded configuration.
def create_app(config):
    app = Flask(__name__)
    cache_dir = config.get("cache_dir") or os.path.join(REPO_ROOT, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    if config.get("backend", "sqlite") == "mysql":
        backend = MysqlBackend(config.get("mysql") or {}, config.get("media_root") or REPO_ROOT, config.get("media_storage", "hash"))
    else:
        backend = SqliteBackend(config["pack_dir"])
    api_keys = [key for key in config.get("api_keys") or [] if key]
    key_required = config.get("require_api_key", True)
    if key_required and not api_keys:
        raise SystemExit("config.json: api_keys must hold at least one key")
    registry = MediaIdRegistry(cache_dir)
    signer = LinkSigner(config.get("link_secret") or secrets.token_hex(32), config.get("link_ttl_seconds", 3600))
    converter = Converter(cache_dir)
    video_wait = float(config.get("video_wait_seconds", 2))
    logos_dir = config.get("logos_dir")

    # Returns the base URL used in absolute links.
    def base_url():
        return (config.get("public_base_url") or request.host_url).rstrip("/")

    # Rejects a request without one of the configured keys (unless the owner turned keys off).
    def require_key():
        if not key_required:
            return
        header = request.headers.get("Authorization", "")
        given = header[7:].strip() if header.startswith("Bearer ") else ""
        if not given or not any(hmac.compare_digest(given, key) for key in api_keys):
            abort(Response(json.dumps({"error": "forbidden"}), 403, mimetype="application/json"))

    # Reads the JSON body as an object, or raises BadRequest.
    def read_body(optional=False):
        if not request.data and optional:
            return {}
        try:
            payload = json.loads(request.data.decode("utf-8") or ("{}" if optional else ""))
        except (ValueError, UnicodeDecodeError):
            raise BadRequest("invalid JSON body")
        if not isinstance(payload, dict):
            raise BadRequest("the body must be a JSON object")
        return payload

    # Reads format, convert and max_video_time from a request body.
    def read_delivery(payload):
        media_format = payload.get("format", "img")
        if media_format not in rules.FORMAT_TYPES:
            raise BadRequest("invalid format")
        convert = payload.get("convert", "auto")
        if convert is True:
            convert = "auto"
        if convert not in CONVERT_VALUES:
            raise BadRequest("invalid convert")
        max_video_time = payload.get("max_video_time")
        if max_video_time is not None and (isinstance(max_video_time, bool) or not isinstance(max_video_time, int) or not 1 <= max_video_time <= 3600):
            raise BadRequest("invalid max_video_time")
        return media_format, convert, max_video_time

    # Chooses the converted profile to deliver, or None for the native file.
    def resolve_profile(row, media_format, convert):
        if convert == "none":
            return None
        if convert != "auto":
            return convert
        family = media_tools.family(row["type"])
        if media_format == "img" or (media_format == "all" and family == "still"):
            return None if row["type"] in ("image/jpeg", "image/png") else "jpg"
        return "ivf"

    # Builds the ready, deferred or failed answer for one media row.
    def describe(context, row, media_format, convert):
        media_id = registry.get(context, row["hash"])
        answer = {"found": True, "mediaId": media_id}
        if not context and backend.is_portrait(row["hash"]):
            answer["referenceHash"] = row["hash"]
        source = backend.file_path(context, row["hash"])
        if source is None:
            return {"found": False}
        profile = resolve_profile(row, media_format, convert)
        if profile is None:
            extension = media_tools.EXTENSIONS.get(row["type"], "bin")
            answer.update({
                "format": "video" if media_tools.family(row["type"]) in ("gif", "film") else "img",
                "converted": True,
                "url": base_url() + "/file/" + signer.token(media_id, "native", extension),
                "audioUrl": None,
            })
            return answer
        state, _ = converter.request(source, row["hash"], row["type"], profile, video_wait)
        answer["format"] = PROFILES[profile]["kind"]
        if state == READY:
            audio = None
            if profile == "ivf" and os.path.isfile(converter.audio_path(row["hash"])):
                audio = base_url() + "/file/" + signer.token(media_id, "ogg", "ogg")
            answer.update({"converted": True, "url": base_url() + "/file/" + signer.token(media_id, profile, PROFILES[profile]["extension"]), "audioUrl": audio})
            return answer
        answer["converted"] = False
        poster_state = None
        if PROFILES[profile]["kind"] == "video":
            poster_state, _ = converter.request(source, row["hash"], row["type"], "jpg")
        if poster_state == READY:
            answer["posterUrl"] = base_url() + "/file/" + signer.token(media_id, "jpg", "jpg")
        if state == FAILED:
            answer["error"] = "conversion_failed"
            return answer
        answer.update({"retryAfterSeconds": RETRY_AFTER_SECONDS, "elapsedSeconds": converter.elapsed(row["hash"], profile), "statusUrl": base_url() + "/media/" + media_id})
        return answer

    # Turns BadRequest into a generic 400 answer.
    @app.errorhandler(BadRequest)
    def bad_request(error):
        return jsonify({"error": str(error)}), 400

    # Adds CORS headers so browser games may call the API.
    @app.after_request
    def cors(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    # Serves the standard, without a key.
    @app.route("/specification", methods=["GET"])
    def specification():
        with open(STANDARD_PATH, "r", encoding="utf-8") as handle:
            return Response(handle.read(), content_type="text/markdown; charset=utf-8")

    # Reports that the server is running.
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    # Returns the tag catalogue.
    @app.route("/tags", methods=["GET", "OPTIONS"])
    def tags():
        if request.method == "OPTIONS":
            return "", 204
        require_key()
        result = []
        for row in backend.tags():
            tag = {
                "id": int(row["id"]),
                "name": row["name"] or "",
                "keywords": row["subcategory_name"] or "",
                "subcategory": row["subcategory_name"] or "",
                "description": row["description"] or "",
                "descriptionFr": row["description_fr"] or "",
                "typeId": int(row["type_tag"]) if row["type_tag"] is not None else None,
                "typeName": row["type_name"] or "",
            }
            path = logo_path(row["id"], logos_dir)
            if path:
                with open(path, "rb") as handle:
                    tag["logoBase64"] = "data:image/png;base64," + base64.b64encode(handle.read()).decode("ascii")
            result.append(tag)
        return jsonify({"tags": result})

    # Draws one media matching the request.
    @app.route("/select", methods=["POST", "OPTIONS"])
    def select():
        if request.method == "OPTIONS":
            return "", 204
        require_key()
        payload = read_body()
        media_format, convert, max_video_time = read_delivery(payload)
        try:
            include = rules.parse_tag_list(payload.get("includeTagImg"), "includeTagImg")
            exclude = rules.parse_tag_list(payload.get("excludeTagImg"), "excludeTagImg")
            exclude_types = rules.parse_tag_list(payload.get("excludeTypeTag"), "excludeTypeTag")
        except rules.RuleViolation as error:
            raise BadRequest(str(error))
        context = ""
        if payload.get("referenceHash") is not None:
            reference = payload["referenceHash"]
            if not isinstance(reference, str) or not HASH_PATTERN.match(reference):
                raise BadRequest("invalid referenceHash")
            context = reference.lower()
            if not backend.supports_reference or not backend.has_context(context):
                return jsonify({"found": False})
        row = backend.select(context, include, exclude, exclude_types, media_format, max_video_time)
        if row is None:
            return jsonify({"found": False})
        return jsonify(describe(context, row, media_format, convert))

    # Describes a media again; also the status address of a conversion.
    @app.route("/media/<media_id>", methods=["POST", "OPTIONS"])
    def describe_again(media_id):
        if request.method == "OPTIONS":
            return "", 204
        require_key()
        payload = read_body(optional=True)
        media_format, convert, max_video_time = read_delivery(payload)
        resolved = registry.resolve(media_id) if MEDIA_ID_PATTERN.match(media_id) else None
        row = backend.find(*resolved) if resolved else None
        if row is None:
            return jsonify({"found": False}), 404
        if max_video_time is not None and media_tools.family(row["type"]) == "film" and row.get("duration") and row["duration"] > max_video_time:
            return jsonify({"found": False})
        return jsonify(describe(resolved[0], row, media_format, convert))

    # Serves a file behind a temporary signed link.
    @app.route("/file/<token>", methods=["GET"])
    def serve_file(token):
        verified = signer.verify(token)
        resolved = registry.resolve(verified[0]) if verified else None
        if resolved is None:
            abort(404)
        context, media_hash = resolved
        variant = verified[1]
        if variant == "native":
            row = backend.find(context, media_hash)
            path = backend.file_path(context, media_hash) if row else None
            mimetype = row["type"] if row else None
        elif variant == "ogg":
            path, mimetype = converter.audio_path(media_hash), "audio/ogg"
        elif variant in PROFILES:
            path, mimetype = converter.path(media_hash, variant), PROFILES[variant]["content_type"]
        else:
            path = mimetype = None
        if not path or not os.path.isfile(path):
            abort(404)
        response = send_file(path, mimetype=mimetype, conditional=True)
        response.headers["Cache-Control"] = "private, max-age=300"
        return response

    # Serves the preview page and its assets (a fixed list: nothing else of the disk is reachable).
    @app.route("/preview/", defaults={"name": "preview.html"})
    @app.route("/preview/<path:name>")
    def preview(name):
        if name not in PREVIEW_FILES:
            abort(404)
        return send_file(os.path.join(WEB_DIR, name), mimetype=PREVIEW_FILES[name])

    return app


# Creates config.json from config.dist.json on first start, with a random key and link secret.
def ensure_config(path):
    if os.path.isfile(path) or path != DEFAULT_CONFIG_PATH:
        return
    with open(os.path.join(SERVER_DIR, "config.dist.json"), "r", encoding="utf-8") as handle:
        config = json.load(handle)
    config["api_keys"] = [secrets.token_urlsafe(24)]
    config["link_secret"] = secrets.token_hex(32)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
    print("  First start: {} created with a new API key.".format(os.path.relpath(path, REPO_ROOT)))


# Creates the default pack (packs/main) when it does not exist yet.
def ensure_pack(config):
    if config.get("backend", "sqlite") != "sqlite" or os.path.isfile(os.path.join(config["pack_dir"], "tags.sqlite")):
        return
    if os.path.isdir(config["pack_dir"]) and os.listdir(config["pack_dir"]):
        raise SystemExit("{} is not a pack (no tags.sqlite). Fix pack_dir in the configuration.".format(config["pack_dir"]))
    from epmts.pack import Pack
    Pack.create(config["pack_dir"]).close()
    print("  No pack yet: an empty one was created in {}. Import a pack with the editor.".format(config["pack_dir"]))


# Parses the command line, loads the configuration and runs the server.
def main():
    parser = argparse.ArgumentParser(description="EPMTS media server")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="configuration file (default: server/config.json)")
    parser.add_argument("pack_folder", nargs="?", help="pack folder to serve (same as --pack)")
    parser.add_argument("--pack", help="pack folder to serve (overrides pack_dir)")
    parser.add_argument("--host", help="listening address (overrides host)")
    parser.add_argument("--port", type=int, help="listening port (overrides port)")
    parser.add_argument("--no-key", dest="require_key", action="store_false", default=None, help="accept requests without an API key")
    parser.add_argument("--key", dest="require_key", action="store_true", help="require an API key (default)")
    args = parser.parse_args()
    ensure_config(args.config)
    config = load_config(args.config)
    if args.pack or args.pack_folder:
        config["backend"] = "sqlite"
        config["pack_dir"] = os.path.abspath(args.pack or args.pack_folder)
    if args.require_key is not None:
        config["require_api_key"] = args.require_key
    ensure_pack(config)
    host = args.host or config.get("host", "127.0.0.1")
    port = args.port or int(config.get("port", 5055))
    app = create_app(config)
    shown_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    print("")
    print("  EPMTS server running")
    print("  Catalogue : {}".format(config.get("pack_dir") if config.get("backend", "sqlite") == "sqlite" else "MySQL"))
    print("  API base  : http://{}:{}".format(shown_host, port))
    print("  Preview   : http://{}:{}/preview/".format(shown_host, port))
    print("  Game URL  : http://{}:{}/select".format(shown_host, port))
    print("  API key   : {}".format(config["api_keys"][0] if config.get("require_api_key", True) else "not required"))
    print("  ffmpeg    : {}".format(media_tools.find_tool("ffmpeg") or "NOT FOUND (videos cannot be converted)"))
    print("  Stop with Ctrl+C")
    print("")
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
