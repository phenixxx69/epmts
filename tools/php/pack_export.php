<?php
/**
 * Rewrites tags.sql and tags.sql.js from tags.sqlite (after editing the database by hand).
 *
 * Usage: php tools/php/pack_export.php <pack_folder>
 */
require __DIR__ . '/lib/epmts.php';
epmts_require_extensions();

[$positional] = epmts_parse_args($argv);
if (!isset($positional[0])) {
    epmts_fail('usage: php tools/php/pack_export.php <pack_folder>');
}
$db = epmts_open($positional[0]);
epmts_export($db, $positional[0]);
$db->close();
echo "tags.sql and tags.sql.js written in {$positional[0]}\n";
