# Phase 1 — Encyclopedia Design Spec
**Date:** 2026-06-21
**Scope:** Fish, Location, Tool, Bait, NPC lookup commands
**Bot:** DankFishingBot · discord.py 2.x · SQLite · dankmemer>=1.0.0rc2

---

## 1. Context

The bot infrastructure is complete (bot setup, DankMemerGameClient, SQLite migrations, logging,
autocomplete index, EmbedBuilder). All cogs are empty stubs. Phase 1 fills in the encyclopedia
layer: read-only commands that surface the Dank Memer game data with rich UI.

Deployment: WispByte.com · 512 MB RAM · 1–5 servers max.

---

## 2. Scope

### Commands delivered in Phase 1

| Command | Description |
|---------|-------------|
| `/fish <name>` | Fish detail embed + interactive buttons |
| `/fishlist` | Paginated fish index with sort + rarity filter |
| `/fishcompare <fish1> <fish2>` | Side-by-side fish comparison |
| `/location <name>` | Location detail + fish pool select menu |
| `/locations` | Paginated location index with sort + filter |
| `/locationcompare <loc1> <loc2>` | Side-by-side location comparison |
| `/tool <name>` | Tool detail embed |
| `/toolcompare` | All-tools comparison (no params, ~8 tools) |
| `/bait <name>` | Bait detail embed |
| `/baitcompare <bait1> <bait2>` | Side-by-side bait comparison |
| `/npc <name>` | NPC detail embed |
| `/stats` | Updated bot statistics (already partially live) |

### Out of scope for Phase 1
- `/profile`, `/favorites`, `/history`, `/settings` → Phase 2
- `/simulate`, `/optimizer`, `/planner`, `/weather`, `/event`, `/time`, `/today` → Phase 3+
- Notifications, import/export → Phase 5

---

## 3. API Data Model

All data is preloaded at startup into `DankMemerGameClient` lookup dicts and never re-fetched
within a session (1-hour TTL on the underlying `DankMemerClient` cache).

### Creature (fish)
```
id          str
name        str
imageURL    str
extra:
  boss      bool
  mythical  bool
  rarity    str    — "Common" | "Uncommon" | "Rare" | "Very Rare" | "Absurdly Rare" | "Mythical"
  flavor    str
  locations list[str]   — location IDs
  time:
    start   datetime.time (UTC)
    end     datetime.time (UTC)
    full_day bool
  variants  list[dict]  — optional; each dict has name + chance fields
```
Method: `creature.get_availability_window()` → `(start_dt, end_dt)`.

### Location
```
id           str
name         str
imageURL     str
extra:
  bannerURL    str
  thumbnailURL str
  creatures    list[str]   — creature IDs in this location
  days         list[int]   — 0–6; empty = all days
  disabled     bool
  temporary    bool
  failChance   int         — percent
  mineChance   int         — percent
  npcs         list[str]   — NPC names
rarityFish   dict[str, list[str]]  — rarity → creature IDs
variantsData dict[str, Any]        — variant multiplier data
```

### Tool
```
id      str
name    str
imageURL str
extra:
  flavor  str
  baits   bool   — supports bait
  buffs   list[dict]   — each: {name, ...}
  debuffs list[dict]   — each: {name, ...}
  usage   int
```

### Bait
```
id      str
name    str
imageURL str
extra:
  flavor      str
  explanation str
  idle        bool
  usage       int
```

### NPC
Fields confirmed at startup from `npc_by_id` preload. Expected: `id`, `name`, `imageURL`,
and `extra` containing description and location data. Actual field names resolved at
implementation time from live API response.

---

## 4. File Structure

