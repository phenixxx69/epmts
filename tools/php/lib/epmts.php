<?php
/**
 * EPMTS PHP library: the MP-1 pack format, the tag catalogue and the tagging rules.
 * Same format and rules as tools/python/epmts. Needs PHP 7.4+ with the sqlite3 extension.
 */

const EPMTS_DATABASE = 'tags.sqlite';
const EPMTS_DUMP = 'tags.sql';
const EPMTS_BROWSER_DUMP = 'tags.sql.js';
const EPMTS_MEDIA_DIRECTORY = 'medias';
const EPMTS_MANIFEST = 'pack.json';
// Every distributed pack names the original project (standard section 11.1.2, NOTICE).
const EPMTS_PROJECT_URL = 'https://github.com/phenixxx69/epmts';
const EPMTS_DUMP_ROWS_PER_INSERT = 500;

const EPMTS_LIFTABLE_DEFAULT_EXCLUSIONS = [47, 48, 66, 135, 143, 163, 168];
const EPMTS_PROTECTED_AGE_TAG_ID = 291;
const EPMTS_ACTION_TYPE_ID = 6;

const EPMTS_TYPE_COLUMNS = ['id', 'name', 'position', 'color'];
const EPMTS_TAG_COLUMNS = ['id', 'name', 'logo', 'type_tag', 'subcategory_name', 'description', 'description_fr', 'ia_text', 'porn'];

const EPMTS_MEDIA_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'video/webm', 'video/mp4', 'video/x-m4v'];

const EPMTS_SCHEMA = [
    "CREATE TABLE type_tag (
            id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            position INTEGER DEFAULT 0,
            color VARCHAR(255) DEFAULT 'black'
        )",
    "CREATE TABLE tag_media (
            id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR(45) DEFAULT NULL,
            logo VARCHAR(255) DEFAULT NULL,
            type_tag INTEGER DEFAULT NULL REFERENCES type_tag (id),
            subcategory_name VARCHAR(45) DEFAULT NULL,
            description VARCHAR(255) DEFAULT NULL,
            description_fr VARCHAR(255) DEFAULT NULL,
            ia_text VARCHAR(255) DEFAULT NULL,
            porn INTEGER NOT NULL DEFAULT 0
        )",
    "CREATE TABLE media (
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
        )",
    "CREATE TABLE media_has_tag_media (
            media_id INTEGER NOT NULL REFERENCES media (id) ON DELETE CASCADE,
            tag_media_id INTEGER NOT NULL REFERENCES tag_media (id),
            PRIMARY KEY (media_id, tag_media_id)
        )",
];

const EPMTS_INDEXES = [
    'CREATE INDEX idx_tag_media_type_tag ON tag_media (type_tag)',
    'CREATE INDEX idx_media_type ON media (type)',
    'CREATE INDEX idx_media_has_tag_media_tag ON media_has_tag_media (tag_media_id, media_id)',
];

// Returns the repository root (tools/php/lib -> three levels up).
function epmts_repo_root(): string
{
    return dirname(__DIR__, 3);
}

// Prints a message and stops with an error status.
function epmts_fail(string $message): void
{
    fwrite(STDERR, "Error: " . $message . "\n");
    exit(1);
}

// Checks the PHP extensions the tools need.
function epmts_require_extensions(): void
{
    if (!class_exists('SQLite3')) {
        epmts_fail('the PHP sqlite3 extension is required (Debian/Ubuntu: sudo apt install php-sqlite3; Windows: enable extension=sqlite3 in php.ini).');
    }
}

// Reads catalogue/catalogue.json.
function epmts_load_catalogue(): array
{
    $path = epmts_repo_root() . '/catalogue/catalogue.json';
    $catalogue = json_decode((string) file_get_contents($path), true);
    if (!is_array($catalogue)) {
        epmts_fail('cannot read ' . $path);
    }

    return $catalogue;
}

