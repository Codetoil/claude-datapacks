#!/usr/bin/env python3
"""Send a chat message to players on the running server over RCON, shown as coming from Claude.

Usage: say.py <server.properties> <message> [--to PLAYER]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pregen import Rcon, props  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("properties")
ap.add_argument("message")
ap.add_argument("--to", default="@a")
args = ap.parse_args()

p = props(args.properties)
r = Rcon("127.0.0.1", int(p["rcon.port"]), p["rcon.password"])
component = [{"text": "[Claude] ", "color": "aqua"}, {"text": args.message, "color": "white"}]
out = r.cmd(f"tellraw {args.to} {json.dumps(component)}")
if out:
    print(out)
