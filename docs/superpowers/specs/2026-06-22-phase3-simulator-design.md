# Phase 3: Simulator + Skills Redesign

## Goal

Replace the broken profile skill fields with the real Dank Memer skill system and build a `/simulate` command that calls the Dank Memer simulator API to show catch probability tables for a given setup.

## Architecture

Three interconnected pieces: (1) a DB migration adding a `skills` JSON column, (2) a 25-skill profile editor with 4-category pagination, and (3) a `/simulate` command with interactive selects, an Extras sub-view, a shared Skills picker, and results display. The Skills picker is shared between the profile flow and the simulator flow via a `return_to` callback.

## Tech Stack

- discord.py views + selects (existing pattern from Phase 2)
- `aiohttp` for the simulator API call (already used in the project)
- SQLite migration (new `002_skills_json.sql`)
- `data.json` for skill metadata (loaded at startup, no extra API call)

---

## Global Constraints

- Discord View max 5 rows; max 5 buttons per row; max 25 select options
- Select menus cannot live in modals — use `edit_message()` / ephemeral reply pattern
- Simulator API: `POST https://dankmemer.lol/api/bot/fish/simulator` with `Origin: https://dankmemer.lol` and `Referer: https://dankmemer.lol/fishing/simulator` headers (no auth required)
- Simulator API `skills` field format: `{"zoologist": 3, "haggler": 1}` — base skill name → tier integer; absent key means not unlocked
- `data.json` is the authoritative source for skill metadata (133 entries, 25 base skills, 4 categories)
- Peak Hours (24-call time sweep) is deferred to Phase 4
- All new DB columns use `ALTER TABLE … ADD COLUMN` — no table recreation

---

## Section 1: Database & Profile

### DB Migration (`migrations/002_skills_json.sql`)

```sql
ALTER TABLE users ADD COLUMN skills TEXT DEFAULT NULL;
```

The existing `fishing_skill`, `luck_skill`, `efficiency_skill` columns are abandoned in place (all values are 0; SQLite column drops require table recreation and are not worth the risk). They are removed from all display and editing code but remain in the schema as dead columns.

### Profile embed — skills field

The SKILLS section of the profile embed changes from `"Fishing: 0 · Luck: 0 · Efficiency: 0"` to a per-category listing:

```
Nature: Zoologist III, Keen Angler II
Economy: Haggler I
```

If `skills` is NULL or `{}`, display `"No skills unlocked"`. Only categories with at least one unlocked skill are shown.

### ProfileView button changes

- **"📊 Edit Skills"** → opens `SkillsPickerView` (see Section 3) with `return_to` callback that restores `ProfileView`
- **"📈 Edit Stats"** (new button, row 1) → opens `EditStatsModal` with two `TextInput` fields: Prestige and Coins
- `EditSkillsModal` is removed; `fishing_skill`, `luck_skill`, `efficiency_skill` fields are dropped from it

### `DankMemerGameClient` — skill data

At startup, load `data.json` and build:

```python
# skill_categories: dict[str, list[dict]]
# {"Economy": [{"base": "haggler", "name": "Haggler", "max_tier": 6}, ...], ...}
dc.skill_categories: dict[str, list[dict]]
```

Parsed by extracting the trailing `-N` from each skill `id` to derive `base` and `max_tier`.

---

## Section 2: Simulator Command

### `/simulate` command (`cogs/simulator.py`)

On invocation, load the calling user's profile from DB. Pre-fill:
- `location` from `favorite_location`
- `tool` from `current_tool`
- `bait` from `current_bait`
- `event` from `current_event`
- `boss_unlock` from `boss_unlock`
- `skills` from `skills` JSON field
- `time` = current UTC hour (0–23)
- `anglerTuesday`, `invasion`, `locationWinner` = `False`

Send an ephemeral reply with a "ready to calculate" embed + `SimulatorView`.

### SimulatorView layout

