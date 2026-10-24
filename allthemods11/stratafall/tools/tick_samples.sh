#!/usr/bin/env bash
HERE=$(cd "$(dirname "$0")" && pwd); ATM=$(cd "$HERE/../.." && pwd); LOGS=${STRATAFALL_LOGS:-$HERE/../test-logs}; mkdir -p "$LOGS"
# Let fluids settle in every sample area of the running server: forceload (<=256 chunks per command),
# /tick sprint (works through pause-when-empty), save, unforce. Usage: tick_samples.sh [seconds=60]
secs=${1:-60}
cd $ATM
R="python3 -I $HERE/rcon.py server.properties"
python3 -I $HERE/sample_bounds.py | while read -r name x0 z0 x1 z1; do
  if [ -n "${SAMPLES:-}" ] && [[ " $SAMPLES " != *" $name "* ]]; then continue; fi
  for ((bx = x0; bx < x1; bx += 256)); do
    for ((bz = z0; bz < z1; bz += 256)); do
      ex=$((bx + 255 < x1 - 1 ? bx + 255 : x1 - 1)); ez=$((bz + 255 < z1 - 1 ? bz + 255 : z1 - 1))
      $R "forceload add $bx $bz $ex $ez" | grep -E 'Marked|No chunks|error|Too many' | sed "s/^/$name: /"
    done
  done
done
L=$(ls -t $LOGS/*.log | head -1)
n0=$(grep -c 'Sprint completed' "$L")
$R "tick sprint ${secs}s" | grep -v '^$'
until [ "$(grep -c 'Sprint completed' "$L")" -gt "$n0" ]; do sleep 2; done
grep 'Sprint completed' "$L" | tail -1 | cut -c1-200
$R "save-all flush" "forceload remove all" | grep -vE '^$|^>'
