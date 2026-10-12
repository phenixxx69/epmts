#!/usr/bin/env bash
# Prepares and starts EPMTS (Linux / macOS). Called by quickstart.sh.
# Usage: tools/setup/setup.sh [home|editor|server] [arguments for the tool]   (default: home)
# Checks Python 3.9+, tkinter and ffmpeg, offers to install what is missing with the system
# package manager, keeps a private Python environment in .venv/, then starts the tool.
set -euo pipefail

TARGET="home"
if [[ "${1:-}" =~ ^(home|editor|server)$ ]]; then
    TARGET="$1"
    shift
fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="$ROOT/.venv"
REQUIREMENTS="$ROOT/tools/python/requirements.txt"
case "$TARGET" in
    home) SCRIPT="$ROOT/tools/python/home/epmts_home.py" ;;
    server) SCRIPT="$ROOT/tools/python/server/epmts_server.py" ;;
    editor) SCRIPT="$ROOT/tools/python/editor/epmts_editor.py" ;;
esac

# Prints the install command of the system package manager for the given needs.
install_command() {
    local needs="$1"
    if command -v apt-get >/dev/null 2>&1; then
        local packages=""
        [[ $needs == *python* ]] && packages+=" python3 python3-venv python3-pip"
        [[ $needs == *tk* ]] && packages+=" python3-tk"
        [[ $needs == *ffmpeg* ]] && packages+=" ffmpeg"
        echo "sudo apt-get update && sudo apt-get install -y$packages"
    elif command -v dnf >/dev/null 2>&1; then
        local packages=""
        [[ $needs == *python* ]] && packages+=" python3 python3-pip"
        [[ $needs == *tk* ]] && packages+=" python3-tkinter"
        [[ $needs == *ffmpeg* ]] && packages+=" ffmpeg-free"
        echo "sudo dnf install -y$packages"
    elif command -v pacman >/dev/null 2>&1; then
        local packages=""
        [[ $needs == *python* ]] && packages+=" python"
        [[ $needs == *tk* ]] && packages+=" tk"
        [[ $needs == *ffmpeg* ]] && packages+=" ffmpeg"
        echo "sudo pacman -S --needed$packages"
    elif command -v zypper >/dev/null 2>&1; then
        local packages=""
        [[ $needs == *python* ]] && packages+=" python3 python3-pip"
        [[ $needs == *tk* ]] && packages+=" python3-tk"
        [[ $needs == *ffmpeg* ]] && packages+=" ffmpeg"
        echo "sudo zypper install -y$packages"
    elif command -v brew >/dev/null 2>&1; then
        local packages=""
        [[ $needs == *python* ]] && packages+=" python"
        [[ $needs == *tk* ]] && packages+=" python-tk"
        [[ $needs == *ffmpeg* ]] && packages+=" ffmpeg"
        echo "brew install$packages"
    fi
}

# Offers to install missing system packages; returns non-zero when declined or impossible.
offer_install() {
    local needs="$1" reason="$2" command
    command="$(install_command "$needs")"
    echo ""
    echo "Missing: $reason"
    if [[ -z "$command" ]]; then
        echo "No known package manager found. Please install it yourself, then run this script again."
        return 1
    fi
    echo "It can be installed with:"
    echo "    $command"
    read -r -p "Install it now? [y/N] " answer
    [[ "$answer" =~ ^[yYoO] ]] || return 1
    eval "$command"
}

# Finds a Python 3.9+ interpreter.
find_python() {
    for candidate in python3 python3.13 python3.12 python3.11 python3.10 python3.9 python; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

PYTHON="$(find_python || true)"
if [[ -z "$PYTHON" ]]; then
    offer_install "python" "Python 3.9 or newer" || exit 1
    PYTHON="$(find_python)" || { echo "Python is still not found."; exit 1; }
fi
if [[ "$TARGET" != "server" ]] && ! "$PYTHON" -c 'import tkinter' 2>/dev/null; then
    offer_install "tk" "tkinter, the Python window toolkit (needed by the EPMTS windows)" || exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1 && ! ls "$ROOT"/tools/bin/*/bin/ffmpeg >/dev/null 2>&1; then
    offer_install "ffmpeg" "ffmpeg (videos: import, thumbnails, conversion for games). Pictures work without it." \
        || echo "Continuing without ffmpeg."
fi

if [[ ! -x "$VENV/bin/python" ]]; then
    echo "Creating the private Python environment in .venv/ ..."
    if ! "$PYTHON" -m venv "$VENV"; then
        rm -rf "$VENV"
        offer_install "python" "the Python venv module" || exit 1
        "$PYTHON" -m venv "$VENV"
    fi
fi

# Reinstalls the requirements only when the requirement file changed.
STAMP="$VENV/.installed"
if [[ ! -f "$STAMP" ]] || ! cmp -s "$REQUIREMENTS" "$STAMP"; then
    echo "Installing the Python packages (first start only)..."
    PIP_DISABLE_PIP_VERSION_CHECK=1 "$VENV/bin/python" -m pip install -q -r "$REQUIREMENTS"
    cp "$REQUIREMENTS" "$STAMP"
fi

exec "$VENV/bin/python" "$SCRIPT" "$@"
