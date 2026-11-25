#!/usr/bin/env bash
HERE=$(cd "$(dirname "$0")" && pwd); ATM=$(cd "$HERE/../.." && pwd); LOGS=${STRATAFALL_LOGS:-$HERE/../test-logs}; mkdir -p "$LOGS"
# Start the ATM11 server on a given world folder (one shot; no restart loop), logging the console.
# Usage: run_server.sh <world-folder-name>
set -u
cd $ATM
w=$1
log=$LOGS/$w-$(date -u +%Y%m%dT%H%M%S).log
echo "console log: $log"
date -u +"start %Y-%m-%dT%H:%M:%SZ" > "$log.times"
# The NeoForge build of the installed server bundle (its startserver.sh sets it; 0.15.0-beta: 26.1.2.126).
neo=${NEOFORGE_VERSION:-$(sed -n 's/^NEOFORGE_VERSION=//p' startserver.sh)}
[ -f "libraries/net/neoforged/neoforge/$neo/unix_args.txt" ] || { echo "NeoForge '$neo' isn't installed in libraries/"; exit 1; }
/usr/lib/jvm/java-25-openjdk-amd64/bin/java @user_jvm_args.txt @libraries/net/neoforged/neoforge/$neo/unix_args.txt nogui --world "$w" < /dev/null > "$log" 2>&1
rc=$?
date -u +"exit %Y-%m-%dT%H:%M:%SZ code $rc" >> "$log.times"
echo "server exited with code $rc"
