#!/usr/bin/env python3
"""MCP server (stdio, standard library only) that lets Claude talk to a vanilla Minecraft server.

Tools: read and wait for in-game chat (from logs/latest.log), send chat as [Claude], run console
commands over RCON, and call the Server Management Protocol (JSON-RPC over TLS WebSocket).
Connection details are read from the server's server.properties on every call, so password or
port changes are picked up without a restart.

Usage: server.py --server-dir /path/to/minecraft/server
"""
import argparse
import base64
import json
import os
import re
import socket
import ssl
import struct
import sys
import time
from pathlib import Path

PROTOCOL_VERSION = "2025-06-18"
CHAT_RE = re.compile(r"^\[(\d\d:\d\d:\d\d)\] \[[^\]]+/INFO\]: (?:<([^>]+)> (.*)|(?:System chat: )?(\S+) (joined|left) the game)$")
ADVANCEMENT_RE = re.compile(r"^\[(\d\d:\d\d:\d\d)\] \[[^\]]+/INFO\]: (?:System chat: )?(\S+) has (?:made the advancement|completed the challenge|reached the goal) \[(.+)\]$")
# Other broadcasts that start with a player's name: death messages ("X was slain by Zombie", "X fell ...").
SYSTEM_RE = re.compile(r"^\[(\d\d:\d\d:\d\d)\] \[Server thread/INFO\]: System chat: (\S+) (.+)$")
SERVER_DIR = None


# --- server.properties / RCON / management --------------------------------------------------

def props():
    out = {}
    for line in (SERVER_DIR / "server.properties").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def rcon(command):
    p = props()
    if p.get("enable-rcon") != "true" or not p.get("rcon.password"):
        raise RuntimeError("RCON is not enabled in server.properties")
    with socket.create_connection(("127.0.0.1", int(p.get("rcon.port", 25575))), timeout=30) as s:
        def send(rid, kind, body):
            payload = struct.pack("<ii", rid, kind) + body.encode("utf-8") + b"\x00\x00"
            s.sendall(struct.pack("<i", len(payload)) + payload)

        def exact(n):
            b = b""
            while len(b) < n:
                chunk = s.recv(n - len(b))
                if not chunk:
                    raise ConnectionError("RCON connection closed")
                b += chunk
            return b

        def recv():
            n = struct.unpack("<i", exact(4))[0]
            data = exact(n)
            return struct.unpack("<i", data[:4])[0], data[8:-2].decode("utf-8", "replace")

        send(1, 3, p["rcon.password"])
        if recv()[0] == -1:
            raise RuntimeError("RCON authentication failed")
        send(2, 2, command)
        return recv()[1]