// Writes catalogue/catalogue.json with a stable layout.
function epmts_save_catalogue(array $catalogue): void
{
    $json = json_encode($catalogue, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    // PHP indents by 4 spaces; halve the leading indentation to keep 2, as the file uses.
    $json = preg_replace_callback('/^ +/m', function ($match) {
        return str_repeat(' ', intdiv(strlen($match[0]), 2));
    }, $json);
    file_put_contents(epmts_repo_root() . '/catalogue/catalogue.json', $json . "\n");
}

// Opens a pack database with foreign keys and exceptions on. A read-only open (for a source pack)
// never upgrades nor writes anything.
function epmts_open(string $packDir, bool $readOnly = false): SQLite3
{
    $path = rtrim($packDir, '/\\') . '/' . EPMTS_DATABASE;
    if (!is_file($path)) {
        epmts_fail('no ' . EPMTS_DATABASE . ' in ' . $packDir);
    }
    try {
        $db = new SQLite3($path, $readOnly ? SQLITE3_OPEN_READONLY : SQLITE3_OPEN_READWRITE);
        $db->enableExceptions(true);
        $db->query('SELECT name FROM sqlite_master LIMIT 1');
    } catch (Exception $exception) {
        epmts_fail($path . ' is not a valid SQLite database');
    }
    if ($readOnly) {
        return $db;
    }
    $db->exec('PRAGMA foreign_keys = ON');
    epmts_upgrade_schema($db);

    return $db;
}

// Adds the columns that older packs lack, without touching existing data.
function epmts_upgrade_schema(SQLite3 $db): void
{
    $upgrades = [
        ['tag_media', 'description_fr', 'VARCHAR(255) DEFAULT NULL'],
        ['tag_media', 'porn', 'INTEGER NOT NULL DEFAULT 0'],
        ['media', 'duration', 'REAL DEFAULT NULL'],
        ['media', 'origin', 'VARCHAR(255) DEFAULT NULL'],
    ];
    foreach ($upgrades as [$table, $column, $definition]) {
        $columns = [];
        $result = $db->query('PRAGMA table_info(' . $table . ')');
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            $columns[] = $row['name'];
        }
        if ($columns && !in_array($column, $columns, true)) {
            $db->exec("ALTER TABLE $table ADD COLUMN $column $definition");
        }
    }
}

// Creates an empty pack (whole catalogue, no media) in a missing or empty directory.
function epmts_create_pack(string $packDir): void
{
    if (is_dir($packDir) && array_diff(scandir($packDir) ?: [], ['.', '..'])) {
        epmts_fail('the target directory is not empty: ' . $packDir);
    }
    if (!is_dir($packDir . '/' . EPMTS_MEDIA_DIRECTORY) && !mkdir($packDir . '/' . EPMTS_MEDIA_DIRECTORY, 0755, true)) {
        epmts_fail('cannot create ' . $packDir);
    }
    $db = new SQLite3($packDir . '/' . EPMTS_DATABASE);
    $db->enableExceptions(true);
    foreach (EPMTS_SCHEMA as $statement) {
        $db->exec($statement);
    }
    epmts_sync_catalogue($db);
    foreach (EPMTS_INDEXES as $statement) {
        $db->exec($statement);
    }
    epmts_export($db, $packDir);
    $db->close();
}

// Replaces type_tag and tag_media with the repository catalogue; ids never change.
function epmts_sync_catalogue(SQLite3 $db): void
{
    $catalogue = epmts_load_catalogue();
    $known = array_column($catalogue['tag_media'], 'id');
    $used = [];
    $result = $db->query('SELECT DISTINCT tag_media_id FROM media_has_tag_media');
    while ($row = $result->fetchArray(SQLITE3_NUM)) {
        $used[] = $row[0];
    }
    $unknown = array_diff($used, $known);
    if ($unknown) {
        epmts_fail('this pack uses tag ids unknown to the catalogue: ' . implode(', ', $unknown));
    }
    $db->exec('PRAGMA foreign_keys = OFF');
    $db->exec('BEGIN');
    $db->exec('DELETE FROM tag_media');
    $db->exec('DELETE FROM type_tag');
    epmts_insert_rows($db, 'type_tag', EPMTS_TYPE_COLUMNS, $catalogue['type_tag']);
    epmts_insert_rows($db, 'tag_media', EPMTS_TAG_COLUMNS, $catalogue['tag_media']);
    $db->exec('COMMIT');
    $db->exec('PRAGMA foreign_keys = ON');
}

