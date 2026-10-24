#!/usr/bin/env python3
"""Print block columns of steep spots in a biome: probe.py <world> <biome> <x0> <z0> <x1> <z1> [max]"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import anvil, dims
from render_map import section_lookup, state
world, biome, x0, z0, x1, z1 = sys.argv[1], sys.argv[2], *map(int, sys.argv[3:7])
mx = int(sys.argv[7]) if len(sys.argv) > 7 else 8
min_y, height, _ = dims.dimension_info("minecraft:overworld", dims.DEFAULT_GENERATED)
rd = dims.region_dir(Path(world), "minecraft:overworld")
chunks = {}
for rx in range(x0 >> 9, (x1 >> 9) + 1):
    for rz in range(z0 >> 9, (z1 >> 9) + 1):
        p = rd / f"r.{rx}.{rz}.mca"
        if p.exists():
            for lx, lz, c in anvil.read_region(str(p)):
                if c.get("Status") == "minecraft:full":
                    c["_sec"] = {s["Y"]: s for s in c.get("sections", [])}
                    c["_h"] = anvil.unpack_longs(c["Heightmaps"]["WORLD_SURFACE"], height.bit_length(), 256)
                    chunks[(rx * 32 + lx, rz * 32 + lz)] = c
def top(x, z):
    c = chunks.get((x >> 4, z >> 4))
    return None if c is None else c["_h"][(z & 15) * 16 + (x & 15)] - 1 + min_y
def blk(x, y, z):
    c = chunks[(x >> 4, z >> 4)]
    s = c["_sec"].get(y >> 4)
    if s is None: return "?"
    return state(section_lookup(s, "block_states", ((y & 15) * 16 + (z & 15)) * 16 + (x & 15), 4))[0].split(":")[-1]
def bio(x, y, z):
    c = chunks[(x >> 4, z >> 4)]
    s = c["_sec"].get(y >> 4)
    return state(section_lookup(s, "biomes", ((y & 15) >> 2) * 16 + ((z & 15) >> 2) * 4 + ((x & 15) >> 2), 1))[0]
n = 0
for x in range(x0, x1, 3):
    for z in range(z0, z1, 3):
        t = top(x, z)
        nb = [top(x + 1, z), top(x - 1, z), top(x, z + 1), top(x, z - 1)]
        if t is None or None in nb: continue
        sl = max(nb) - min(nb)
        if sl < 9 or bio(x, t, z) != biome: continue
        col = [blk(x, y, z) for y in range(t, t - 14, -1)]
        print(f"({x},{t},{z}) slope {sl} nb {nb}: " + " ".join(col))
        n += 1
        if n >= mx: sys.exit()
