#!/usr/bin/env bash
HERE=$(cd "$(dirname "$0")" && pwd); ATM=$(cd "$HERE/../.." && pwd); LOGS=${STRATAFALL_LOGS:-$HERE/../test-logs}; mkdir -p "$LOGS"
# Start the server on an existing test world, tick its sample areas, stop. Usage: tick_world.sh <world> [secs]
w=$1; secs=${2:-60}
$HERE/run_server.sh "$w" &
sleep 5
$HERE/wait_ready.sh | tail -3
$HERE/tick_samples.sh "$secs" | tail -4
cd $ATM
python3 -I $HERE/rcon.py server.properties "stop" | tail -1
wait
