#!/bin/sh
# Open Horizon's launcher: pick your Minecraft files, press Play. No account, no sign-in.
#
#   ./tools/launcher.sh          the window
#   ./tools/launcher.sh --self-test   what it found, without a window
#
# It hands over to tools/launcher.py with the first Python on this machine that has Tk:
# Homebrew's python3 often does not (brew install python-tk), while the system one does.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

for candidate in "$PYTHON" python3.14 python3.13 python3.12 python3.11 python3.10 python3 /usr/bin/python3 python; do
    [ -n "$candidate" ] || continue
    if command -v "$candidate" >/dev/null 2>&1 &&
        "$candidate" -c "import tkinter" >/dev/null 2>&1; then
        exec "$candidate" "$ROOT/tools/launcher.py" "$@"
    fi
done

cat >&2 <<'MSG'
launcher: no Python on this machine has tkinter, so the window cannot open.
  macOS (Homebrew):  brew install python-tk
  Debian/Ubuntu:     sudo apt install python3-tk
  Windows:           the python.org installer includes Tk by default
Without it you can still play with ./tools/play-offline.sh.
MSG
exit 1
