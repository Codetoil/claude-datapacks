#!/usr/bin/env python3
"""Find the tallest exposed faces in a world and render each head-on with face_view.py.

Usage: sheer_faces.py <world> <out_prefix> [--count 6] [--min-drop 14] [--size 72] [--scale 5] [--exclude-cold]
Picks columns whose lowest neighbour is at least --min-drop blocks lower, keeps the best per 96-block cell
(so the renders show different places), and looks at the face from the side it faces.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import terrain_stats as ts  # noqa: E402
import dims  # noqa: E402

PACK_TAGS = Path(__file__).resolve().parents[1] / "pack/data/stratafall/tags/worldgen/biome"


def tag(name):
    return {v if isinstance(v, str) else v["id"] for v in json.loads((PACK_TAGS / f"{name}.json").read_text())["values"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("world")
    ap.add_argument("out_prefix")
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--min-drop", type=int, default=14)
    ap.add_argument("--size", type=int, default=72)
    ap.add_argument("--scale", type=int, default=5)
    ap.add_argument("--exclude-cold", action="store_true")
    ap.add_argument("--biomes", help="comma-separated biome ids to keep (default: strata biomes)")
    args = ap.parse_args()
    min_y, height, _ = dims.dimension_info("minecraft:overworld", dims.DEFAULT_GENERATED)
    keep = set(args.biomes.split(",")) if args.biomes else tag("strata")
    if args.exclude_cold:
        keep -= tag("climate/cold")
    rd = dims.region_dir(Path(args.world), "minecraft:overworld")
    cols = {}
    for p in sorted(rd.glob("r.*.mca")):
        for cx, cz, cl, *_ in ts.process_region((str(p), min_y, height, None)):
            for i, col in enumerate(cl):
                cols[(cx * 16 + (i & 15), cz * 16 + (i >> 4))] = col
    best = {}
    dirs = {(1, 0): "west", (-1, 0): "east", (0, 1): "north", (0, -1): "south"}  # low side -> viewer looks this way
    for (x, z), (y, blk, above, bio) in cols.items():
        if bio not in keep:
            continue
        nbs = {d: cols.get((x + d[0], z + d[1])) for d in dirs}
        if None in nbs.values():
            continue
        d, low = min(nbs.items(), key=lambda kv: kv[1][0])
        drop = y - low[0]
        if drop < args.min_drop:
            continue
        cell = (x // 96, z // 96)
        if cell not in best or drop > best[cell][0]:
            best[cell] = (drop, x, z, y, bio, dirs[d])
    picks = sorted(best.values(), reverse=True)[:args.count]
    for k, (drop, x, z, y, bio, facing) in enumerate(picks):
        dx, dz = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}[facing]
        cx, cz = x - dx * args.size // 4, z - dz * args.size // 4  # centre a little in front of the face
        out = f"{args.out_prefix}-{k}.png"
        subprocess.run([sys.executable, "-I", str(Path(__file__).resolve().parent / "face_view.py"), args.world, out,
                        str(cx), str(cz), str(args.size), "--scale", str(args.scale), "--facing", facing],
                       check=True, capture_output=True)
        print(f"{out}: drop {drop} at ({x}, {y}, {z}) {bio}, looking {facing}")


if __name__ == "__main__":
    main()
