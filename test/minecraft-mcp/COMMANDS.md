# Useful commands on this 26.3 server

Notes for using the `minecraft` MCP tools (and RCON in general) on the Vastlands server. All 94
commands in 26.3 are covered: syntax comes from `generated/reports/commands.json`, and permission
levels were read from the server jar's command classes.

- **Full syntax** of any command: `python3 -I minecraft-mcp/command_usage.py generated/reports/commands.json <command>`
- **Tools:** `minecraft_command` runs everything below without asking, except the **Server admin**
  section, which needs `minecraft_admin_command` (asks Codetoil each time). RCON runs at level 4.
- **Level** matters for datapacks: functions run at `function-permission-level=2`, so a function can
  only use level 0–2 commands. Level-3/4 commands in a function fail to load.

## 26.x gotchas (differs from what I knew before 26.1)

- **Game rules are snake_case**: `gamerule keep_inventory true` (also accepts `minecraft:keep_inventory`). 118 rules.
- **Time uses world clocks and timelines**: `time query time`, `time query gametime`, `time set <time>`,
  `time pause|resume`, `time rate <rate>`, `time of <clock> …`. `time query daytime` no longer exists.
- **New commands**: `compute`, `posteffect`, `swing`, `stopwatch`, `fetchprofile`, `dialog`, `waypoint`, `rotate`.
- **New `execute` condition**: `execute if stopwatch …`.
- **Text components** in `tellraw`/`title` are SNBT; JSON-style `{"text":"…"}` still parses.
- Some server settings are better changed through the Management Protocol (`minecraft_rpc`), which
  also saves them to `server.properties` (e.g. difficulty). Commands like `/difficulty` change only the running game.

## 1. Look and inspect (read-only)

| Command | Level | Use |
|---|---|---|
| `list` | 0 | Who is online |
| `data get entity <player> Pos` / `Dimension` / `LastDeathLocation` / `Inventory` / `Health` | 2 | Where someone is, where they died, what they carry |
| `data get block <pos>` | 2 | Contents of chests, signs, spawners |
| `locate structure <id>` · `locate biome <id>` · `locate poi <id>` | 2 | Nearest village, peak, biome… (add `execute positioned <x y z> run` to search from elsewhere) |
| `execute if block|blocks|entity|biome|loaded|score|items|predicate|function|stopwatch …` | 2 | Yes/no tests; e.g. `execute if loaded <x> 0 <z>` = chunk fully generated |
| `seed` | 2 | World seed |
| `time query time` · `time query gametime` | 2 | Current time |
| `gamerule <rule>` | 2 | Read a game rule |
| `datapack list enabled` · `datapack list available` | 2 | Which packs are active |
| `scoreboard objectives list` · `scoreboard players list [<target>]` · `scoreboard players get …` | 2 | Scores |
| `attribute <entity> <attribute> get` | 2 | Max health, speed, scale… |
| `forceload query [<pos>]` | 2 | Force-loaded chunks |
| `worldborder get` | 2 | Border size |
| `team list` · `bossbar list` · `waypoint list` · `posteffect list <target>` · `stopwatch query <id>` | 2 | State of those systems |
| `fetchprofile name <name>` · `fetchprofile id <uuid>` | 2 | Look up a player profile |
| `tick query` | 3 | Tick rate and timing (admin-level read, still auto-allowed) |
| `whitelist list` · `banlist` | 3 | Read-only access lists (allowed by the guard) |
| `version` · `help [<command>]` | 2 / 0 | Server version; usage help |

## 2. Help the player

| Command | Level | Use |
|---|---|---|
| `tp <player> <x y z>` · `tp <player> <target>` · `execute at <player> positioned over motion_blocking_no_leaves run tp <player> ~ ~ ~` | 2 | Move someone; the last one lifts a stuck player to the surface |
| `spawnpoint <player> <pos>` · `setworldspawn <pos>` | 2 | Respawn points |
| `give <player> <item>[components] [count]` · `clear <player> [item] [max]` · `item replace|modify …` | 2 | Items |
| `effect give <player> <effect> [seconds] [amplifier]` · `effect clear` | 2 | Night vision, water breathing, regeneration… |
| `gamemode <mode> [player]` · `defaultgamemode <mode>` | 2 | Survival/creative/spectator |
| `xp add|set <player> <n> [points|levels]` · `enchant <player> <enchantment> [level]` | 2 | Progression helpers |
| `weather clear|rain|thunder [duration]` · `time set <time>` · `difficulty <level>` | 2 | Comfort settings |
| `gamerule keep_inventory true` | 2 | Keep items on death |
| `kill <target>` | 2 | Clear hostile mobs near the player: `kill @e[type=zombie,distance=..32]` run `at` the player. Careful with `@e` (pets, item frames, villagers) |
| `rotate <target> facing <pos>` | 2 | Point someone at something |
| `waypoint modify <entity> color|style …` | 2 | Locator-bar waypoints |
| `title <player> title|subtitle|actionbar <text>` | 2 | Big on-screen messages |
| `tellraw <player> <text>` | 2 | What `minecraft_chat_send` uses |

## 3. Building and terrain editing

| Command | Level | Use |
|---|---|---|
| `setblock <pos> <block> [replace|keep|destroy|strict]` | 2 | One block |
| `fill <from> <to> <block> [replace <filter>|destroy|hollow|outline|keep|strict]` | 2 | Boxes; size capped by the `max_block_modifications` game rule (also applies to `clone` and `fillbiome`) |
| `clone <from> <to> <dest> [replace|masked|filtered] [force|move|normal]` | 2 | Copy regions |
| `fillbiome <from> <to> <biome> [replace <filter>]` | 2 | Repaint biomes (grass/foliage colors, mob spawns) |
| `place feature|structure|jigsaw|template …` | 2 | Spawn a tree, village, structure piece or saved template |