// Inserts rows (arrays keyed by column) through one prepared statement.
function epmts_insert_rows(SQLite3 $db, string $table, array $columns, array $rows): void
{
    $statement = $db->prepare(sprintf(
        'INSERT INTO %s (%s) VALUES (%s)',
        $table,
        implode(', ', $columns),
        implode(', ', array_fill(0, count($columns), '?'))
    ));
    foreach ($rows as $row) {
        $statement->reset();
        foreach ($columns as $position => $column) {
            $value = $row[$column] ?? null;
            if ($column === 'porn') {
                $value = (int) $value;
            }
            $statement->bindValue($position + 1, $value, epmts_sqlite_type($value));
        }
        $statement->execute();
    }
}

// Maps a PHP value to the SQLite binding type that keeps it as is.
function epmts_sqlite_type($value): int
{
    if ($value === null) {
        return SQLITE3_NULL;
    }
    if (is_bool($value) || is_int($value)) {
        return SQLITE3_INTEGER;
    }

    return is_float($value) ? SQLITE3_FLOAT : SQLITE3_TEXT;
}

// Writes a value as an SQL literal, the same way as the Python tools.
function epmts_quote($value): string
{
    if ($value === null) {
        return 'NULL';
    }
    if (is_int($value)) {
        return (string) $value;
    }
    if (is_float($value)) {
        return json_encode($value, JSON_PRESERVE_ZERO_FRACTION);
    }

    return "'" . str_replace("'", "''", (string) $value) . "'";
}

// Dumps the database: tables in creation order, rows, then indexes.
function epmts_dump(SQLite3 $db): string
{
    $tables = [];
    $indexes = [];
    $objects = $db->query("SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY rowid");
    while ($object = $objects->fetchArray(SQLITE3_ASSOC)) {
        if ($object['type'] === 'table') {
            $tables[$object['name']] = $object['sql'];
        } elseif ($object['type'] === 'index') {
            $indexes[] = $object['sql'];
        }
    }
    $sql = implode(";\n", $tables) . ";\n";
    foreach (array_keys($tables) as $table) {
        $values = [];
        $rows = $db->query('SELECT * FROM ' . $table . ' ORDER BY rowid');
        while ($row = $rows->fetchArray(SQLITE3_ASSOC)) {
            $values[] = '(' . implode(',', array_map('epmts_quote', $row)) . ')';
        }
        foreach (array_chunk($values, EPMTS_DUMP_ROWS_PER_INSERT) as $chunk) {
            $sql .= 'INSERT INTO ' . $table . ' VALUES ' . implode(',', $chunk) . ";\n";
        }
    }

    return $sql . ($indexes ? implode(";\n", $indexes) . ";\n" : '');
}

// Writes tags.sql and tags.sql.js beside the database.
function epmts_export(SQLite3 $db, string $packDir): void
{
    $sql = epmts_dump($db);
    file_put_contents($packDir . '/' . EPMTS_DUMP, $sql);
    file_put_contents($packDir . '/' . EPMTS_BROWSER_DUMP, 'var encodedStr = "' . base64_encode($sql) . '";' . "\n"
        . 'var db_str = new TextDecoder().decode(Uint8Array.from(atob(encodedStr), function (c) { return c.charCodeAt(0); }));' . "\n");
}

// Returns the porn-flagged action tag ids.
function epmts_porn_actions(SQLite3 $db): array
{
    $ids = [];
    $result = $db->query('SELECT id FROM tag_media WHERE type_tag = ' . EPMTS_ACTION_TYPE_ID . ' AND porn = 1');
    while ($row = $result->fetchArray(SQLITE3_NUM)) {
        $ids[] = (int) $row[0];
    }

    return $ids;
}

// Returns null when a tag set is allowed, otherwise the reason it is refused.
function epmts_tag_problem(SQLite3 $db, array $tagIds): ?string
{
    $known = [];
    $result = $db->query('SELECT id FROM tag_media');
    while ($row = $result->fetchArray(SQLITE3_NUM)) {
        $known[] = (int) $row[0];
    }
    $unknown = array_diff($tagIds, $known);
    if ($unknown) {
        return 'unknown tag ids: ' . implode(', ', $unknown) . '. Tags are created only in the EPMTS repository.';
    }
    $porn = array_intersect($tagIds, epmts_porn_actions($db));
    if (in_array(EPMTS_PROTECTED_AGE_TAG_ID, $tagIds, true) && $porn) {
        return 'tag ' . EPMTS_PROTECTED_AGE_TAG_ID . ' (Age other) can never be set on a media that has a porn action tag ('
            . implode(', ', $porn) . ').';
    }

    return null;
}

