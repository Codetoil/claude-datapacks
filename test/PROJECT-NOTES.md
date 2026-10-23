# ~/datapacks/test: project notes

State as of 2026-10-23 06:38 EDT (Vastlands server) and 16:35 EDT (All The Mods 11 section at the end).
Written so a fresh Claude session (or Codetoil) can pick up where the 2026-10-23 session left off.

## The server

- **Vanilla Minecraft Java 26.3** (built 2026-09-15; protocol 777; data pack format **121.0**; Java 25).
  `server.jar` is the bundler; the real jar is `versions/26.3/server-26.3.jar` (unobfuscated, so
  `javap` on it shows real class and field names).
- **Currently stopped.** Start it with `cd ~/datapacks/test && java -Xmx4G -jar server.jar nogui`
  (run it in a Terminal panel tab so it outlives the Claude session).
- `level-name=vastlands-world`, `level-seed=2743401496026046295`, allowlist on (only Codetoil),
  `online-mode=true`, difficulty normal, no operators, `pause-when-empty-seconds=60`.
- **Remote access** (all only reachable from this machine; see Security):
  - RCON on TCP 25575. The password is in `server.properties`.
  - Query (GS4) on UDP 25565.
  - Management Protocol (JSON-RPC over WebSocket) at `wss://localhost:25585`: TLS with a self-signed
    PKCS12 keystore `management-keystore.p12` (cert for clients: `management-cert.pem`), auth with
    `management-server-secret` from `server.properties`.
  - `server.properties` and the keystore are mode 600.
- The 26.3 data reports (command tree, registries, blocks, item components, data pack layout,
  JSON-RPC schema) are in `generated/reports/`.

## Worlds (keep all of them; Codetoil asked that none be deleted)

| Folder | What | Size |
|---|---|---|
| `world` | Codetoil's original vanilla world (vanilla pack only) | 18 MB |
| `vastlands-world` | **The live world**: fresh world with the Vastlands pack, seed above | 42 MB |
| `vastlands-test-1` | Test 1 (first parameter set) | 340 MB |
| `vastlands-test-2` | Test 2 (more mountains, deep rivers) | 391 MB |
| `vastlands-test-3` | Test 3 (final terrain parameters) + a far sample at (4400, −4000) | 706 MB |
| `vastlands-test-vanilla` | Same seed without the pack, for comparison | 183 MB |

To switch worlds, stop the server and set `level-name` in `server.properties`
(`vastlands/tools/setprop.py server.properties level-name=<folder>`).

## Vastlands datapack (`vastlands/`)

A terrain overhaul that keeps vanilla biomes. `vastlands/build.py` reads the vanilla files from
the server jar and writes the pack to `vastlands/pack/` (32 files); every tweak is in its `PARAMS`.

| Change | Setting |
|---|---|
| Taller world | height 512, y −64 … 447 (dimension type + noise settings); terrain faded out between y 400 and 416 |
| Bigger continents / erosion zones / ridges / biomes | `xz_scale` ÷ 1.6 / 1.4 / 1.1 / 1.4 |
| More mountains, a bit more land | erosion −0.1, continentalness +0.05 |
| Taller land | offset h (≈0 at sea level, surface ≈ 63.5 + 128h): land above h=0.08 raised by 1.0× the excess |
| Deeper oceans | h<0 lowered by 0.9·h, faded in from continentalness −0.11 (coast) to −0.45 (deep ocean), so rivers and lakes keep vanilla depth |
| Sharper peaks | jaggedness × 1.5 |
| Waterfalls | `vastlands:cliff_springs` (24 water-spring attempts/chunk, y 96–416) in 11 mountain biomes |
| Ores and other features for the taller world | features spread up to the world top get counts scaled by the height-range growth: upper coal 30→51, ore_gravel 14→19, monster_room 10→14, fossil_upper 1/64→1/46, underground lava lakes 1/9→1/6 |

