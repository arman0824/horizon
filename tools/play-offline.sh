#!/bin/sh
# Play this fork offline from a terminal: no account, no sign-in.
# (tools/launcher.sh is the same thing with a window.)
#
#   ./tools/play-offline.sh                      # opens the game
#   ./tools/play-offline.sh --creative --seed 7  # extra flags go to the game
#
# The game's saved worlds, options.txt and the player name live in HORIZON_GAME_DIR
# (default ~/horizon-game), so the repository stays clean and your worlds survive rebuilds.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GAME_DIR="${HORIZON_GAME_DIR:-$HOME/horizon-game}"
BIN="$ROOT/target/fast/horizon-client"
# Absolute, so the game finds them no matter which folder this is run from.
RESOURCES="$ROOT/.local/horizon-client/26.3"

# Build once when the binary is missing (skipped when HORIZON_NO_AUTOBUILD=1 is set).
if [ ! -x "$BIN" ] && [ -z "$HORIZON_NO_AUTOBUILD" ]; then
    echo "play-offline: building the game first (this takes a few minutes)…"
    CARGO="${CARGO:-$HOME/.cargo/bin/cargo}"
    "$CARGO" build --manifest-path "$ROOT/Cargo.toml" --profile fast -p horizon-game
fi
[ -x "$BIN" ] || { echo "play-offline: $BIN is missing; run: cargo build --profile fast -p horizon-game" >&2; exit 1; }

if [ ! -f "$RESOURCES/horizon-resources.json" ]; then
    cat >&2 <<'MSG'
play-offline: the prepared resources are missing. From your own Minecraft install, once:

    ./target/fast/horizon-prepare --prepare --server-jar /path/to/server.jar

(the pins in research-lock.json name the exact files it checks.)
MSG
    exit 1
fi

mkdir -p "$GAME_DIR"
echo "play-offline: game folder $GAME_DIR"
if [ -z "$(find "$RESOURCES" -name '*.ogg' 2>/dev/null | head -n 1)" ]; then
    echo "play-offline: no sound files in $RESOURCES — the game will be silent." >&2
    echo "play-offline: add them with: \"$ROOT/target/fast/horizon-prepare\" sounds   (run from $ROOT)" >&2
    echo "play-offline: or prepare again — --prepare copies the sounds too." >&2
fi
exec "$BIN" --resources "$RESOURCES" --game-dir "$GAME_DIR" --home "$GAME_DIR" "$@"
