#!/usr/bin/env python3
"""Before/after preview images for the Stratafall notes.

Usage: previews.py <baseline_world> <pack_world> <out_dir> <spec.json>
spec.json: {"name": {"x": .., "z": .., "size": .., "facing": "north", "scale": 3, "label": "..."}, ...}
Each entry renders face_view.py for both worlds and writes <out_dir>/<name>.png with the two views side by side
(baseline left, Stratafall right) and a caption strip.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

FACE = str(Path(__file__).resolve().parent / "face_view.py")


def render(world, x, z, size, facing, scale, out):
    subprocess.run([sys.executable, "-I", FACE, world, out, str(x), str(z), str(size), "--scale", str(scale),
                    "--facing", facing], check=True, capture_output=True)


def main():
    base, pack, out_dir, spec = sys.argv[1], sys.argv[2], Path(sys.argv[3]), json.loads(Path(sys.argv[4]).read_text())
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, s in spec.items():
            pair = []
            for i, world in enumerate((base, pack) if s.get("compare", True) else (pack,)):
                p = f"{tmp}/{name}-{i}.png"
                render(world, s["x"], s["z"], s["size"], s.get("facing", "north"), s.get("scale", 3), p)
                pair.append(Image.open(p))
            w = sum(im.width for im in pair) + 10 * (len(pair) - 1)
            h = max(im.height for im in pair) + 26
            img = Image.new("RGB", (w, h), (255, 255, 255))
            x = 0
            for im in pair:
                img.paste(im, (x, 0))
                x += im.width + 10
            d = ImageDraw.Draw(img)
            labels = ["without Stratafall", "with Stratafall"] if len(pair) == 2 else ["with Stratafall"]
            x = 0
            for im, lab in zip(pair, labels):
                d.text((x + 4, h - 22), lab, fill=(0, 0, 0))
                x += im.width + 10
            d.text((4, h - 11), s.get("label", "")[:160], fill=(60, 60, 60))
            img.save(out_dir / f"{name}.png")
            print(f"{out_dir / (name + '.png')}: {img.size}")


if __name__ == "__main__":
    main()
