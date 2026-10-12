# PHP command-line tools

Scripts for automation and servers. They need **PHP 7.4 or newer** with the **sqlite3**
extension (Debian/Ubuntu: `sudo apt install php-cli php-sqlite3`; Windows: download PHP from
windows.php.net and enable `extension=sqlite3` in `php.ini`). Videos need ffmpeg (the
launchers install it in `tools/bin`, which the scripts find too).

Run them from the repository folder. Tag ids are listed in [catalogue/TAGS.md](../../catalogue/TAGS.md).

## Packs

| Command | Purpose |
| --- | --- |
| `php tools/php/pack_create.php <folder>` | Creates an empty pack (whole catalogue, no media). |
| `php tools/php/pack_add_media.php <pack> <tag_ids> <file>…` | Adds files with the same tags, e.g. `php tools/php/pack_add_media.php packs/main 1,56 a.jpg b.mp4`. Metadata is removed, files are named by SHA-256. |
| `php tools/php/pack_add_person.php <pack> <folder> <portrait> [--tags=ids]` | Creates a person pack from a folder of pictures of one person. Asks the tags of the portrait, then of each picture (or applies `--tags` to all). |
| `php tools/php/pack_merge.php <target> <source>…` | Merges packs by union. Each source is checked first (structure, database, `pack.json`, SHA-256 of every file, safety rule) and refused as a whole on any problem. New media get the source pack name as origin. The target is created if missing. |
| `php tools/php/pack_validate.php <pack> [--deep]` | Checks a pack; `--deep` re-hashes every file. Exit status 1 on problems. |
| `php tools/php/pack_update_catalogue.php <pack>` | Brings the tag list of a pack and its person packs up to date. |
| `php tools/php/pack_export.php <pack>` | Rewrites `tags.sql` and `tags.sql.js` after editing `tags.sqlite` by hand. |

To import a **.zip**, or to create a shareable pack, use the home window / media manager or
`tools/python/epmts_cli.py` (same checks). Media added by `pack_add_media.php` are *local*
(no origin).

Every tool enforces the tagging rules of the [standard](../../standard/EPMTS-HTTP.md) (section 12)
and refuses unknown tag ids (tags are created only in this repository).

## Catalogue (this repository only)

| Command | Purpose |
| --- | --- |
| `php tools/php/catalogue_add_tag.php "Name" --type=<id> [--description=] [--description-fr=] [--subcategory=] [--ia-text=] [--porn]` | Creates a tag with the next free id. |
| `php tools/php/catalogue_add_type.php "Name" [--position=] [--color=]` | Creates a tag type. |
| `php tools/php/catalogue_build.php` | Rebuilds `catalogue/TAGS.md` and `empty-pack/` from `catalogue.json`. |

See [catalogue/README.md](../../catalogue/README.md) for the rules.

## Library

`tools/php/lib/epmts.php` holds the format (schema, dump, export), the rules and the import
helpers, for your own PHP code:

```php
require 'tools/php/lib/epmts.php';
$db = epmts_open('packs/main');
[$mediaId, $created] = epmts_add_media($db, 'packs/main', 'picture.jpg', [1, 56]);
epmts_export($db, 'packs/main');
```

It writes packs byte-identical to the Python tools.
