#!/usr/bin/env bash
HERE=$(cd "$(dirname "$0")" && pwd); ATM=$(cd "$HERE/../.." && pwd); LOGS=${STRATAFALL_LOGS:-$HERE/../test-logs}; mkdir -p "$LOGS"
# Wait until the newest console log shows "Done", a fatal error, or the JVM is gone (max 15 min).
L=$(ls -t $LOGS/*.log | head -1)
s=$SECONDS
until grep -qE 'Done \([0-9.]+s\)!|Exception in server tick loop|Failed to start|Crash report saved|Encountered an unexpected exception|LoadingFailedException' "$L" 2>/dev/null || ! pgrep -x java >/dev/null || [ $((SECONDS-s)) -gt 900 ]; do sleep 2; done
echo "log: $L; waited $((SECONDS-s)) s"
grep -E 'Preparing level|Done \(|Exception in server tick loop|Failed to start|Crash report saved|unexpected exception|LoadingFailedException|Found new data pack|RCON running' "$L" | cut -c1-200 | head
pgrep -x java >/dev/null && echo "java running" || echo "java NOT running"
