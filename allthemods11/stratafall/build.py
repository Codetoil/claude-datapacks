#!/usr/bin/env python3
"""Build the Stratafall worldgen datapack for All The Mods 11 (Minecraft 26.1.2, NeoForge, data pack format 101).

Stratafall leaves the terrain shape to Tectonic + Terralith + Regions Unexplored and adds what their cliffs lack:
- Rock strata: steep faces (in every direction, unlike vanilla's north/east-only `steep`) become banded rock instead
  of grass, snow or dirt. Each climate has two palettes; a large-scale "province" noise picks one of them, so a
  mountain range keeps one look and the next range may have another.
- Cliff springs: water springs aimed just below the surface, so they open in cliff faces and become waterfalls.

Everything is additive through lithostitched worldgen modifiers (a prepended surface rule and add_features), so no
noise settings, biome or other mod file is replaced. Biome lists are resolved from the pack's generated reports
(reportdump-neo's runDataATM11 output) and written as tags with "required": false entries, so a missing mod only
drops its biomes from the lists.

Usage: python3 build.py [--reports DIR] [--out DIR]
"""
import argparse
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_REPORTS = HERE.parent / "datagen" / "generated" / "reports"
NS = "stratafall"
PACK_FORMAT = 101  # data_major of 26.1.2 (version.json: data_major 101, data_minor 1)

PARAMS = {
    # Steepness tiers: (min height difference between the 4 neighbouring columns, max stone depth painted).
    # A column whose neighbours differ by d blocks exposes a face up to d blocks tall, so the painted depth grows
    # with the tier. The lowest tier sets how steep a slope must be to lose its soil/snow cover.
    "strata_tiers": [(5, 8), (9, 16), (17, 32), (33, 64)],
    # Lower runs first; regions_unexplored's surface rules use the default 1000.
    "strata_priority": 900,
    # Province noise: picks one of the two palettes of a climate. firstOctave -10 => provinces ~1-2 km across.
    "province_noise": {"firstOctave": -10, "amplitudes": [1.0, 1.0]},
    # Cliff springs: attempts per chunk, depth below the surface they aim at, allowed absolute heights.
    "spring_attempts": {"high": 10, "low": 3},
    "spring_depth": (4, 14),
    "spring_y": (72, 400),
}

# Banded palettes (lithostitched bandlands: a 192-entry array filled with `base`, then each band placed `count`
# times with a random `size`; sampled at y + 4 * clay-band offset noise, like vanilla badlands).
PALETTES = {
    "alpine": ("minecraft:stone", [("minecraft:andesite", 9, 2, 6), ("minecraft:tuff", 7, 1, 3),
                                   ("minecraft:calcite", 6, 1, 2), ("minecraft:deepslate", 4, 1, 2)]),
    "slate": ("minecraft:andesite", [("minecraft:stone", 7, 2, 5), ("minecraft:tuff", 6, 1, 3),
                                     ("minecraft:deepslate", 6, 1, 3), ("minecraft:calcite", 3, 1, 1)]),
    "granite": ("minecraft:stone", [("minecraft:granite", 9, 2, 5), ("minecraft:andesite", 6, 1, 4),
                                    ("minecraft:diorite", 4, 1, 2), ("minecraft:dripstone_block", 4, 1, 2)]),
    "chalk": ("minecraft:stone", [("minecraft:calcite", 8, 1, 4), ("minecraft:diorite", 6, 1, 3),
                                  ("minecraft:andesite", 5, 2, 4), ("minecraft:tuff", 4, 1, 2)]),
    "tropical": ("minecraft:stone", [("minecraft:granite", 6, 2, 4), ("minecraft:dripstone_block", 6, 1, 3),
                                     ("minecraft:moss_block", 5, 1, 2), ("minecraft:packed_mud", 3, 1, 2),
                                     ("minecraft:andesite", 4, 1, 3)]),
    "desert": ("minecraft:sandstone", [("minecraft:red_sandstone", 7, 2, 5), ("minecraft:smooth_sandstone", 6, 1, 2),
                                       ("minecraft:orange_terracotta", 5, 1, 3), ("minecraft:terracotta", 6, 1, 3),
                                       ("minecraft:white_terracotta", 3, 1, 1)]),
    "redrock": ("minecraft:terracotta", [("minecraft:orange_terracotta", 8, 2, 4), ("minecraft:red_sandstone", 5, 1, 3),
                                         ("minecraft:brown_terracotta", 4, 1, 2), ("minecraft:white_terracotta", 3, 1, 1),
                                         ("minecraft:granite", 4, 1, 3)]),
}
# climate -> (palette below the province noise threshold, palette above it)
CLIMATES = {"cold": ("alpine", "slate"), "arid": ("desert", "redrock"), "tropical": ("tropical", "tropical"),
            "temperate": ("granite", "chalk")}

