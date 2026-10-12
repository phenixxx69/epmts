<?php
/**
 * Rebuilds what is generated from catalogue/catalogue.json: the empty pack (empty-pack/)
 * and the readable tag list (catalogue/TAGS.md).
 *
 * Usage: php tools/php/catalogue_build.php
 */
require __DIR__ . '/lib/epmts.php';
epmts_require_extensions();

$root = epmts_repo_root();
$catalogue = epmts_load_catalogue();

// Empty pack: only generated files are replaced.
$emptyPack = $root . '/empty-pack';
foreach ([EPMTS_DATABASE, EPMTS_DUMP, EPMTS_BROWSER_DUMP] as $file) {
    if (is_file($emptyPack . '/' . $file)) {
        unlink($emptyPack . '/' . $file);
    }
}
if (is_dir($emptyPack . '/' . EPMTS_MEDIA_DIRECTORY)) {
    rmdir($emptyPack . '/' . EPMTS_MEDIA_DIRECTORY);
}
epmts_create_pack($emptyPack);
rmdir($emptyPack . '/' . EPMTS_MEDIA_DIRECTORY); // git keeps no empty folder; the tools create it on demand
echo "empty-pack/ rebuilt (" . count($catalogue['tag_media']) . " tags, " . count($catalogue['type_tag']) . " types)\n";

// TAGS.md, grouped by type.
// Escapes a value for a Markdown table cell.
function cell($value): string
{
    return str_replace(['|', "\n"], ['\\|', ' '], (string) $value);
}

$types = $catalogue['type_tag'];
usort($types, function ($a, $b) {
    return [$a['position'], $a['id']] <=> [$b['position'], $b['id']];
});
$tagsByType = [];
foreach ($catalogue['tag_media'] as $tag) {
    $tagsByType[$tag['type_tag']][] = $tag;
}
$lines = [
    '# EPMTS tag list',
    '',
    '> Generated from `catalogue/catalogue.json` by `php tools/php/catalogue_build.php`. Do not edit by hand.',
    '',
    'This repository is the **only authority** on tag ids: a tag is created here and nowhere else,',
    'and an id is never renumbered nor reused. See [catalogue/README.md](README.md).',
    '',
    'Legend: 🔞 porn action tag · ⛔ excluded by default (section 4.1 of the standard) · 🛡 protected tag (see section 12 of the standard).',
    '',
    count($catalogue['tag_media']) . ' tags in ' . count($types) . ' types. Retired ids (never reused): '
        . (implode(', ', $catalogue['retired_tag_ids'] ?? []) ?: 'none') . '.',
    '',
    '## Types',
    '',
    '| Type id | Name | Tags |',
    '| ---: | --- | ---: |',
];
foreach ($types as $type) {
    $anchor = strtolower(preg_replace('/[^A-Za-z0-9]+/', '-', $type['id'] . '-' . $type['name']));
    $lines[] = '| ' . $type['id'] . ' | [' . cell($type['name']) . '](#' . trim($anchor, '-') . ') | ' . count($tagsByType[$type['id']] ?? []) . ' |';
}
foreach ($types as $type) {
    $lines[] = '';
    $lines[] = '## ' . $type['id'] . ' ' . $type['name'];
    $lines[] = '';
    $lines[] = '| Id | Name | Subcategory | Description | Description (FR) | Flags |';
    $lines[] = '| ---: | --- | --- | --- | --- | --- |';
    $tags = $tagsByType[$type['id']] ?? [];
    usort($tags, function ($a, $b) {
        return [strtolower((string) $a['subcategory_name']), strtolower((string) $a['name'])] <=> [strtolower((string) $b['subcategory_name']), strtolower((string) $b['name'])];
    });
    foreach ($tags as $tag) {
        $flags = [];
        if ((int) $tag['porn'] === 1 && (int) $tag['type_tag'] === EPMTS_ACTION_TYPE_ID) {
            $flags[] = '🔞';
        }
        if (in_array((int) $tag['id'], EPMTS_LIFTABLE_DEFAULT_EXCLUSIONS, true)) {
            $flags[] = '⛔';
        }
        if ((int) $tag['id'] === EPMTS_PROTECTED_AGE_TAG_ID) {
            $flags[] = '⛔ 🛡';
        }
        $lines[] = '| ' . $tag['id'] . ' | ' . cell($tag['name']) . ' | ' . cell($tag['subcategory_name']) . ' | '
            . cell($tag['description']) . ' | ' . cell($tag['description_fr']) . ' | ' . implode(' ', $flags) . ' |';
    }
}
file_put_contents($root . '/catalogue/TAGS.md', implode("\n", $lines) . "\n");
echo "catalogue/TAGS.md rebuilt\n";