```
cogs/
  fish.py         — FishCog + FishView + FishListView + FishCompareView
  locations.py    — LocationsCog + LocationView + LocationsListView + LocationCompareView
  tools.py        — ToolsCog + ToolView + ToolCompareView
  baits.py        — BaitsCog + BaitView + BaitCompareView
  npcs.py         — NpcsCog (no custom views)
  core.py         — CoreCog (ping + stats — update existing)
  encyclopedia.py — DELETE (was a stub, replaced by fish.py)
  profile.py      — keep stub
  simulator.py    — keep stub

utils/
  embeds.py       — extend: add build_fish_embed, build_location_embed,
                    build_tool_embed, build_bait_embed, build_npc_embed,
                    build_fish_compare_embed, build_location_compare_embed,
                    build_bait_compare_embed, build_peak_hours_embed
  views.py        — extend: add PaginationView base class
  formatters.py   — NEW: availability_bar, progress_bar, rarity_emoji,
                    rarity_color, is_available_now, format_time_window,
                    bold_winner (for compare tables)
  autocomplete.py — populate fish/location/tool/bait autocomplete (already stubbed)
  pagination.py   — keep as-is (unused; absorbing it is out of scope for Phase 1)
  db.py           — unchanged
  logging_config.py — unchanged
```

Views are defined in the cog file that owns them. `utils/views.py` holds only
`PaginationView` (the shared paginator base). No cross-cog view imports.

---

## 5. Visual Design System

### Embed Colour by Entity / Rarity

```python
RARITY_COLORS = {
    "Common":        0x8e9297,   # Discord grey
    "Uncommon":      0x57f287,   # green
    "Rare":          0x5865f2,   # blurple
    "Very Rare":     0xeb459e,   # fuchsia
    "Absurdly Rare": 0xed4245,   # red
    "Mythical":      0xffd700,   # gold
}
BOSS_COLOR     = 0xff6b35   # orange-red (overrides rarity if boss=True)
LOCATION_COLOR = 0x00b4d8   # ocean blue
TOOL_COLOR     = 0xff9500   # amber
BAIT_COLOR     = 0x95d44a   # lime
NPC_COLOR      = 0xb967ff   # violet
COMPARE_COLOR  = 0x5865f2   # blurple
```

### Rarity Emojis

```python
RARITY_EMOJI = {
    "Common":        "⚪",
    "Uncommon":      "🟢",
    "Rare":          "🔵",
    "Very Rare":     "🟣",
    "Absurdly Rare": "🔴",
    "Mythical":      "🌟",
}
```

### Progress / Availability Bars

`formatters.progress_bar(value, total, width=20)` → `████████░░░░░░░░░░░░  40%`

`formatters.availability_bar(start_h, end_h, width=24)` → `▐███████░░░░░░░░░░░░░░░░▌`

Uses Unicode block `█` (U+2588) and light shade `░` (U+2591).

---

## 6. Command Designs

### 6.1 `/fish <name>`

**Autocomplete:** fish names from `AutocompleteIndex`.

**Embed:**
```
Color:       rarity color (BOSS_COLOR if boss=True)
Author:      "🐟 Fish Encyclopedia"
Thumbnail:   creature.imageURL
Title:       creature.name
Description:
  "<flavor text>"

  {rarity_emoji} {rarity}  ·  👑 Boss: ✅/❌  ·  ✨ Mythical: ✅/❌

  ─────────────────────────────────────
  🕐 AVAILABILITY
  ▐{availability_bar}▌  {start}–{end} UTC  ·  {hours}h
  Right now: ✅ Available  /  ❌ Not available  (omit if full_day)

  ─────────────────────────────────────
  📍 LOCATIONS  ({n})
  {name}  ·  {name}  ·  …

  ─────────────────────────────────────  (omit section if no variants)
  🔮 VARIANTS  ({n})
  ✨ {variant_name}  ·  💎 {variant_name}  …

  ─────────────────────────────────────
Footer: "Internal ID: {creature.id}"
```

**Buttons:**
```
Row 1:  [🕐 Peak Hours]  [🔮 Variants]  [📍 Locations]
Row 2:  [⚔️ Compare]  [🤍 Favourite · disabled]  [🎮 Simulate · disabled]  [🗑️ Delete]
```
- Variants button hidden if `extra.variants` is empty/absent.
- All button callbacks call `interaction.response.edit_message(embed=new_embed, view=self)`.
- Delete: `await interaction.message.delete()`.
- Compare: opens `FishCompareModal` (text input for second fish name) → on submit,
  calls `build_fish_compare_embed` and edits message.

