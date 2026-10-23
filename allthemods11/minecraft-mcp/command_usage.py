#!/usr/bin/env python3
"""Print the usage of every command (or the ones named) from a commands.json data report.

Usage: command_usage.py <commands.json> [command ...] [--max-per-command N]

Each executable path through the command tree becomes one line: literals as-is, arguments as
<name:parser>. Redirects (e.g. execute's subcommands) end in "-> <target> ...".
"""
import argparse
import json


def paths(node, prefix, out, limit, depth=0):
    if len(out) >= limit or depth > 40:
        return
    if node.get("executable"):
        out.append(" ".join(prefix))
    if "redirect" in node:
        out.append(" ".join(prefix + ["->", " ".join(node["redirect"]) or "<any command>"]))
        return
    for name, child in node.get("children", {}).items():
        if child["type"] == "literal":
            token = name
        else:
            parser = child.get("parser", "?").removeprefix("minecraft:").removeprefix("brigadier:")
            token = f"<{name}:{parser}>"
        paths(child, prefix + [token], out, limit, depth + 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report")
    ap.add_argument("commands", nargs="*")
    ap.add_argument("--max-per-command", type=int, default=40)
    args = ap.parse_args()
    root = json.load(open(args.report, encoding="utf-8"))
    names = args.commands or sorted(root["children"])
    for name in names:
        out = []
        paths(root["children"][name], [name], out, args.max_per_command)
        more = " (truncated)" if len(out) >= args.max_per_command else ""
        print(f"## {name}{more}")
        for line in out:
            print(f"  {line}")


if __name__ == "__main__":
    main()
