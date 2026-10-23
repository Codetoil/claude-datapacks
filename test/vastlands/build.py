#!/usr/bin/env python3
"""Build the Vastlands worldgen datapack from the vanilla data inside the 26.3 server jar.

Every overridden vanilla file is read from the jar and patched, so the pack never carries a
hand-copied (and possibly stale) vanilla file. Tune the terrain with PARAMS below.

Usage: python3 build.py [--jar PATH] [--out DIR]
"""
import argparse
import copy
import json
import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_JAR = HERE.parent / "versions" / "26.3" / "server-26.3.jar"
PACK_FORMAT = 121  # data_major from the jar's version.json

PARAMS = {
    # World: vanilla is min_y -64, height 384 (top block y=319).
    "min_y": -64,
    "height": 512,  # top block y=447
    # Terrain is faded out between these heights (vanilla 240 -> 256).
    "top_slide": (400, 416),
    # Horizontal feature scale: >1 makes features that many times larger (vanilla 1.0).
    "continent_scale": 1.6,
    "erosion_scale": 1.4,
    "ridge_scale": 1.1,
    "climate_scale": 1.4,  # temperature + vegetation, i.e. biome size
    # Shifts added to the climate noises (which drive both terrain and biome choice, so the two
    # stay consistent). Negative erosion = more mountain ranges; positive continents = more land.
    "erosion_bias": -0.1,
    "continent_bias": 0.05,
    # Offset shaping. h = vanilla offset + 0.50375 is ~0 at sea level and the surface sits at
    # roughly y = 63.5 + 128 h. Land above h = land_threshold is raised by land_gain * excess;
    # sea floor (h < 0) is lowered by sea_gain * h, fading in from the coast to the deep ocean
    # (continentalness sea_fade[0] -> sea_fade[1]) so rivers and inland lakes keep vanilla depth.
    "land_threshold": 0.08,
    "land_gain": 1.0,
    "sea_gain": 0.9,
    "sea_fade": (-0.11, -0.45),
    # Multiplier on vanilla peak jaggedness.
    "jaggedness_gain": 1.5,
    # Extra water springs on cliff faces of mountain biomes (attempts per chunk).
    "cliff_springs_per_chunk": 24,
    "cliff_springs_y": (96, 416),
}

CLIFF_SPRING_BIOMES = [
    "jagged_peaks", "frozen_peaks", "stony_peaks", "snowy_slopes", "grove", "meadow",
    "cherry_grove", "windswept_hills", "windswept_gravelly_hills", "windswept_forest",
    "windswept_savanna",
]
FLUID_SPRINGS_STEP = 8  # index of the fluid_springs decoration step in a biome's feature list
OFFSET_SEA_LEVEL = 0.50375  # vanilla adds -0.50375 to the offset spline


def gradient_retarget(node, old_range, new_range):
    """Re-point every y gradient spanning old_range to new_range, keeping its slope."""
    if isinstance(node, dict):
        if (node.get("type") == "minecraft:gradient" and node.get("axis") == "y"
                and (node["from_coordinate"], node["to_coordinate"]) == old_range):
            f0, t0 = old_range
            f1, t1 = new_range
            slope = (node["to_value"] - node["from_value"]) / (t0 - f0)
            node["from_value"] = node["from_value"] + slope * (f1 - f0)
            node["to_value"] = node["from_value"] + slope * (t1 - f1)
            node["from_coordinate"], node["to_coordinate"] = f1, t1
        for v in node.values():
            gradient_retarget(v, old_range, new_range)
    elif isinstance(node, list):
        for v in node:
            gradient_retarget(v, old_range, new_range)


def slide_retarget(node, old_range, new_range):
    """Move a 1 -> 0 (or 0 -> 1) fade gradient to new coordinates without rescaling its values."""
    if isinstance(node, dict):
        if (node.get("type") == "minecraft:gradient" and node.get("axis") == "y"
                and (node["from_coordinate"], node["to_coordinate"]) == old_range):
            node["from_coordinate"], node["to_coordinate"] = new_range
        for v in node.values():
            slide_retarget(v, old_range, new_range)
    elif isinstance(node, list):
        for v in node:
            slide_retarget(v, old_range, new_range)


