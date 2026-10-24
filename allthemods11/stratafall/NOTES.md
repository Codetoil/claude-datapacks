# Stratafall: cliffs and falls for All The Mods 11

A worldgen datapack for the ATM11 server (Minecraft 26.1.2, NeoForge 26.1.2.109, data pack format 101).
It leaves the shape of the land to Tectonic, Terralith and Regions Unexplored and adds what their cliffs lack:

- **Rock strata.** Steep faces turn into banded rock instead of grass, snow, dirt or ice, on every side of a
  mountain (vanilla's own rule only bares north- and east-facing slopes). Each climate has two banded palettes, and a
  large-scale "province" noise picks one, so one range is granite-and-andesite and the next may be chalky white.
- **Falls from the cliffs.** Water springs that open in cliff faces where there is a real drop in front
  (waterfalls), curtains of packed ice hanging from cliffs in snowy biomes (frozen falls), and lava falls in
  Terralith's volcanic biomes. None in deserts and savannas.

Made by Claude (a cloud session) for Codetoil on 2026-10-23/24, on request: "Make me a really good worldgen
datapack for ATM11. Your choice on the details. Keep the test worlds, like with Vastlands." The choices below are
mine and the reasons are written down so they can be argued with.

## Why this and not a terrain overhaul

The local session had already found that overriding `noise_settings/overworld` or the biome parameter list collides
with Tectonic + Terralith + lithostitched. So instead of reshaping the land (Vastlands-style), I measured what the
existing worldgen leaves missing, in a baseline world on `world`'s seed (`atm11-test-0`, 8 sample areas, 5,928
chunks, 888k land columns):

| Baseline measurement | Value |
|---|---|
| Cliff columns (neighbour height difference 7-12) that are bare rock | 46% (rest: snow/soil/ice/gravel) |
| `minecraft:jagged_peaks` cliff columns covered in snow | 97% |
| Water at the surface above sea level | 37 columns in 888k (unticked); 1,991 after letting fluids flow |

Two clear gaps: cliffs dressed like gentle slopes, and dry mountains. Both can be fixed additively, without touching
any other mod's files, and both are visible from far away.

## How it works

All of it goes through lithostitched worldgen modifiers (`data/stratafall/lithostitched/worldgen_modifier/`):

- `strata.json`: `lithostitched:add_surface_rule`, `injection_type: prepend`, `priority: 900`. lithostitched sorts
  surface-rule modifiers by priority and puts prepends in that order before the original rule, so 900 runs before
  Regions Unexplored's rules (default 1000), Terralith's and vanilla's.
  - Steepness: `lithostitched:slope` = max - min of the `WORLD_SURFACE_WG` heights of the 4 neighbouring columns,
    all directions. Tiers `(slope >= 4, paint 7 deep)`, `(8, 15)`, `(16, 31)`, `(32, 63)`, `(64, 127)`: a column
    whose neighbours differ by d exposes a face up to d tall, so each tier paints down to the next threshold.
  - Also required: `above_preliminary_surface`, not under water, biome in `#stratafall:strata`.
  - Palettes: `lithostitched:bandlands` (192-entry band array, sampled at y + 4 x the vanilla clay-band offset
    noise, like badlands); they must be registry entries (`data/stratafall/lithostitched/bandlands/*.json`, the
    rule only accepts a reference). Cold: `alpine` / `slate`; temperate: `granite` / `chalk`; tropical:
    `tropical`; arid: `desert` / `redrock`. `stratafall:province` (firstOctave -10, provinces ~1-2 km) picks.
  - Vanilla blocks only, so the pack never depends on a decorative-stone mod.
- `water_falls_{high,low}.json`, `ice_falls_{high,low}.json`, `lava_falls.json`: `lithostitched:add_features` at
  step `fluid_springs`.
  - Each attempt starts at `WORLD_SURFACE_WG`, drops 2-12 blocks into the column (1-3 for ice), keeps only
    positions with open air in front of them at 0, 1 and 3 blocks down (a free fall, not a 1-block step).
  - Water and lava: `minecraft:spring_feature` (4 rock + 1 open side, rock below), so the opening is in the face.
  - Ice: a `lithostitched:composite` of three `minecraft:block_column`s (packed ice 4-14 + blue ice tip 1-2),
    hung in the air in front of the face (one placed feature per facing direction).
  - More attempts in mountain/hill/plateau biomes (`high`) than elsewhere (`low`).