// Parses "1,2,3" into distinct positive ints, or stops on an invalid value.
function epmts_parse_tag_ids(string $list): array
{
    $ids = [];
    foreach (explode(',', $list) as $value) {
        $value = trim($value);
        if ($value === '') {
            continue;
        }
        if (!ctype_digit($value) || (int) $value < 1) {
            epmts_fail('"' . $value . '" is not a tag id; tags are numbers separated by commas (see catalogue/TAGS.md).');
        }
        $ids[(int) $value] = (int) $value;
    }

    return array_values($ids);
}

// Detects a supported media type from the file content, never from its name.
function epmts_sniff_type(string $path): ?string
{
    $head = (string) file_get_contents($path, false, null, 0, 64);
    if (strncmp($head, "\xFF\xD8\xFF", 3) === 0) {
        return 'image/jpeg';
    }
    if (strncmp($head, "\x89PNG\r\n\x1A\n", 8) === 0) {
        return 'image/png';
    }
    if (in_array(substr($head, 0, 6), ['GIF87a', 'GIF89a'], true)) {
        return 'image/gif';
    }
    if (substr($head, 0, 4) === 'RIFF' && substr($head, 8, 4) === 'WEBP') {
        return 'image/webp';
    }
    if (strncmp($head, "\x1A\x45\xDF\xA3", 4) === 0) {
        return 'video/webm';
    }
    if (substr($head, 4, 4) === 'ftyp') {
        return strncmp(substr($head, 8, 4), 'M4V', 3) === 0 ? 'video/x-m4v' : 'video/mp4';
    }

    return null;
}

// Finds an ffmpeg/ffprobe binary in tools/bin (downloaded by the launchers) or the PATH.
function epmts_find_tool(string $name): ?string
{
    $executable = $name . (DIRECTORY_SEPARATOR === '\\' ? '.exe' : '');
    $candidates = glob(epmts_repo_root() . '/tools/bin/*/bin/' . $executable) ?: [];
    $candidates[] = epmts_repo_root() . '/tools/bin/' . $executable;
    foreach ($candidates as $candidate) {
        if (is_file($candidate)) {
            return $candidate;
        }
    }
    $finder = DIRECTORY_SEPARATOR === '\\' ? 'where ' : 'command -v ';
    $found = trim((string) shell_exec($finder . escapeshellarg($name) . ' 2>' . (DIRECTORY_SEPARATOR === '\\' ? 'NUL' : '/dev/null')));

    return $found !== '' ? strtok($found, "\r\n") : null;
}

// Removes APPn metadata (except ICC, APP2) and comments from JPEG bytes.
function epmts_strip_jpeg(string $data): string
{
    $out = substr($data, 0, 2);
    $position = 2;
    $length = strlen($data);
    while ($position + 4 <= $length && $data[$position] === "\xFF") {
        $marker = ord($data[$position + 1]);
        if ($marker === 0xDA) {
            return $out . substr($data, $position);
        }
        $size = unpack('n', substr($data, $position + 2, 2))[1];
        $isMetadata = ($marker >= 0xE1 && $marker <= 0xEF && $marker !== 0xE2) || $marker === 0xFE;
        if (!$isMetadata) {
            $out .= substr($data, $position, 2 + $size);
        }
        $position += 2 + $size;
    }

    return $out . substr($data, $position);
}

// Removes text, time and EXIF chunks from PNG bytes.
function epmts_strip_png(string $data): string
{
    $out = substr($data, 0, 8);
    $position = 8;
    while ($position + 8 <= strlen($data)) {
        $size = unpack('N', substr($data, $position, 4))[1];
        $kind = substr($data, $position + 4, 4);
        if (!in_array($kind, ['tEXt', 'zTXt', 'iTXt', 'tIME', 'eXIf'], true)) {
            $out .= substr($data, $position, 12 + $size);
        }
        $position += 12 + $size;
    }

    return $out;
}

