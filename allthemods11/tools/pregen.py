#!/usr/bin/env python3
"""Pre-generate a square of chunks on a running server over RCON.

Usage: pregen.py <server.properties> <center_x> <center_z> <radius_blocks> [--dimension minecraft:overworld]
       [--method neoforge|forceload]

--method neoforge (default): NeoForge's own generator, `/neoforge generate start` (a square
2*ceil(radius/16)+1 chunks on a side, e.g. 9x9 for radius 64), polled with `/neoforge generate status`
until it's done. Works while the server is paused (tested 2026-10-23: 81 chunks in ~8 s).
--method forceload: works on any server. 16x16-chunk batches (the /forceload limit is 256
chunks per command), a few in flight; each is released once every chunk in it reports loaded
(`execute if loaded` = entity-ticking), so the server saves and unloads it. Needs a ticking server:
with nobody online the server pauses after pause-when-empty-seconds (60 here) and forceloaded
chunks never become entity-ticking, so every batch times out.
Both end with save-all.
"""
import argparse
import re
import socket
import struct
import sys
import time


class Rcon:
    def __init__(self, host, port, password):
        self.s = socket.create_connection((host, port), timeout=30)
        self.rid = 0
        if self.cmd(password, kind=3) is None:
            raise SystemExit("RCON auth failed")

    def _recv(self):
        n = struct.unpack("<i", self._exact(4))[0]
        data = self._exact(n)
        rid, _ = struct.unpack("<ii", data[:8])
        return rid, data[8:-2].decode("utf-8", "replace")

    def _exact(self, n):
        b = b""
        while len(b) < n:
            chunk = self.s.recv(n - len(b))
            if not chunk:
                raise ConnectionError("RCON closed")
            b += chunk
        return b

    def cmd(self, text, kind=2):
        self.rid += 1
        payload = struct.pack("<ii", self.rid, kind) + text.encode() + b"\x00\x00"
        self.s.sendall(struct.pack("<i", len(payload)) + payload)
        rid, body = self._recv()
        return None if rid == -1 else body


def props(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def generate_neoforge(r, args):
    radius_chunks = -(-args.radius // 16)
    resp = r.cmd(f"execute in {args.dimension} run neoforge generate start {args.cx} 0 {args.cz} {radius_chunks} false")
    print(resp, flush=True)
    if not resp.startswith("Generating"):
        raise SystemExit("generation didn't start (one may already be running: neoforge generate stop)")
    start = time.time()
    while True:
        time.sleep(args.poll)
        status = r.cmd("neoforge generate status")
        m = re.search(r"(\d+) out of (\d+) chunks", status)
        if not m:  # "No pregeneration currently running": done (errors, if any, are in the server log)
            break
        done, el = int(m[1]), time.time() - start
        print(f"{done}/{m[2]} chunks, {done / el:.0f} chunks/s, {el:.0f}s", flush=True)


def generate_forceload(r, args):
    ex = f"execute in {args.dimension} run "

    c0x, c1x = (args.cx - args.radius) >> 4, (args.cx + args.radius - 1) >> 4
    c0z, c1z = (args.cz - args.radius) >> 4, (args.cz + args.radius - 1) >> 4
    batches = [(bx, bz, min(bx + 15, c1x), min(bz + 15, c1z))
               for bz in range(c0z, c1z + 1, 16) for bx in range(c0x, c1x + 1, 16)]
    total = sum((b[2] - b[0] + 1) * (b[3] - b[1] + 1) for b in batches)
    print(f"{total} chunks in {len(batches)} batches", flush=True)

    start = time.time()
    done = 0
    pending = list(batches)
    active = []  # (batch, remaining chunk set, started)
    while pending or active:
        while pending and len(active) < args.in_flight:
            b = pending.pop(0)
            resp = r.cmd(ex + f"forceload add {b[0] * 16} {b[1] * 16} {b[2] * 16} {b[3] * 16}")
            if "Marked" not in resp and "already" not in resp:
                print(f"forceload add failed: {resp}", file=sys.stderr)
            chunks = {(x, z) for x in range(b[0], b[2] + 1) for z in range(b[1], b[3] + 1)}
            active.append((b, chunks, time.time()))
        time.sleep(0.5)
        for entry in list(active):
            b, remaining, t0 = entry
            for c in list(remaining):
                if "passed" in r.cmd(ex.replace(" run ", "") + f" if loaded {c[0] * 16} 0 {c[1] * 16}"):
                    remaining.discard(c)
            if not remaining or time.time() - t0 > args.timeout:
                if remaining:
                    print(f"batch {b}: {len(remaining)} chunks timed out (is the server paused because it's empty?"
                          " use --method neoforge or have a player online)", file=sys.stderr)
                r.cmd(ex + f"forceload remove {b[0] * 16} {b[1] * 16} {b[2] * 16} {b[3] * 16}")
                n = (b[2] - b[0] + 1) * (b[3] - b[1] + 1)
                done += n
                active.remove(entry)
                el = time.time() - start
                print(f"{done}/{total} chunks, {done / el:.0f} chunks/s, {el:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("properties")
    ap.add_argument("cx", type=int)
    ap.add_argument("cz", type=int)
    ap.add_argument("radius", type=int)
    ap.add_argument("--dimension", default="minecraft:overworld")
    ap.add_argument("--method", choices=("neoforge", "forceload"), default="neoforge")
    ap.add_argument("--poll", type=float, default=5, help="neoforge: seconds between status checks")
    ap.add_argument("--in-flight", type=int, default=4, help="forceload: batches at a time")
    ap.add_argument("--timeout", type=float, default=600, help="forceload: seconds per batch")
    args = ap.parse_args()

    p = props(args.properties)
    r = Rcon("127.0.0.1", int(p["rcon.port"]), p["rcon.password"])
    (generate_neoforge if args.method == "neoforge" else generate_forceload)(r, args)
    # Plain save-all: "flush" blocks the server thread on disk IO and can trip the watchdog.
    print(r.cmd("save-all"), flush=True)


if __name__ == "__main__":
    main()
