"""The MP-1 media pack: tags.sqlite, tags.sql, tags.sql.js and medias/<sha256>.

A pack directory is self-contained. A person pack is a pack stored at medias/<portraitSha256>/
inside another pack (standard section 11.1.1).
"""

import base64
import datetime
import json
import os
import re
import shutil
import sqlite3

from . import media as media_tools
from . import rules
from .catalogue import TAG_COLUMNS, TYPE_COLUMNS, load_catalogue

DATABASE = "tags.sqlite"
DUMP = "tags.sql"
BROWSER_DUMP = "tags.sql.js"
MANIFEST = "pack.json"
MANIFEST_FORMAT = "EPMTS-MP-1"
MANIFEST_FIELDS = ("name", "author", "version", "date")
# Every distributed pack names the original project (standard section 11.1.2, NOTICE).
PROJECT_URL = "https://github.com/phenixxx69/epmts"
MEDIA_DIRECTORY = "medias"
DUMP_ROWS_PER_INSERT = 500
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")

SCHEMA = (
    """CREATE TABLE type_tag (
            id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            position INTEGER DEFAULT 0,
            color VARCHAR(255) DEFAULT 'black'
        )""",
    """CREATE TABLE tag_media (
            id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR(45) DEFAULT NULL,
            logo VARCHAR(255) DEFAULT NULL,
            type_tag INTEGER DEFAULT NULL REFERENCES type_tag (id),
            subcategory_name VARCHAR(45) DEFAULT NULL,
            description VARCHAR(255) DEFAULT NULL,
            description_fr VARCHAR(255) DEFAULT NULL,
            ia_text VARCHAR(255) DEFAULT NULL,
            porn INTEGER NOT NULL DEFAULT 0
        )""",
    """CREATE TABLE media (
            id INTEGER NOT NULL PRIMARY KEY,
            size INTEGER DEFAULT NULL,
            hash CHAR(64) NOT NULL UNIQUE,
            unique_use INTEGER DEFAULT NULL,
            type VARCHAR(32) NOT NULL,
            size_x INTEGER DEFAULT NULL,
            size_y INTEGER DEFAULT NULL,
            path VARCHAR(255) DEFAULT NULL,
            duration REAL DEFAULT NULL,
            origin VARCHAR(255) DEFAULT NULL
        )""",
    """CREATE TABLE media_has_tag_media (
            media_id INTEGER NOT NULL REFERENCES media (id) ON DELETE CASCADE,
            tag_media_id INTEGER NOT NULL REFERENCES tag_media (id),
            PRIMARY KEY (media_id, tag_media_id)
        )""",
)

INDEXES = (
    "CREATE INDEX idx_tag_media_type_tag ON tag_media (type_tag)",
    "CREATE INDEX idx_media_type ON media (type)",
    "CREATE INDEX idx_media_has_tag_media_tag ON media_has_tag_media (tag_media_id, media_id)",
)

REQUIRED_COLUMNS = {
    "type_tag": set(TYPE_COLUMNS),
    "tag_media": set(TAG_COLUMNS),
    "media": {"id", "size", "hash", "unique_use", "type", "size_x", "size_y", "path", "duration", "origin"},
    "media_has_tag_media": {"media_id", "tag_media_id"},
}

# Columns that older packs may lack; upgrade_schema() adds them.
UPGRADABLE_COLUMNS = {
    ("tag_media", "description_fr"): "VARCHAR(255) DEFAULT NULL",
    ("tag_media", "porn"): "INTEGER NOT NULL DEFAULT 0",
    ("media", "duration"): "REAL DEFAULT NULL",
    ("media", "origin"): "VARCHAR(255) DEFAULT NULL",
}


class PackError(Exception):
    """A pack that cannot be opened, written or merged as asked."""


