#!/usr/bin/env python3
"""Build the Stratafall worldgen datapack for All The Mods 11 (Minecraft 26.1.2, NeoForge, data pack format 101).

Stratafall leaves the terrain shape to Tectonic + Terralith + Regions Unexplored and adds what their cliffs lack:
- Rock strata: steep faces (in every direction, unlike vanilla's north/east-only `steep`) become banded rock instead
  of grass, snow or dirt. Each climate has two palettes; a large-scale "province" noise picks one of them, so a
  mountain range keeps one look and the next range may have another.
- Falls from cliff faces, only where there is a real drop in front of the face:
  waterfalls (springs) in temperate, tropical and cold-but-not-snowy biomes, frozen falls (curtains of packed ice)
  in snowy biomes, lava falls in Terralith's volcanic biomes. None in deserts and savannas.

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
    # A column whose neighbours differ by d blocks exposes a face up to d blocks tall, so each tier paints down to
    # the next tier's threshold. The first threshold (4, like vanilla's steep) decides what counts as a cliff.
    "strata_tiers": [(4, 7), (8, 15), (16, 31), (32, 63), (64, 127)],
    # Lower runs first; regions_unexplored's surface rules use the default 1000.
    "strata_priority": 900,
    # Province noise: picks one of the two palettes of a climate. firstOctave -10 => provinces ~1-2 km across.
    "province_noise": {"firstOctave": -10, "amplitudes": [1.0, 1.0]},
    # Falls. attempts = tries per chunk ("ice" per facing direction, 4 directions); depth = how far below the
    # column's surface the opening is aimed; drop = open air required in front of / below the opening.
    # v2 needed air 6 blocks below an opening 3-16 blocks deep (a 10+ block step between neighbouring columns),
    # which almost never happens; v1 had no check and flooded 1-2 block steps. drop 3 sits between the two.
    # Only ~3-8 in 10,000 random (column, depth) tries hit a valid opening (measured with tools/spring_sites.py in
    # atm11-test-3), so the counts are high; each try costs a handful of block reads.
    # Targets: ~1 waterfall per 16 mountain chunks, ~1 per 64 lowland chunks.
    "water": {"attempts": {"high": 96, "low": 32, "snowy": 32}, "depth": (2, 8), "drop": 3, "y": (72, 400)},
    # v4's 3-wide curtains on 3-block drops came out 6-8 blocks long and easy to miss next to waterfalls; v5 hangs
    # 5-wide curtains on 4+ block drops (the columns still stop at the first ledge below).
    "ice": {"attempts": {"high": 12, "low": 4}, "depth": (1, 3), "drop": 4, "y": (80, 400),
            "length": (6, 16), "tip": (1, 2), "width": 5},
    "lava": {"attempts": 96, "depth": (2, 8), "drop": 3, "y": (64, 400)},
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
VOLCANIC = ["terralith:volcanic_peaks", "terralith:volcanic_crater", "terralith:caldera", "terralith:basalt_cliffs"]
EXCLUDE_IDS = [
    # Terralith biomes with their own cliff or spire surfaces
    "terralith:amethyst_canyon", "terralith:bryce_canyon", "terralith:desert_canyon", "terralith:desert_spires",
    "terralith:frozen_cliffs", "terralith:glacial_chasm", "terralith:granite_cliffs", "terralith:painted_mountains",
    "terralith:savanna_badlands", "terralith:snowy_badlands", "terralith:stony_spires", "terralith:warped_mesa",
    "terralith:white_cliffs", "terralith:white_mesa", "terralith:windswept_spires", "terralith:yellowstone",
    "terralith:yosemite_cliffs", "terralith:alpha_islands", "terralith:alpha_islands_winter", "terralith:mirage_isles",
    "terralith:red_oasis", *VOLCANIC,
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
SNOWY_TAGS = ["#c:is_snowy", "#c:is_icy", "#c:is_snowy_plains"]
HIGH_TAGS = ["#c:is_mountain", "#minecraft:is_mountain", "#c:is_hill", "#minecraft:is_hill", "#c:is_plateau",
             "#c:is_windswept", "#c:is_mountain/slope", "#c:is_mountain/peak"]
HIGH_ID_WORDS = {"highlands", "mountain", "mountains", "peaks", "slopes", "cliffs", "heights", "hills", "plateau"}

ROCKS = ["minecraft:stone", "minecraft:granite", "minecraft:diorite", "minecraft:andesite", "minecraft:deepslate",
         "minecraft:tuff", "minecraft:calcite", "minecraft:dripstone_block", "minecraft:cobblestone",
         "minecraft:mossy_cobblestone", "minecraft:cobbled_deepslate", "minecraft:smooth_basalt"]
SPRING_BLOCKS = ROCKS + ["minecraft:dirt", "minecraft:coarse_dirt", "minecraft:grass_block", "minecraft:podzol",
                         "minecraft:snow_block", "minecraft:powder_snow", "minecraft:packed_ice", "minecraft:moss_block",
                         "minecraft:packed_mud", "minecraft:gravel", "minecraft:clay"]
LAVA_BLOCKS = ROCKS + ["minecraft:basalt", "minecraft:polished_basalt", "minecraft:blackstone", "minecraft:magma_block",
                       "minecraft:obsidian", "minecraft:netherrack", "minecraft:coarse_dirt", "minecraft:gravel"]
DIRECTIONS = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}


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


def air(dx, dy, dz):
    return {"type": "minecraft:matching_blocks", "offset": [dx, dy, dz], "blocks": "minecraft:air"}


def open_drop(dx, dz, drop):
    """Air in front of the opening (dx, dz), halfway down and `drop` blocks below it: a free fall, not a step."""
    return {"type": "minecraft:all_of", "predicates": [air(dx, -k, dz) for k in sorted({0, drop // 2, drop})]}


def surface_aim(attempts, depth, y_range):
    lo_d, hi_d = depth
    return [{"type": "minecraft:count", "count": attempts},
            {"type": "minecraft:in_square"},
            {"type": "minecraft:heightmap", "heightmap": "WORLD_SURFACE_WG"},
            {"type": "minecraft:random_offset", "xz_spread": 0, "y_spread": uniform(-hi_d, -lo_d)},
            {"type": "lithostitched:condition", "condition": {
                "type": "lithostitched:height_filter", "range_type": "absolute", "permitted_range": list(y_range)}}]


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
    high = {b for b in strata if b in resolve(tags, HIGH_TAGS) or HIGH_ID_WORDS & set(b.split(":", 1)[1].split("_"))}
    snowy = strata & resolve(tags, SNOWY_TAGS)
    wet = {b for b in strata if climate_of[b] != "arid" and b not in snowy}
    # Snowy mountains get frozen falls and, at a lower rate, running ones; snowy lowlands only frozen ones.
    falls = {"water_high": wet & high, "water_low": wet - high, "water_snowy": snowy & high,
             "ice_high": snowy & high, "ice_low": snowy - high, "lava": overworld & set(VOLCANIC)}

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    files = {}

    def put(rel, obj):
        files[rel] = obj

    put("pack.mcmeta", {"pack": {"description": "Stratafall: rock strata on cliffs, waterfalls, ice falls and lava falls "
                                                "for All The Mods 11",
                                 "min_format": PACK_FORMAT, "max_format": PACK_FORMAT}})
    d = f"data/{NS}"
    put(f"{d}/tags/worldgen/biome/strata.json", tag_json(strata))
    for climate in ("cold", "arid", "tropical"):
        put(f"{d}/tags/worldgen/biome/climate/{climate}.json",
            tag_json({b for b, c in climate_of.items() if c == climate}))
    for name, biomes in falls.items():
        put(f"{d}/tags/worldgen/biome/falls/{name}.json", tag_json(biomes))
    put(f"{d}/worldgen/noise/province.json", PARAMS["province_noise"])

    # --- rock strata -----------------------------------------------------------------------------------------
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

    # --- waterfalls and lava falls: springs that open in a face with open air below ---------------------------
    palette_blocks = sorted({blk for base, bands in PALETTES.values() for blk in [base] + [b[0] for b in bands]})
    for fluid, valid in (("water", SPRING_BLOCKS + [b for b in palette_blocks if b not in SPRING_BLOCKS]),
                         ("lava", LAVA_BLOCKS)):
        put(f"{d}/worldgen/configured_feature/{fluid}_fall.json", {
            "type": "minecraft:spring_feature",
            "config": {"state": {"Name": f"minecraft:{fluid}", "Properties": {"falling": "true"}},
                       "requires_block_below": True, "rock_count": 4, "hole_count": 1, "valid_blocks": valid}})
    sheer = lambda drop: {"type": "minecraft:block_predicate_filter", "predicate": {
        "type": "minecraft:any_of", "predicates": [open_drop(dx, dz, drop) for dx, dz in DIRECTIONS.values()]}}
    modifiers = {}
    for kind in ("high", "low", "snowy"):
        p = PARAMS["water"]
        put(f"{d}/worldgen/placed_feature/water_fall_{kind}.json", {
            "feature": f"{NS}:water_fall",
            "placement": surface_aim(p["attempts"][kind], p["depth"], p["y"]) + [sheer(p["drop"]), {"type": "minecraft:biome"}]})
        modifiers[f"water_falls_{kind}"] = (f"#{NS}:falls/water_{kind}", [f"{NS}:water_fall_{kind}"])
    p = PARAMS["lava"]
    put(f"{d}/worldgen/placed_feature/lava_fall.json", {
        "feature": f"{NS}:lava_fall",
        "placement": surface_aim(p["attempts"], p["depth"], p["y"]) + [sheer(p["drop"]), {"type": "minecraft:biome"}]})
    modifiers["lava_falls"] = (f"#{NS}:falls/lava", [f"{NS}:lava_fall"])

    # --- frozen falls: a curtain of packed ice (columns of random length) hanging in front of a face -------------
    p = PARAMS["ice"]
    put(f"{d}/worldgen/configured_feature/ice_column.json", {
        "type": "minecraft:block_column",
        "config": {"direction": "down", "prioritize_tip": True,
                   "allowed_placement": {"type": "minecraft:matching_blocks", "blocks": "minecraft:air"},
                   "layers": [{"height": uniform(*p["length"]),
                               "provider": {"type": "minecraft:simple_state_provider",
                                            "state": {"Name": "minecraft:packed_ice"}}},
                              {"height": uniform(*p["tip"]),
                               "provider": {"type": "minecraft:simple_state_provider",
                                            "state": {"Name": "minecraft:blue_ice"}}}]}})
    for face, (dx, dz) in DIRECTIONS.items():
        # The face looks toward (dx, dz): its rock is at -(dx, dz) from the hanging column.
        side = (dz, dx)  # perpendicular, along the face
        behind = {"type": "minecraft:solid", "offset": [-dx, 0, -dz]}

        def column_at(ox, oz):
            return {"feature": f"{NS}:ice_column", "placement": [
                {"type": "lithostitched:offset", "x_offset": ox, "y_offset": 0, "z_offset": oz},
                {"type": "minecraft:block_predicate_filter", "predicate": {
                    "type": "minecraft:all_of", "predicates": [air(0, 0, 0), behind]}}]}
        half = p["width"] // 2
        put(f"{d}/worldgen/configured_feature/ice_fall_{face}.json", {
            "type": "lithostitched:composite",
            "config": {"placement_type": "never_cancel",
                       "features": [column_at(side[0] * k, side[1] * k) for k in range(-half, half + 1)]}})
        for kind in ("high", "low"):
            put(f"{d}/worldgen/placed_feature/ice_fall_{face}_{kind}.json", {
                "feature": f"{NS}:ice_fall_{face}",
                "placement": surface_aim(p["attempts"][kind], p["depth"], p["y"]) + [
                    {"type": "minecraft:block_predicate_filter", "predicate": {
                        "type": "minecraft:all_of", "predicates": [
                            {"type": "minecraft:solid"}, open_drop(dx, dz, p["drop"])]}},
                    {"type": "lithostitched:offset", "x_offset": dx, "y_offset": 0, "z_offset": dz},
                    {"type": "minecraft:biome"}]})
    for kind in ("high", "low"):
        modifiers[f"ice_falls_{kind}"] = (f"#{NS}:falls/ice_{kind}",
                                          [f"{NS}:ice_fall_{face}_{kind}" for face in DIRECTIONS])

    for name, (biomes, features) in modifiers.items():
        put(f"{d}/lithostitched/worldgen_modifier/{name}.json", {
            "type": "lithostitched:add_features", "biomes": biomes, "features": features, "step": "fluid_springs"})

    for rel, obj in files.items():
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, indent=2) + "\n")
    counts = {c: sum(1 for v in climate_of.values() if v == c) for c in CLIMATES}
    print(f"wrote {len(files)} files to {out}")
    print(f"strata biomes: {len(strata)} of {len(overworld)} overworld ({counts})")
    print("falls: " + ", ".join(f"{k} {len(v)}" for k, v in falls.items()))


if __name__ == "__main__":
    main()
