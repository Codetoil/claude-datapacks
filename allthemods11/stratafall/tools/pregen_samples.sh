#!/usr/bin/env bash
HERE=$(cd "$(dirname "$0")" && pwd); ATM=$(cd "$HERE/../.." && pwd); LOGS=${STRATAFALL_LOGS:-$HERE/../test-logs}; mkdir -p "$LOGS"
# Pregenerate every sample area of samples.txt in the running server; prints timing per area.
cd $ATM
grep -vE '^\s*(#|$)' $HERE/samples.txt | while read -r name cx cz r; do
  if [ -n "${SAMPLES:-}" ] && [[ " $SAMPLES " != *" $name "* ]]; then continue; fi
  s=$SECONDS
  out=$(timeout 3600 python3 -I tools/pregen.py server.properties "$cx" "$cz" "$r" 2>&1 | tail -3 | tr '\n' ' ')
  echo "$(date -u +%T) $name ($cx,$cz r$r): $((SECONDS-s)) s | $out"
done
