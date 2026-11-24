#!/bin/sh
# Open Horizon's launcher on macOS: pick your Minecraft files, press Play.
# Double-click this file. The first time, use right-click -> Open so Gatekeeper asks once.
cd "$(dirname "$0")" || exit 1
exec ./tools/launcher.sh "$@"
