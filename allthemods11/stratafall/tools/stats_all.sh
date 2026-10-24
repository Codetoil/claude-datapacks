#!/usr/bin/env bash
HERE=$(cd "$(dirname "$0")" && pwd); ATM=$(cd "$HERE/../.." && pwd); LOGS=${STRATAFALL_LOGS:-$HERE/../test-logs}; mkdir -p "$LOGS"
# terrain_stats.py over every sample area of a world; writes JSON per sample into <out_dir>.
# Usage: stats_all.sh <world> <out_dir>
w=$1; out=$2; mkdir -p "$out"
cd $ATM
python3 -I $HERE/sample_bounds.py | while read -r name x0 z0 x1 z1; do
  python3 -I $HERE/terrain_stats.py "$w" --bounds $x0 $z0 $x1 $z1 --json "$out/$name.json" --cliff-png "$out/$name-cliffs.png" > "$out/$name.txt" 2>&1 || echo "$name: failed"
done
python3 -I - "$out" <<'PY'
import json, sys, glob, os
from collections import Counter
tot = Counter(); land = 0; hw = 0; hl = 0; ws = 0; wf = 0; ch = 0
cls_tot = {}
for f in sorted(glob.glob(os.path.join(sys.argv[1], "*.json"))):
    d = json.load(open(f))
    land += d["land_columns"]; hw += d["high_water_columns"]; hl += d["high_lava_columns"]
    ws += d.get("water_sources_y72", 0); wf += d.get("water_flowing_y72", 0); ch += d["chunks"]
    for k in ("lava_y64", "packed_ice_y80", "blue_ice_y80"): tot[k] += d.get(k, 0)
    for c, v in d["classes"].items():
        n = v.pop("n")
        cc = cls_tot.setdefault(c, Counter())
        for g, share in v.items():
            cc[g] += share * n
        cc["_n"] += n
print(f"ALL SAMPLES: {ch} chunks, land columns {land}, surface water above sea {hw} ({1e4*hw/max(land,1):.1f}/10k), lava above sea {hl}; water y>=72: {ws} sources ({ws/max(ch,1):.2f}/chunk), {wf} flowing; lava y>=64 {tot['lava_y64']}, packed ice y>=80 {tot['packed_ice_y80']}, blue ice y>=80 {tot['blue_ice_y80']}")
for c in ("flat(0-1)", "gentle(2-3)", "steep(4-6)", "cliff(7-12)", "sheer(13+)"):
    cc = cls_tot.get(c)
    if not cc: continue
    n = cc.pop("_n")
    print(f"  {c:12s} n={int(n):7d}: " + ", ".join(f"{g} {100*v/n:.0f}%" for g, v in cc.most_common(7)))
PY
