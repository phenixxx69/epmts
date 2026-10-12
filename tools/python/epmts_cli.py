"""EPMTS command line (Python): the same operations as the editor, for scripts.

  python tools/python/epmts_cli.py import <pack_folder> <pack.zip | pack_folder>
  python tools/python/epmts_cli.py check <pack_folder>
  python tools/python/epmts_cli.py create <new_pack_folder>
  python tools/python/epmts_cli.py update-catalogue <pack_folder>
  python tools/python/epmts_cli.py create-pack <pack_folder> <out.zip> --name N --author A --version V [--date YYYY-MM-DD] [--local-only]

Use the Python of the launchers' environment: .venv/bin/python (Windows: .venv\\Scripts\\python).
"""

import argparse
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from epmts.importer import ImportRefused, create_pack_zip, import_pack  # noqa: E402
from epmts.pack import Pack, PackError  # noqa: E402


# Imports a pack folder or zip after a full check.
def command_import(args):
    report = import_pack(args.pack, args.source)
    print("{} media checked: {} added, {} already present (tags united), {} person pack(s).".format(
        report["checked"], report["added"], report["updated"], report["persons"]))
    for media_hash, reason in report["skipped"]:
        print("  skipped {}…: {}".format(media_hash[:12], reason))


# Builds a shareable pack zip with pack.json.
def command_create_pack(args):
    manifest = {"name": args.name, "author": args.author, "version": args.version, "date": args.date, "description": args.description}
    count = create_pack_zip(args.pack, manifest, args.local_only, args.zip)
    print("{} media saved in {}".format(count, args.zip))


# Checks a pack, re-hashing every file.
def command_check(args):
    with Pack(args.pack) as pack:
        problems = pack.validate(deep=True)
    if problems:
        print("{} problem(s):".format(len(problems)))
        for problem in problems:
            print(" - " + problem)
        return 1
    print("The pack is valid.")
    return 0


# Creates an empty pack.
def command_create(args):
    Pack.create(args.pack).close()
    print("Empty pack created in " + args.pack)


# Replaces the catalogue of a pack and its person packs with the repository one.
def command_update_catalogue(args):
    with Pack(args.pack, upgrade=True) as pack:
        for directory in [pack.directory] + [pack.person_directory(h) for h in pack.person_hashes()]:
            with Pack(directory, upgrade=True) as target:
                target.sync_catalogue()
                target.export()
            print("Updated " + directory)


# Parses the command line and runs one command.
def main():
    parser = argparse.ArgumentParser(description="EPMTS pack tools")
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import", help="import a pack (.zip or folder) into a pack, after checking it")
    importer.add_argument("pack")
    importer.add_argument("source")
    importer.set_defaults(run=command_import)
    creator = commands.add_parser("create-pack", help="build a shareable pack zip (all media, or --local-only)")
    creator.add_argument("pack")
    creator.add_argument("zip")
    creator.add_argument("--name", required=True)
    creator.add_argument("--author", required=True)
    creator.add_argument("--version", required=True)
    creator.add_argument("--date", default=datetime.date.today().isoformat())
    creator.add_argument("--description", default="")
    creator.add_argument("--local-only", action="store_true", help="only the media you added yourself")
    creator.set_defaults(run=command_create_pack)
    for name, run, text in (("check", command_check, "check a pack completely"),
                            ("create", command_create, "create an empty pack"),
                            ("update-catalogue", command_update_catalogue, "bring a pack up to date with the catalogue")):
        command = commands.add_parser(name, help=text)
        command.add_argument("pack")
        command.set_defaults(run=run)
    args = parser.parse_args()
    try:
        return args.run(args) or 0
    except ImportRefused as error:
        print("Refused: {}".format(error))
        for problem in error.problems:
            print(" - " + problem)
        return 1
    except PackError as error:
        print("Error: {}".format(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