**Peak Hours sub-embed** (replaces main embed content on button click):
```
🕐 PEAK HOURS — {name}

`00 01 02 03 04 05 06 07 08 09 10 11`
` ✅  ✅  ✅  ✅  ✅  ✅  ✅  ❌  ❌  ❌  ❌  ❌`

`12 13 14 15 16 17 18 19 20 21 22 23`
` ❌  ❌  ❌  ❌  ❌  ❌  ❌  ❌  ❌  ❌  ❌  ❌`

Window: {start} – {end} UTC  ({hours}h)
Current UTC: {HH:MM}  →  ✅/❌  [{hour highlighted with [ ]}]
```
A `[↩ Back]` button restores the original fish embed.

---

### 6.2 `/fishlist`

**Items per page:** 10
**Each row:**
```
{rarity_emoji} **{name}**  ·  {boss_badge}{mythical_badge}  ·  ✅/❌ now
```
Boss badge: `👑 BOSS` · Mythical badge: `✨ MYTHICAL` · shown only when true.

**Embed header:**
```
Color:       rarity filter colour (COMPARE_COLOR if "All")
Author:      "🐟 Fish Encyclopedia"
Title:       "All Fish  (N total)"  or  "⚪ Common Fish  (N)"  etc.
Description: one row per fish (10 per page)
Footer:      "Page {page} / {total}  ·  Sort: {sort}  ·  Filter: {filter}"
```

**Controls:**
```
Row 1:  [◀ Prev]  [Page 1 / N  ○]  [▶ Next]
           (middle button opens JumpModal — user types page number)
Row 2:  [📊 Sort ▾]          — select: Alphabetical / Rarity (asc) / Rarity (desc)
Row 3:  [🔍 Filter Rarity ▾] — select: All / Common / Uncommon / Rare / Very Rare /
                                        Absurdly Rare / Mythical / Boss / Mythical only
```

State (sort, filter, page) held in the `FishListView` instance. Each select/button
interaction calls `interaction.response.edit_message` with a rebuilt embed + same view.
View timeout: 5 minutes.

---

### 6.3 `/fishcompare <fish1> <fish2>`

Both params use autocomplete. Also callable via Compare button inside `/fish`.

**Embed:**
```
Color:  COMPARE_COLOR
Title:  ⚔️ {fish1.name}  vs  {fish2.name}
Description (code block for monospace alignment):

  ┌──────────────┬────────────────┬────────────────┐
  │              │ {fish1.name}   │ {fish2.name}   │
  ├──────────────┼────────────────┼────────────────┤
  │ Rarity       │ ⚪ Common      │ 🔵 Rare  ✓     │
  │ Boss         │ ❌             │ ❌             │
  │ Mythical     │ ❌             │ ✅  ✓          │
  │ Window       │ 00:00–07:00    │ All Day  ✓     │
  │ Hours        │ 7h             │ 24h  ✓         │
  │ Locations    │ 3              │ 5  ✓           │
  │ Variants     │ 2  ✓          │ 1              │
  └──────────────┴────────────────┴────────────────┘
```
`✓` marks the superior value per row. Ties show no marker.
Rarity rank order: Common < Uncommon < Rare < Very Rare < Absurdly Rare < Mythical.

---

### 6.4 `/location <name>`

**Embed:**
```
Color:       LOCATION_COLOR
Author:      "📍 Location"
Image:       extra.bannerURL   (full-width at bottom of embed)
Thumbnail:   extra.thumbnailURL
Title:       location.name
Description:
  {status_line}  — "🔴 Temporary" / "⛔ Disabled" / "" (active)

  🌊 STATISTICS
  💀 Fail: **{failChance}%**   ⛏️ Mine: **{mineChance}%**   🐟 Pool: **{n} fish**

  🌈 RARITY DISTRIBUTION
  ⚪ Common    {progress_bar}  {pct}%
  🟢 Uncommon  {progress_bar}  {pct}%
  🔵 Rare      {progress_bar}  {pct}%
  …

  👤 NPCs  (omit if none)
  {npc}  ·  {npc}  …

Footer: "Internal ID: {location.id}"
```

