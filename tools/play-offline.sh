#!/bin/sh
# Play this fork offline: no account, no launcher, no sign-in.
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
exec "$BIN" --resources "$RESOURCES" --game-dir "$GAME_DIR" --home "$GAME_DIR" "$@"
