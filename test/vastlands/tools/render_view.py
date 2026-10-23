#!/usr/bin/env python3
"""Render an oblique 3D-style view of a square of terrain, looking north from the south.

Usage: render_view.py <world_dir> <out.png> <center_x> <center_z> <size> [--height 512] [--min-y -64]
       [--tilt 0.5] [--exaggeration 1.0]

Heights are true scale unless --exaggeration is given. Columns are drawn back to front, so
cliffs, overhang-free slopes and waterfalls read as they would from a distance.
"""
import argparse
import sys
from multiprocessing import Pool
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_map  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("world", type=Path)
    ap.add_argument("out")
    ap.add_argument("cx", type=int)
    ap.add_argument("cz", type=int)
    ap.add_argument("size", type=int)
    ap.add_argument("--height", type=int, default=512)
    ap.add_argument("--min-y", type=int, default=-64)
    ap.add_argument("--tilt", type=float, default=0.5, help="screen pixels per block of depth")
    ap.add_argument("--exaggeration", type=float, default=1.0)
    args = ap.parse_args()

    x0, z0 = args.cx - args.size // 2, args.cz - args.size // 2
    x1, z1 = x0 + args.size, z0 + args.size
    region_dir = args.world / "dimensions" / "minecraft" / "overworld" / "region"
    wanted = {(rx, rz) for rx in range(x0 >> 9, (x1 - 1 >> 9) + 1) for rz in range(z0 >> 9, (z1 - 1 >> 9) + 1)}
    jobs = [(str(region_dir / f"r.{rx}.{rz}.mca"), args.min_y, args.height) for rx, rz in sorted(wanted)
            if (region_dir / f"r.{rx}.{rz}.mca").exists()]
    with Pool(len(jobs) or 1) as pool:
        chunks = [c for res in pool.map(render_map.process_region, jobs) for c in res]

    n = args.size
    grid = [[None] * n for _ in range(n)]
    for cx, cz, cols in chunks:
        for i, (top, flo, blk, bio) in enumerate(cols):
            x, z = cx * 16 + (i & 15) - x0, cz * 16 + (i >> 4) - z0
            if 0 <= x < n and 0 <= z < n:
                grid[z][x] = (top, blk)

    ex, tilt = args.exaggeration, args.tilt
    ys = [c[0] for row in grid for c in row if c]
    lo, hi = min(ys), max(ys)
    w = n
    h = int(n * tilt + (hi - lo) * ex) + 40
    img = Image.new("RGB", (w, h), (160, 195, 235))
    d = ImageDraw.Draw(img)
    base = h - 10
    for z in range(n):
        row = grid[z]
        for x in range(n):
            c = row[x]
            if not c:
                continue
            top, blk = c
            nxt = row[x + 1][0] if x + 1 < n and row[x + 1] else top
            north = grid[z - 1][x][0] if z > 0 and grid[z - 1][x] else top
            light = max(0.5, min(1.35, 1.0 + 0.05 * (top - nxt) + 0.03 * (north - top) * -1))
            col = tuple(min(255, int(v * light)) for v in render_map.block_color(blk))
            # depth fog toward the back
            f = 0.35 * (1 - z / n)
            col = tuple(int(v * (1 - f) + s * f) for v, s in zip(col, (160, 195, 235)))
            sy = base - (n - 1 - z) * tilt - (top - lo) * ex
            # Draw down only as far as the next row toward the viewer can hide, so the near
            # edge doesn't grow a skirt down to the base line.
            front = grid[z + 1][x][0] if z + 1 < n and grid[z + 1][x] else top
            d.line([(x, sy), (x, sy + tilt + 1 + max(0, (top - front) * ex))], fill=col)
    img.save(args.out)
    print(f"view {w}x{h}, heights {lo}..{hi}")


if __name__ == "__main__":
    main()