**Select menu** (above buttons, up to 25 options):
`[Fish Pool: Choose a creature… ▾]`
Each option: `{rarity_emoji} {fish_name}  ·  ✅/❌ now`
If pool > 25, show top 25 sorted by rarity desc with footer note "Showing 25 of N".
On select: edits embed to show inline fish detail (same layout as `/fish` embed minus buttons
section, plus a `[↩ Back to Location]` button).

**Buttons:**
```
Row 1: [🔗 Open Fish]  [⚔️ Compare]  [🎮 Simulate · disabled]  [🤍 Fav · disabled]  [🗑️ Delete]
```
- Open Fish: posts fish embed for currently-selected creature as a new ephemeral message.
- Compare: `LocationCompareModal` → edits to comparison embed.

---

### 6.5 `/locations`

**Items per page:** 8
**Each row:**
```
📍 **{name}**  ·  🐟 {fish_count}  ·  💀 {fail}%  ·  {status_badges}
```
Status badges: `🔴 Temp` / `⛔ Disabled` — shown only when true.

**Controls:**
```
Row 1: [◀ Prev]  [Page N / M ○]  [▶ Next]
Row 2: [📊 Sort ▾]    — Name / Fish Count / Fail Chance / Mine Chance
Row 3: [🔍 Filter ▾]  — All / Active / Temporary / Disabled
```

---

### 6.6 `/locationcompare <loc1> <loc2>`

**Compared fields:** Fish Count, Fail Chance, Mine Chance, Rarity pool breakdown (Common /
Rare / Boss / Mythical counts), Temporary, Disabled.
Superior value bolded with ✓. Lower fail/mine chance = better (marked accordingly).

---

### 6.7 `/tool <name>`

**Embed:**
```
Color:       TOOL_COLOR
Author:      "🔧 Tool"
Thumbnail:   tool.imageURL
Title:       tool.name
Description:
  "<flavor text>"

  ─────────────────────────────────────
  ✨ BUFFS
  • {buff.name}
  …  (omit section if empty)

  ─────────────────────────────────────
  💢 DEBUFFS
  • {debuff.name}
  …  (omit section if empty)

  ─────────────────────────────────────
  🪱 Bait Support: ✅/❌   ·   📊 Usage: {usage}
```

**Buttons:**
```
Row 1: [⚔️ Compare]  [🎮 Simulate · disabled]
```
Compare: `ToolCompareModal` for second tool name → edits to comparison embed.

---

### 6.8 `/toolcompare`

No parameters. Shows all tools (~8) in a single embed.

**Embed:**
```
Color:  COMPARE_COLOR
Title:  ⚔️ Tool Comparison
Description (code block):

  Tool           │ Baits │ Usage │ Buffs │ Debuffs
  ───────────────┼───────┼───────┼───────┼────────
  Fishing Rod    │  ✅   │  100  │   2   │   1
  Harpoon        │  ❌   │   50  │   1   │   0
  …
```

---

### 6.9 `/bait <name>`

**Embed:**
```
Color:       BAIT_COLOR
Author:      "🪱 Bait"
Thumbnail:   bait.imageURL
Title:       bait.name
Description:
  "<flavor text>"

  ─────────────────────────────────────
  💡 WHAT IT DOES
  {explanation}

  ─────────────────────────────────────
  🤖 Idle Compatible: ✅/❌   ·   📊 Usage: {usage}
```

**Buttons:**
```
Row 1: [⚔️ Compare]  [🎮 Simulate · disabled]
```

---

### 6.10 `/baitcompare <bait1> <bait2>`

**Compared fields:** Idle Compatible, Usage, Explanation (shown side-by-side as text, not as a
winner/loser table — explanation is qualitative).

---

### 6.11 `/npc <name>`

**Embed:**
```
Color:       NPC_COLOR
Author:      "👤 NPC"
Thumbnail:   npc.imageURL
Title:       npc.name
Description:
  {description or flavor from extra — exact field name resolved at implementation}

  ─────────────────────────────────────
  📍 FOUND IN
  {location names resolved from npc location data}
```

