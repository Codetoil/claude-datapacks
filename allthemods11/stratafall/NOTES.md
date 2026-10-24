# Stratafall: cliffs and falls for All The Mods 11

A worldgen datapack for the ATM11 server (Minecraft 26.1.2, NeoForge 26.1.2.109, data pack format 101).
It leaves the shape of the land to Tectonic, Terralith and Regions Unexplored and adds what their cliffs lack:

- **Rock strata.** Steep faces turn into banded rock instead of grass, snow, dirt or ice, on every side of a
  mountain (vanilla's own rule only bares north- and east-facing slopes). Each climate has two banded palettes, and a
  large-scale "province" noise picks one, so one range is granite-and-andesite and the next may be chalky white.
- **Falls from the cliffs.** Water springs that open in cliff faces where there is a real drop in front
  (waterfalls), curtains of packed ice hanging from cliffs in snowy biomes (frozen falls; snowy mountains also get
  some waterfalls), and lava falls in Terralith's volcanic biomes. None in deserts and savannas.

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
- `water_falls_{high,low,snowy}.json`, `ice_falls_{high,low}.json`, `lava_falls.json`:
  `lithostitched:add_features` at step `fluid_springs`.
  - Each attempt starts at `WORLD_SURFACE_WG`, drops 2-8 blocks into the column (1-3 for ice) and keeps only
    positions with open air in front of them at 0, 1 and 3 blocks down (a free fall, not a 1-2 block step).
  - Water and lava: `minecraft:spring_feature` (4 rock + 1 open side, rock below), so the opening is in the face.
  - Ice: a `lithostitched:composite` of five `minecraft:block_column`s along the face (packed ice 6-16 + blue ice
    tip 1-2), hung in the air in front of it; one placed feature per facing direction. Side columns only appear
    where the face continues, and every column stops at the first ledge below.
  - Valid openings are rare (only ~3-8 in 10,000 random tries; `tools/spring_sites.py`), so the attempt counts
    are high: water 96 per chunk in mountain/hill/plateau biomes, 32 elsewhere and 32 in snowy mountains; ice 12
    (mountains) or 4 per facing direction; lava 96. Each try is a handful of block reads; generation time per
    sample did not change measurably (v3 vs v4 on the same machine, within 5 s).

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

All on `world`'s seed, 9 sample areas (`tools/samples.txt`, 6,217 chunks, 940k land columns), fluids ticked 60 s.
Pooled over all samples (`test-results.txt` has every sample and metric):

| | test-0 (no pack) | test-1 v1 | test-2 v2 | test-3 v3 | test-4 v4 | test-5 v5 | **test-6 v6** |
|---|---|---|---|---|---|---|---|
| Rock on steep columns (slope 4-6) | 48.4% | 57.4% | 73.1% | 73.0% | 72.0% | 72.3% | **72.1%** |
| Rock on cliff columns (slope 7+) | 47.5% | 64.4% | 65.5% | 65.3% | 63.4% | 63.7% | **63.3%** |
| Flowing water above y 72 | 11,060 | 17,614 | 10,494 | 11,244 | 18,317 | 18,072 | **16,174** |
| Lava above y 64, volcano sample | 173 | 173 | 173 | 182 | 815 | 815 | **818** |
| Ice-fall tips (blue ice above y 80), peaks + savanna | 0 | 0 | 61 | 121 | 289 | 147 | **320** |

- Slope classes use the terrain under trees (the stats step down past logs, plants and snow layers). What is left
  on steep columns besides rock is mostly snow and, in big-tree forests, dirt/podzol that tree features write
  after the surface stage, plus the chunk-edge effect below. Some "cliff columns" are not cliffs at all. In the
  overview area's alpine-highlands, plains and magnolia-woodland parts, 62 of the 96 soil cliff columns are grass
  next to stone standing on the soil (a structure's walls, boulders), and 29 of the other 34 have air within 10
  blocks below them or their high neighbour: caves cut by carvers after the surface stage, or overhangs.
- v1's water came from springs flooding 1-2 block steps (sheets); v6's comes only from openings with a free fall,
  and lands as streams. The water numbers vary by about +-50% between runs of the same terrain (e.g. the volcano
  sample: 364 to 2,549 across worlds), so compare the big differences only.
- Generation speed: no measurable change (same fresh area on the same machine: no pack 54 s, v1 53 s, v2 40 s;
  v3-v6 per-sample times within 5 s of each other). Thread dumps during generation showed no Stratafall frames.
- No new log errors in any test world (the pack loads as "Found new data pack file/stratafall").

Previews (`previews/`, `tools/previews.py` with `tools/preview_spec.json`; left without, right with Stratafall):
`mountains-overview.png`, `waterfall.png`, `strata-temperate.png`, `strata-arid.png`, `lava-falls.png`, `ice-falls.png`.
The renderer draws south-, north-, east- or west-facing faces block by block in approximate texture colours. The
overview area was picked as the 192-block window of the samples where the most steep columns turned to rock; in it,
rock on steep columns goes from 32% to 77% and on frozen-peaks cliffs from 4% to 77%.

## Known limitations

- `lithostitched:slope` (like vanilla `steep`) only sees inside the chunk being surfaced; at chunk edges the
  difference is one-sided, so some cliff columns along chunk borders keep their snow or grass. Measured in the peaks
  sample (v1 and v3 alike): rock 62% at chunk-edge cliff columns vs 76% inside chunks.
- In snowy biomes vanilla's `freeze_top_layer` still lays a snow layer on top of the rock (58% of steep columns in
  the peaks sample stay snow-capped), so seen from above the rock only shows on the faces, and a mostly gentle
  snowy range looks almost unchanged from a distance (in the peaks sample only 4.9% of columns are steep).
- Ice falls stay short (median ~4 blocks): Tectonic's faces are stepped, and a hanging column stops at the first
  ledge. Next to a waterfall they are easy to miss.
- Adding features to the `fluid_springs` step shifts the random seeds of features after them in that step, so
  feature-level details (e.g. vanilla springs) differ slightly between a world with and without the pack. Terrain
  and surface rules are identical.
- Waterfalls and lava falls flow once a player is near (fluid ticks run in ticking chunks); right after
  pregeneration they are single source blocks in the faces.
- Water from a fall still spreads where it lands; on long staircases it cascades rather than falls.
- The flowing-water metric is noisy between runs of the same terrain (about +-50% in one sample), so only large
  differences mean something.

## Decisions log

- Terrain shape untouched (collisions with Tectonic/Terralith/lithostitched, see above).
- Palettes from vanilla blocks only.
- v1 springs had no drop check and flooded 1-2 block steps into sheets; v2 required 6 blocks of air below an
  opening 3-16 deep (a 10+ block step between neighbouring columns) and placed almost none; v3 used a 3-block
  drop but kept v2's low attempt counts, so still few falls; v4 raised the counts after measuring how rare valid
  openings are. v5 tried a 4-block drop for ice (fewer curtains, no longer ones); v6 keeps 3 with 5-wide curtains.
- Frozen falls in snowy biomes (this seed is very cold), plus waterfalls at a third of the mountain rate in snowy
  mountains (v4+): v2/v3 had moved all snowy biomes to ice only, which removed most of the water.
- Lava falls only in the four Terralith volcanic biomes.
- First strata tier 5 -> 4 in v2 (vanilla's own `steep` threshold).
- Not done: a chunk-independent slope estimate (`lithostitched:shift` + `find_top_surface` could compute one, but
  a surface condition evaluates it per block and it would scan the terrain noise each time: far too slow).
