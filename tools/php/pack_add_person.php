<?php
/**
 * Creates a person pack: one portrait and the other pictures of the same person, tagged one by
 * one. The portrait is chosen in the enclosing pack, then the person's media are drawn from
 * medias/<portrait_sha256>/ (standard section 11.1.1 and PR-1).
 *
 * Usage: php tools/php/pack_add_person.php <pack_folder> <person_source_folder> <portrait_file_name> [--tags=1,8]
 *   Without --tags, the tags of every file are asked one by one.
 *   With --tags, every non-portrait file gets those tags (the portrait is still asked).
 *   Portrait tip: give it a gender tag, tag 8 (kink status) when relevant, and an age-group tag.
 */
require __DIR__ . '/lib/epmts.php';
epmts_require_extensions();

[$positional, $options] = epmts_parse_args($argv);
if (count($positional) !== 3) {
    epmts_fail('usage: php tools/php/pack_add_person.php <pack_folder> <person_source_folder> <portrait_file_name> [--tags=ids]');
}
[$packDir, $sourceDir, $portraitName] = $positional;
if (basename(dirname(realpath($packDir))) === EPMTS_MEDIA_DIRECTORY) {
    epmts_fail('a person pack cannot contain another person pack; give the main pack folder.');
}
$portraitPath = $sourceDir . '/' . $portraitName;
if (!is_file($portraitPath)) {
    epmts_fail('portrait not found: ' . $portraitPath);
}

// Asks the tag ids of one file until a valid list is typed.
function ask_tags(SQLite3 $db, string $label): array
{
    while (true) {
        $answer = readline("Tag ids for $label (comma separated, see catalogue/TAGS.md): ");
        if ($answer === false) {
            epmts_fail('cancelled');
        }
        if (!preg_match('/^\s*\d+(\s*,\s*\d+)*\s*$/', $answer)) {
            echo "  Please type numbers separated by commas, e.g. 1,8,292\n";
            continue;
        }
        $ids = epmts_parse_tag_ids($answer);
        $problem = epmts_tag_problem($db, $ids);
        if ($problem === null) {
            return $ids;
        }
        echo "  Refused: $problem\n";
    }
}

$db = epmts_open($packDir);
$mediaDir = $packDir . '/' . EPMTS_MEDIA_DIRECTORY;
if (!is_dir($mediaDir)) {
    mkdir($mediaDir, 0755, true);
}
$portrait = epmts_prepare_media($portraitPath, $mediaDir);
if (!in_array($portrait['type'], ['image/jpeg', 'image/png', 'image/webp'], true)) {
    unlink($portrait['path']);
    epmts_fail('the portrait must be a still image (jpeg, png or webp)');
}
if (epmts_find_media($db, $portrait['hash']) !== null) {
    unlink($portrait['path']);
    epmts_fail('this portrait is already a media of the pack');
}
$portraitTags = ask_tags($db, 'the PORTRAIT ' . $portraitName);
$personDir = $mediaDir . '/' . $portrait['hash'];
epmts_create_pack($personDir);
$person = epmts_open($personDir);
epmts_insert_media($person, $portrait, $portraitTags);
rename($portrait['path'], $personDir . '/' . EPMTS_MEDIA_DIRECTORY . '/' . $portrait['hash']);
epmts_insert_media($db, $portrait, $portraitTags);

$commonTags = isset($options['tags']) ? epmts_parse_tag_ids((string) $options['tags']) : null;
foreach (array_diff(scandir($sourceDir) ?: [], ['.', '..', $portraitName]) as $file) {
    $path = $sourceDir . '/' . $file;
    if (!is_file($path) || epmts_sniff_type($path) === null) {
        continue;
    }
    $tags = $commonTags ?? ask_tags($person, $file);
    [$mediaId, $created] = epmts_add_media($person, $personDir, $path, $tags);
    echo "  $file " . ($created ? "added as media #$mediaId\n" : "already present, skipped\n");
}
epmts_export($person, $personDir);
epmts_export($db, $packDir);
$person->close();
$db->close();
echo "Person pack created: medias/{$portrait['hash']}\n";
