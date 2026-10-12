<?php
/**
 * Creates a new tag type in the shared catalogue (ONLY in the EPMTS repository).
 *
 * Usage: php tools/php/catalogue_add_type.php "Type name" [--position=0] [--color=black]
 */
require __DIR__ . '/lib/epmts.php';
epmts_require_extensions();

[$positional, $options] = epmts_parse_args($argv);
$name = trim((string) ($positional[0] ?? ''));
if ($name === '') {
    epmts_fail('usage: php tools/php/catalogue_add_type.php "Type name" [--position=0] [--color=black]');
}
$catalogue = epmts_load_catalogue();
foreach ($catalogue['type_tag'] as $type) {
    if (strcasecmp($type['name'], $name) === 0) {
        epmts_fail('type "' . $name . '" already exists (id ' . $type['id'] . ')');
    }
}
$id = max(array_merge(array_column($catalogue['type_tag'], 'id'), $catalogue['retired_type_ids'] ?? [0])) + 1;
$catalogue['type_tag'][] = ['id' => $id, 'name' => $name, 'position' => (int) ($options['position'] ?? 0), 'color' => $options['color'] ?? 'black'];
epmts_save_catalogue($catalogue);
echo "Type $id \"$name\" created.\n";
passthru(escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg(__DIR__ . '/catalogue_build.php'));
