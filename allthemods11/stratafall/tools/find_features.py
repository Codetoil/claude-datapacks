#!/usr/bin/env python3
"""Find where falls are in a world: 48x48 cells ranked by flowing water above y 72, blue ice above y 80 (ice-fall
tips) and lava above y 64, optionally minus the same cells of a baseline world.

Usage: find_features.py <world> [--baseline <world>] [--top 5]
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import dims  # noqa: E402
import anvil  # noqa: E402
from render_map import section_lookup, state  # noqa: E402

CELL = 48


def scan(world):
    min_y, height, _ = dims.dimension_info("minecraft:overworld", dims.DEFAULT_GENERATED)
    rd = dims.region_dir(Path(world), "minecraft:overworld")
    out = {"water": Counter(), "ice": Counter(), "lava": Counter()}
    for p in sorted(rd.glob("r.*.mca")):
        rx, rz = map(int, p.name.split(".")[1:3])
        for lx, lz, c in anvil.read_region(str(p)):
            if c.get("Status") != "minecraft:full":
                continue
            cx, cz = rx * 32 + lx, rz * 32 + lz
            for sec in c.get("sections", []):
                sy = sec["Y"]
                if sy * 16 + 15 < 64:
                    continue
                st = sec.get("block_states")
                if not st or not any(state(e)[0] in ("minecraft:water", "minecraft:blue_ice", "minecraft:lava")
                                     for e in st["palette"]):
                    continue
                for idx in range(4096):
                    y = sy * 16 + (idx >> 8)
                    n, props = state(section_lookup(sec, "block_states", idx, 4))
                    x = cx * 16 + (idx & 15)
                    z = cz * 16 + ((idx >> 4) & 15)
                    cell = (x // CELL, z // CELL)
                    if n == "minecraft:water" and y >= 72 and (props or {}).get("level", "0") != "0":
                        out["water"][cell] += 1
                    elif n == "minecraft:blue_ice" and y >= 80:
                        out["ice"][cell] += 1
                    elif n == "minecraft:lava" and y >= 64:
                        out["lava"][cell] += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("world")
    ap.add_argument("--baseline")
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()
    got = scan(args.world)
    base = scan(args.baseline) if args.baseline else None
    for kind, cells in got.items():
        scored = Counter()
        for cell, v in cells.items():
            scored[cell] = v - (base[kind].get(cell, 0) if base else 0)
        print(f"== {kind}")
        for (gx, gz), v in scored.most_common(args.top):
            if v <= 0:
                break
            print(f"  centre ({gx * CELL + CELL // 2}, {gz * CELL + CELL // 2}): +{v}")


if __name__ == "__main__":
    main()
