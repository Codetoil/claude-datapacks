# Useful commands on the All The Mods 11 server (26.1.2, NeoForge)

Notes for using the `minecraft` MCP tools (and RCON in general) on ATM11: 91 vanilla commands plus
146 from mods (237 in the report; `chisel`, `ftbchunks_dev` and `newFamily` exist only in the dev
data run). Syntax comes from the pack's command report; vanilla permission levels were read from the
26.1.2 sources (`Commands.LEVEL_*`). Modded levels aren't recorded anywhere yet.

- **Full syntax** of any command:
  `python3 -I minecraft-mcp/command_usage.py datagen/generated/reports/commands.json <command>`
  (the report comes from `./gradlew runDataATM11` in `~/IdeaProjects/reportdump-neo`).
- **Tools:** `minecraft_command` runs everything below without asking, except the **Server admin**
  section, which needs `minecraft_admin_command` (asks Codetoil each time). RCON runs at level 4.
- **Level** matters for datapacks: functions run at `function-permission-level=2`, so a function can
  only use level 0–2 commands; others make the function fail to load. For a modded command, try it
  in a function and check the log.
- **Player-only commands** (homes, `heal`, `kubejs hand`, …) need a player as the source over RCON:
  `execute as Codetoil at @s run heal`.

## Differences from the 26.3 server in ~/datapacks/test

- **Not in 26.1.2:** `compute`, `posteffect`, `unpublish`. Everything else vanilla is the same, at the same levels.
- **Game rules are snake_case** here too (`gamerule keep_inventory true`); 119 rules.
- **Time** already uses clocks and timelines: `time query time|gametime|timeline`, `time set|add`,
  `time pause|resume`, `time rate`, `time of <clock> …`.
- **Text components** in `tellraw`/`title` are SNBT; JSON-style `{"text":"…"}` still parses.
- **Logs:** chat is logged by `net.minecraft.server.MinecraftServer` without 26.3's "System chat:" prefix;
  No Chat Reports marks all chat trusted, so no "[Not Secure]" tag.
- **Management Protocol:** the same methods as 26.3 except the four `notification/world/upgrade_*`.

## 1. Look and inspect (read-only)

| Command | Level | Use |
|---|---|---|
| `list` | 0 | Who is online |
| `data get entity <player> Pos` / `Dimension` / `LastDeathLocation` / `Inventory` / `Health` | 2 | Where someone is, where they died, what they carry |
| `data get block <pos>` | 2 | Contents of chests, machines, signs, spawners |
| `locate structure <id>` · `locate biome <id>` · `locate poi <id>` | 2 | Nearest structure or biome, modded ones too |
| `execute if block|blocks|entity|biome|loaded|score|items|predicate|function|stopwatch …` | 2 | Yes/no tests; `execute if loaded <x> 0 <z>` = chunk fully generated |
| `seed` · `time query time` · `gamerule <rule>` · `datapack list enabled|available` | 2 | World facts |
| `scoreboard …list|get` · `attribute <entity> <attribute> get` · `forceload query` · `worldborder get` | 2 | State |
| `neoforge tps [<dimension>]` · `neoforge entity list [<filter>] [<dim>]` · `neoforge dimensions` · `neoforge mods` | mod | Server health, entity counts, dimensions, mod list |
| `neoforge dump registry <registry>` · `neoforge data_components list` · `neoforge tags …` | mod | Registry and tag contents in the running game |
| `wits` (as a player) · `witsop <dimension> <pos>` | mod | Which structure is at a position |
| `tectonic debug …` · `tectonic locate …` | mod | Tectonic's terrain debugging |
| `kubejs errors` · `kubejs dump …` · `kubejs list-tag <tag>` | mod | KubeJS script errors and data |
| `ftbranks list_all_ranks` · `ftbranks list_ranks_of <player>` · `ftbranks list_players_with <rank>` | mod | Ranks (read-only, allowed) |
| `ftbteams list` · `ftbteams info …` · `ftbchunks info …` | mod | Teams and claims |
| `crashutilities entities|blockentities|chunks|activity …` (alias `cu`) | mod | Lag hunting: what's loaded where |
| `whitelist list` · `banlist` · `tick query` | 3 | Read-only admin views (allowed by the guard) |

## 2. Help the player

