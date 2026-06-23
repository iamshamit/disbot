# Phase 7 — Search & Discovery + Encyclopedia Enhancements Design
**Date:** 2026-06-23
**Scope:** `/searchfish`, `/searchlocation`, `/creatures`, `/fish` tool section, `/fishlist` new filters, `/tool` fish section, simulator weather cleanup
**Bot:** DankFishingBot · discord.py 2.x · SQLite · dankmemer>=1.0.0rc2

---

## 1. Context

Phases 1–6 delivered the full encyclopedia, simulator, profile system, and utility commands.
Phase 7 adds three new search/discovery commands and fills in missing encyclopedia fields.
No new DB tables, no new dependencies.

**Confirmed removals:**
- `/weather` — no weather mechanic in Dank Memer
- Disabled weather selects in `SimulatorView` — clutter for a non-existent feature
- "Related Fish" — not in `data.json`; skipped

---

## 2. Architecture

**New file:** `cogs/search.py` — `/searchfish`, `/searchlocation`, `/creatures`

**Modified files:**

| File | What changes |
|------|-------------|
| `utils/embeds.py` | Add `emoji_from_url()` helper; update `build_fish_embed`, `build_tool_embed`, `build_fish_compare_embed` |
| `cogs/fish.py` | `FishListView` gains Tool filter (row 3) and Type flags filter (row 4); update selects to use `emoji_from_url` |
| `cogs/simulator.py` | Remove disabled weather selects from `SimulatorView` |
| `tests/test_search_cog.py` | New test file |
| `tests/test_fish_cog.py` | Tests for new embed fields and fishlist filters |
| `tests/test_tools_cog.py` | Tests for new tool embed fields |

**No new DB migrations. No new dependencies.**

---

## 3. Global UI Rule — Emoji in Select Options

All `discord.SelectOption` instances for game items use their actual in-game emoji via
`discord.PartialEmoji` extracted from the item's `imageURL`.

Discord CDN emoji URLs follow the pattern:
`https://cdn.discordapp.com/emojis/{id}.png` or `.gif`

**Helper added to `utils/embeds.py`:**

```python
import re as _re

def emoji_from_url(url: str | None) -> discord.PartialEmoji | None:
    if not url:
        return None
    m = _re.search(r'/emojis/(\d+)\.(png|gif)$', url)
    if not m:
        return None
    return discord.PartialEmoji(name='_', id=int(m.group(1)), animated=m.group(2) == 'gif')
```

Applied in: all fish selects, tool selects, bait selects, location selects — everywhere a
`discord.SelectOption` is constructed for a game item.

---

## 4. Encyclopedia Enhancements

### 4.1 `/fish` embed — new TOOLS section

**Data source:** `fish.extra["tools"]` — dict of `{tool_id: {min: int, max: int}}`

Add a new section after LOCATIONS in `build_fish_embed`:

```
────────────────────────
🔧 TOOLS  (N)
[emoji] Tool Name — 1–3  ⭐ Best
[emoji] Tool Name — 1–1
...
📍 Best Location: [emoji] Location Name  (fail: X%)
```

**Best Tool:** tool(s) with the highest `max` value — ties all get ⭐.
**Best Location:** among locations where this fish appears (`fish.extra["locations"]`),
the one with the lowest `failChance` in `location.extra["failChance"]`.
If tie on fail chance, pick first alphabetically.

**Lookup:** `dc.tool_by_id[tool_id].name` and `dc.tool_by_id[tool_id].imageURL` for emoji.

### 4.2 `/fishlist` — new filter rows

Current rows: row 0 = pagination, row 1 = sort, row 2 = rarity filter.

**Add row 3 — Tool filter:**
```python
@discord.ui.select(placeholder="🔧 Filter Tool ▾", row=3, options=[...])
```
Options: "All tools" + one option per tool using `emoji_from_url(tool.imageURL)`.
Filter logic: `tool_id in fish.extra.get("tools", {})`.

**Add row 4 — Type flags:**
```python
@discord.ui.select(placeholder="🏷️ Filter Type ▾", row=4, options=[...])
```
Options:
- `All` (default)
- `✨ Has Variants` — `fish.extra.get("variants")`
- `✅ Available Now` — `is_available_now(fish)` at current UTC hour
- `👑 Boss` — `fish.extra.get("boss")`
- `⭐ Mythical` — `fish.extra.get("mythical")`

Note: rarity filter already covers Boss and Mythical as separate options, but this row
provides a quick single-click flag filter independent of rarity.

**`_refresh()` update:** apply tool_filter and type_filter on top of existing rarity/sort logic.

