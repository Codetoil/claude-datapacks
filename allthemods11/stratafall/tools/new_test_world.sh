#!/usr/bin/env bash
HERE=$(cd "$(dirname "$0")" && pwd); ATM=$(cd "$HERE/../.." && pwd); LOGS=${STRATAFALL_LOGS:-$HERE/../test-logs}; mkdir -p "$LOGS"
# Create allthemods11/<name> with world's seed files and (optionally) the current Stratafall pack installed.
# Usage: new_test_world.sh <name> [--no-pack]
set -euo pipefail
A=$ATM
w=$1
[ -e "$A/$w" ] && { echo "$w exists — refusing to touch it"; exit 1; }
mkdir -p "$A/$w/data/minecraft"
cp -p "$A/world/level.dat" "$A/$w/level.dat"
cp -p "$A/world/data/minecraft/world_gen_settings.dat" "$A/$w/data/minecraft/world_gen_settings.dat"
if [ "${2:-}" != "--no-pack" ]; then
  mkdir -p "$A/$w/datapacks"
  cp -r "$A/stratafall/pack" "$A/$w/datapacks/stratafall"
fi
find "$A/$w" -maxdepth 3 | sort
