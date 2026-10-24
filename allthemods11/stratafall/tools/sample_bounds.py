#!/usr/bin/env python3
"""Print 'name x0 z0 x1 z1' block bounds of each sample area (same square as /neoforge generate makes)."""
import math
from pathlib import Path
for line in open(Path(__file__).resolve().parent / "samples.txt"):
    if not line.strip() or line.startswith("#"):
        continue
    name, cx, cz, r = line.split()
    cx, cz, r = int(cx), int(cz), int(r)
    n = math.ceil(r / 16)
    ccx, ccz = cx // 16, cz // 16
    print(name, (ccx - n) * 16, (ccz - n) * 16, (ccx + n + 1) * 16, (ccz + n + 1) * 16)