# Writes a value as an SQL literal, the same way as the PHP tools.
def _quote(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return json.dumps(value)
    return "'" + str(value).replace("'", "''") + "'"


# Checks a manifest dict and returns it normalised (raises PackError when a field is wrong).
def check_manifest(manifest):
    if not isinstance(manifest, dict):
        raise PackError("{} must hold a JSON object".format(MANIFEST))
    if manifest.get("project", PROJECT_URL) != PROJECT_URL:
        raise PackError("{}: 'project' must be {}".format(MANIFEST, PROJECT_URL))
    clean = {"format": MANIFEST_FORMAT, "project": PROJECT_URL}
    for field in MANIFEST_FIELDS:
        value = str(manifest.get(field) or "").strip()
        if not value or len(value) > 255:
            raise PackError("{}: '{}' is required (at most 255 characters)".format(MANIFEST, field))
        clean[field] = value
    try:
        datetime.date.fromisoformat(clean["date"])
    except ValueError:
        raise PackError("{}: date must be YYYY-MM-DD".format(MANIFEST))
    clean["description"] = str(manifest.get("description") or "").strip()[:2000]
    return clean


# Reads the manifest of a pack folder, or None when it has none.
def read_manifest(directory):
    path = os.path.join(directory, MANIFEST)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except ValueError:
        raise PackError("{} is not valid JSON".format(MANIFEST))
    # A received pack must name the project itself; only a pack being built gets it added.
    if not isinstance(manifest, dict) or manifest.get("project") != PROJECT_URL:
        raise PackError("{}: 'project' must be {}".format(MANIFEST, PROJECT_URL))
    return check_manifest(manifest)


# Wraps the SQL dump into the script that browser readers load.
def build_browser_dump(sql):
    encoded = base64.b64encode(sql.encode("utf-8")).decode("ascii")
    return (
        'var encodedStr = "' + encoded + '";\n'
        "var db_str = new TextDecoder().decode(Uint8Array.from(atob(encodedStr), function (c) { return c.charCodeAt(0); }));\n"
    )


class Pack:
    """One open pack directory."""

    # Opens an existing pack; use Pack.create() for a new one. With in_memory, the database is
    # copied into memory: an upgrade or a check never writes to the source folder.
    def __init__(self, directory, upgrade=False, in_memory=False):
        self.directory = os.path.realpath(directory)
        self.db_path = os.path.join(self.directory, DATABASE)
        if not os.path.isfile(self.db_path):
            raise PackError("No {} in {}".format(DATABASE, self.directory))
        try:
            if in_memory:
                self.conn = sqlite3.connect(":memory:")
                with sqlite3.connect("file:{}?mode=ro".format(self.db_path), uri=True) as disk:
                    disk.backup(self.conn)
            else:
                self.conn = sqlite3.connect(self.db_path)
            self.conn.execute("SELECT name FROM sqlite_master LIMIT 1")
        except sqlite3.DatabaseError as error:
            raise PackError("{} is not a valid SQLite database ({})".format(DATABASE, error))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if upgrade:
            self.upgrade_schema()
        missing = self.missing_columns()
        if missing:
            self.conn.close()
            raise PackError("Not an EPMTS pack (missing {}). Open it with the upgrade option.".format(", ".join(missing)))

    # Creates a new pack holding the whole catalogue and no media.
    @classmethod
    def create(cls, directory, catalogue=None):
        directory = os.path.realpath(directory)
        if os.path.isdir(directory) and os.listdir(directory):
            raise PackError("The target directory is not empty: {}".format(directory))
        os.makedirs(os.path.join(directory, MEDIA_DIRECTORY), exist_ok=True)
        conn = sqlite3.connect(os.path.join(directory, DATABASE))
        try:
            for statement in SCHEMA:
                conn.execute(statement)
            conn.commit()
        finally:
            conn.close()
        pack = cls(directory)
        pack.sync_catalogue(catalogue)
        for statement in INDEXES:
            pack.conn.execute(statement)
        pack.conn.commit()
        pack.export()
        return pack

    # Closes the database connection.
    def close(self):
        self.conn.close()

    # Supports "with Pack(...) as pack".
    def __enter__(self):
        return self

    # Closes the pack when leaving a "with" block.
    def __exit__(self, *exc):
        self.close()

    # Lists "table.column" entries that the standard requires but the database lacks.
    def missing_columns(self):
        missing = []
        for table, columns in REQUIRED_COLUMNS.items():
            available = {row["name"] for row in self.conn.execute("PRAGMA table_info({})".format(table))}
            if not available:
                missing.append(table)
                continue
            missing.extend("{}.{}".format(table, column) for column in sorted(columns - available))
        return missing

    # Adds the columns that older packs lack, without touching existing data.
    def upgrade_schema(self):
        for (table, column), definition in UPGRADABLE_COLUMNS.items():
            available = {row["name"] for row in self.conn.execute("PRAGMA table_info({})".format(table))}
            if available and column not in available:
                self.conn.execute("ALTER TABLE {} ADD COLUMN {} {}".format(table, column, definition))
        self.conn.commit()

    # Replaces type_tag and tag_media with the repository catalogue; ids never change.
    def sync_catalogue(self, catalogue=None):
        catalogue = catalogue or load_catalogue()
        types = {int(row["id"]): row for row in catalogue["type_tag"]}
        tags = {int(row["id"]): row for row in catalogue["tag_media"]}
        used = {row[0] for row in self.conn.execute("SELECT DISTINCT tag_media_id FROM media_has_tag_media")}
        unknown = sorted(used - set(tags))
        if unknown:
            raise PackError("This pack uses tag ids unknown to the catalogue: {}".format(unknown))
        self.conn.execute("PRAGMA foreign_keys = OFF")
        try:
            self.conn.execute("DELETE FROM tag_media")
            self.conn.execute("DELETE FROM type_tag")
            self.conn.executemany(
                "INSERT INTO type_tag ({}) VALUES ({})".format(", ".join(TYPE_COLUMNS), ", ".join("?" for _ in TYPE_COLUMNS)),
                [tuple(row.get(column) for column in TYPE_COLUMNS) for _, row in sorted(types.items())],
            )
            self.conn.executemany(
                "INSERT INTO tag_media ({}) VALUES ({})".format(", ".join(TAG_COLUMNS), ", ".join("?" for _ in TAG_COLUMNS)),
                [tuple(row.get(column) if column != "porn" else int(row.get("porn") or 0) for column in TAG_COLUMNS)
                 for _, row in sorted(tags.items())],
            )
            self.conn.commit()
        finally:
            self.conn.execute("PRAGMA foreign_keys = ON")

    # Returns the porn-flagged action tag ids of this pack.
    def porn_actions(self):
        return rules.porn_action_ids(self.conn)

    # Returns the catalogue tags as rows, ordered by type position then name.
    def tags(self):
        return self.conn.execute(
            "SELECT tm.*, tt.name AS type_name, tt.position AS type_position FROM tag_media tm "
            "LEFT JOIN type_tag tt ON tt.id = tm.type_tag "
            "ORDER BY tt.position, tt.id, tm.name COLLATE NOCASE, tm.id"
        ).fetchall()

    # Returns the tag ids of one media.
    def media_tags(self, media_id):
        return {row[0] for row in self.conn.execute("SELECT tag_media_id FROM media_has_tag_media WHERE media_id = ?", (int(media_id),))}

    # Returns one media row.
    def get_media(self, media_id):
        return self.conn.execute("SELECT * FROM media WHERE id = ?", (int(media_id),)).fetchone()

    # Returns one media row by hash.
    def get_media_by_hash(self, media_hash):
        return self.conn.execute("SELECT * FROM media WHERE hash = ?", (media_hash,)).fetchone()

    # Returns the person-pack directory named by a portrait hash, or None.
    def person_directory(self, portrait_hash):
        if not HASH_PATTERN.match(str(portrait_hash or "")):
            return None
        path = os.path.join(self.directory, MEDIA_DIRECTORY, portrait_hash)
        return path if os.path.isfile(os.path.join(path, DATABASE)) else None

    # Lists the person packs of this pack as portrait hashes.
    def person_hashes(self):
        root = os.path.join(self.directory, MEDIA_DIRECTORY)
        if not os.path.isdir(root):
            return []
        return sorted(name for name in os.listdir(root) if HASH_PATTERN.match(name) and self.person_directory(name))

    # Returns the file of a media of this pack (a portrait lives in its person pack), or None.
    def media_file(self, media_hash):
        if not HASH_PATTERN.match(str(media_hash or "")):
            return None
        plain = os.path.join(self.directory, MEDIA_DIRECTORY, media_hash)
        if os.path.isfile(plain):
            return plain
        portrait = os.path.join(plain, MEDIA_DIRECTORY, media_hash)
        return portrait if os.path.isfile(portrait) else None

    # Checks that every tag id exists and that the set respects the protected-age rule.
    def check_tags(self, tag_ids):
        tag_ids = {int(tag_id) for tag_id in tag_ids}
        known = {row[0] for row in self.conn.execute("SELECT id FROM tag_media")}
        unknown = sorted(tag_ids - known)
        if unknown:
            raise rules.RuleViolation("Unknown tag ids: {}. Tags are created only in the EPMTS repository.".format(unknown))
        rules.check_media_tags(tag_ids, self.porn_actions())
        return tag_ids

    # Replaces the tags of one media after checking them.
    def set_tags(self, media_id, tag_ids):
        tag_ids = self.check_tags(tag_ids)
        with self.conn:
            self.conn.execute("DELETE FROM media_has_tag_media WHERE media_id = ?", (int(media_id),))
            self.conn.executemany(
                "INSERT INTO media_has_tag_media (media_id, tag_media_id) VALUES (?, ?)",
                [(int(media_id), tag_id) for tag_id in sorted(tag_ids)],
            )

    # Inserts a prepared media row and its tags; returns the new id.
    def _insert_media(self, info, tag_ids):
        cursor = self.conn.execute(
            "INSERT INTO media (size, hash, unique_use, type, size_x, size_y, path, duration, origin) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)",
            (info["size"], info["hash"], info.get("unique_use"), info["type"], info["size_x"], info["size_y"], info["duration"], info.get("origin")),
        )
        media_id = cursor.lastrowid
        self.conn.executemany(
            "INSERT INTO media_has_tag_media (media_id, tag_media_id) VALUES (?, ?)",
            [(media_id, tag_id) for tag_id in sorted(tag_ids)],
        )
        return media_id

    # Imports one file (metadata removed, named by SHA-256); returns (media_id, created).
    def add_media(self, source, tag_ids=()):
        tag_ids = self.check_tags(tag_ids)
        media_dir = os.path.join(self.directory, MEDIA_DIRECTORY)
        os.makedirs(media_dir, exist_ok=True)
        info = media_tools.prepare(source, media_dir)
        try:
            existing = self.get_media_by_hash(info["hash"])
            if existing is not None:
                return existing["id"], False
            with self.conn:
                media_id = self._insert_media(info, tag_ids)
                os.replace(info["path"], os.path.join(media_dir, info["hash"]))
            return media_id, True
        finally:
            if os.path.exists(info["path"]):
                os.unlink(info["path"])

    # Deletes one media and its file; a portrait is refused while its person pack exists.
    def delete_media(self, media_id):
        row = self.get_media(media_id)
        if row is None:
            return
        if self.person_directory(row["hash"]) or row["hash"] == os.path.basename(self.directory):
            raise PackError("This media is the portrait of a person pack; delete the person pack folder first.")
        with self.conn:
            self.conn.execute("DELETE FROM media_has_tag_media WHERE media_id = ?", (row["id"],))
            self.conn.execute("DELETE FROM media WHERE id = ?", (row["id"],))
        path = os.path.join(self.directory, MEDIA_DIRECTORY, row["hash"])
        if os.path.isfile(path):
            os.unlink(path)

    # Creates a person pack from a portrait file; returns the portrait hash.
    def create_person(self, portrait_source, tag_ids):
        if os.path.basename(os.path.dirname(self.directory)) == MEDIA_DIRECTORY and HASH_PATTERN.match(os.path.basename(self.directory)):
            raise PackError("A person pack cannot contain another person pack.")
        tag_ids = self.check_tags(tag_ids)
        media_dir = os.path.join(self.directory, MEDIA_DIRECTORY)
        os.makedirs(media_dir, exist_ok=True)
        info = media_tools.prepare(portrait_source, media_dir)
        try:
            if media_tools.family(info["type"]) != "still":
                raise PackError("A portrait must be a still image (jpeg, png or webp).")
            if self.get_media_by_hash(info["hash"]) is not None:
                raise PackError("This picture is already a media of the pack.")
            person_dir = os.path.join(media_dir, info["hash"])
            with Pack.create(person_dir) as person:
                with person.conn:
                    person._insert_media(info, tag_ids)
                person.export()
            with self.conn:
                self._insert_media(info, tag_ids)
            os.replace(info["path"], os.path.join(person_dir, MEDIA_DIRECTORY, info["hash"]))
            return info["hash"]
        finally:
            if os.path.exists(info["path"]):
                os.unlink(info["path"])

    # Merges another pack into this one by union; returns a report dict. Source media without an
    # origin get the given origin (the name of the imported pack); known media keep theirs.
    def merge_from(self, source_directory, origin=None):
        report = {"added": 0, "updated": 0, "skipped": [], "persons": 0}
        with Pack(source_directory, upgrade=True, in_memory=True) as source:
            source_tags = {row[0] for row in source.conn.execute("SELECT DISTINCT tag_media_id FROM media_has_tag_media")}
            known = {row[0] for row in self.conn.execute("SELECT id FROM tag_media")}
            if source_tags - known:
                raise PackError("The source pack uses tag ids unknown here: {}".format(sorted(source_tags - known)))
            porn_actions = self.porn_actions()
            for row in source.conn.execute("SELECT * FROM media ORDER BY id").fetchall():
                tags = source.media_tags(row["id"])
                existing = self.get_media_by_hash(row["hash"])
                merged = tags | (self.media_tags(existing["id"]) if existing else set())
                try:
                    rules.check_media_tags(merged, porn_actions)
                except rules.RuleViolation as error:
                    report["skipped"].append((row["hash"], str(error)))
                    continue
                if existing is not None:
                    with self.conn:
                        self.conn.executemany(
                            "INSERT OR IGNORE INTO media_has_tag_media (media_id, tag_media_id) VALUES (?, ?)",
                            [(existing["id"], tag_id) for tag_id in sorted(tags)],
                        )
                    report["updated"] += 1
                    continue
                source_file = source.media_file(row["hash"])
                is_portrait = source.person_directory(row["hash"]) is not None
                if source_file is None:
                    report["skipped"].append((row["hash"], "file missing in the source pack"))
                    continue
                info = {key: row[key] for key in ("size", "hash", "unique_use", "type", "size_x", "size_y", "duration", "origin")}
                info["origin"] = info["origin"] or origin
                with self.conn:
                    self._insert_media(info, tags)
                if not is_portrait:
                    shutil.copyfile(source_file, os.path.join(self.directory, MEDIA_DIRECTORY, row["hash"]))
                report["added"] += 1
            for portrait_hash in source.person_hashes():
                target_dir = os.path.join(self.directory, MEDIA_DIRECTORY, portrait_hash)
                person = Pack(target_dir, upgrade=True) if self.person_directory(portrait_hash) else Pack.create(target_dir)
                with person:
                    person_report = person.merge_from(source.person_directory(portrait_hash), origin)
                    person.export()
                report["skipped"].extend(person_report["skipped"])
                report["persons"] += 1
        return report

    # Lists every problem that keeps this pack from conforming to MP-1 (empty list = valid).
    # With for_import, an older catalogue and missing exports are accepted (the importer
    # rewrites both), but every tag a media uses must exist in the repository catalogue.
    def validate(self, deep=False, allow_persons=True, for_import=False):
        problems = ["missing column " + column for column in self.missing_columns()]
        if problems:
            return problems
        catalogue = load_catalogue()
        expected = {int(row["id"]): row for row in catalogue["tag_media"]}
        actual = {row["id"]: row for row in self.conn.execute("SELECT * FROM tag_media")}
        if for_import:
            used = {row[0] for row in self.conn.execute("SELECT DISTINCT tag_media_id FROM media_has_tag_media")}
            if used - set(expected):
                problems.append("media use tag ids unknown to the EPMTS catalogue: {}".format(sorted(used - set(expected))[:20]))
        elif set(expected) != set(actual):
            problems.append("tag catalogue differs from the repository (run the catalogue update)")
        else:
            changed = [tag_id for tag_id, row in expected.items()
                       if (row.get("name"), row.get("type_tag"), int(row.get("porn") or 0)) != (actual[tag_id]["name"], actual[tag_id]["type_tag"], actual[tag_id]["porn"])]
            if changed:
                problems.append("tags differ from the repository catalogue: {} (run the catalogue update)".format(changed[:10]))
        for row in self.conn.execute("PRAGMA foreign_key_check"):
            problems.append("broken reference in table {}".format(row[0]))
        porn_actions = self.porn_actions()
        allowed_types = set(rules.FORMAT_TYPES["all"])
        hashes = set()
        for row in self.conn.execute("SELECT * FROM media").fetchall():
            hashes.add(row["hash"])
            label = "media {}".format(row["hash"][:12])
            if not HASH_PATTERN.match(row["hash"] or ""):
                problems.append("{}: hash is not a lowercase SHA-256".format(label))
                continue
            if row["type"] not in allowed_types:
                problems.append("{}: unsupported type {}".format(label, row["type"]))
            if row["path"] is not None:
                problems.append("{}: path must be NULL".format(label))
            try:
                rules.check_media_tags(self.media_tags(row["id"]), porn_actions)
            except rules.RuleViolation as error:
                problems.append("{}: {}".format(label, error))
            path = self.media_file(row["hash"])
            if path is None:
                problems.append("{}: file missing".format(label))
            elif deep and media_tools.sha256_file(path) != row["hash"]:
                problems.append("{}: file content does not match its hash".format(label))
        allowed_entries = {DATABASE, DUMP, BROWSER_DUMP, MEDIA_DIRECTORY} | ({MANIFEST} if allow_persons else set())
        try:
            read_manifest(self.directory)
        except PackError as error:
            problems.append(str(error))
        extra = sorted(set(os.listdir(self.directory)) - allowed_entries)
        if extra:
            problems.append("unexpected entries in the pack folder: {}".format(extra))
        media_dir = os.path.join(self.directory, MEDIA_DIRECTORY)
        for name in sorted(os.listdir(media_dir)) if os.path.isdir(media_dir) else []:
            path = os.path.join(media_dir, name)
            if not HASH_PATTERN.match(name):
                problems.append("unexpected file medias/{}".format(name))
            elif os.path.isdir(path):
                if not allow_persons:
                    problems.append("a person pack cannot contain person packs (medias/{})".format(name[:12]))
                elif name not in hashes:
                    problems.append("person pack {} has no portrait row".format(name[:12]))
                else:
                    try:
                        with Pack(path, upgrade=for_import, in_memory=for_import) as person:
                            problems.extend("person {}: {}".format(name[:12], p) for p in person.validate(deep, False, for_import))
                    except PackError as error:
                        problems.append("person {}: {}".format(name[:12], error))
            elif name not in hashes:
                problems.append("medias/{} is not referenced by the database".format(name[:12]))
        for name in () if for_import else (DUMP, BROWSER_DUMP):
            if not os.path.isfile(os.path.join(self.directory, name)):
                problems.append("{} is missing (export the pack)".format(name))
        return problems

    # Counts the media of this pack and its person packs by origin (None = local), with one
    # read-only query per database; a portrait is counted once, in the main pack.
    def origin_counts(self):
        counts = {}
        for directory in [self.directory] + [self.person_directory(h) for h in self.person_hashes()]:
            connection = sqlite3.connect("file:{}?mode=ro".format(os.path.join(directory, DATABASE)), uri=True)
            try:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(media)")}
                origin = "origin" if "origin" in columns else "NULL"  # older packs: everything is local
                skip = os.path.basename(directory) if directory != self.directory else ""
                for value, count in connection.execute(
                    "SELECT {}, COUNT(*) FROM media WHERE hash <> ? GROUP BY 1".format(origin), (skip,)
                ):
                    counts[value] = counts.get(value, 0) + count
            finally:
                connection.close()
        return counts

    # Builds a distributable pack in target_dir from this pack: all media, or only local ones
    # (origin NULL). Exported local media then take the new pack name as origin, here too.
    def build_distribution(self, target_dir, manifest, local_only):
        manifest = check_manifest(manifest)
        name = manifest["name"]
        selection = "WHERE origin IS NULL" if local_only else ""
        exported = {}

        # Copies the selected rows of one pack into a new pack folder.
        def copy_pack(source, destination, keep_hash=None):
            with Pack.create(destination) as target:
                rows = source.conn.execute("SELECT * FROM media {} ORDER BY id".format(selection)).fetchall()
                if keep_hash and not any(row["hash"] == keep_hash for row in rows):
                    rows.append(source.get_media_by_hash(keep_hash))  # a person pack always keeps its portrait
                for row in rows:
                    info = dict(row)
                    info["origin"] = row["origin"] or name
                    with target.conn:
                        target._insert_media(info, source.media_tags(row["id"]))
                    if source.person_directory(row["hash"]) is None:
                        shutil.copyfile(source.media_file(row["hash"]), os.path.join(destination, MEDIA_DIRECTORY, row["hash"]))
                    if row["origin"] is None:
                        exported.setdefault(source.directory, []).append(row["hash"])
                # Media count of the whole pack: a portrait is counted once, not in its person pack too.
                count = target.conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
                for portrait_hash in source.person_hashes():
                    if target.get_media_by_hash(portrait_hash) is not None:
                        with Pack(source.person_directory(portrait_hash), upgrade=True) as person:
                            count += copy_pack(person, os.path.join(destination, MEDIA_DIRECTORY, portrait_hash), portrait_hash) - 1
                target.export()
            return count

        count = copy_pack(self, target_dir)
        if count == 0:
            shutil.rmtree(target_dir)
            raise PackError("There is no media to put in this pack.")
        manifest["media_count"] = count
        with open(os.path.join(target_dir, MANIFEST), "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
        for directory, hashes in exported.items():
            with Pack(directory, upgrade=True) as pack:
                with pack.conn:
                    pack.conn.executemany("UPDATE media SET origin = ? WHERE hash = ? AND origin IS NULL", [(name, h) for h in hashes])
                pack.export()
        return count

    # Dumps the database as SQL: tables in creation order, rows, then indexes.
    def dump(self):
        tables = []
        indexes = []
        for kind, name, sql in self.conn.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY rowid"
        ):
            (tables if kind == "table" else indexes).append((name, sql))
        parts = [";\n".join(sql for _, sql in tables) + ";\n"]
        for name, _ in tables:
            values = ["(" + ",".join(_quote(value) for value in row) + ")"
                      for row in self.conn.execute("SELECT * FROM {} ORDER BY rowid".format(name))]
            for start in range(0, len(values), DUMP_ROWS_PER_INSERT):
                parts.append("INSERT INTO {} VALUES {};\n".format(name, ",".join(values[start:start + DUMP_ROWS_PER_INSERT])))
        if indexes:
            parts.append(";\n".join(sql for _, sql in indexes) + ";\n")
        return "".join(parts)

    # Writes tags.sql and tags.sql.js beside the database.
    def export(self):
        sql = self.dump()
        with open(os.path.join(self.directory, DUMP), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(sql)
        with open(os.path.join(self.directory, BROWSER_DUMP), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(build_browser_dump(sql))