### 4.3 `/tool` embed — new FISH section

**Data source:** Computed at call time by scanning `dc.fish_by_id.values()` for fish
where `tool_id in fish.extra.get("tools", {})`.

Add a new section after BUFFS/DEBUFFS in `build_tool_embed`:

```
────────────────────────
🐟 SUPPORTED FISH  (N)
Best: [emoji] Fish Name (Rarity) — catches 2–4
[emoji] Fish 1 — 1–1
[emoji] Fish 2 — 1–3
[emoji] Fish 3 — 1–1
... (up to 12, then "… and N more")
```

**Best Fish:** highest-rarity fish this tool can catch (use `rarity_rank()` from `utils/formatters.py`).

`build_tool_embed` gains a second parameter `dc` (the dank client) to do the lookup.
All callers updated accordingly.

### 4.4 `/fishcompare` embed — 2 new rows

Add to `build_fish_compare_embed`:
- **Best Tool** row: name of best tool (highest max) for each fish — ✓ on winner (or tie)
- **Max Catch** row: the best tool's max catch value — ✓ on higher value

### 4.5 `/bait` embed

Already complete — `idle`, `explanation`, `flavor`, `usage` all shown. **No changes.**

---

## 5. Search Commands — `cogs/search.py`

Discord select menus are limited to 25 options, so search commands use paginated
in-message **filter** selects (rarity, tool, type) — not per-fish selects. Users set
filters and browse the paginated result list.

`is_available_now` and `rarity_rank` are both in `utils/formatters.py` — import from there.

### 5.2 `/searchfish`

**Command:** `/searchfish` — no required arguments. Opens an interactive view.

**`SearchFishView(DynamicPaginationView)`:**

```python
class SearchFishView(DynamicPaginationView):
    ITEMS_PER_PAGE = 10

    def __init__(self, dank_client):
        super().__init__()
        self.dc = dank_client
        self.rarity_filter = "All"
        self.tool_filter = "All"
        self.type_filter = "All"
        self._refresh()
```

**Rows:**
- Row 0: Prev · Page N/M · Next (from `DynamicPaginationView`)
- Row 1: Rarity select — All + each rarity + Boss + Mythical (with rarity emojis)
- Row 2: Tool select — All + each tool (with `emoji_from_url(tool.imageURL)`)
- Row 3: Type flags — All / ✨ Has Variants / ✅ Available Now
- Row 4: Delete button

**Filter logic (`_refresh`):**
```python
creatures = list(self.dc.fish_by_id.values())
if self.rarity_filter == "Boss":
    creatures = [c for c in creatures if c.extra.get("boss")]
elif self.rarity_filter == "Mythical":
    creatures = [c for c in creatures if c.extra.get("mythical")]
elif self.rarity_filter != "All":
    creatures = [c for c in creatures if c.extra.get("rarity") == self.rarity_filter]
if self.tool_filter != "All":
    creatures = [c for c in creatures if self.tool_filter in c.extra.get("tools", {})]
if self.type_filter == "Has Variants":
    creatures = [c for c in creatures if c.extra.get("variants")]
elif self.type_filter == "Available Now":
    creatures = [c for c in creatures if is_available_now(c)]
creatures.sort(key=lambda c: c.name.lower())
```

**Result embed `build_search_fish_embed(creatures, page, total_pages, filters)`:**
- Title: `🔍 Fish Search`
- Each line: `[emoji] **Name** · Rarity · N locations`
- Footer: `Page N/M · X results`
- If 0 results: description = "No fish match these filters."

### 5.3 `/searchlocation`

**Command:** `/searchlocation` — no required arguments.

**`SearchLocationView(discord.ui.View)`:**

No pagination needed — 14 locations fit on one embed.

```python
class SearchLocationView(discord.ui.View):
    def __init__(self, dank_client):
        super().__init__(timeout=300)
        self.dc = dank_client
        self.type_filter = "All"
        self.sort = "name"
        self.message: discord.Message | None = None
```

**Rows:**
- Row 0: Type select — All / 🌊 Saltwater / 🏞️ Freshwater
- Row 1: Sort select — By Name / By Fish Count ↓ / By Fail Chance ↑ / By Mine Chance ↓
- Row 2: Delete button

**`on_timeout`:** disable children, `await self.message.edit(view=self)` guarded with try/except.

**Result embed `build_search_location_embed(locations, type_filter, sort)`:**
- Title: `🔍 Location Search`
- Each line: `[emoji] **Name** · 🐟 N fish · 💀 Fail X% · ⛏️ Mine X%`
- Type badge: `🌊` or `🏞️` after name
- Footer: `N locations`

