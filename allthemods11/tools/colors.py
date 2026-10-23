"""Block and biome colors for the map renderers, from the pack's generated reports (runDataATM11).

Blocks use the colors of in-game maps (reports/map_colors.json from reportdump): every block sets
one, modded ones included, and "none" means maps look through it to the block below. Vanilla
biomes use the classic biome-map palette; modded ones a color for their kind, from the
conventional #c:is_* tags in reports/data_registries.json (then words in the name, then
temperature), shaded a little per biome so neighbors of the same kind stay apart.
"""
import colorsys
import json
import zlib
from functools import lru_cache
from pathlib import Path

import dims

VANILLA_BIOMES = {
    "ocean": (0, 0, 112), "deep_ocean": (0, 0, 48), "warm_ocean": (0, 0, 172), "lukewarm_ocean": (0, 0, 144),
    "deep_lukewarm_ocean": (0, 0, 64), "cold_ocean": (32, 32, 112), "deep_cold_ocean": (32, 32, 56),
    "frozen_ocean": (112, 112, 214), "deep_frozen_ocean": (64, 64, 144), "river": (0, 0, 255), "frozen_river": (160, 160, 255),
    "beach": (250, 222, 85), "snowy_beach": (250, 240, 192), "stony_shore": (162, 162, 132),
    "plains": (141, 179, 96), "sunflower_plains": (181, 219, 136), "snowy_plains": (255, 255, 255), "ice_spikes": (180, 220, 220),
    "desert": (250, 148, 24), "swamp": (7, 249, 178), "mangrove_swamp": (44, 204, 142),
    "forest": (5, 102, 33), "flower_forest": (45, 142, 73), "birch_forest": (48, 116, 68), "dark_forest": (64, 81, 26),
    "old_growth_birch_forest": (88, 156, 108), "pale_garden": (160, 168, 150),
    "taiga": (11, 102, 89), "snowy_taiga": (49, 85, 74), "old_growth_pine_taiga": (89, 102, 81), "old_growth_spruce_taiga": (129, 142, 121),
    "savanna": (189, 178, 95), "savanna_plateau": (167, 157, 100), "windswept_savanna": (229, 218, 135),
    "jungle": (83, 123, 9), "sparse_jungle": (98, 139, 23), "bamboo_jungle": (118, 142, 20),
    "badlands": (217, 69, 21), "eroded_badlands": (255, 109, 61), "wooded_badlands": (176, 151, 101),
    "meadow": (131, 187, 109), "cherry_grove": (255, 160, 220), "grove": (160, 210, 190), "snowy_slopes": (210, 225, 240),
    "frozen_peaks": (160, 190, 255), "jagged_peaks": (220, 220, 230), "stony_peaks": (123, 143, 116),
    "windswept_hills": (96, 96, 96), "windswept_gravelly_hills": (136, 136, 136), "windswept_forest": (88, 106, 88),
    "mushroom_fields": (255, 0, 255), "dripstone_caves": (130, 90, 60), "lush_caves": (40, 200, 40), "deep_dark": (10, 30, 40),
    "nether_wastes": (191, 59, 59), "soul_sand_valley": (94, 56, 48), "crimson_forest": (221, 8, 8),
    "warped_forest": (73, 144, 123), "basalt_deltas": (64, 54, 54), "the_end": (128, 128, 255),
    "small_end_islands": (128, 128, 255), "end_midlands": (128, 128, 255), "end_highlands": (128, 128, 255),
    "end_barrens": (128, 128, 255), "the_void": (0, 0, 0),
}
# First matching tag wins, so specific kinds come before general ones.
BIOME_KINDS = [
    ("#c:is_river", (0, 0, 255)), ("#c:is_deep_ocean", (0, 0, 80)), ("#c:is_ocean", (0, 0, 150)),
    ("#c:is_beach", (250, 222, 85)), ("#c:is_stony_shores", (162, 162, 132)),
    ("#c:is_mushroom", (255, 0, 255)), ("#c:is_swamp", (7, 200, 150)), ("#c:is_badlands", (217, 69, 21)),
    ("#c:is_desert", (250, 148, 24)), ("#c:is_icy", (160, 190, 255)), ("#c:is_snowy", (235, 240, 250)),
    ("#c:is_mountain/peak", (200, 200, 210)), ("#c:is_mountain", (120, 130, 120)),
    ("#c:is_jungle", (83, 123, 9)), ("#c:is_savanna", (189, 178, 95)), ("#c:is_taiga", (11, 102, 89)),
    ("#c:is_coniferous", (40, 100, 80)), ("#c:is_dark_forest", (64, 81, 26)),
    ("#c:is_birch_forest", (48, 116, 68)), ("#c:is_flower_forest", (45, 142, 73)), ("#c:is_forest", (5, 102, 33)),
    ("#c:is_plains", (141, 179, 96)), ("#c:is_hill", (110, 140, 90)), ("#c:is_plateau", (167, 157, 100)),
    ("#c:is_wasteland", (150, 130, 110)), ("#c:is_dead", (130, 115, 100)), ("#c:is_cave", (90, 70, 60)),
    ("#c:is_underground", (90, 70, 60)), ("#c:is_nether", (150, 40, 30)), ("#c:is_end", (200, 200, 150)),
    ("#c:is_magical", (170, 90, 200)), ("#c:is_spooky", (70, 60, 80)), ("#c:is_lush", (40, 200, 40)),
]
NAME_KINDS = [
    (("sea", "ocean", "lake"), (30, 60, 170)), (("river",), (0, 0, 255)), (("swamp", "bog", "marsh"), (7, 200, 150)),
    (("mushroom",), (255, 0, 255)), (("jungle", "tropic"), (83, 123, 9)), (("desert", "dune"), (250, 148, 24)),
    (("tundra", "frozen", "frost", "icy", "ice", "winter", "frigid", "sierra"), (200, 215, 240)),
    (("basalt", "soul", "crimson", "warped", "burnt"), (110, 40, 40)), (("cliff", "spire", "scar", "crater"), (140, 140, 130)),
    (("forest", "wood", "grove"), (40, 110, 40)), (("field", "plain", "shrub", "clearing", "valley", "basin"), (140, 175, 95)),
    (("cave", "cavern", "depth", "abyss", "mining"), (90, 70, 60)), (("void", "space", "storage"), (20, 20, 30)),
]
TEMPERATURE_KINDS = [("#c:is_hot", (200, 160, 90)), ("#c:is_cold", (170, 190, 215)), ("#c:is_temperate", (110, 150, 80))]


