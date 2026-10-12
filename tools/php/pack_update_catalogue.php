<?php
/**
 * Brings a pack (and its person packs) up to date with catalogue/catalogue.json: new tags,
 * new names and descriptions. Ids never change; media tags are kept.
 *
 * Usage: php tools/php/pack_update_catalogue.php <pack_folder>
 */
require __DIR__ . '/lib/epmts.php';
epmts_require_extensions();

[$positional] = epmts_parse_args($argv);
if (!isset($positional[0])) {
    epmts_fail('usage: php tools/php/pack_update_catalogue.php <pack_folder>');
}
$packs = [$positional[0]];
foreach (glob($positional[0] . '/' . EPMTS_MEDIA_DIRECTORY . '/*', GLOB_ONLYDIR) ?: [] as $person) {
    if (epmts_is_pack($person)) {
        $packs[] = $person;
    }
}
foreach ($packs as $packDir) {
    $db = epmts_open($packDir);
    epmts_sync_catalogue($db);
    epmts_export($db, $packDir);
    $db->close();
    echo "Updated $packDir\n";
}
