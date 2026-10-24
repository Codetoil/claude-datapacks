#!/usr/bin/env python3
"""Side-by-side metrics of test worlds from their stats JSON (stats/<world>/<sample>.json).

Usage: compare.py <stats_dir_a> <stats_dir_b> [...]
"""
import json
import sys
from pathlib import Path

dirs = [Path(a) for a in sys.argv[1:]]
samples = sorted(p.stem for p in dirs[0].glob("*.json"))


def load(d, s):
    p = d / f"{s}.json"
    return json.loads(p.read_text()) if p.exists() else None


def cliff_rock(d):
    cls = (d or {}).get("classes", {})
    n = r = 0
    for c in ("cliff(7-12)", "sheer(13+)"):
        if c in cls:
            n += cls[c]["n"]
            r += cls[c].get("rock", 0) * cls[c]["n"]
    return 100 * r / n if n else float("nan")


def steep_rock(d):
    c = (d or {}).get("classes", {}).get("steep(4-6)")
    return 100 * c.get("rock", 0) if c else float("nan")


metrics = [("rock% cliffs(7+)", cliff_rock), ("rock% steep(4-6)", steep_rock),
           ("flowing water y72", lambda d: d.get("water_flowing_y72", 0)),
           ("surface water cols", lambda d: d.get("high_water_columns", 0)),
           ("lava y64", lambda d: d.get("lava_y64", 0)),
           ("packed ice y80", lambda d: d.get("packed_ice_y80", 0)),
           ("blue ice y80", lambda d: d.get("blue_ice_y80", 0))]
head = f"{'sample':10s} {'metric':20s} " + " ".join(f"{d.name:>12s}" for d in dirs)
print(head)
print("-" * len(head))
for s in samples + ["ALL"]:
    for name, f in metrics:
        vals = []
        for d in dirs:
            if s == "ALL":
                ds = [load(d, x) for x in samples]
                ds = [x for x in ds if x]
                if name.startswith("rock%"):
                    # pool the class counts across samples
                    pooled = {"classes": {}}
                    for x in ds:
                        for c, v in x["classes"].items():
                            pc = pooled["classes"].setdefault(c, {"n": 0})
                            for g, share in v.items():
                                if g != "n":
                                    pc[g] = pc.get(g, 0) + share * v["n"]
                            pc["n"] += v["n"]
                    for c, v in pooled["classes"].items():
                        for g in list(v):
                            if g != "n":
                                v[g] /= v["n"]
                    vals.append(f(pooled))
                else:
                    vals.append(sum(f(x) for x in ds))
            else:
                x = load(d, s)
                vals.append(f(x) if x else float("nan"))
        print(f"{s:10s} {name:20s} " + " ".join(f"{v:12.1f}" if isinstance(v, float) else f"{v:12d}" for v in vals))
    print()
