#!/usr/bin/env bash
HERE=$(cd "$(dirname "$0")" && pwd); ATM=$(cd "$HERE/../.." && pwd); LOGS=${STRATAFALL_LOGS:-$HERE/../test-logs}; mkdir -p "$LOGS"
# Start the server on a world, pregen + tick only the given samples, stop. Usage: sample_pass.sh <world> "<samples>" [secs]
w=$1; samples=$2; secs=${3:-60}
N=$HERE
$N/run_server.sh "$w" &
sleep 5
$N/wait_ready.sh | tail -2
SAMPLES="$samples" $N/pregen_samples.sh
SAMPLES="$samples" $N/tick_samples.sh "$secs" | tail -2
cd $ATM
python3 -I $N/rcon.py server.properties "stop" | tail -1
wait