| Command | Level | Use |
|---|---|---|
| `tp <player> <x y z>` · `tp <player> <target>` · `execute in <dim> run tp …` | 2 | Move someone, also between dimensions |
| `give <player> <item>[components] [count]` · `clear …` · `item replace|modify …` | 2 | Items (modded ids work) |
| `effect give …` · `gamemode …` · `xp …` · `enchant …` · `weather …` · `time set day` · `difficulty …` | 2 | Comfort and progression |
| `gamerule keep_inventory true` · `spawnpoint …` · `setworldspawn …` | 2 | Death and spawn |
| `kill <target>` · `cu e remove [byType] <type>` | 2 / mod | Clear mobs or items (careful with `@e`: pets, item frames, machines' entities) |
| `title …` · `tellraw …` | 2 | Messages; `minecraft_chat_send` uses `tellraw` |
| Player utilities, mostly FTB Essentials: `back`, `spawn`, `home`/`sethome`/`delhome`/`listhomes`, `warp`/`setwarp`/`delwarp`/`listwarps`, `tpa`/`tpahere`/`tpaccept`/`tpdeny`, `rtp`, `tpx <dimension>`, `heal`, `feed`, `extinguish`, `fly`, `god`, `speed`, `jump`, `hat`, `near`, `enderchest`, `invsee <player>`, `trashcan`, `nickname`, `kit …`, `leaderboard …`, `tp_offline …`, `teleport_last <player>` | mod | Run `as` the player |
| `waystones …` · `ftbquests change_progress …` · `curios …` · `sb …` (Sophisticated Backpacks) · `epitaphs list|preview|recover …` · `lootr …` | mod | Mod-specific help: waystones, quest progress, curio slots, backpacks, saved death records, per-player loot chests |

## 3. Building and terrain editing

| Command | Level | Use |
|---|---|---|
| `setblock` · `fill` · `clone` · `fillbiome` · `place feature|structure|jigsaw|template …` | 2 | As in vanilla; modded blocks, features and structures work |
| `witchery changeBiome …` | mod | Witchery's own biome change |
| `ae2 spatial …` | mod | AE2 spatial storage tools (leave `ae2 setuptestworld`, a test helper, alone on the real world) |

## 4. Worldgen testing

| Command | Level | Use |
|---|---|---|
| `neoforge generate start <pos> <chunkRadius> [progressBar]` · `status` · `stop` | mod | NeoForge's pregenerator (square 2·radius chunks on a side); `tools/pregen.py` uses it. Other dimensions: `execute in <dim> run neoforge generate …` |
| `forceload add|remove|query …` | 2 | Generate without a player (≤ 256 chunks per command); `pregen.py --method forceload` |
| `locate biome|structure …` · `execute if biome …` · `place feature <id> <pos>` | 2 | Find and test worldgen |
| `tectonic locate …` · `wits` / `witsop …` | mod | Tectonic terrain and structure lookups |
| `save-all` | 4 | Write chunks before rendering maps (no `flush`: it can trip the watchdog) |
| `tick freeze|step|sprint …` | 3 | Pause or fast-forward |

Worldgen changes (datapack or KubeJS `dynamic_data`) need a server restart; `/reload` doesn't touch worldgen.

## 5. Datapack development

| Command | Level | Use |
|---|---|---|
| `reload` | 2 | Reload functions, loot tables, recipes, tags, advancements, and KubeJS server scripts. **Not** worldgen |
| `kubejs reload server-scripts|startup-scripts|config` | mod | Reload KubeJS alone (what startup scripts register still needs a restart) |
| `datapack enable|disable <name> …` · `function <id> [with …]` · `schedule …` · `return …` | 2 | As in vanilla |
| `execute … store …` · `scoreboard …` · `data merge|modify|remove …` · `trigger …` (0) | 2 | Data plumbing |
| `advancement …` · `recipe …` · `loot …` · `summon …` · `random …` · `stopwatch …` · `dialog …` · `swing …` | 2 | Progression, loot, entities, timers |
| `placebo serialize_loot_table …` · `placebo get_dimension_type` | mod | Inspect loot tables and dimension types |
| `ftbquests editing_mode …` | mod | Quest editing |
| `test …` | 2 | GameTest |

## 6. Performance and diagnostics

`neoforge tps` · `neoforge track …` · `tick query|rate` (3) · `perf start|stop` (4) · `jfr start|stop` (4) ·
`debug start|stop|function` (3) · `crashutilities …` · `pdl profiler toggle` · `ln networkTicking` (Logistics Networks).

## 7. Server admin (`minecraft_admin_command`: asks Codetoil every time)

- Vanilla: `stop` (4) · `op` / `deop` (3) · `ban` / `ban-ip` / `pardon` / `pardon-ip` (3) ·
  `whitelist add|remove|on|off|reload` (3) · `kick` (3) · `save-off` (4) · `transfer` (3) · `setidletimeout` (3).
- Modded: `ftbranks` (ranks and permission nodes; the `list_*` subcommands stay allowed) · `mute` / `unmute` ·
  `ftbchunks admin …` and `ftbchunks unclaim_all` (also as `chunks`) · `ftbteams force …` · `ftbteams server …` ·
  `kubejs eval` / `kjs eval` (runs JavaScript on the server).
- Read-only `whitelist list` and `banlist` stay on the auto-allowed tool; `save-all` and `save-on` too.
- The pack's `startserver.sh` restarts the server 10 s after `stop` unless it was started with `ATM11_RESTART=false`.

## 8. Rarely useful here

`me`, `msg` / `tell` / `w`, `teammsg` / `tm` (level 0) · `say` (use `tellraw`) · `publish` (4) · `spectate`, `spreadplayers` ·
mod debug and GUI commands: `cdg`, `closeguiscreen`, `openguiscreen`, `open …`, `ftbchunks_dev`, `newFamily`, `chisel`
(the last three only in the dev data run), `balm dev`, `craftingtweaks debug`,
`irons_artifice debug`, `occultism debug`, the `*config` / `version` subcommands of Cyclops mods.

## Permission levels of vanilla commands (26.1.2 sources)

- **0:** help, list, me, msg, teammsg, tell, tm, trigger, w
- **2:** advancement, attribute, bossbar, clear, clone, damage, data, datapack, defaultgamemode, dialog, difficulty,
  effect, enchant, execute, experience/xp, fetchprofile, fill, fillbiome, forceload, function, gamemode, gamerule,
  give, item, kill, locate, loot, particle, place, playsound, random, recipe, reload, return, ride, rotate, say,
  schedule, scoreboard, seed, setblock, setworldspawn, spawnpoint, spectate, spreadplayers, stopsound, stopwatch,
  summon, swing, tag, team, teleport/tp, tellraw, test, time, title, version, waypoint, weather, worldborder
- **3:** ban, ban-ip, banlist, debug, deop, kick, op, pardon, pardon-ip, setidletimeout, tick, transfer, whitelist
- **4:** jfr, perf, publish, save-all, save-off, save-on, stop
