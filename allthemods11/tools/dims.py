"""Build height and sea level of a dimension, read from the pack's generated data (runDataATM11).

Dimensions in All The Mods 11 differ a lot (the_beyond is y -128..383, the Undergarden -64..127),
and heightmaps can only be decoded with the right height, so the map tools look it up here.
"""
import json
from pathlib import Path

DEFAULT_GENERATED = Path(__file__).resolve().parent.parent / "datagen" / "generated"
# Settings for dimensions that come from the world preset rather than a dimension/*.json file.
PRESET_SETTINGS = {"minecraft:overworld": "minecraft:overworld", "minecraft:the_nether": "minecraft:nether",
                   "minecraft:the_end": "minecraft:end"}


def dimension_id(name):
    """'minecraft/overworld', 'minecraft:overworld' or 'overworld' -> 'minecraft:overworld'."""
    name = name.replace("/", ":", 1)
    return name if ":" in name else f"minecraft:{name}"


def region_dir(world, dim):
    ns, path = dimension_id(dim).split(":", 1)
    return Path(world) / "dimensions" / ns / path / "region"


def _read(generated, kind, rid):
    ns, path = rid.split(":", 1)
    f = Path(generated) / "data" / ns / kind / f"{path}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


def dimension_info(dim, generated=DEFAULT_GENERATED):
    """Return (min_y, height, sea_level) for a dimension; sea_level is None when it has no noise settings."""
    dim = dimension_id(dim)
    spec = _read(generated, "dimension", dim)
    dim_type, settings = dim, PRESET_SETTINGS.get(dim)
    if spec is not None:
        dim_type = spec.get("type", dim)
        settings = spec.get("generator", {}).get("settings", settings)
    if isinstance(dim_type, str):
        dim_type = _read(generated, "dimension_type", dim_type)
    if not dim_type:
        raise SystemExit(f"no dimension type for {dim} in {generated}; pass --min-y and --height")
    if isinstance(settings, str):
        settings = _read(generated, "worldgen/noise_settings", settings)
    sea = settings.get("sea_level") if isinstance(settings, dict) else None
    return dim_type["min_y"], dim_type["height"], sea