**Filter + sort logic:**
```python
locs = list(self.dc.location_by_id.values())
if self.type_filter != "All":
    locs = [l for l in locs if l.extra.get("type") == self.type_filter.lower()]
if self.sort == "fish_count":
    locs.sort(key=lambda l: -len(l.extra.get("creatures", [])))
elif self.sort == "fail_asc":
    locs.sort(key=lambda l: l.extra.get("failChance", 0))
elif self.sort == "mine_desc":
    locs.sort(key=lambda l: -l.extra.get("mineChance", 0))
else:
    locs.sort(key=lambda l: l.name.lower())
```

### 5.4 `/creatures`

**Command:** `/creatures` — no required arguments.

Reuses `SearchFishView` — same class, same view, same filters. `/creatures` is a distinct
entry point with a different embed title (`🦎 Creatures`) and author line (`Browse all 153 creatures`).

Implementation: the `/creatures` command handler creates a `SearchFishView` instance but
passes `title="🦎 Creatures"` to the embed builder. One parameter on `build_search_fish_embed`
controls the title.

---

## 6. Simulator Cleanup

Remove the two `disabled=True` selects from `cogs/simulator.py`:

1. In `SimulatorView._build_selects()`: locate the select with `disabled=True` and `row=2` — this is the weather select. Remove it entirely.
2. In `PeakHoursView`: same — remove the `disabled=True` row=2 select.

After removal, verify row numbering of remaining selects is still correct (no gaps that break Discord's layout).

---

## 7. Error Handling

- All commands: guard with `if not dc.fish_by_id` → ephemeral `EmbedBuilder.error`
- `/searchfish` / `/creatures` with 0 results: show "No fish match these filters." in embed body (not an error)
- `/searchlocation` with 0 results (all filtered out): show "No locations match." in embed body
- `emoji_from_url` returns `None` on any parse failure — callers pass it as `emoji=None` (Discord renders no emoji rather than crashing)
- `build_tool_embed` dc lookup: if `tool_id` not in `dc.tool_by_id`, skip that tool silently

---

## 8. Testing

All new tests in `tests/test_search_cog.py`, embed tests in existing test files.

| Test | File | Covers |
|------|------|--------|
| `test_emoji_from_url_png` | `tests/test_search_cog.py` | Returns correct PartialEmoji id, animated=False |
| `test_emoji_from_url_gif` | `tests/test_search_cog.py` | Returns PartialEmoji with animated=True |
| `test_emoji_from_url_none` | `tests/test_search_cog.py` | Returns None for missing/invalid URL |
| `test_build_search_fish_embed_shows_results` | `tests/test_search_cog.py` | Embed has fish names in description |
| `test_build_search_fish_embed_zero_results` | `tests/test_search_cog.py` | Shows "No fish match" message |
| `test_build_search_location_embed_shows_all` | `tests/test_search_cog.py` | All locations listed |
| `test_search_fish_tool_filter` | `tests/test_search_cog.py` | Filter by tool returns only fish that support it |
| `test_search_fish_rarity_filter` | `tests/test_search_cog.py` | Filter by rarity returns correct subset |
| `test_search_fish_type_filter_variants` | `tests/test_search_cog.py` | Has Variants filter correct |
| `test_search_location_type_filter` | `tests/test_search_cog.py` | Saltwater/freshwater filter correct |
| `test_search_location_sort_fail_asc` | `tests/test_search_cog.py` | Sort by fail chance ascending |
| `test_fish_embed_tools_section` | `tests/test_fish_cog.py` | TOOLS section present, best tool marked |
| `test_fish_embed_best_location` | `tests/test_fish_cog.py` | Best Location = lowest fail chance among fish's locations |
| `test_tool_embed_fish_section` | `tests/test_tools_cog.py` | SUPPORTED FISH section present, best fish correct |
| `test_fishlist_tool_filter` | `tests/test_fish_cog.py` | Tool filter narrows to correct fish |
| `test_fishlist_type_flag_available_now` | `tests/test_fish_cog.py` | Available Now filter uses current UTC hour |

---

## 9. Out of Scope

- "Related Fish" — no data backing, skipped
- `/weather` — no weather mechanic in Dank Memer
- Weather dropdown in simulator — removed as cleanup
- Best Location computed via simulation engine — uses fail chance heuristic instead (faster, no engine call)
- `/fishlist` search-by-name text input — existing `/fishlist` already supports search; `/searchfish` handles multi-filter
- Profit / XP per fish — no sell price data in `data.json`