def _rgb(hex_color):
    return None if hex_color == "none" else tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def state_key(properties):
    """'name=value,...' with the properties sorted by name, as map_colors.json keys block states."""
    return ",".join(f"{k}={v}" for k, v in sorted((properties or {}).items()))


class Palette:
    def __init__(self, generated):
        reports = Path(generated) / "reports"
        try:
            self.blocks = json.loads((reports / "map_colors.json").read_text(encoding="utf-8"))
            biomes = json.loads((reports / "data_registries.json").read_text(encoding="utf-8"))["minecraft:worldgen/biome"]
        except OSError as e:
            raise SystemExit(f"{e}: run ./gradlew runDataATM11 in ~/IdeaProjects/reportdump-neo first")
        tags = {t: set(ids) for t, ids in biomes["tags"].items() if isinstance(ids, list)}
        self.biomes = {bid: self._biome(bid, tags) for bid in biomes["entries"]}

    @staticmethod
    def _biome(bid, tags):
        ns, name = bid.split(":", 1)
        if ns == "minecraft" and name in VANILLA_BIOMES:
            return VANILLA_BIOMES[name]
        h = zlib.crc32(bid.encode())
        base = (next((c for t, c in BIOME_KINDS if bid in tags.get(t, ())), None)
                or next((c for words, c in NAME_KINDS if any(w in name for w in words)), None)
                or next((c for t, c in TEMPERATURE_KINDS if bid in tags.get(t, ())), None)
                or tuple(int(255 * v) for v in colorsys.hsv_to_rgb((h % 360) / 360, 0.45, 0.7)))
        f = 0.82 + (h % 37) / 100  # 0.82..1.18
        return tuple(max(0, min(255, int(c * f))) for c in base)

    def block(self, name, properties=None):
        """In-game map color of a block state, or None when maps look through it."""
        entry = self.blocks.get(name)
        if entry is None:  # not in the report (a block from a mod that's gone): a stable gray-ish color
            h = zlib.crc32(name.encode())
            return 96 + (h & 63), 96 + ((h >> 6) & 63), 96 + ((h >> 12) & 63)
        states = entry.get("states")
        return _rgb(states.get(state_key(properties), entry["color"]) if states else entry["color"])

    def biome(self, bid):
        return self.biomes.get(bid, (128, 128, 128))


@lru_cache(maxsize=None)
def palette(generated=dims.DEFAULT_GENERATED):
    return Palette(generated)
