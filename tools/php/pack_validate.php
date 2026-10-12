<?php
/**
 * Checks that a pack follows the standard: catalogue, files named by hash, no metadata path,
 * no stray file, the protected-age rule, person packs. Exit status 1 when a problem is found.
 *
 * Usage: php tools/php/pack_validate.php <pack_folder> [--deep]   (--deep re-hashes every file)
 */
require __DIR__ . '/lib/epmts.php';
epmts_require_extensions();

[$positional, $options] = epmts_parse_args($argv);
if (!isset($positional[0])) {
    epmts_fail('usage: php tools/php/pack_validate.php <pack_folder> [--deep]');
}

$problems = epmts_validate($positional[0], isset($options['deep']));
if (!$problems) {
    echo "The pack is valid.\n";
    exit(0);
}
echo count($problems) . " problem(s):\n - " . implode("\n - ", $problems) . "\n";
exit(1);