```
Row 0: Location select   (min_values=0, max_values=1, 14 options + "— None —")
Row 1: Tool select       (min_values=0, max_values=1, from dc.tool_by_id + "— None —")
Row 2: Bait select       (min_values=0, max_values=1, from dc.bait_by_id + "— None —")
Row 3: Event select      (min_values=0, max_values=1, from dc.event_by_id + "— None —")
Row 4: [🔄 Calculate] [👥 Skills] [⚙️ Extras] [🕐 Set Time] [🗑️ Delete]
```

Each select uses `min_values=0` so leaving it blank means "keep current value". Changing a select updates the view's internal state immediately but does not recalculate until `🔄 Calculate` is clicked.

### Button actions

- **🔄 Calculate**: build API payload from current state, call simulator API, update embed with results
- **👥 Skills**: call `interaction.response.edit_message(view=SkillsPickerView(..., return_to=self))`
- **⚙️ Extras**: call `interaction.response.edit_message(view=ExtrasView(..., parent=self))`
- **🕐 Set Time**: open `TimeModal` (single `TextInput`, validates 0–23 integer)
- **🗑️ Delete**: `interaction.message.delete()`

### ExtrasView layout

```
Row 0: anglerTuesday select  (Yes / No)
Row 1: invasion select       (Yes / No)
Row 2: locationWinner select (Yes / No)
Row 3: [✅ Save] [❌ Cancel]
```

Save updates the parent `SimulatorView`'s boolean fields and restores it via `edit_message`. Cancel restores without changing.

### Simulator API payload

```python
{
    "locationID": location_id,        # e.g. "river"
    "toolID": tool_id,                # e.g. "basic-fishing-rod"
    "baitsIDs": [bait_id] if bait_id else [],
    "time": utc_epoch_ms,             # int(datetime.utcnow().replace(hour=selected_hour, ...).timestamp() * 1000)
    "events": [event_id] if event_id else [],
    "bosses": bool(boss_unlock),
    "skills": skills_dict,            # {"zoologist": 3} or {}
    "bonusBossMultiplier": 1,
    "bonusMythicalMultiplier": 1,
    "forceTrash": False,
    "mythicalFishID": None,
    "discoveredCreatures": None,
    "anglerTuesday": angler_tuesday,
    "invasion": None,                 # None when False, object when active (Phase 4)
    "locationWinner": location_winner,
}
```

`invasion` is sent as `None` (no active invasion data) when the toggle is off, and also `None` when on for Phase 3 (the detailed invasion object is a Phase 4 concern). `anglerTuesday` and `locationWinner` are plain booleans.

### Results embed

```
🎣 Simulator — River · Basic Rod · No Bait · 14:00 UTC

❌ Fail: 12.3%   👤 NPC: 5.1%

Catch Table
───────────────────────────────
Bass              15.2%  (base 12.5%)
Trout              9.9%  (base  9.9%)
...
Misc Loot          2.1%  (base  2.1%)

Variants
───────────────────────────────
Bass — Unique: 0.5% · Chroma: 0.7%
```

Numeric item IDs (e.g. 244, 247, 251) from `reward.type == "loot"` are displayed as `"Misc Loot"`. Catch table is sorted by chance descending. Variants section only appears if any fish have non-zero variant chances.

### Simulate buttons in existing embeds

| Source embed | Pre-filled field | Immediate Calculate? |
|---|---|---|
| `/location` | location | Yes |
| `/tool` | tool | Yes |
| `/bait` | bait | Yes |
| `/fish` | none | No |

All four open an ephemeral `SimulatorView`. When pre-filling + immediate calculate, the bot defers the interaction, builds the initial payload, calls the API, and sends the ephemeral reply with the results embed already populated.

### History

Each successful Calculate call writes to the `history` table:

```python
{
    "type": "simulation",
    "item_id": location_id,           # or None if no location selected
    "data": json.dumps(api_response)
}
```

The existing `/history` Simulation tab displays rows as: `location name · time ago · fail %`.

---