Biome lists are resolved by `build.py` from the pack's generated reports
(`../datagen/generated/reports/data_registries.json`, reportdump-neo's runDataATM11) and written as tags with
`"required": false` entries, so a removed mod only drops its biomes. Excluded from strata (they keep their own
cliffs or are not land): oceans, rivers, beaches, caves, badlands, mushroom fields, Terralith's canyons, spires,
mesas, white/granite/frozen cliffs, Yosemite, Yellowstone and volcanoes, RU's chalk cliffs, spires and icy heights,
Thaumaturge's tainted lands and eerie, vanilla ice spikes.

## Installing

Copy `pack/` to `<world>/datapacks/stratafall/` **before the world's first start**; new worlds enable it
automatically ("Found new data pack file/stratafall"). On an existing world it only affects chunks generated
afterwards, and terrain next to old chunks will show seams (rock faces only in new chunks). Rebuild after mods
change: `python3 build.py` (needs the reports; see reportdump-neo).

## Testing (tools/)

Test worlds live next to `world` in `allthemods11/` and are kept, like Vastlands':
`atm11-test-0` = no pack (baseline), `atm11-test-N` = Stratafall iteration N. Each gets `world`'s `level.dat` and
`data/minecraft/world_gen_settings.dat` (26.1.2 keeps the seed there, not in level.dat) and is started with the
server's `--world` option, so `server.properties` is never edited.

- `tools/new_test_world.sh atm11-test-N` creates the folder with the seed files and the current `pack/`.
- `tools/full_test.sh atm11-test-N` starts the server, checks the log for pack errors, generates the 9 sample areas
  of `tools/samples.txt` with `/neoforge generate`, lets fluids flow (forceload + `/tick sprint 60s`, which works
  through `pause-when-empty-seconds`), saves, unforces and stops. `tools/sample_pass.sh` does the same for some samples.
- `tools/stats_all.sh <world> <dir>` + `tools/compare.py <dir>...`: per-sample and pooled metrics (cliff materials
  by slope class after stepping down past trees, water/lava/ice counts).
- `tools/face_view.py`: oblique view that draws each face block by block (strata show), any facing direction;
  `tools/sheer_faces.py` renders the tallest faces head-on.

Never send other RCON commands while `pregen_samples.sh` runs: a blocked server thread makes `pregen.py` time out
and the following samples refuse to start ("Generation already running").

## Results

RESULTS_PLACEHOLDER

## Known limitations

- `lithostitched:slope` (like vanilla `steep`) only sees inside the chunk being surfaced; at chunk edges the
  difference is one-sided, so some cliff columns along chunk borders keep their snow or grass. Measured in v1: rock
  62% at chunk-edge cliff columns vs 76% inside chunks.
- Waterfalls and lava falls flow once a player is near (fluid ticks run in ticking chunks); right after
  pregeneration they are single source blocks in the faces.
- Water from a fall still spreads where it lands; on long staircases it cascades rather than falls.
- The flowing-water metric is noisy between runs of the same terrain (about +-50% in one sample), so only large
  differences mean something.

## Decisions log

- Terrain shape untouched (collisions with Tectonic/Terralith/lithostitched, see above).
- Palettes from vanilla blocks only.
- v1 springs had no drop check and flooded 1-2 block steps into sheets; v2 required 6 blocks of air below an
  opening 3-16 deep (a 10+ block step between neighbouring columns) and placed almost none; v3 uses a 3-block drop.
- Ice falls instead of waterfalls in snowy biomes; lava falls only in the four Terralith volcanic biomes.
- First strata tier 5 -> 4 in v2 (vanilla's own `steep` threshold; also helps chunk-edge columns).
