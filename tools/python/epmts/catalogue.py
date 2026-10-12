"""Reads the shared tag catalogue. This repository is the only authority on tag ids."""

import json
import os

from . import CATALOGUE_DIR

CATALOGUE_PATH = os.path.join(CATALOGUE_DIR, "catalogue.json")

TYPE_COLUMNS = ("id", "name", "position", "color")
TAG_COLUMNS = ("id", "name", "logo", "type_tag", "subcategory_name", "description", "description_fr", "ia_text", "porn")


# Loads catalogue.json and returns it as a dict with type_tag and tag_media lists.
def load_catalogue(path=CATALOGUE_PATH):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


# Returns the absolute path of a tag logo, or None when the tag has none on disk.
def logo_path(tag_id, logos_dir=None):
    logos_dir = logos_dir or os.path.join(CATALOGUE_DIR, "logos")
    path = os.path.join(logos_dir, "{}.png".format(int(tag_id)))
    return path if os.path.isfile(path) else None
