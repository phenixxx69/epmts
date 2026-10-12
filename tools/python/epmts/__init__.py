"""EPMTS core: the shared tag catalogue, the selection rules and the media pack format.

The server, the editor and the tests all use this package, so a rule is written once.
"""

import os

# The repository root: tools/python/epmts/__init__.py -> three levels up.
REPO_ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
CATALOGUE_DIR = os.path.join(REPO_ROOT, "catalogue")
EMPTY_PACK_DIR = os.path.join(REPO_ROOT, "empty-pack")
STANDARD_PATH = os.path.join(REPO_ROOT, "standard", "EPMTS-HTTP.md")
