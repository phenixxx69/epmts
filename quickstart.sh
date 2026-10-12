#!/usr/bin/env bash
# EPMTS: run ./quickstart.sh to start. Installs what is missing on first start, then opens the home window.
# Advanced: ./quickstart.sh editor [pack folder]   /   ./quickstart.sh server [pack folder] [--no-key] [--port 5055]
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tools/setup/setup.sh" "$@"