# Biomes that keep their own cliffs or are not land.
EXCLUDE_TAGS = ["#c:is_ocean", "#c:is_deep_ocean", "#c:is_shallow_ocean", "#minecraft:is_ocean",
                "#minecraft:is_deep_ocean", "#c:is_river", "#minecraft:is_river", "#c:is_beach", "#minecraft:is_beach",
                "#c:is_cave", "#c:is_underground", "#c:is_badlands", "#minecraft:is_badlands", "#c:is_mushroom",
                "#c:is_void"]
EXCLUDE_IDS = [
    # Terralith biomes with their own cliff or spire surfaces
    "terralith:amethyst_canyon", "terralith:basalt_cliffs", "terralith:bryce_canyon", "terralith:caldera",
    "terralith:desert_canyon", "terralith:desert_spires", "terralith:frozen_cliffs", "terralith:glacial_chasm",
    "terralith:granite_cliffs", "terralith:painted_mountains", "terralith:savanna_badlands",
    "terralith:snowy_badlands", "terralith:stony_spires", "terralith:volcanic_crater", "terralith:volcanic_peaks",
    "terralith:warped_mesa", "terralith:white_cliffs", "terralith:white_mesa", "terralith:windswept_spires",
    "terralith:yellowstone", "terralith:yosemite_cliffs", "terralith:alpha_islands", "terralith:alpha_islands_winter",
    "terralith:mirage_isles", "terralith:red_oasis",
    # Regions Unexplored
    "regions_unexplored:chalk_cliffs", "regions_unexplored:spires", "regions_unexplored:inferno",
    "regions_unexplored:icy_heights",
    # Thaumaturge's special lands, vanilla ice spikes
    "thaumaturge:tainted_lands", "thaumaturge:eerie", "minecraft:ice_spikes",
]
CLIMATE_TAGS = {
    "cold": ["#c:is_snowy", "#c:is_icy", "#c:is_cold/overworld", "#c:is_mountain/peak"],
    "arid": ["#c:is_desert", "#c:is_savanna", "#c:is_sandy", "#c:is_dry/overworld"],
    "tropical": ["#c:is_jungle", "#c:is_tree/jungle", "#c:is_wet/overworld"],
}
HIGH_SPRING_TAGS = ["#c:is_mountain", "#minecraft:is_mountain", "#c:is_hill", "#minecraft:is_hill", "#c:is_plateau",
                    "#c:is_windswept", "#c:is_mountain/slope", "#c:is_mountain/peak"]
HIGH_SPRING_ID_WORDS = {"highlands", "mountain", "mountains", "peaks", "slopes", "cliffs", "heights", "hills", "plateau"}

SPRING_BLOCKS = ["minecraft:stone", "minecraft:granite", "minecraft:diorite", "minecraft:andesite",
                 "minecraft:deepslate", "minecraft:tuff", "minecraft:calcite", "minecraft:dirt", "minecraft:coarse_dirt",
                 "minecraft:grass_block", "minecraft:podzol", "minecraft:snow_block", "minecraft:powder_snow",
                 "minecraft:packed_ice", "minecraft:dripstone_block", "minecraft:moss_block", "minecraft:packed_mud",
                 "minecraft:cobblestone", "minecraft:mossy_cobblestone", "minecraft:cobbled_deepslate",
                 "minecraft:gravel", "minecraft:clay", "minecraft:smooth_basalt"]


def resolve(tags, entries):
    out = set()
    for e in entries:
        out |= set(tags.get(e, [])) if e.startswith("#") else {e}
    return out


def uniform(lo, hi):
    return lo if lo == hi else {"type": "minecraft:uniform", "min_inclusive": lo, "max_inclusive": hi}


