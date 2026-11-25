#!/usr/bin/env bash
HERE=$(cd "$(dirname "$0")" && pwd); ATM=$(cd "$HERE/../.." && pwd); LOGS=${STRATAFALL_LOGS:-$HERE/../test-logs}; mkdir -p "$LOGS"
# Full test cycle on a (new) test world: start, check pack errors, pregen samples, tick fluids, stop.
# Usage: full_test.sh <world> [tick_secs]
w=$1; secs=${2:-60}
N=$HERE
$N/run_server.sh "$w" &
sleep 5
$N/wait_ready.sh | tail -4
L=$(ls -t $LOGS/*.log | head -1)
echo "--- pack-related log lines:"
grep -iE 'stratafall|lithostitched.*(error|fail|invalid)|Unknown (registry|key|element)' "$L" | grep -v DEBUG | cut -c1-260 | head -15
echo "--- pregen:"
$N/pregen_samples.sh
echo "--- tick:"
$N/tick_samples.sh "$secs" | tail -3
cd $ATM
python3 -I $N/rcon.py server.properties "stop" | tail -1
wait
echo "--- done $(date -u +%T)"
