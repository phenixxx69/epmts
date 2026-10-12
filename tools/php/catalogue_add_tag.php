<?php
/**
 * Creates a new tag in the shared catalogue. ONLY in the EPMTS repository: a tag created
 * anywhere else would collide with another id. The new id is the next free one; retired ids
 * are never reused.
 *
 * Usage: php tools/php/catalogue_add_tag.php "Tag name" --type=6 [--subcategory=...]
 *        [--description="english keywords"] [--description-fr="mots clés"] [--ia-text=...] [--porn]
 */
require __DIR__ . '/lib/epmts.php';
epmts_require_extensions();

[$positional, $options] = epmts_parse_args($argv);
$name = trim((string) ($positional[0] ?? ''));
if ($name === '' || !isset($options['type'])) {
    epmts_fail('usage: php tools/php/catalogue_add_tag.php "Tag name" --type=<type id> [--subcategory=] [--description=] [--description-fr=] [--ia-text=] [--porn]');
}
$catalogue = epmts_load_catalogue();
$typeId = (int) $options['type'];
if (!in_array($typeId, array_column($catalogue['type_tag'], 'id'), true)) {
    epmts_fail('unknown type ' . $options['type'] . ' (see catalogue/TAGS.md, or create it with catalogue_add_type.php)');
}
foreach ($catalogue['tag_media'] as $tag) {
    if (strcasecmp((string) $tag['name'], $name) === 0 && (int) $tag['type_tag'] === $typeId) {
        epmts_fail('this type already has a tag named "' . $name . '" (id ' . $tag['id'] . ')');
    }
}
if (isset($options['porn']) && $typeId !== EPMTS_ACTION_TYPE_ID) {
    epmts_fail('only action tags (type ' . EPMTS_ACTION_TYPE_ID . ') carry the porn flag');
}
$id = max(array_merge(array_column($catalogue['tag_media'], 'id'), $catalogue['retired_tag_ids'] ?? [0])) + 1;
// Returns an option value as a trimmed string, or null when empty.
function option_text(array $options, string $key): ?string
{
    $value = isset($options[$key]) ? trim((string) $options[$key]) : '';

    return $value === '' ? null : $value;
}
$catalogue['tag_media'][] = [
    'id' => $id,
    'name' => $name,
    'type_tag' => $typeId,
    'subcategory_name' => option_text($options, 'subcategory'),
    'description' => option_text($options, 'description'),
    'description_fr' => option_text($options, 'description-fr'),
    'ia_text' => option_text($options, 'ia-text'),
    'porn' => isset($options['porn']) ? 1 : 0,
    'logo' => null,
];
epmts_save_catalogue($catalogue);
echo "Tag $id \"$name\" created in type $typeId.\n";
echo "A logo may be added as catalogue/logos/$id.png (PNG, at most 100x100) with \"logo\": \"logos/$id.png\".\n";
passthru(escapeshellarg(PHP_BINARY) . ' ' . escapeshellarg(__DIR__ . '/catalogue_build.php'));
