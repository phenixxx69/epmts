<?php
/**
 * Merges packs by union (standard section 11.5): media with the same SHA-256 appear once with
 * all their tags, person packs are merged too, tag ids never change. The target is created
 * when missing. Every source is checked first (structure, database, SHA-256 of every file,
 * tagging rules) and refused as a whole on any problem. A media whose united tags would break the
 * tagging rules is skipped and reported.
 *
 * Usage: php tools/php/pack_merge.php <target_pack> <source_pack> [<source_pack>...]
 */
require __DIR__ . '/lib/epmts.php';
epmts_require_extensions();

[$positional] = epmts_parse_args($argv);
if (count($positional) < 2) {
    epmts_fail('usage: php tools/php/pack_merge.php <target_pack> <source_pack> [<source_pack>...]');
}
$targetDir = array_shift($positional);
if (!epmts_is_pack($targetDir)) {
    epmts_create_pack($targetDir);
    echo "Created $targetDir\n";
}
foreach ($positional as $sourceDir) {
    if (!epmts_is_pack($sourceDir)) {
        epmts_fail($sourceDir . ' is not a pack (no tags.sqlite). A .zip must be imported with the editor or tools/python/epmts_cli.py import.');
    }
    echo "Checking $sourceDir (every file is re-hashed)...\n";
    $problems = epmts_validate($sourceDir, true, false, true);
    if ($problems) {
        epmts_fail("$sourceDir was not merged, " . count($problems) . " problem(s):\n - " . implode("\n - ", $problems));
    }
    $manifest = epmts_read_manifest($sourceDir);
    $origin = $manifest ? $manifest['name'] : basename(realpath($sourceDir));
    $report = epmts_merge($targetDir, $sourceDir, $origin);
    echo "$sourceDir (\"$origin\"): {$report['added']} added, {$report['updated']} already present (tags united), {$report['persons']} person pack(s)\n";
    foreach ($report['skipped'] as $line) {
        echo "  skipped $line\n";
    }
}