## 4. Worldgen testing (Vastlands)

| Command | Level | Use |
|---|---|---|
| `locate biome …` · `locate structure …` | 2 | Find places to inspect without generating them |
| `forceload add <from> <to>` / `remove` / `query` | 2 | Generate chunks without a player (≤ 256 chunks per command); this is what `vastlands/tools/pregen.py` does |
| `place feature <id> <pos>` | 2 | Test one feature, e.g. `place feature minecraft:spring_water` |
| `execute if biome <pos> <biome>` | 2 | Check biome placement |
| `seed` | 2 | Seed for reproducing a world |
| `save-all` | 4 | Write chunks to disk before rendering maps (no `flush`: it can trip the watchdog) |
| `tick freeze` / `tick step` / `tick sprint <time>` | 3 | Pause or fast-forward to watch generation or growth |

## 5. Datapack development

| Command | Level | Use |
|---|---|---|
| `reload` | 2 | Reload functions, loot tables, recipes, tags, advancements. **Not** worldgen (that needs a restart) |
| `datapack enable|disable <name> [first|last|before|after]` · `datapack create <id> <description>` | 2 (create: 4) | Pack management |
| `function <id> [with …]` | 2 | Run a function, optionally with macro arguments |
| `schedule function <id> <time> [append|replace]` · `schedule clear <id>` | 2 | Delayed or recurring logic |
| `return <value>` · `return fail` · `return run <command>` | 2 | Function results |
| `execute … store result|success score|storage|block|entity|bossbar … run …` | 2 | Data plumbing |
| `scoreboard objectives add|remove|modify` · `scoreboard players set|add|remove|operation|reset|enable` | 2 | State |
| `data merge|modify … set|append|insert|remove` · `data remove …` | 2 | NBT and storage |
| `trigger <objective> [add|set]` | 0 | Lets non-op players press buttons in your pack (pair with `scoreboard players enable`) |
| `tag <targets> add|remove|list` · `team …` · `bossbar …` | 2 | Grouping and UI |
| `advancement grant|revoke …` · `recipe give|take …` · `loot …` | 2 | Progression and loot testing |
| `summon <entity> [pos] [nbt]` · `ride …` · `damage …` · `attribute … base set …` | 2 | Entity setup |
| `random value|roll <range> [sequence]` · `random reset …` | 2 | Seeded randomness |
| `stopwatch create|query|restart|remove <id>` | 2 | New: timers you can test with `execute if stopwatch` |
| `compute block|entity|default integer|float <provider> [scale]` | 2 | New: evaluates the new context int/float providers (data types `context_int_provider` / `context_float_provider`) |
| `dialog show|clear <targets> <dialog>` | 2 | Show a data-driven dialog screen |
| `posteffect add|remove|clear|list …` | 2 | New: screen post-processing effects on players |
| `swing <targets> [mainhand|offhand] [animation] [duration]` | 2 | New: play arm-swing animations |
| `particle …` · `playsound …` · `stopsound …` | 2 | Effects |
| `test run|runthese|runclosest|runfailed|runmultiple|verify|stop|create|locate|pos|clearall …` | 2 | GameTest: automated tests defined by `test_instance` / `test_environment` |

## 6. Performance and diagnostics

| Command | Level | Use |
|---|---|---|
| `tick query` · `tick rate <tps>` | 3 | Server tick health |
| `perf start` / `perf stop` | 4 | 10-second profiling report in `debug/` |
| `jfr start` / `jfr stop` | 4 | Java Flight Recorder profile |
| `debug start|stop|function <id>` | 3 | Tick profiling; `debug function` traces a function's execution |

## 7. Server admin (`minecraft_admin_command`: asks Codetoil every time)

`stop` (4) · `op` / `deop` (3) · `ban` / `ban-ip` / `pardon` / `pardon-ip` (3) · `whitelist add|remove|on|off|reload` (3) ·
`kick` (3) · `save-off` (4) · `transfer` (3) · `setidletimeout` (3).
Read-only `whitelist list` and `banlist` stay on the auto-allowed tool; `save-all` and `save-on` too.

## 8. Rarely useful here

`me`, `msg` / `tell` / `w`, `teammsg` / `tm` (player-to-player chat; level 0) · `say` (use `tellraw` instead) ·
`publish` / `unpublish` (LAN hosting, level 4; not meaningful on a dedicated server) · `spectate`, `spreadplayers`, `worldborder` (situational).

## Permission levels (from the 26.3 jar)

- **0:** help, list, me, msg, teammsg, tell, tm, trigger, w
- **2:** advancement, attribute, bossbar, clear, clone, compute, damage, data, datapack (create: 4), defaultgamemode,
  dialog, difficulty, effect, enchant, execute, experience/xp, fetchprofile, fill, fillbiome, forceload, function,
  gamemode, gamerule, give, item, kill, locate, loot, particle, place, playsound, posteffect, random, recipe, reload,
  return, ride, rotate, say, schedule, scoreboard, seed, setblock, setworldspawn, spawnpoint, spectate, spreadplayers,
  stopsound, stopwatch, summon, swing, tag, team, teleport/tp, tellraw, test, time, title, version, waypoint, weather, worldborder
- **3:** ban, ban-ip, banlist, debug, deop, kick, op, pardon, pardon-ip, setidletimeout, tick, transfer, whitelist
- **4:** jfr, perf, publish, save-all, save-off, save-on, stop, unpublish