// Removes EXIF and XMP chunks from WebP bytes and clears their VP8X flags.
function epmts_strip_webp(string $data): string
{
    $chunks = '';
    $position = 12;
    while ($position + 8 <= strlen($data)) {
        $kind = substr($data, $position, 4);
        $size = unpack('V', substr($data, $position + 4, 4))[1];
        $chunk = substr($data, $position, 8 + $size + ($size & 1));
        if ($kind === 'VP8X') {
            $chunk[8] = chr(ord($chunk[8]) & ~0x0C & 0xFF);
        }
        if ($kind !== 'EXIF' && $kind !== 'XMP ') {
            $chunks .= $chunk;
        }
        $position += 8 + $size + ($size & 1);
    }

    return 'RIFF' . pack('V', strlen($chunks) + 4) . 'WEBP' . $chunks;
}

// Writes a metadata-free copy of a media; films need ffmpeg.
function epmts_strip_metadata(string $source, string $target, string $type): void
{
    if ($type === 'image/jpeg' && function_exists('exif_read_data')) {
        $exif = @exif_read_data($source);
        if (!empty($exif['Orientation']) && (int) $exif['Orientation'] !== 1) {
            fwrite(STDERR, "Warning: this JPEG relies on EXIF rotation, which is removed; it may appear rotated. Use the Python editor to import it.\n");
        }
    }
    $cleaners = ['image/jpeg' => 'epmts_strip_jpeg', 'image/png' => 'epmts_strip_png', 'image/webp' => 'epmts_strip_webp'];
    if (isset($cleaners[$type])) {
        file_put_contents($target, $cleaners[$type]((string) file_get_contents($source)));

        return;
    }
    if (strpos($type, 'video/') === 0) {
        $ffmpeg = epmts_find_tool('ffmpeg');
        if ($ffmpeg === null) {
            epmts_fail('ffmpeg is required to import a video (its metadata must be removed). Run quickstart once and accept the ffmpeg download.');
        }
        $format = $type === 'video/webm' ? 'webm' : 'mp4';
        exec(escapeshellarg($ffmpeg) . ' -y -nostdin -loglevel error -i ' . escapeshellarg($source)
            . ' -map 0 -map_metadata -1 -map_chapters -1 -c copy -f ' . $format . ' ' . escapeshellarg($target), $output, $status);
        if ($status !== 0) {
            epmts_fail('ffmpeg could not copy ' . basename($source));
        }

        return;
    }
    copy($source, $target);
}

// Returns [width, height, duration] of a prepared media file.
function epmts_probe(string $path, string $type): array
{
    if (strpos($type, 'image/') === 0) {
        $size = @getimagesize($path);

        return [$size ? $size[0] : null, $size ? $size[1] : null, null];
    }
    $ffprobe = epmts_find_tool('ffprobe');
    if ($ffprobe === null) {
        return [null, null, null];
    }
    $json = shell_exec(escapeshellarg($ffprobe) . ' -v error -select_streams v:0 -show_entries stream=width,height:format=duration -of json ' . escapeshellarg($path));
    $info = json_decode((string) $json, true) ?: [];
    $stream = $info['streams'][0] ?? [];
    $duration = $info['format']['duration'] ?? null;

    return [$stream['width'] ?? null, $stream['height'] ?? null, is_numeric($duration) ? round((float) $duration, 3) : null];
}

// Prepares a source file: metadata stripped into a temp file in $workDir, hashed and probed.
function epmts_prepare_media(string $source, string $workDir): array
{
    if (!is_file($source)) {
        epmts_fail('file not found: ' . $source);
    }
    $type = epmts_sniff_type($source);
    if ($type === null) {
        epmts_fail(basename($source) . ': unsupported media type (allowed: jpeg, png, webp, gif, webm, mp4)');
    }
    $temporary = tempnam($workDir, 'epmts');
    epmts_strip_metadata($source, $temporary, $type);
    [$width, $height, $duration] = epmts_probe($temporary, $type);

    return [
        'path' => $temporary,
        'hash' => hash_file('sha256', $temporary),
        'size' => filesize($temporary),
        'type' => $type,
        'size_x' => $width,
        'size_y' => $height,
        'duration' => $duration,
    ];
}

