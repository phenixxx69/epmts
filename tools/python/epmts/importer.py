"""Imports a downloaded pack (folder or .zip) into an existing pack, after checking it fully,
and builds shareable pack zips.

The one entry point used by the home window, the editor and the command line: nothing is
merged unless the source is a complete, valid pack whose every file matches its SHA-256.
Imported media remember where they come from (media.origin = the pack name of pack.json).
"""

import os
import re
import shutil
import stat
import tempfile
import zipfile

from .pack import DATABASE, Pack, PackError, read_manifest

MAX_ZIP_ENTRIES = 500000
MAX_ZIP_BYTES = 200 * 1024 ** 3
# Files that archivers add on their own; they are not part of the pack and are left out.
IGNORED_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
IGNORED_PREFIXES = ("__MACOSX/",)


class ImportRefused(PackError):
    """The source is not a pack that may be imported; problems lists why."""

    # Keeps the problem list for display.
    def __init__(self, message, problems=()):
        super().__init__(message)
        self.problems = list(problems)


# Extracts a zip into target_dir, refusing unsafe entries (absolute paths, "..", links, bombs).
def safe_extract(zip_path, target_dir):
    target_dir = os.path.realpath(target_dir)
    try:
        archive = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError) as error:
        raise ImportRefused("This file is not a readable zip archive ({}).".format(error))
    with archive:
        entries = [info for info in archive.infolist()
                   if not info.filename.startswith(IGNORED_PREFIXES) and os.path.basename(info.filename.rstrip("/")) not in IGNORED_NAMES]
        if len(entries) > MAX_ZIP_ENTRIES:
            raise ImportRefused("The archive holds too many entries.")
        declared = sum(info.file_size for info in entries)
        if declared > MAX_ZIP_BYTES:
            raise ImportRefused("The archive is too large once extracted.")
        if declared > shutil.disk_usage(target_dir).free:
            raise ImportRefused("Not enough free disk space to extract the archive ({} MB needed).".format(declared // 1024 ** 2))
        for info in entries:
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ":" in name.split("/")[0] or ".." in name.split("/"):
                raise ImportRefused("Unsafe path in the archive: {}".format(name))
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ImportRefused("The archive contains a link, which a pack never does: {}".format(name))
            destination = os.path.realpath(os.path.join(target_dir, name))
            if os.path.commonpath([target_dir, destination]) != target_dir:
                raise ImportRefused("Unsafe path in the archive: {}".format(name))
            if info.is_dir():
                os.makedirs(destination, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            written = 0
            with archive.open(info) as source, open(destination, "wb") as output:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    written += len(chunk)
                    if written > info.file_size:  # the header lied about the size
                        raise ImportRefused("Corrupted archive entry: {}".format(name))
                    output.write(chunk)


# Finds the pack root of an extracted tree: the folder itself or its only sub-folder.
def find_pack_root(directory):
    if os.path.isfile(os.path.join(directory, DATABASE)):
        return directory
    children = [name for name in os.listdir(directory) if name not in IGNORED_NAMES]
    if len(children) == 1 and os.path.isfile(os.path.join(directory, children[0], DATABASE)):
        return os.path.join(directory, children[0])
    raise ImportRefused("No {} found: this is not an EPMTS pack (or the zip holds several folders).".format(DATABASE))


# Checks a source pack completely (schema, references, files, hashes, tagging rules); returns warnings.
def check_source(directory):
    try:
        with Pack(directory, upgrade=True, in_memory=True) as source:
            problems = source.validate(deep=True, for_import=True)
            media_count = source.conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    except PackError as error:
        raise ImportRefused(str(error), [str(error)])
    if problems:
        raise ImportRefused("The pack was not imported: {} problem(s) found.".format(len(problems)), problems)
    return media_count


# Imports a pack folder or .zip into target_dir; returns the merge report with "checked" media
# count and "origin" (the pack name recorded on the imported media).
def import_pack(target_dir, source_path, work_dir=None):
    work = tempfile.mkdtemp(prefix="epmts-import-", dir=work_dir or os.path.dirname(os.path.realpath(target_dir)))
    try:
        if os.path.isfile(source_path):
            safe_extract(source_path, work)
            source_dir = find_pack_root(work)
        elif os.path.isdir(source_path):
            source_dir = find_pack_root(source_path)
        else:
            raise ImportRefused("Nothing to import at {}".format(source_path))
        if os.path.realpath(source_dir) == os.path.realpath(target_dir):
            raise ImportRefused("A pack cannot be imported into itself.")
        checked = check_source(source_dir)
        manifest = read_manifest(source_dir)
        origin = manifest["name"] if manifest else os.path.splitext(os.path.basename(os.path.normpath(source_path)))[0]
        with Pack(target_dir, upgrade=True) as target:
            report = target.merge_from(source_dir, origin)
            target.export()
            for portrait_hash in target.person_hashes():
                with Pack(target.person_directory(portrait_hash), upgrade=True) as person:
                    person.sync_catalogue()
                    person.export()
        report["checked"] = checked
        report["origin"] = origin
        report["manifest"] = manifest
        return report
    finally:
        shutil.rmtree(work, ignore_errors=True)


# Turns a pack name into a safe folder name.
def slugify(name):
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")
    return slug[:80] or "pack"


# Builds a shareable zip from a pack: all media or only local ones, with pack.json. Exported
# local media take the new pack name as origin. Returns the number of media in the zip.
def create_pack_zip(pack_dir, manifest, local_only, zip_path):
    work = tempfile.mkdtemp(prefix="epmts-export-", dir=os.path.dirname(os.path.realpath(zip_path)))
    try:
        folder = slugify("{}-{}".format(manifest.get("name", ""), manifest.get("version", "")))
        build_dir = os.path.join(work, folder)
        with Pack(pack_dir, upgrade=True) as pack:
            count = pack.build_distribution(build_dir, manifest, local_only)
        partial = zip_path + ".part"
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as archive:
            for root, _, files in os.walk(build_dir):
                for name in sorted(files):
                    full = os.path.join(root, name)
                    # media are already compressed: storing them is much faster
                    method = zipfile.ZIP_STORED if os.sep + "medias" + os.sep in full else zipfile.ZIP_DEFLATED
                    archive.write(full, os.path.relpath(full, work), compress_type=method)
        os.replace(partial, zip_path)
        return count
    finally:
        shutil.rmtree(work, ignore_errors=True)
