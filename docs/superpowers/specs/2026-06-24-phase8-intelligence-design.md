# Phase 8 — Intelligence Commands Design
**Date:** 2026-06-24
**Scope:** `/optimizer`, `/planner`, enhanced `/today`
**Bot:** DankFishingBot · discord.py 2.x · SQLite · dankmemer>=1.0.0rc2

---

## 1. Context

Phases 1–7 delivered the full encyclopedia, simulator, profile system, utility commands, and search/discovery layer. Phase 8 adds three intelligence features that reason over the game data to give users actionable recommendations.

**Explicitly out of scope (deferred to Phase 9):**
- DM bot `on_message` listener for auto-detecting active events
- Fish Skills message parser for auto-syncing skill tiers to DB
- Both require per-server channel config and background task infrastructure — Phase 9's domain

**No new DB tables. No new dependencies.**

---

## 2. Architecture

**New files:**

| File | Responsibility |
|------|---------------|
| `utils/optimizer.py` | Pure recommendation functions — no Discord imports; shared by all three features |
| `cogs/intelligence.py` | `IntelligenceCog` with `/optimizer` and `/planner` commands |
| `tests/test_optimizer.py` | Unit tests for pure optimizer functions |
| `tests/test_intelligence_cog.py` | Integration tests for the new cog |

**Modified files:**

| File | What changes |
|------|-------------|
| `cogs/utilities.py` | `_build_today_embed` gains two new fields; `/today` passes tool/bait from DB row |
| `tests/test_utilities_cog.py` | Tests for the two new `/today` fields |

**Key design principle:** Recommendation logic lives in `utils/optimizer.py` as pure functions `(dc, hour, ...) → results`. Cogs handle only Discord presentation. Pure functions are testable without any Discord mocking.

**Engine foundation:** `fishing_engine.creature_eligible(fish, location_id, tool_id, hour)` + `RARITY_WEIGHTS` provide all eligibility and weighting data needed. Bait does not affect which fish are catchable — only weight distribution — so the optimizer ranks by tool+location, and bait is surfaced as a secondary note.

---

## 3. `utils/optimizer.py`

Three pure functions:

### `score_setup(dc, tool_id, location_id, hour) → float`

Scores a tool+location combo at a given hour. Returns the sum of `RARITY_WEIGHTS[rarity]` for every fish where `creature_eligible(fish, location_id, tool_id, hour, bosses=False, ignore_time=False)` is True.

```python
def score_setup(dc, tool_id: str, location_id: str, hour: int) -> float:
    total = 0.0
    for fish in dc.fish_by_id.values():
        if creature_eligible(fish, location_id, tool_id, hour, bosses=False, ignore_time=False):
            rarity = fish.extra.get("rarity", "")
            total += RARITY_WEIGHTS.get(rarity, 0.0)
    return total
```

### `best_setups(dc, hour, target_fish_id=None, limit=3) → list[dict]`

Iterates all `(tool_id, location_id)` pairs from `dc.tool_by_id × dc.location_by_id`. Skips pairs with score 0 (nothing catchable). If `target_fish_id` is given, further filters to pairs where the target fish is eligible. Sorts by `score_setup` descending, returns top `limit` as dicts:

```python
{
    "tool": tool_obj,
    "location": location_obj,
    "score": float,
    "target_eligible": bool,  # always True when target_fish_id given
}
```

When `target_fish_id` is given, eligibility for the target fish uses `bosses=True` (so boss fish targets work). The score of each setup is still computed with `bosses=False` (bosses excluded from general quality scoring).

Returns empty list if no eligible combos exist (target not catchable, or hour with no fish).

### `session_windows(dc, location_id, start_hour, duration_hours) → list[dict]`

For each hour `h` in `[start_hour, start_hour + duration_hours)` (mod 24), records which fish IDs are eligible across **all** tools (union). Computes `opens` and `closes` relative to the previous hour.

```python
{
    "hour": int,
    "fish_ids": set[str],
    "opens": set[str],   # fish_ids not in previous hour
    "closes": set[str],  # fish_ids in previous hour but not this hour
}
```

First entry has `opens` = all fish eligible at `start_hour`, `closes` = empty.

---

## 4. `/optimizer` Command

**File:** `cogs/intelligence.py`

**Signature:** `/optimizer [target]` — `target` is optional, autocompletes on fish names.

**Output:** Static embed (no view — results valid until the next UTC hour).

### No target — Best Overall

Calls `best_setups(dc, hour, limit=3)`. Embed title: `🏆 Best Setup Right Now`. Shows top 3 combos:

```
1. [tool_emoji] Tool Name  ·  📍 Location Name  — score 42.1
2. [tool_emoji] Tool Name  ·  📍 Location Name  — score 38.6
3. [tool_emoji] Tool Name  ·  📍 Location Name  — score 35.0

🪱 Bait: Golden Bait (your current)
```

If the user has no bait set: `🪱 Bait: any — bait doesn't change which fish appear`

### With target — Catch [Fish Name]

Calls `best_setups(dc, hour, target_fish_id=target.id, limit=3)`. Embed title: `🎯 Best Setup for [Fish Name]`. Same ranked format. If 0 results (target not catchable at this hour), embed says:

```
❌ [Fish Name] is not catchable at this UTC hour.
Next window: HH:00 UTC
```

Next window computed by checking hours `[hour+1 .. hour+23]` mod 24 until `best_setups` returns non-empty.

### Error states

- Data not loaded → ephemeral `EmbedBuilder.error`
- Target fish name not found → ephemeral "No fish named **X** found. Try `/fishlist` to browse."
- No setups score > 0 (hour where genuinely nothing is catchable) → embed body "No fish catchable right now — try again at HH:00"