// Inserts a prepared media row and its tags; returns the new id.
function epmts_insert_media(SQLite3 $db, array $info, array $tagIds): int
{
    $statement = $db->prepare('INSERT INTO media (size, hash, unique_use, type, size_x, size_y, path, duration, origin) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)');
    foreach ([$info['size'] ?? null, $info['hash'], $info['unique_use'] ?? null, $info['type'], $info['size_x'] ?? null, $info['size_y'] ?? null, $info['duration'] ?? null, $info['origin'] ?? null] as $i => $value) {
        $statement->bindValue($i + 1, $value, epmts_sqlite_type($value));
    }
    $statement->execute();
    $mediaId = $db->lastInsertRowID();
    $link = $db->prepare('INSERT INTO media_has_tag_media (media_id, tag_media_id) VALUES (?, ?)');
    foreach ($tagIds as $tagId) {
        $link->reset();
        $link->bindValue(1, $mediaId, SQLITE3_INTEGER);
        $link->bindValue(2, $tagId, SQLITE3_INTEGER);
        $link->execute();
    }

    return $mediaId;
}

// Returns the id of the media with this hash, or null.
function epmts_find_media(SQLite3 $db, string $hash): ?int
{
    $statement = $db->prepare('SELECT id FROM media WHERE hash = ?');
    $statement->bindValue(1, $hash, SQLITE3_TEXT);
    $row = $statement->execute()->fetchArray(SQLITE3_NUM);

    return $row ? (int) $row[0] : null;
}

// Imports one file into a pack with checked tags; returns [mediaId, created].
function epmts_add_media(SQLite3 $db, string $packDir, string $source, array $tagIds): array
{
    $problem = epmts_tag_problem($db, $tagIds);
    if ($problem !== null) {
        epmts_fail(basename($source) . ': ' . $problem);
    }
    $mediaDir = $packDir . '/' . EPMTS_MEDIA_DIRECTORY;
    if (!is_dir($mediaDir)) {
        mkdir($mediaDir, 0755, true);
    }
    $info = epmts_prepare_media($source, $mediaDir);
    $existing = epmts_find_media($db, $info['hash']);
    if ($existing !== null) {
        unlink($info['path']);

        return [$existing, false];
    }
    $db->exec('BEGIN');
    $mediaId = epmts_insert_media($db, $info, $tagIds);
    rename($info['path'], $mediaDir . '/' . $info['hash']);
    $db->exec('COMMIT');

    return [$mediaId, true];
}

// Returns the tag ids of one media.
function epmts_media_tags(SQLite3 $db, int $mediaId): array
{
    $ids = [];
    $result = $db->query('SELECT tag_media_id FROM media_has_tag_media WHERE media_id = ' . $mediaId);
    while ($row = $result->fetchArray(SQLITE3_NUM)) {
        $ids[] = (int) $row[0];
    }

    return $ids;
}

// Tells whether a directory is a pack (holds tags.sqlite).
function epmts_is_pack(string $directory): bool
{
    return is_file($directory . '/' . EPMTS_DATABASE);
}

// Returns the file of a media of a pack (a portrait lives in its person pack), or null.
function epmts_media_file(string $packDir, string $hash): ?string
{
    $plain = $packDir . '/' . EPMTS_MEDIA_DIRECTORY . '/' . $hash;
    if (is_file($plain)) {
        return $plain;
    }
    $portrait = $plain . '/' . EPMTS_MEDIA_DIRECTORY . '/' . $hash;

    return is_file($portrait) ? $portrait : null;
}

// Reads and checks pack.json of a pack folder; returns null when there is none.
function epmts_read_manifest(string $packDir): ?array
{
    $path = $packDir . '/' . EPMTS_MANIFEST;
    if (!is_file($path)) {
        return null;
    }
    $manifest = json_decode((string) file_get_contents($path), true);
    if (!is_array($manifest)) {
        throw new RuntimeException(EPMTS_MANIFEST . ' is not valid JSON');
    }
    if (($manifest['project'] ?? null) !== EPMTS_PROJECT_URL) {
        throw new RuntimeException(EPMTS_MANIFEST . ": 'project' must be " . EPMTS_PROJECT_URL);
    }
    foreach (['name', 'author', 'version', 'date'] as $field) {
        if (!isset($manifest[$field]) || trim((string) $manifest[$field]) === '' || strlen((string) $manifest[$field]) > 255) {
            throw new RuntimeException(EPMTS_MANIFEST . ": '$field' is required (at most 255 characters)");
        }
    }
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', (string) $manifest['date'])) {
        throw new RuntimeException(EPMTS_MANIFEST . ': date must be YYYY-MM-DD');
    }

    return $manifest;
}