def replace_clamp_max(node, old, new):
    if isinstance(node, dict):
        if node.get("type") == "minecraft:clamp" and node.get("max") == old:
            node["max"] = new
        for v in node.values():
            replace_clamp_max(v, old, new)
    elif isinstance(node, list):
        for v in node:
            replace_clamp_max(v, old, new)


def add(a, b):
    return {"type": "minecraft:add", "left": a, "right": b}


def mul(a, b):
    return {"type": "minecraft:mul", "left": a, "right": b}


def build(jar_path, out):
    p = PARAMS
    top = p["min_y"] + p["height"]  # first y above the build limit
    vanilla_top = 320
    jar = zipfile.ZipFile(jar_path)

    def vanilla(path):
        return json.loads(jar.read(f"data/minecraft/{path}.json"))

    files = {}

    def put(path, obj):
        files[path] = obj

    put("pack.mcmeta", {"pack": {
        "description": "Vastlands: bigger continents, towering mountains, deeper seas",
        "min_format": PACK_FORMAT, "max_format": PACK_FORMAT,
    }})

    # Taller overworld.
    dim = vanilla("dimension_type/overworld")
    dim["min_y"], dim["height"], dim["logical_height"] = p["min_y"], p["height"], p["height"]
    put("data/minecraft/dimension_type/overworld.json", dim)

    settings = vanilla("worldgen/noise_settings/overworld")
    settings["noise"]["min_y"], settings["noise"]["height"] = p["min_y"], p["height"]
    put("data/minecraft/worldgen/noise_settings/overworld.json", settings)

    df = "worldgen/density_function/overworld"

    # Depth keeps its vanilla slope but now runs to the new top, so biome depth is unchanged.
    depth = vanilla(f"{df}/depth")
    gradient_retarget(depth, (-64, vanilla_top), (p["min_y"], top))
    put(f"data/minecraft/{df}/depth.json", depth)

    final = vanilla(f"{df}/final_density")
    slide_retarget(final, (240, 256), p["top_slide"])
    put(f"data/minecraft/{df}/final_density.json", final)

    psl = vanilla(f"{df}/preliminary_surface_level")
    gradient_retarget(psl, (-64, vanilla_top), (p["min_y"], top))
    slide_retarget(psl, (240, 256), p["top_slide"])
    replace_clamp_max(psl, float(vanilla_top), float(top))
    put(f"data/minecraft/{df}/preliminary_surface_level.json", psl)

    # Larger horizontal features: lower the noise frequency.
    for name, key in [("continents", "continent_scale"), ("erosion", "erosion_scale"),
                      ("ridges", "ridge_scale"), ("temperature", "climate_scale"),
                      ("vegetation", "climate_scale")]:
        fn = vanilla(f"{df}/{name}")
        noise = fn["input"] if fn["type"] == "minecraft:cache" else fn
        noise["xz_scale"] = noise["xz_scale"] / p[key]
        bias = p.get(name.rstrip("s") + "_bias", 0.0)  # continent_bias, erosion_bias
        if bias:
            biased = add(noise, bias)
            fn = {"type": "minecraft:cache", "input": biased} if fn["type"] == "minecraft:cache" else biased
        put(f"data/minecraft/{df}/{name}.json", fn)

    # Offset: vanilla shape, with land raised and sea floor lowered.
    put("data/vastlands/worldgen/density_function/vanilla_offset.json", vanilla(f"{df}/offset"))
    v = "vastlands:vanilla_offset"
    h = add(v, OFFSET_SEA_LEVEL)
    land = mul(p["land_gain"], {"type": "minecraft:max", "left": add(h, -p["land_threshold"]), "right": 0.0})
    c0, c1 = p["sea_fade"]
    oceanness = {"type": "minecraft:clamp", "min": 0.0, "max": 1.0,
                 "input": mul(add("minecraft:overworld/continents", -c0), -1.0 / (c0 - c1))}
    sea = mul(mul(p["sea_gain"], oceanness), {"type": "minecraft:min", "left": h, "right": 0.0})
    put(f"data/minecraft/{df}/offset.json", {"type": "minecraft:cache", "input": add(v, add(land, sea))})

    put("data/vastlands/worldgen/density_function/vanilla_jaggedness.json", vanilla(f"{df}/jaggedness"))
    put(f"data/minecraft/{df}/jaggedness.json",
        {"type": "minecraft:cache", "input": mul(p["jaggedness_gain"], "vastlands:vanilla_jaggedness")})

    # Features spread uniformly up to the top of the world (e.g. upper coal from y=136 to the top)
    # would get thinner per block in a taller world. Scale their attempt counts by how much their
    # height range grew, so density in the vanilla range stays the same.
    overworld_features = set()
    for name in jar.namelist():
        if name.startswith("data/minecraft/worldgen/biome/") and name.endswith(".json"):
            b = json.loads(jar.read(name))
            if any(c in b.get("carvers", []) for c in ("minecraft:cave", "minecraft:canyon")) or "ocean" in name or "river" in name:
                overworld_features.update(f for step in b.get("features", []) for f in step)

    def resolve(anchor, bottom, top_y):
        (kind, v), = anchor.items()
        return {"absolute": v, "above_bottom": bottom + v, "below_top": top_y - v}[kind]

    for fid in sorted(overworld_features):
        pf = vanilla(f"worldgen/placed_feature/{fid.split(':', 1)[1]}")
        hr = next((s["height"] for s in pf["placement"] if s["type"] == "minecraft:height_range"), None)
        if not hr or hr["type"] != "minecraft:uniform" or "below_top" not in json.dumps(hr):
            continue
        old_span = resolve(hr["max_inclusive"], -64, vanilla_top - 1) - resolve(hr["min_inclusive"], -64, vanilla_top - 1) + 1
        new_span = resolve(hr["max_inclusive"], p["min_y"], top - 1) - resolve(hr["min_inclusive"], p["min_y"], top - 1) + 1
        ratio = new_span / old_span
        for s in pf["placement"]:
            if s["type"] == "minecraft:count" and isinstance(s["count"], int):
                s["count"] = round(s["count"] * ratio)
            elif s["type"] == "minecraft:rarity_filter":
                s["chance"] = max(1, round(s["chance"] / ratio))
        put(f"data/minecraft/worldgen/placed_feature/{fid.split(':', 1)[1]}.json", pf)

    # Waterfalls: extra springs high up, appended last in the fluid_springs step so feature order
    # stays consistent across biomes.
    lo, hi = p["cliff_springs_y"]
    put("data/vastlands/worldgen/placed_feature/cliff_springs.json", {
        "feature": "minecraft:spring_water",
        "placement": [
            {"type": "minecraft:count", "count": p["cliff_springs_per_chunk"]},
            {"type": "minecraft:in_square"},
            {"type": "minecraft:height_range", "height": {
                "type": "minecraft:uniform",
                "min_inclusive": {"absolute": lo}, "max_inclusive": {"absolute": hi}}},
            {"type": "minecraft:biome"},
        ],
    })
    for biome in CLIFF_SPRING_BIOMES:
        b = copy.deepcopy(vanilla(f"worldgen/biome/{biome}"))
        b["features"][FLUID_SPRINGS_STEP].append("vastlands:cliff_springs")
        put(f"data/minecraft/worldgen/biome/{biome}.json", b)

    if out.exists():
        if not (out / "pack.mcmeta").exists():
            raise SystemExit(f"refusing to replace {out}: not a previous build")
        shutil.rmtree(out)
    for rel, obj in files.items():
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    return len(files)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jar", type=Path, default=DEFAULT_JAR)
    ap.add_argument("--out", type=Path, default=HERE / "pack")
    args = ap.parse_args()
    n = build(args.jar, args.out)
    print(f"wrote {n} files to {args.out}")