## Section 3: Skills Picker UI (`SkillsPickerView`)

Shared between profile ("📊 Edit Skills") and simulator ("👥 Skills"). Constructed with:

```python
SkillsPickerView(db, member, dc, current_skills: dict, return_to_embed, return_to_view)
```

`current_skills` is the parsed `skills` JSON from DB (or `{}` if NULL). `return_to_embed` and `return_to_view` are restored on Save and Cancel.

### Layout

```
Row 0: [Economy] [Nature] [Science] [Social]   ← category tab buttons
Row 1: Skill select A
Row 2: Skill select B
Row 3: Skill select C
Row 4: [◀] [▶] [✅ Save] [❌ Cancel]
```

### Pagination

| Category | Skills | Pages |
|---|---|---|
| Economy | 6 | 2 (3 + 3) |
| Nature | 5 | 2 (3 + 2) |
| Science | 8 | 3 (3 + 3 + 2) |
| Social | 6 | 2 (3 + 3) |

`◀` / `▶` are disabled when at the first/last page of the current category. Navigation triggers `self.clear_items()` and rebuilds rows 0–4 dynamically.

### Each skill select

- `placeholder`: `"Haggler — Tier III"` if currently at tier 3, or `"Haggler — Not Unlocked"` if absent/0
- Options: `[("— Not Unlocked —", "0"), ("Tier I", "1"), ..., ("Tier N", "N")]`
- On change: `self._pending[base_name] = int(values[0])`
- Leaving a select untouched means the skill is not in `_pending` and will not be updated on Save

### Save behaviour

Merge `_pending` into `current_skills`: set tier if > 0, delete key if 0 (not unlocked). Write merged dict as JSON to `users.skills`. Then `edit_message(embed=return_to_embed, view=return_to_view)`.

### Cancel behaviour

`edit_message(embed=return_to_embed, view=return_to_view)` without writing to DB.

---

## Section 4: Remaining pieces

### Edit Stats modal

`EditStatsModal` has two `TextInput` fields:
- **Prestige** (placeholder: current value, validates non-negative integer)
- **Coins** (placeholder: current value, validates non-negative integer)

On submit, writes both to DB via `db.update_user(discord_id, prestige=..., coins=...)`.

### Simulation history tab

The `/history` command's Simulation tab (already exists as a tab in `HistoryView`) displays each `type='simulation'` row as:

```
River · 2 hours ago · ❌ 12.3%
```

`fail%` is extracted from `json.loads(row["data"])["failChance"]`.

---

## Files touched

| File | Change |
|---|---|
| `migrations/002_skills_json.sql` | New — adds `skills TEXT` column |
| `data/skill_loader.py` | New — loads skill category data from `data.json` |
| `utils/db.py` | Add `skills` field to `get_user`/`update_user`; run migration 002 |
| `utils/game_client.py` | Add `skill_categories` loaded from `data.json` at startup |
| `cogs/profile.py` | Remove `EditSkillsModal`; add `EditStatsModal`; import `SkillsPickerView` from `cogs/simulator`; update profile embed skills display; update `ProfileView` buttons |
| `cogs/simulator.py` | Full implementation: `SimulatorView`, `ExtrasView`, `TimeModal`, `SkillsPickerView`, `/simulate` command |
| `cogs/fish.py` | Enable Simulate button (pre-fill none, no immediate calculate) |
| `cogs/location.py` | Enable Simulate button (pre-fill location, immediate calculate) |
| `cogs/tools.py` | Enable Simulate button (pre-fill tool, immediate calculate) |
| `cogs/baits.py` | Enable Simulate button (pre-fill bait, immediate calculate) |
| `utils/embeds.py` | Update simulation history tab row format to show fail% |
| `tests/test_simulator_cog.py` | New — tests for SimulatorView, ExtrasView, SkillsPickerView, API payload construction |
| `tests/test_profile_cog.py` | Update: remove EditSkillsModal tests; add SkillsPickerView and EditStatsModal tests |
