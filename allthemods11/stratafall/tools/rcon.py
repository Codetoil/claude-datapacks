"""Minimal RCON client for the local ATM11 server. Reads port and password from server.properties (never prints them).

Usage: rcon.py <server.properties> "<command>" ["<command>" ...]
"""
import socket
import struct
import sys


def props(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def packet(req_id, kind, body):
    payload = struct.pack("<ii", req_id, kind) + body.encode("utf-8") + b"\x00\x00"
    return struct.pack("<i", len(payload)) + payload


def read_packet(sock):
    def exact(n):
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("RCON connection closed")
            buf += chunk
        return buf
    length = struct.unpack("<i", exact(4))[0]
    data = exact(length)
    req_id, kind = struct.unpack("<ii", data[:8])
    return req_id, kind, data[8:-2].decode("utf-8", "replace")


def run(prop_path, commands, timeout=600):
    p = props(prop_path)
    with socket.create_connection(("127.0.0.1", int(p.get("rcon.port", "25575"))), timeout=timeout) as s:
        s.sendall(packet(1, 3, p["rcon.password"]))
        req_id, _, _ = read_packet(s)
        if req_id == -1:
            raise PermissionError("RCON login failed")
        results = []
        for i, cmd in enumerate(commands, start=2):
            s.sendall(packet(i, 2, cmd))
            _, _, body = read_packet(s)
            results.append(body)
        return results


if __name__ == "__main__":
    for cmd, out in zip(sys.argv[2:], run(sys.argv[1], sys.argv[2:])):
        print(f"> {cmd}\n{out}")