**Measured (test 3 vs vanilla, same seed):**
- Land surface p99 ≈ y 240 (vanilla ≈ 125). Highest point y 348 (vanilla 153).
- A sample 4 km away had a median land height of y 111.
- Generation speed ≈ 125 chunks/s (vanilla ≈ 165).

**Installing and updating:**
- Copy `vastlands/pack` to `<world>/datapacks/vastlands`. On a new world the server enables it automatically.
- Worldgen changes need a **server restart** (`/reload` doesn't touch worldgen), and only affect chunks not generated yet.
- Terrain changes leave visible seams in an existing world; underground feature changes (ores) don't.

**Decisions made with Codetoil:**
- River centers can be deep (up to ~22 blocks seen near (150, −85)). Kept as is ("It's your datapack"). It's a knob for future worlds.
- The ore rebalance was applied to `vastlands-world` at 06:04. The extra coal hasn't been measured in-game yet.

**Tools (`vastlands/tools/`, standard library + Pillow):**
- `pregen.py <server.properties> <cx> <cz> <radius>`: forceload-based chunk generation over RCON.
  Ends with `save-all` (not `flush`, which tripped the watchdog once).
- `render_map.py <world> <prefix> [--height 512] [--bounds x0 z0 x1 z1]`: terrain, elevation and biome PNGs plus height stats. Reads 26.x chunk NBT.
- `render_view.py <world> <out.png> <cx> <cz> <size>`: oblique 3D view.
- `anvil.py`: region/NBT reader. `setprop.py`: edit `server.properties` while the server is stopped.
- `say.py <server.properties> "<text>"`: in-game `[Claude]` chat over RCON (fallback for the MCP tool).
- Previews are in `vastlands/previews/`.

## The `minecraft` MCP server (`minecraft-mcp/server.py`)

Standard-library Python, stdio MCP, registered with `claude mcp add --scope local minecraft …`
for this project. **Its tools load in the next Claude session** (this session used `say.py`
and the watcher instead).

| Tool | Approval |
|---|---|
| `minecraft_chat_read`, `minecraft_chat_wait`, `minecraft_chat_send`, `minecraft_status` | automatic |
| `minecraft_command` (refuses admin commands, also inside `execute … run`) | automatic |
| `minecraft_rpc` (refuses operator/allowlist/ban changes, kick, stop, autosave off, …) | automatic |
| `minecraft_admin_command`, `minecraft_admin_rpc` | always asks |

- **Listening:** `python3 -I -u minecraft-mcp/server.py --server-dir ~/datapacks/test --watch` prints one
  line per chat message, join/leave, advancement and death. Run it under a Monitor while the server is up,
  re-arm every 30 minutes, and react in-game to Codetoil's chat, advancements and deaths.
- **Command reference:** `minecraft-mcp/COMMANDS.md` (all 94 commands by category, permission levels,
  26.x changes). Full syntax: `python3 -I minecraft-mcp/command_usage.py generated/reports/commands.json <cmd>`.

## Permissions and security

- This session ran in `acceptEdits` mode, which auto-approves file edits only (MCP tools and most Bash still ask unless allowed).
- **`.claude/settings.local.json`** (project):
  - allows the six automatic tools above and `Bash(python3 -I vastlands/tools/say.py server.properties *)`;
  - **asks** for the two admin tools and for edits to `ops.json`, `whitelist.json`, `banned-players.json`,
    `banned-ips.json`, `server.properties` (absolute-path rules).
- **`~/.claude/settings.json`** (user) has copies of the `say.py` allow rule and the five file "ask" rules,
  only because the project `.claude/` folder didn't exist when the session started.
  **To do:** once a new session has the MCP tools loaded, remove the `say.py` Bash rule from both files;
  the user-level ask rules can go too once the project file is confirmed active.
- **Firewall (`ufw`):** default deny incoming (IPv4 and IPv6), no rules for 25565/25575/25585, so RCON,
  Query and the game are only reachable from localhost. LAN friends can't join unless 25565/tcp is allowed.
- **SSH:** password authentication is on (OpenSSH default), with port 22 open from 192.168.1.238–.242 on Wi-Fi
  and the cluster. Reserved addresses on the router, or key-only login, would tighten it (not changed).
- Gemini's write-up was checked against the machine: `local-llm-mcp` already runs its programs with
  argument lists and no shell; `tellraw` can't execute commands; the real gap was unprompted edits to
  server files, now closed by the ask rules.

## Gotchas learned (26.3 and this setup)

- **Never run `server.jar` (data generator, `--help`, second server) from this folder while the server runs.**
  Log4j rolls `logs/latest.log` away from the live server. Use a scratch folder and absolute paths.
- **Render maps only after the server has fully exited.** Chunks are still being written right after `save-all`/`stop`.
- **26.x chunk NBT:** block states are `{"id": …, "properties": {…}}`, and mixed palettes wrap plain strings as `{"": "minecraft:…"}`.
- **26.x worldgen:**
  - Density functions use `gradient` (with `axis`), `noise` with `shift_x/z`, `lerp`, `find_top_surface`, `interpolated`, `cache`.
  - Surface rules are a `material_rule` registry; configured features moved to `worldgen/feature/`.
  - `noise_settings` has `aquifers`, `debug_functions`, `spawn_target`.
- **Commands:** game rules are snake_case (`keep_inventory`). `time` works through clocks and timelines
  (`time query time`). `tick` needs level 3, so datapack functions can't use it.
- **`/difficulty`** changes only the running game; `minecraft:serversettings/difficulty/set` over the
  Management Protocol also saves it to `server.properties`.
- **The vanilla offset spline** puts the surface at y ≈ 63.5 + 128·(offset + 0.50375).

## Open items and ideas

- No world backups exist yet (a backup command or tool was suggested, not built).
- Clean up the `say.py` Bash allow rules (see Permissions).
- Test worlds use about 1.6 GB together (kept on purpose).

## All The Mods 11 (the modded game, added 2026-10-23)

Codetoil's next target: datapacks for **All The Mods 11** (MC 26.1.2, NeoForge 26.1.2.109, 280 mods, KubeJS 8.0.6,
**data pack format 101.1**, not the 26.3 server's 121.0).
**Full ATM11 handoff: `~/datapacks/allthemods11/NOTES.md`** (start/stop, remote access, Claude setup, toolkit,
reports, 26.1.2 facts, test results). State at 17:12: the ATM11 server is **stopped** (ran 16:17–17:12, stopped
cleanly over RCON at Codetoil's request), so either server can start (only one at a time); every toolkit
test passed (RCON, MSMP, Query, MCP tools, `/neoforge generate` pregen, map renders).
- **Pack:** `~/datapacks/allthemods11` (moved there at ~14:45; not a git repo), a production server install with
  NeoForge .109 reinstalled and the pack's own `startserver.sh`. That script loops: after a stop it restarts
  in 10 s unless `ATM11_RESTART=false`. One-shot start from that folder:
  `java @user_jvm_args.txt @libraries/net/neoforged/neoforge/26.1.2.109/unix_args.txt nogui`. Codetoil's test
  start at 14:48 reached "Done" and created the world `world` (keep it). The NeoForge MDK it came from is now
  the blank `~/IdeaProjects/NeoForge-26.1.2-blank` (no mod, its own `run/`). Its dev `runServer` (NeoForge
  .122) crashed with the pack in it: Jade rethrows the Undergarden plugin error in dev.
- **Its server.properties** (set up 2026-10-23 16:10 at Codetoil's request, mirroring this server):
  RCON on TCP 25575 and the Management Protocol at `wss://localhost:25585` (TLS keystore
  `management-keystore.p12`, client cert `management-cert.pem`, self-signed RSA 3072 for localhost/127.0.0.1/::1,
  valid to 2029-01-25); fresh passwords, the server's own 40-char management secret; `server.properties` and the
  keystore mode 600. Query (GS4) on UDP 25565 too (16:13), and the allowlist on with only Codetoil, the same
  `whitelist.json` as this server (16:15). Same ports as this server (25565, 25575, 25585), so only one of the
  two can run at a time; the firewall keeps them localhost-only here too.
- **Toolkit (ported 2026-10-23, 15:20–16:05):** `~/datapacks/allthemods11/tools/` and `minecraft-mcp/`, adapted copies of
  `vastlands/tools` and `minecraft-mcp` here:
  - `render_map.py` / `render_view.py`: blocks in their **in-game map colors** (Codetoil's idea;
    `reports/map_colors.json` from reportdump, looking through blocks without one like a map does), biome
    colors by kind from the `#c:is_*` tags (`colors.py`); `--dimension ns:path`, and the build height and sea
    level come from the dimension type (`dims.py`; ATM11 dimensions run from y −128..383 to −64..127). 26.1.2
    chunks store states as `{"Name", "Properties"}`.
  - `pregen.py`: `/neoforge generate` by default (`--method forceload` as before). `setprop.py` hides
    password/secret values. `anvil.py`, `say.py` unchanged.
  - `minecraft-mcp/server.py`: parses NeoForge's log format (only the `MinecraftServer` logger), FTB Ranks name
    prefixes, NeoForge's `usernamecache.json`; admin guard also covers `ftbranks` (except `list_*`), `mute`,
    `unmute`, `ftbchunks admin|unclaim_all`, `ftbteams force|server`, `kubejs eval`. `COMMANDS.md` there covers
    the 91 vanilla + 146 modded commands.
  - Registered as `minecraft` (local scope) for the `~/datapacks/allthemods11` project, with the same permission
    split in its `.claude/settings.local.json` (plus "ask" for FTB Ranks' config); the user-level
    `~/.claude/settings.json` has copies of its file "ask" rules, like this server's. Its tools load in a Claude
    session started in that folder. Tested against the running server 16:18–16:32 (see its NOTES.md).
  - Pregen: `--method forceload` doesn't work while a server is paused for being empty (`pause-when-empty-seconds`,
    60 on both servers): forceloaded chunks never become entity-ticking, so `execute if loaded` fails. The
    default `/neoforge generate` works while paused. (The vanilla `vastlands/tools/pregen.py` has the same limit.)
- **Reports with every mod loaded:** `~/IdeaProjects/reportdump-neo` (Codetoil's Gradle project; I write code
  in it). `./gradlew runDataATM11` (~50 s) uses `~/datapacks/allthemods11/datagen` as its game folder (its own
  `logs/`, so it can run beside the server) and writes `~/datapacks/allthemods11/datagen/generated` (1.3 GB):
  - `reports/registries.json`, `blocks.json`, `commands.json`, `<ns>/components/item/*.json`:
    vanilla report formats, with all mods and KubeJS-registered content;
  - `reports/data_registries.json` (biomes, features, structures, biome modifiers… with resolved tags),
    `reports/static_registry_tags.json` (block/item/… tags, resolved, after KubeJS tag events);
  - `data/`: the effective data files (top pack wins; tags merged), `skipped_by_conditions/`,
    `reports/effective_data/` (pack order, overrides, condition failures);
  - `loaded/data/` + `reports/loaded_data.json`: recipes, loot tables, advancements as the server loaded
    them, after KubeJS scripts;
  - `reports/map_colors.json`: every block state's in-game map color (for the map tools).
  - Details, quirks and caveats: `~/IdeaProjects/reportdump-neo/NOTES.md`.
- **Worldgen facts:** the overworld terrain comes from Tectonic + Terralith ("Terratonic") with lithostitched;
  `#minecraft:is_overworld` has 222 biomes (Terralith 90, Regions Unexplored 73, vanilla 54); Terralith's own
  `dimension/overworld.json` is skipped by its conditions. KubeJS (`kubejs/dynamic_data`) also changes
  biomes, features and biome modifiers. A Vastlands-style `noise_settings/overworld` override would
  collide with Tectonic/Terralith's.