### Autocomplete

Reuses the existing `fish_autocomplete` pattern from `FishCog`. Register `IntelligenceCog.optimizer_autocomplete` on the `target` parameter.

---

## 5. `/planner` Command

**File:** `cogs/intelligence.py`

**Signature:** `/planner [location] [hours]`
- `location` — optional string, autocompletes on location names. Default: best location right now (highest `score_setup` across all tools at current hour).
- `hours` — optional integer, `min_value=1`, `max_value=6`, default 3.

**Output:** Static embed, no view.

### Embed structure

```
🗓️ Session Plan — Ocean Beach  (14:00–17:00 UTC)

🐟 Catchable the whole session  (N fish)
  Bass · Trout · Koi · …

🔓 Opens during session
  15:00 → Sunfish, Marlin
  16:00 → Anglerfish

🔒 Closes during session
  15:00 → Clownfish

🎣 Recommended setup
  Tool: Fishing Rod  (best across all windows)
  Bait: Golden Bait (your current)
```

**"Catchable the whole session":** fish IDs present in every hour's `fish_ids` set.

**Opens/closes:** aggregated from `session_windows` `opens`/`closes` fields, grouped by hour. Skip hours with no changes.

**Tool recommendation:** for each tool in `dc.tool_by_id`, sum `score_setup` across all session hours. Pick the tool with the highest sum. If only one tool covers the location at all, use it without comparison.

**Bait:** user's `current_bait` from profile if set; otherwise `"any — bait doesn't change which fish appear"`.

**"Catchable the whole session" empty:** if the intersection of all hourly fish sets is empty, show "No fish are available the entire session — fish availability varies by hour, see windows above."

### Error states

- Location name not found → ephemeral error
- No fish catchable at any hour in the window → embed body "No fish available at **[Location]** during this window."
- Data not loaded → ephemeral `EmbedBuilder.error`

### Autocomplete

`planner_location_autocomplete` on `location` parameter — same pattern as existing location autocomplete in `LocationsCog`.

---

## 6. Enhanced `/today`

**File:** `cogs/utilities.py`

`_build_today_embed(dc, db_row, hour)` gains two new embed fields. The function signature does not change — it already receives `db_row` which contains `current_tool` and `current_bait`.

### New field 1 — "Best Catch Right Now"

Calls `best_setups(dc, hour, limit=1)`. Takes the top setup, finds the highest-`RARITY_WEIGHTS` fish eligible within it. Adds field:

```
🏆 Best Catch Right Now
⭐ Koi (Very Rare)  ·  📍 Coral Reef  ·  🎣 Fishing Rod
```

If `best_setups` returns empty: field value = "Nothing catchable right now."

### New field 2 — "Your Setup"

Reads `current_tool` and `current_bait` from `db_row`. If `current_tool` is set:
- Find the best location for that tool: `max(dc.location_by_id, key=lambda lid: score_setup(dc, current_tool, lid, hour))`
- Add field:

```
🎣 Your Setup
Tool: Fishing Rod  ·  Bait: Golden Bait
Best location right now: Ocean Beach
```

If `current_tool` is not set in profile:
```
🎣 Your Setup
Not configured — use /profile to set your gear
```

Both fields are appended after the existing "Top Locations" field, before the footer.

---

## 7. Error Handling

- All commands: `if not dc.fish_by_id` → ephemeral `EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG)`
- `/optimizer` target not found: ephemeral error, suggest `/fishlist`
- `/optimizer` target not catchable: informational embed (not an error), shows next window
- `/planner` location not found: ephemeral error
- `/planner` no fish in window: informational embed body (not an error)
- `score_setup` unknown rarity: `RARITY_WEIGHTS.get(rarity, 0.0)` — silently scores 0

---

## 8. Testing

### `tests/test_optimizer.py` (new file)

| Test | Covers |
|------|--------|
| `test_score_setup_sums_rarity_weights` | Returns correct float for known eligible fish |
| `test_score_setup_zero_when_no_eligible_fish` | Returns 0.0 when nothing eligible |
| `test_best_setups_ranked_by_score` | Top result has highest score |
| `test_best_setups_target_filters_correctly` | Only returns combos where target fish is eligible |
| `test_best_setups_target_not_catchable_returns_empty` | Returns `[]` when target ineligible at hour |
| `test_session_windows_tracks_opens_and_closes` | Fish newly available/expiring between hours correct |

### `tests/test_intelligence_cog.py` (new file)

| Test | Covers |
|------|--------|
| `test_optimizer_no_target_embed_has_best_setup` | Embed title contains "Best Setup" |
| `test_optimizer_with_target_mentions_fish` | Target fish name appears in embed |
| `test_optimizer_target_not_found_returns_error` | Ephemeral error response |
| `test_planner_embed_shows_session_structure` | All three sections present (whole session / opens / closes) |
| `test_planner_no_fish_returns_error` | No-fish-available message in embed |

### `tests/test_utilities_cog.py` (additions)

| Test | Covers |
|------|--------|
| `test_today_embed_best_catch_field_present` | "Best Catch Right Now" field in embed |
| `test_today_embed_your_setup_with_tool` | Shows tool+location from profile |
| `test_today_embed_your_setup_no_tool` | Shows "Not configured" fallback |

---

## 9. Out of Scope

- DM bot `on_message` event/weather listener — Phase 9
- Fish Skills message parser — Phase 9
- Multi-hour optimizer (best setup for a future hour) — YAGNI
- `/optimizer` saving recommendations to profile automatically — user controls their profile
- Profit/XP optimization — no sell price data in `data.json`
