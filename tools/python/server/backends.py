"""Catalogue backends of the server: an EPMTS pack (SQLite, the default) or a MySQL database.

Both expose the same tables (type_tag, tag_media, media, media_has_tag_media) and answer the
same questions; the selection SQL itself comes from epmts.rules so the rules never diverge.
"""

import os
import sqlite3

from epmts import rules
from epmts.pack import HASH_PATTERN, Pack

TAG_SQL = (
    "SELECT tm.id, tm.name, tm.subcategory_name, tm.description, tm.description_fr, tm.type_tag, tt.name AS type_name "
    "FROM tag_media tm LEFT JOIN type_tag tt ON tt.id = tm.type_tag ORDER BY tm.id"
)


# Returns the real path of candidate when it is a file inside root, else None.
def _inside(root, candidate):
    root = os.path.realpath(root)
    path = os.path.realpath(os.path.join(root, candidate))
    try:
        if os.path.commonpath([root, path]) != root:
            return None
    except ValueError:
        return None
    return path if os.path.isfile(path) else None


class SqliteBackend:
    """Serves one pack directory, its person packs included (PR-1)."""

    supports_reference = True

    # Remembers the pack directory after checking it opens.
    def __init__(self, pack_dir):
        self.pack_dir = os.path.realpath(pack_dir)
        Pack(self.pack_dir).close()

    # Returns the database directory of a context: "" is the pack, a hash is a person pack.
    def _directory(self, context):
        if not context:
            return self.pack_dir
        if not HASH_PATTERN.match(context):
            return None
        directory = os.path.join(self.pack_dir, "medias", context)
        return directory if os.path.isfile(os.path.join(directory, "tags.sqlite")) else None

    # Opens a read-only connection on a context database.
    def _connect(self, context):
        directory = self._directory(context)
        if directory is None:
            return None
        connection = sqlite3.connect("file:{}?mode=ro".format(os.path.join(directory, "tags.sqlite")), uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    # Tells whether a person context exists.
    def has_context(self, context):
        return self._directory(context) is not None

    # Returns the tag catalogue rows.
    def tags(self):
        connection = self._connect("")
        try:
            return [dict(row) for row in connection.execute(TAG_SQL)]
        finally:
            connection.close()

    # Draws one random matching media row in a context, or None.
    def select(self, context, include, exclude, exclude_types, media_format, max_video_time):
        connection = self._connect(context)
        if connection is None:
            return None
        try:
            sql, params = rules.build_selection_sql(
                include, exclude, exclude_types, media_format, max_video_time, rules.porn_action_ids(connection)
            )
            if sql is None:
                return None
            row = connection.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    # Returns one media row of a context by hash, or None.
    def find(self, context, media_hash):
        connection = self._connect(context)
        if connection is None:
            return None
        try:
            row = connection.execute("SELECT id, hash, type, duration FROM media WHERE hash = ?", (media_hash,)).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    # Returns the file of a media in a context, or None.
    def file_path(self, context, media_hash):
        directory = self._directory(context)
        if directory is None or not HASH_PATTERN.match(media_hash):
            return None
        return _inside(directory, os.path.join("medias", media_hash)) or _inside(
            directory, os.path.join("medias", media_hash, "medias", media_hash)
        )

    # Tells whether a media of the main pack is the portrait of a person pack.
    def is_portrait(self, media_hash):
        return self._directory(media_hash) is not None if HASH_PATTERN.match(media_hash) else False


class MysqlBackend:
    """Serves a MySQL catalogue whose files live under media_root (person packs unsupported)."""

    supports_reference = False

    # Keeps the connection settings; pymysql is imported only when this backend is used.
    def __init__(self, settings, media_root, media_storage="hash"):
        import pymysql
        self.pymysql = pymysql
        self.settings = settings
        self.media_root = os.path.realpath(media_root)
        if media_storage not in ("hash", "path", "auto"):
            raise ValueError("media_storage must be hash, path or auto")
        self.media_storage = media_storage

    # Runs one query and returns its rows as dicts.
    def _query(self, sql, params=None):
        connection = self.pymysql.connect(
            host=self.settings.get("host", "127.0.0.1"),
            port=int(self.settings.get("port", 3306)),
            user=self.settings.get("user", ""),
            password=self.settings.get("password", ""),
            database=self.settings.get("database", ""),
            charset="utf8mb4",
            cursorclass=self.pymysql.cursors.DictCursor,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())
        finally:
            connection.close()

    # Only the main catalogue exists in MySQL.
    def has_context(self, context):
        return not context

    # Returns the tag catalogue rows.
    def tags(self):
        return self._query(TAG_SQL)

    # Draws one random matching media row, or None.
    def select(self, context, include, exclude, exclude_types, media_format, max_video_time):
        if context:
            return None
        porn_actions = {int(row["id"]) for row in self._query(rules.PORN_ACTION_SQL)}
        sql, params = rules.build_selection_sql(
            include, exclude, exclude_types, media_format, max_video_time, porn_actions, dialect="mysql"
        )
        if sql is None:
            return None
        rows = self._query(sql, params)
        return rows[0] if rows else None

    # Returns one media row by hash, or None.
    def find(self, context, media_hash):
        if context:
            return None
        rows = self._query("SELECT id, hash, type, duration FROM media WHERE hash = %s LIMIT 1", (media_hash,))
        return rows[0] if rows else None

    # Resolves the file of a media from its hash or from media.path, inside media_root.
    def file_path(self, context, media_hash):
        if context or not HASH_PATTERN.match(media_hash):
            return None
        if self.media_storage in ("hash", "auto"):
            path = _inside(self.media_root, media_hash)
            if path:
                return path
        if self.media_storage in ("path", "auto"):
            rows = self._query("SELECT path FROM media WHERE hash = %s LIMIT 1", (media_hash,))
            if rows and rows[0].get("path"):
                return _inside(self.media_root, str(rows[0]["path"]).lstrip("/\\"))
        return None

    # MySQL catalogues hold no person packs.
    def is_portrait(self, media_hash):
        return False
