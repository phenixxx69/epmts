<?php
/**
 * Creates a new, empty pack: the whole tag catalogue and no media.
 *
 * Usage: php tools/php/pack_create.php <new_pack_folder>
 */
require __DIR__ . '/lib/epmts.php';
epmts_require_extensions();

[$positional] = epmts_parse_args($argv);
if (!isset($positional[0])) {
    epmts_fail('usage: php tools/php/pack_create.php <new_pack_folder>');
}
epmts_create_pack($positional[0]);
echo "Empty pack created in {$positional[0]}\n";
