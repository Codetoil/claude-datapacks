#!/usr/bin/env python3
"""Where inside their chunk are steep soil/snow columns? edge_check.py <world> <x0> <z0> <x1> <z1>"""
import sys
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parent))
import terrain_stats as ts
from pathlib import Path
import dims
world, x0, z0, x1, z1 = sys.argv[1], *map(int, sys.argv[2:6])
min_y, height, _ = dims.dimension_info("minecraft:overworld", dims.DEFAULT_GENERATED)
rd = dims.region_dir(Path(world), "minecraft:overworld")
cols = {}
for p in sorted(rd.glob("r.*.mca")):
    rx, rz = map(int, p.name.split(".")[1:3])
    if not (rx * 512 < x1 and rx * 512 + 512 > x0 and rz * 512 < z1 and rz * 512 + 512 > z0):
        continue
    for cx, cz, cl, *_ in ts.process_region((str(p), min_y, height, (x0, z0, x1, z1))):
        for i, col in enumerate(cl):
            cols[(cx * 16 + (i & 15), cz * 16 + (i >> 4))] = col
edge = Counter(); inner = Counter()
for (x, z), (y, blk, above, bio) in cols.items():
    nb = [cols.get(k) for k in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1))]
    if None in nb or "ocean" in bio:
        continue
    s = max(n[0] for n in nb) - min(n[0] for n in nb)
    if s < 7:
        continue
    g = ts.group(blk)
    at_edge = (x & 15) in (0, 15) or (z & 15) in (0, 15)
    (edge if at_edge else inner)[g] += 1
for name, c in (("chunk-edge columns", edge), ("inner columns", inner)):
    n = sum(c.values())
    print(f"{name}: n={n}: " + ", ".join(f"{g} {100 * v / n:.0f}%" for g, v in c.most_common(6)))
print("edge share of columns: expected 23.4% (60/256)")
