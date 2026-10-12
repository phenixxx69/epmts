<?php
/**
 * Adds media files to a pack with the same tags. Metadata is removed, each file is stored as
 * medias/<sha256> and its original name is forgotten. A file already in the pack is skipped.
 *
 * Usage: php tools/php/pack_add_media.php <pack_folder> <tag_ids> <file> [<file>...]
 * Example: php tools/php/pack_add_media.php packs/main 1,7,56 picture.jpg clip.mp4
 * Tag ids are listed in catalogue/TAGS.md.
 */
require __DIR__ . '/lib/epmts.php';
epmts_require_extensions();

[$positional] = epmts_parse_args($argv);
if (count($positional) < 3) {
    epmts_fail('usage: php tools/php/pack_add_media.php <pack_folder> <tag_ids> <file> [<file>...]');
}
[$packDir, $tagList] = $positional;
$tagIds = epmts_parse_tag_ids($tagList);
$db = epmts_open($packDir);
foreach (array_slice($positional, 2) as $file) {
    [$mediaId, $created] = epmts_add_media($db, $packDir, $file, $tagIds);
    echo basename($file) . ($created ? " added as media #$mediaId\n" : " is already media #$mediaId, skipped\n");
}
epmts_export($db, $packDir);
$db->close();
echo "tags.sql and tags.sql.js updated.\n";