// Merges a source pack into a target pack by union; returns a report. Source media without an
// origin get $origin (the imported pack name); media already in the target keep theirs.
function epmts_merge(string $targetDir, string $sourceDir, ?string $origin = null): array
{
    $report = ['added' => 0, 'updated' => 0, 'skipped' => [], 'persons' => 0];
    $target = epmts_open($targetDir);
    $source = epmts_open($sourceDir, true);
    $pornActions = epmts_porn_actions($target);
    $rows = $source->query('SELECT * FROM media ORDER BY id');
    $medias = [];
    while ($row = $rows->fetchArray(SQLITE3_ASSOC)) {
        $medias[] = $row;
    }
    foreach ($medias as $row) {
        $tags = epmts_media_tags($source, (int) $row['id']);
        $existing = epmts_find_media($target, $row['hash']);
        $merged = array_values(array_unique(array_merge($tags, $existing !== null ? epmts_media_tags($target, $existing) : [])));
        $problem = epmts_tag_problem($target, $merged);
        if ($problem !== null) {
            $report['skipped'][] = substr($row['hash'], 0, 12) . ': ' . $problem;
            continue;
        }
        if ($existing !== null) {
            $link = $target->prepare('INSERT OR IGNORE INTO media_has_tag_media (media_id, tag_media_id) VALUES (?, ?)');
            foreach ($tags as $tagId) {
                $link->reset();
                $link->bindValue(1, $existing, SQLITE3_INTEGER);
                $link->bindValue(2, $tagId, SQLITE3_INTEGER);
                $link->execute();
            }
            $report['updated']++;
            continue;
        }
        $file = epmts_media_file($sourceDir, $row['hash']);
        if ($file === null) {
            $report['skipped'][] = substr($row['hash'], 0, 12) . ': file missing in the source pack';
            continue;
        }
        $row['origin'] = ($row['origin'] ?? null) ?: $origin;
        epmts_insert_media($target, $row, $tags);
        if (!is_dir($sourceDir . '/' . EPMTS_MEDIA_DIRECTORY . '/' . $row['hash'])) {
            copy($file, $targetDir . '/' . EPMTS_MEDIA_DIRECTORY . '/' . $row['hash']);
        }
        $report['added']++;
    }
    epmts_export($target, $targetDir);
    $target->close();
    $source->close();
    foreach (array_diff(scandir($sourceDir . '/' . EPMTS_MEDIA_DIRECTORY) ?: [], ['.', '..']) as $entry) {
        $personSource = $sourceDir . '/' . EPMTS_MEDIA_DIRECTORY . '/' . $entry;
        if (!preg_match('/^[0-9a-f]{64}$/', $entry) || !epmts_is_pack($personSource)) {
            continue;
        }
        $personTarget = $targetDir . '/' . EPMTS_MEDIA_DIRECTORY . '/' . $entry;
        if (!epmts_is_pack($personTarget)) {
            epmts_create_pack($personTarget);
        }
        $personReport = epmts_merge($personTarget, $personSource, $origin);
        $report['skipped'] = array_merge($report['skipped'], $personReport['skipped']);
        $report['persons']++;
    }

    return $report;
}

// Splits command-line arguments into positional values and --key=value / --flag options.
function epmts_parse_args(array $argv): array
{
    $positional = [];
    $options = [];
    foreach (array_slice($argv, 1) as $argument) {
        if (strncmp($argument, '--', 2) === 0) {
            $parts = explode('=', substr($argument, 2), 2);
            $options[$parts[0]] = $parts[1] ?? true;
        } else {
            $positional[] = $argument;
        }
    }

    return [$positional, $options];
}

