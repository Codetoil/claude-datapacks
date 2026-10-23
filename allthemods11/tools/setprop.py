#!/usr/bin/env python3
"""Set key=value pairs in a server.properties file in place (only while the server is stopped).

Usage: setprop.py <server.properties> key=value [key=value ...]
"""
import sys

if len(sys.argv) < 3:
    sys.exit(__doc__.strip())
path, pairs = sys.argv[1], dict(a.split("=", 1) for a in sys.argv[2:])


def shown(k, v):
    return "<hidden>" if v and ("password" in k or "secret" in k) else repr(v)


lines = open(path, encoding="utf-8").read().splitlines()
seen = set()
for i, line in enumerate(lines):
    if line and not line.startswith("#") and "=" in line:
        k = line.split("=", 1)[0]
        if k in pairs:
            print(f"{k}: {shown(k, line.split('=', 1)[1])} -> {shown(k, pairs[k])}")
            lines[i] = f"{k}={pairs[k]}"
            seen.add(k)
for k in pairs.keys() - seen:
    sys.exit(f"{k} not found in {path}")
with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