No buttons. Informational only.

---

### 6.12 `/stats` (update existing)

Add to existing embed:
- Fish count, Location count, Tool count, Bait count, NPC count
- Cache status (preload complete ✅ / in progress ⏳ / failed ❌)
- Bot uptime

---

## 7. Shared Utilities

### `utils/formatters.py` (new)

```python
def rarity_color(rarity: str, boss: bool = False) -> int: ...
def rarity_emoji(rarity: str) -> str: ...
def progress_bar(value: int, total: int, width: int = 20) -> str: ...
def availability_bar(start_h: int, end_h: int, full_day: bool, width: int = 24) -> str: ...
def is_available_now(creature) -> bool: ...
def format_time_window(creature) -> str: ...  # "00:00–07:00 UTC  ·  7h" or "All Day"
def bold_winner(a, b, higher_is_better: bool = True) -> tuple[str, str]: ...
```

### `utils/views.py` — `PaginationView` base

```python
class PaginationView(discord.ui.View):
    page: int
    total_pages: int
    async def prev_page(interaction): ...
    async def next_page(interaction): ...
    async def jump_page(interaction): ...  # opens JumpModal
    async def rebuild_embed(self) -> discord.Embed: ...  # abstract
```

Each list view (`FishListView`, `LocationsListView`) subclasses `PaginationView` and
implements `rebuild_embed` with its own sort/filter state.

### `utils/autocomplete.py` — populate existing `AutocompleteIndex`

Add/confirm methods:
```python
async def fish_autocomplete(interaction, current: str) -> list[Choice]: ...
async def location_autocomplete(interaction, current: str) -> list[Choice]: ...
async def tool_autocomplete(interaction, current: str) -> list[Choice]: ...
async def bait_autocomplete(interaction, current: str) -> list[Choice]: ...
async def npc_autocomplete(interaction, current: str) -> list[Choice]: ...
```

Returns up to 25 `app_commands.Choice` items filtered by `current` prefix (case-insensitive).
The index is populated once at startup from preloaded data.

---

## 8. Error Handling

All commands wrapped by the existing `_tree_error_handler` in `bot.py`.

Additional per-command guard: if `dank_client.fish_by_id` is empty (preload still running),
respond with an ephemeral embed: `"⏳ Data is still loading, please try again in a moment."`.

If a name lookup returns `None` (entity not found), respond with:
`"❌ No fish named **{name}** found. Try /fishlist to browse."` (ephemeral embed).

---

## 9. Cross-Reference Data

Some display fields require cross-referencing two data sources. These are computed once
at startup and stored on `DankMemerGameClient`:

```python
# Populated in preload() after both creatures and locations are loaded:
self.location_creature_map: dict[str, list[Creature]] = {}
# key = location_id, value = resolved Creature objects from location.extra.creatures

# Fish → location names (for /fish Locations display):
# Derived on the fly from creature.extra.locations → location_by_id[id].name
# No extra dict needed — O(n) lookup over a small list per request is fine.
```

---

## 10. Constraints & Notes

- **Discord limits:** 25 select options, 5 action rows, 5 buttons per row, 4096 char description,
  25 embed fields, 6000 total embed chars. All displays must respect these.
- **View timeout:** 5 minutes on all interactive views. On timeout, buttons are disabled in place
  (override `on_timeout` to call `message.edit(view=disabled_view)`).
- **"Best tool per fish"** and **"catch amount per tool"** are not present in the API.
  These fields are omitted in Phase 1 rather than fabricated.
- **Saltwater/freshwater** classification is not in the API. Omitted in Phase 1.
- **Location fish pool > 25:** show top 25 by rarity (rarest first), note "Showing 25 of N"
  in select menu placeholder.
- **NPC field names:** confirmed at implementation time from live `npc_by_id` data.
  If description/location fields differ from expected, display whatever is available.
- The `encyclopedia.py` stub cog must be deleted before new cogs are loaded, or the bot
  will register a duplicate `/fish` command.