// Returns the problems of one pack, person packs included unless $isPerson. With $forImport, an
// older catalogue and missing exports are accepted, the database is opened read-only, but every
// tag a media uses must exist in the repository catalogue.
function epmts_validate(string $packDir, bool $deep, bool $isPerson = false, bool $forImport = false): array
{
    $problems = [];
    $db = epmts_open($packDir, $forImport);
    $catalogue = epmts_load_catalogue();
    $expected = [];
    foreach ($catalogue['tag_media'] as $tag) {
        $expected[(int) $tag['id']] = [$tag['name'], $tag['type_tag'], (int) $tag['porn']];
    }
    $actual = [];
    $result = $db->query('SELECT id, name, type_tag, porn FROM tag_media');
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $actual[(int) $row['id']] = [$row['name'], $row['type_tag'], (int) $row['porn']];
    }
    if ($forImport) {
        $unknown = [];
        $result = $db->query('SELECT DISTINCT tag_media_id FROM media_has_tag_media');
        while ($row = $result->fetchArray(SQLITE3_NUM)) {
            if (!isset($expected[(int) $row[0]])) {
                $unknown[] = $row[0];
            }
        }
        if ($unknown) {
            $problems[] = 'media use tag ids unknown to the EPMTS catalogue: ' . implode(', ', array_slice($unknown, 0, 20));
        }
    } elseif ($expected != $actual) {
        $problems[] = 'tag catalogue differs from the repository (run pack_update_catalogue.php)';
    }
    $result = $db->query('PRAGMA foreign_key_check');
    while ($row = $result->fetchArray(SQLITE3_NUM)) {
        $problems[] = 'broken reference in table ' . $row[0];
    }
    $hashes = [];
    $result = $db->query('SELECT * FROM media');
    $rows = [];
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $rows[] = $row;
    }
    foreach ($rows as $row) {
        $label = 'media ' . substr((string) $row['hash'], 0, 12);
        $hashes[$row['hash']] = true;
        if (!preg_match('/^[0-9a-f]{64}$/', (string) $row['hash'])) {
            $problems[] = "$label: hash is not a lowercase SHA-256";
            continue;
        }
        if (!in_array($row['type'], EPMTS_MEDIA_TYPES, true)) {
            $problems[] = "$label: unsupported type {$row['type']}";
        }
        if (($row['path'] ?? null) !== null) {
            $problems[] = "$label: path must be NULL";
        }
        $problem = epmts_tag_problem($db, epmts_media_tags($db, (int) $row['id']));
        if ($problem !== null) {
            $problems[] = "$label: $problem";
        }
        $file = epmts_media_file($packDir, $row['hash']);
        if ($file === null) {
            $problems[] = "$label: file missing";
        } elseif ($deep && hash_file('sha256', $file) !== $row['hash']) {
            $problems[] = "$label: file content does not match its hash";
        }
    }
    $allowed = ['.', '..', EPMTS_DATABASE, EPMTS_DUMP, EPMTS_BROWSER_DUMP, EPMTS_MEDIA_DIRECTORY];
    if (!$isPerson) {
        $allowed[] = EPMTS_MANIFEST;
        try {
            epmts_read_manifest($packDir);
        } catch (RuntimeException $exception) {
            $problems[] = $exception->getMessage();
        }
    }
    foreach (array_diff(scandir($packDir) ?: [], $allowed) as $extra) {
        $problems[] = "unexpected entry in the pack folder: $extra";
    }
    foreach ($forImport ? [] : [EPMTS_DUMP, EPMTS_BROWSER_DUMP] as $file) {
        if (!is_file($packDir . '/' . $file)) {
            $problems[] = "$file is missing (run pack_export.php)";
        }
    }
    foreach (array_diff((is_dir($packDir . '/' . EPMTS_MEDIA_DIRECTORY) ? scandir($packDir . '/' . EPMTS_MEDIA_DIRECTORY) : []), ['.', '..']) as $entry) {
        $path = $packDir . '/' . EPMTS_MEDIA_DIRECTORY . '/' . $entry;
        if (!preg_match('/^[0-9a-f]{64}$/', $entry)) {
            $problems[] = "unexpected file medias/$entry";
        } elseif (is_dir($path)) {
            if ($isPerson) {
                $problems[] = 'a person pack cannot contain person packs (medias/' . substr($entry, 0, 12) . ')';
            } elseif (!isset($hashes[$entry])) {
                $problems[] = 'person pack ' . substr($entry, 0, 12) . ' has no portrait row';
            } else {
                foreach (epmts_validate($path, $deep, true, $forImport) as $problem) {
                    $problems[] = 'person ' . substr($entry, 0, 12) . ": $problem";
                }
            }
        } elseif (!isset($hashes[$entry])) {
            $problems[] = 'medias/' . substr($entry, 0, 12) . ' is not referenced by the database';
        }
    }
    $db->close();

    return $problems;
}