def management(method, params=None):
    p = props()
    if p.get("management-server-enabled") != "true":
        raise RuntimeError("the management server is not enabled in server.properties")
    host, port = p.get("management-server-host", "localhost"), int(p["management-server-port"])
    raw = socket.create_connection((host, port), timeout=30)
    if p.get("management-server-tls-enabled", "true") == "true":
        cert = SERVER_DIR / "management-cert.pem"
        ctx = ssl.create_default_context(cafile=str(cert)) if cert.exists() else ssl._create_unverified_context()
        s = ctx.wrap_socket(raw, server_hostname=host)
    else:
        s = raw
    with s:
        key = base64.b64encode(os.urandom(16)).decode()
        s.sendall((f"GET / HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                   f"Authorization: Bearer {p['management-server-secret']}\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            c = s.recv(1)
            if not c:
                raise ConnectionError("management server closed the connection")
            head += c
        status = head.split(b"\r\n")[0].decode()
        if " 101 " not in status:
            raise RuntimeError(f"management handshake failed: {status}")

        def exact(n):
            b = b""
            while len(b) < n:
                chunk = s.recv(n - len(b))
                if not chunk:
                    raise ConnectionError("management connection closed")
                b += chunk
            return b

        req = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            req["params"] = params
        data = json.dumps(req).encode()
        mask = os.urandom(4)
        if len(data) < 126:
            hdr = bytes([0x81, 0x80 | len(data)])
        elif len(data) < 65536:
            hdr = bytes([0x81, 0x80 | 126]) + struct.pack(">H", len(data))
        else:
            hdr = bytes([0x81, 0x80 | 127]) + struct.pack(">Q", len(data))
        s.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
        while True:  # skip server notifications until our reply arrives
            _, b1 = exact(2)
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", exact(8))[0]
            msg = json.loads(exact(n))
            if msg.get("id") == 1:
                if "error" in msg:
                    raise RuntimeError(json.dumps(msg["error"]))
                return msg.get("result")


# --- chat log -------------------------------------------------------------------------------

def log_path():
    return SERVER_DIR / "logs" / "latest.log"


def cursor_now():
    st = log_path().stat()
    return f"{st.st_ino}:{st.st_size}"


def known_players():
    names = set()
    for f in ("whitelist.json", "ops.json", "usercache.json"):
        try:
            names.update(e["name"] for e in json.loads((SERVER_DIR / f).read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return names


def parse_events(lines):
    events = []
    players = None
    for line in lines:
        line = line.rstrip("\n")
        m = CHAT_RE.match(line)
        if m:
            t, player, text, who, what = m.groups()
            if player is not None:
                events.append({"time": t, "player": player, "message": text})
            else:
                events.append({"time": t, "player": who, "event": what})
            continue
        m = ADVANCEMENT_RE.match(line)
        if m:
            events.append({"time": m[1], "player": m[2], "event": "advancement", "advancement": m[3]})
            continue
        m = SYSTEM_RE.match(line)
        if m:
            if players is None:
                players = known_players()
            if m[2] in players:  # e.g. a death message
                events.append({"time": m[1], "player": m[2], "event": "other", "text": f"{m[2]} {m[3]}"})
    return events


def describe(e):
    if "message" in e:
        return f"<{e['player']}> {e['message']}"
    if e["event"] == "advancement":
        return f"{e['player']} got advancement [{e['advancement']}]"
    if e["event"] == "other":
        return e["text"]
    return f"{e['player']} {e['event']} the game"


def read_since(cursor):
    """Return (events, new_cursor) for log lines after `cursor` ("inode:offset")."""
    path = log_path()
    st = path.stat()
    start = 0
    if cursor:
        ino, off = (int(x) for x in cursor.split(":"))
        if ino == st.st_ino and off <= st.st_size:
            start = off
    with open(path, "rb") as f:
        f.seek(start)
        data = f.read()
    end = start + len(data)
    if not data.endswith(b"\n"):  # leave a partly written line for next time
        cut = data.rfind(b"\n") + 1
        end = start + cut
        data = data[:cut]
    return parse_events(data.decode("utf-8", "replace").splitlines()), f"{st.st_ino}:{end}"


# --- tools ----------------------------------------------------------------------------------

def tool_chat_read(args):
    limit = int(args.get("limit", 30))
    if args.get("cursor"):
        events, cur = read_since(args["cursor"])
    else:
        events = parse_events(log_path().read_text(encoding="utf-8", errors="replace").splitlines())
        cur = cursor_now()
    return {"events": events[-limit:], "cursor": cur,
            "note": "Pass cursor to minecraft_chat_read or minecraft_chat_wait to get only newer events."}


def tool_chat_wait(args):
    timeout = max(1, min(int(args.get("timeout_seconds", 120)), 600))
    cur = args.get("cursor") or cursor_now()
    deadline = time.time() + timeout
    while True:
        events, cur = read_since(cur)
        wanted = [e for e in events if "message" in e] if args.get("messages_only", True) else events
        if wanted or time.time() >= deadline:
            return {"events": wanted, "cursor": cur, "timed_out": not wanted}
        time.sleep(0.5)


def tool_chat_send(args):
    msg = str(args["message"])
    target = args.get("player") or "@a"
    if not re.fullmatch(r"@a|[A-Za-z0-9_]{1,16}", target):
        raise ValueError("player must be a player name or @a")
    component = [{"text": "[Claude] ", "color": "aqua"}, {"text": msg, "color": "white"}]
    out = rcon(f"tellraw {target} {json.dumps(component)}")
    return {"sent_to": target, "server_reply": out}


# Server administration, kept behind the *_admin_* tools so it can stay on "ask" while everyday
# commands are auto-approved. Gameplay commands (fill, kill, gamerule, ...) are not on the list.
ADMIN_COMMANDS = {"stop", "op", "deop", "ban", "ban-ip", "pardon", "pardon-ip", "whitelist",
                  "save-off", "transfer", "kick", "setidletimeout"}
ADMIN_READ_ONLY = {("whitelist", "list")}
ADMIN_RPC_PREFIXES = ("minecraft:operators/", "minecraft:allowlist/", "minecraft:bans/", "minecraft:ip_bans/")
ADMIN_RPC_METHODS = {
    "minecraft:server/stop", "minecraft:players/kick",
    "minecraft:serversettings/use_allowlist/set", "minecraft:serversettings/enforce_allowlist/set",
    "minecraft:serversettings/autosave/set", "minecraft:serversettings/operator_user_permission_level/set",
    "minecraft:serversettings/accept_transfers/set", "minecraft:serversettings/player_idle_timeout/set",
}


def admin_command_in(cmd):
    """Return the admin command `cmd` would run (also via `execute ... run` / `return run`), or None."""
    tokens = cmd.lower().split()
    starts = [0] + [i + 1 for i, t in enumerate(tokens) if t == "run"]
    for i in starts:
        if i >= len(tokens):
            continue
        name = tokens[i].lstrip("/").removeprefix("minecraft:")
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if name in ADMIN_COMMANDS and (name, nxt) not in ADMIN_READ_ONLY:
            return name
    return None


def is_admin_rpc(method):
    m = method.strip().lower()
    return m in ADMIN_RPC_METHODS or m.startswith(ADMIN_RPC_PREFIXES)


def clean_command(args):
    cmd = str(args["command"]).strip().lstrip("/")
    if "\n" in cmd or "\r" in cmd:
        raise ValueError("one command at a time")
    return cmd


def tool_command(args):
    cmd = clean_command(args)
    admin = admin_command_in(cmd)
    if admin:
        raise PermissionError(f"'{admin}' is a server-admin command; use minecraft_admin_command, which asks the user first.")
    return {"command": cmd, "output": rcon(cmd)}


def tool_admin_command(args):
    cmd = clean_command(args)
    return {"command": cmd, "output": rcon(cmd)}


def tool_rpc(args):
    if is_admin_rpc(args["method"]):
        raise PermissionError(f"'{args['method']}' changes operators, the allowlist, bans or server state; use minecraft_admin_rpc, which asks the user first.")
    return {"method": args["method"], "result": management(args["method"], args.get("params"))}


def tool_admin_rpc(args):
    return {"method": args["method"], "result": management(args["method"], args.get("params"))}


def tool_status(args):
    p = props()
    out = {"level_name": p.get("level-name")}
    try:
        out["status"] = management("minecraft:server/status")
    except Exception as e:  # management server off or unreachable: fall back to RCON
        out["management_error"] = str(e)
        out["list"] = rcon("list")
    return out


TOOLS = {
    "minecraft_chat_read": (tool_chat_read, "Read recent in-game chat messages plus join/leave, advancement and death events from the server log (newest last). Returns a cursor for fetching only newer events later.", {
        "type": "object", "properties": {
            "limit": {"type": "integer", "description": "Max events to return (default 30)."},
            "cursor": {"type": "string", "description": "Cursor from a previous call; only events after it are returned."}}}),
    "minecraft_chat_wait": (tool_chat_wait, "Block until a player says something in chat (or until the timeout), then return the new messages. Use to listen for a reply.", {
        "type": "object", "properties": {
            "cursor": {"type": "string", "description": "Cursor from a previous read/wait; default is 'from now'."},
            "timeout_seconds": {"type": "integer", "description": "1-600, default 120."},
            "messages_only": {"type": "boolean", "description": "Ignore joins/leaves (default true)."}}}),
    "minecraft_chat_send": (tool_chat_send, "Send a chat message in-game, shown to players as '[Claude] <message>'.", {
        "type": "object", "required": ["message"], "properties": {
            "message": {"type": "string"},
            "player": {"type": "string", "description": "Send privately to this player name; default everyone (@a)."}}}),
    "minecraft_command": (tool_command, "Run an everyday server console command over RCON and return its output, e.g. 'list', 'time set day', 'tp Codetoil 0 100 0', 'gamerule ...'. Refuses server-admin commands (stop, op, deop, ban, ban-ip, pardon, pardon-ip, whitelist changes, save-off, transfer, kick, setidletimeout), including inside 'execute ... run'; use minecraft_admin_command for those.", {
        "type": "object", "required": ["command"], "properties": {
            "command": {"type": "string", "description": "Command without the leading slash."}}}),
    "minecraft_admin_command": (tool_admin_command, "Run any server console command over RCON, including server-admin ones (stop, op, ban, whitelist, save-off, transfer, kick, ...). The user approves each call.", {
        "type": "object", "required": ["command"], "properties": {
            "command": {"type": "string", "description": "Command without the leading slash."}}}),
    "minecraft_rpc": (tool_rpc, "Call a Minecraft Server Management Protocol method, e.g. 'minecraft:players', 'minecraft:serversettings/difficulty/set' with params ['normal'], or 'rpc.discover' to list all methods. Refuses methods that change operators, the allowlist, bans, kick players, stop the server or turn off autosave; use minecraft_admin_rpc for those.", {
        "type": "object", "required": ["method"], "properties": {
            "method": {"type": "string"},
            "params": {"description": "JSON-RPC params (array or object), if the method takes any."}}}),
    "minecraft_admin_rpc": (tool_admin_rpc, "Call any Management Protocol method, including ones that change operators, the allowlist or bans, kick players or stop the server. The user approves each call.", {
        "type": "object", "required": ["method"], "properties": {
            "method": {"type": "string"},
            "params": {"description": "JSON-RPC params (array or object), if the method takes any."}}}),
    "minecraft_status": (tool_status, "Get the server's status: running world, version and online players.", {
        "type": "object", "properties": {}}),
}


# --- MCP stdio loop -------------------------------------------------------------------------

def reply(msg_id, result=None, error=None):
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


def handle(req):
    method, msg_id = req.get("method"), req.get("id")
    if msg_id is None:  # notification
        return
    if method == "initialize":
        version = req.get("params", {}).get("protocolVersion") or PROTOCOL_VERSION
        reply(msg_id, {"protocolVersion": version, "capabilities": {"tools": {}},
                       "serverInfo": {"name": "minecraft", "version": "1.0.0"},
                       "instructions": "Tools for the local Minecraft server: chat with players in-game, run console commands, and query the Server Management Protocol."})
    elif method == "ping":
        reply(msg_id, {})
    elif method == "tools/list":
        reply(msg_id, {"tools": [{"name": n, "description": d, "inputSchema": s} for n, (_, d, s) in TOOLS.items()]})
    elif method == "tools/call":
        params = req.get("params", {})
        name = params.get("name")
        if name not in TOOLS:
            reply(msg_id, error={"code": -32602, "message": f"unknown tool {name}"})
            return
        try:
            result = TOOLS[name][0](params.get("arguments") or {})
            reply(msg_id, {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
        except Exception as e:
            reply(msg_id, {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True})
    else:
        reply(msg_id, error={"code": -32601, "message": f"method not found: {method}"})


def main():
    global SERVER_DIR
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server-dir", type=Path, default=Path(os.environ.get("MINECRAFT_SERVER_DIR", ".")))
    ap.add_argument("--watch", action="store_true",
                    help="instead of serving MCP, print each new chat/join/leave event as a line (for a log monitor)")
    args = ap.parse_args()
    SERVER_DIR = args.server_dir.resolve()
    if args.watch:
        cur = cursor_now()
        while True:
            try:
                events, cur = read_since(cur)
            except FileNotFoundError:  # log is being rotated by a restart
                events = []
            for e in events:
                print(f"[{e['time']}] {describe(e)}", flush=True)
            time.sleep(0.5)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            reply(None, error={"code": -32700, "message": "parse error"})
            continue
        handle(req)


if __name__ == "__main__":
    main()