def tag_json(biomes):
    vals = [b if b.startswith("minecraft:") else {"id": b, "required": False} for b in sorted(biomes)]
    return {"replace": False, "values": vals}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    ap.add_argument("--out", type=Path, default=HERE / "pack")
    args = ap.parse_args()

    tags = json.loads((args.reports / "data_registries.json").read_text())["minecraft:worldgen/biome"]["tags"]
    overworld = set(tags["#minecraft:is_overworld"])
    excluded = resolve(tags, EXCLUDE_TAGS) | set(EXCLUDE_IDS)
    strata = overworld - excluded
    climate_of = {}
    for b in sorted(strata):
        climate_of[b] = "temperate"
        for climate in ("cold", "arid", "tropical"):
            if b in resolve(tags, CLIMATE_TAGS[climate]):
                climate_of[b] = climate
                break
    high = {b for b in strata if b in resolve(tags, HIGH_SPRING_TAGS)
            or HIGH_SPRING_ID_WORDS & set(b.split(":", 1)[1].split("_"))}
    springs_high = {b for b in high if climate_of[b] != "arid"}
    springs_low = {b for b in strata if b not in high and climate_of[b] != "arid"}

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    files = {}

    def put(rel, obj):
        files[rel] = obj

    put("pack.mcmeta", {"pack": {"description": "Stratafall: rock strata on cliffs and waterfalls for All The Mods 11",
                                 "min_format": PACK_FORMAT, "max_format": PACK_FORMAT}})
    d = f"data/{NS}"
    put(f"{d}/tags/worldgen/biome/strata.json", tag_json(strata))
    for climate in ("cold", "arid", "tropical"):
        put(f"{d}/tags/worldgen/biome/climate/{climate}.json",
            tag_json({b for b, c in climate_of.items() if c == climate}))
    put(f"{d}/tags/worldgen/biome/springs_high.json", tag_json(springs_high))
    put(f"{d}/tags/worldgen/biome/springs_low.json", tag_json(springs_low))
    put(f"{d}/worldgen/noise/province.json", PARAMS["province_noise"])

    for name, (base, bands) in PALETTES.items():
        put(f"{d}/lithostitched/bandlands/{name}.json", {
            "base": {"Name": base},
            "bands": [{"type": "lithostitched:base", "count": count, "size": uniform(lo, hi), "state": {"Name": blk}}
                      for blk, count, lo, hi in bands]})

    def band_rule(palette):
        return {"type": "lithostitched:bandlands", "options": f"{NS}:{palette}"}

    def climate_rule(climate):
        a, b = CLIMATES[climate]
        if a == b:
            return band_rule(a)
        return {"type": "minecraft:sequence", "sequence": [
            {"type": "minecraft:condition",
             "if_true": {"type": "minecraft:noise_threshold", "noise": f"{NS}:province",
                         "min_threshold": -1e9, "max_threshold": 0.0},
             "then_run": band_rule(a)},
            band_rule(b)]}

    palette_rule = {"type": "minecraft:sequence", "sequence": [
        *({"type": "minecraft:condition",
           "if_true": {"type": "lithostitched:biome", "biomes": f"#{NS}:climate/{climate}"},
           "then_run": climate_rule(climate)} for climate in ("cold", "arid", "tropical")),
        climate_rule("temperate")]}
    steep_enough = {"type": "lithostitched:any_of", "conditions": [
        {"type": "lithostitched:all_of", "conditions": [
            {"type": "lithostitched:slope", "height_difference": [lo, 2147483647]},
            {"type": "minecraft:stone_depth", "offset": depth - 1, "add_surface_depth": False,
             "secondary_depth_range": 0, "surface_type": "floor"}]}
        for lo, depth in PARAMS["strata_tiers"]]}
    strata_rule = {"type": "minecraft:condition",
                   "if_true": {"type": "lithostitched:all_of", "conditions": [
                       {"type": "minecraft:above_preliminary_surface"},
                       {"type": "lithostitched:biome", "biomes": f"#{NS}:strata"},
                       {"type": "minecraft:water", "offset": 0, "surface_depth_multiplier": 0,
                        "add_stone_depth": False},
                       steep_enough]},
                   "then_run": palette_rule}
    put(f"{d}/lithostitched/worldgen_modifier/strata.json", {
        "type": "lithostitched:add_surface_rule", "priority": PARAMS["strata_priority"],
        "injection_type": "prepend", "levels": ["minecraft:overworld"], "surface_rule": strata_rule})

    put(f"{d}/worldgen/configured_feature/cliff_spring.json", {
        "type": "minecraft:spring_feature",
        "config": {"state": {"Name": "minecraft:water", "Properties": {"falling": "true"}},
                   "requires_block_below": True, "rock_count": 4, "hole_count": 1,
                   "valid_blocks": SPRING_BLOCKS + sorted({blk for _, (base, bands) in PALETTES.items()
                                                          for blk in [base] + [b[0] for b in bands]} - set(SPRING_BLOCKS))}})
    lo_d, hi_d = PARAMS["spring_depth"]
    y0, y1 = PARAMS["spring_y"]
    for kind, attempts in PARAMS["spring_attempts"].items():
        put(f"{d}/worldgen/placed_feature/cliff_spring_{kind}.json", {
            "feature": f"{NS}:cliff_spring",
            "placement": [
                {"type": "minecraft:count", "count": attempts},
                {"type": "minecraft:in_square"},
                {"type": "minecraft:heightmap", "heightmap": "WORLD_SURFACE_WG"},
                {"type": "minecraft:random_offset", "xz_spread": 0, "y_spread": uniform(-hi_d, -lo_d)},
                {"type": "lithostitched:condition", "condition": {
                    "type": "lithostitched:height_filter", "range_type": "absolute", "permitted_range": [y0, y1]}},
                {"type": "minecraft:biome"}]})
        put(f"{d}/lithostitched/worldgen_modifier/cliff_springs_{kind}.json", {
            "type": "lithostitched:add_features", "biomes": f"#{NS}:springs_{kind}",
            "features": f"{NS}:cliff_spring_{kind}", "step": "fluid_springs"})

    for rel, obj in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, indent=2) + "\n")
    counts = {c: sum(1 for v in climate_of.values() if v == c) for c in CLIMATES}
    print(f"wrote {len(files)} files to {out}")
    print(f"strata biomes: {len(strata)} of {len(overworld)} overworld ({counts}); "
          f"springs: {len(springs_high)} high, {len(springs_low)} low")


if __name__ == "__main__":
    main()
