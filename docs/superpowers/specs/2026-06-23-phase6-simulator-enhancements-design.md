# Phase 6 — Simulator Enhancements & Stubs Design
**Date:** 2026-06-23
**Scope:** Favourite buttons, Profile Export/Import, Simulator Statistics + auto-save, FavoritesView Simulate, Simulations history tab, Settings Default Sim Values
**Bot:** DankFishingBot · discord.py 2.x · SQLite · dankmemer>=1.0.0rc2

---

## 1. Context

Phases 1–5 delivered the encyclopedia, user profiles, simulator, local engine, and utility commands.
Phase 6 wires up disabled stubs and adds simulator statistics + auto-save. No new cogs, no new DB
migrations — all required columns already exist.

**`fishing_rod` column is legacy and must not be referenced.** The game uses tool + bait only.
Use `current_tool` and `current_bait` exclusively.

---

## 2. Architecture

**Modified files only — no new files:**

| File | What changes |
|------|-------------|
| `cogs/fish.py` | Enable ⭐ Favourite, pre-check DB on view init |
| `cogs/locations.py` | Same |
| `cogs/tools.py` | Same |
| `cogs/baits.py` | Same |
| `cogs/profile.py` | Wire Export/Import, FavoritesView Simulate, HistoryView Simulations tab, Settings Default Sim Values |
| `cogs/simulator.py` | Add StatisticsView, 📊 Statistics button, auto-save after Calculate |

**No new DB migrations.** Columns used:
- `current_tool TEXT` — stores tool name (e.g. `"Fishing Rod"`)
- `current_bait TEXT` — stores bait name
- `favorite_location TEXT` — stores location name
- `current_event TEXT` — stores event name
- `favorites` table — `(discord_id, type, item_id)` where type ∈ `{fish, location, tool, bait}`
- `history` table — type `"simulation"` already used by Calculate

**No new dependencies.**

---

## 3. Features

### 3.1 Favourite Buttons (fish.py, locations.py, tools.py, baits.py)

Each encyclopedia detail view (`FishView`, `LocationView`, `ToolView`, `BaitView`) currently has
a ⭐ Favourite button that starts `disabled=True`.

**Changes:**
- Add `db` and `user_id` parameters to each view's `__init__`
- On init, call `await db.get_favorites(user_id, type)` to fetch the user's existing favourites
  for that type; store as a `set` of item IDs
- Set button `disabled=False` on init
- Set initial button label: `"★ Unfavourite"` if item already in favourites, else `"⭐ Favourite"`
- Toggle on click: if currently favourite → `db.remove_favorite` → label `"⭐ Favourite"`; else
  `db.add_favorite` → label `"★ Unfavourite"`
- After toggle: `await interaction.response.edit_message(view=self)` (no embed rebuild needed)

**Callers** (the command functions that create these views) must be updated to pass `db` and
`str(interaction.user.id)` when constructing the view.

**Guard:** if `db` is `None`, keep button disabled and skip the DB call silently.

---

### 3.2 Profile Export / Import (cogs/profile.py — ProfileView)

Both buttons are currently `disabled=True` stubs.

#### Export (📤)
1. Fetch `user_row = await db.get_or_create_user(discord_id)`
2. Fetch `fav_rows = await db.get_favorites(discord_id)`
3. Build export dict:
```python
{
    "version": 1,
    "profile": {
        "current_tool": user_row["current_tool"],
        "current_bait": user_row["current_bait"],
        "favorite_location": user_row["favorite_location"],
        "current_event": user_row["current_event"],
        "fishing_skill": user_row["fishing_skill"],
        "luck_skill": user_row["luck_skill"],
        "efficiency_skill": user_row["efficiency_skill"],
        "prestige": user_row["prestige"],
        "coins": user_row["coins"],
        "boss_unlock": user_row["boss_unlock"],
        "mythical_unlock": user_row["mythical_unlock"],
        "skills": user_row["skills"],
        "timezone": user_row["timezone"],
        "theme": user_row["theme"],
        "compact_mode": user_row["compact_mode"],
    },
    "favorites": [{"type": r["type"], "item_id": r["item_id"]} for r in fav_rows],
}
```
4. Send as `discord.File(io.BytesIO(json.dumps(payload, indent=2).encode()), filename="profile.json")`
   with `ephemeral=True` and a brief embed: `EmbedBuilder.info("Profile Exported", "Your profile data is attached.")`

#### Import (📥)
1. Open an `ImportModal` (`discord.ui.Modal`, title `"Import Profile"`) with one `TextInput`:
   - label: `"Paste your profile JSON"`, style: paragraph, max_length: 4000
2. In `on_submit`:
   - Parse JSON; if invalid → ephemeral `EmbedBuilder.error`
   - Validate `payload.get("version") == 1`; if not → ephemeral error
   - Extract `profile` dict; call `db.update_user(discord_id, **profile_fields)` — only update
     the keys listed in the export dict above (never write `discord_id`, `updated_at`, etc.)
   - Re-insert favourites: for each entry in `payload.get("favorites", [])`, call
     `db.add_favorite(discord_id, entry["type"], entry["item_id"])` — use `INSERT OR IGNORE`
     (already the DB's behaviour)
   - On success: `EmbedBuilder.info("Profile Imported", "Your profile has been restored.")` ephemeral
   - On any error: `EmbedBuilder.error(...)` ephemeral; do not partially-commit

---

### 3.3 Simulator Statistics (cogs/simulator.py)

#### StatisticsView

A new view shown in-place (via `edit_original_response`) when the user clicks 📊 Statistics.
Inherits the same `timeout=300` / `self.message` / `on_timeout` pattern as all other views.

**Constructor:** `StatisticsView(sim_view: SimulatorView, sim_data: dict, dc)`

- `sim_view` — reference back to the parent `SimulatorView` (for the ← Back button)
- `sim_data` — the raw simulation result dict from the last Calculate
- `dc` — dank client for location lookup

**Embed builder:** `build_statistics_embed(sim_data: dict, state: dict, dc) -> discord.Embed`

Module-level function. Computes from `sim_data`:

| Field | Computation |
|-------|-------------|
| Fail rate | `sim_data["failChance"]` |
| NPC rate | `sim_data["npcChance"]` |
| Net catch rate | `100 - failChance - npcChance` |
| Mine chance | `dc.location_by_id[state["location_id"]].extra.get("mineChance", 0)` if location set, else `"—"` |
| Rarity breakdown | Group `sim_data["table"]` entries by rarity (looked up via `dc.fish_by_id[creatureID].extra["rarity"]` for fish-creature entries); sum chances per rarity tier |
| Boss % | Sum chances of entries where `dc.fish_by_id[creatureID].extra.get("boss")` is truthy |
| Variant distribution | From `sim_data.get("variants", {})` — list each fish with variants > 0 |

Each stat is displayed as a field: name + formatted value. No progress bar rendering (text only).
Title: `"📊 Statistics"`. Footer: same location + hour as the results embed.

**Buttons:**
- `← Back` (primary, row=0): calls `interaction.response.edit_message(embed=sim_view._last_embed, view=sim_view)`
- `🗑️ Delete` (danger, row=0): `await interaction.message.delete()`

#### 📊 Statistics button in SimulatorView

Add as the 5th button on row 4 (Discord allows 5 per row). Initially `disabled=True`.
Enabled (via `button.disabled = False`) inside `calculate_btn` after a successful result,
immediately before `edit_original_response`.

```python
self.statistics_btn.disabled = False
```

On click:
```python
embed = build_statistics_embed(data, self._current_state(), self.dc)
await interaction.response.edit_message(
    embed=embed,
    view=StatisticsView(self, data, self.dc),
)
```

`_last_sim_data` attribute must be stored on `SimulatorView` (set in `calculate_btn` alongside
`_last_embed`) so the Statistics button always has the latest data.

---

### 3.4 Simulator Auto-Save (cogs/simulator.py — calculate_btn)

After a successful Calculate (both local and API paths), call:

```python
await db.update_user(
    str(self.member.id),
    current_tool=dc.tool_by_id[self._tool_id].name if self._tool_id and self._tool_id in dc.tool_by_id else None,
    current_bait=dc.bait_by_id[self._bait_id].name if self._bait_id and self._bait_id in dc.bait_by_id else None,
    favorite_location=dc.location_by_id[self._loc_id].name if self._loc_id and self._loc_id in dc.location_by_id else None,
    current_event=dc.event_by_id[self._event_id].name if self._event_id and self._event_id in dc.event_by_id else None,
)
```

Wrap in `try/except Exception` and log the error — do not surface DB failures to the user.
Place the call after `edit_original_response` and `add_history` (fire-and-forget pattern).

`dc` is accessed via `self.dc` (already an attribute on `SimulatorView`).

---

### 3.5 FavoritesView Simulate Button (cogs/profile.py)

Enable the `🎮 Simulate` stub. Requires `dc` to be passed to `FavoritesView.__init__` (add it).

On click, build `initial_state` from `self.selected_type` and `self.selected_id`:

```python
initial_state = {}
if self.selected_type == "location":
    initial_state["location_id"] = self.selected_id
elif self.selected_type == "tool":
    initial_state["tool_id"] = self.selected_id
# fish and bait types: no relevant pre-fill for simulator
```

Then:
```python
view = SimulatorView(self.db, self.user, self.dc, initial_state=initial_state)
embed = EmbedBuilder.info("🎣 Simulator", "Select your options and click **🔄 Calculate**.")
await interaction.response.send_message(embed=embed, view=view)
```

The Simulate button should only be enabled when `self.selected_id is not None` (same rule as
Open/Remove). Update `_update_action_buttons` to include `"🎮 Simulate"` in the label check.

---

### 3.6 HistoryView Simulations Tab (cogs/profile.py)

Enable the `🎮 Simulations` stub by calling `_switch_tab(interaction, "simulation")`.

`db.get_history` already accepts `type="simulation"`. The `build_history_embed` function
in `utils/embeds.py` must handle `"simulation"` type — check if it already does; if not, add a
branch that renders rows as: `"{location_id} — {created_at}"` (the `data` field contains full
JSON which can be skipped for the list view).

---

### 3.7 Settings Default Sim Values (cogs/profile.py — SettingsView)

Enable the `🎮 Default Sim Values` stub. On click:
1. Fetch `user_row = await db.get_or_create_user(str(member.id))`
2. Build an ephemeral embed showing current defaults:
   - Tool: `user_row["current_tool"] or "None"`
   - Bait: `user_row["current_bait"] or "None"`
   - Location: `user_row["favorite_location"] or "None"`
   - Event: `user_row["current_event"] or "None"`
3. Add a note: `"Run /simulate and click 🔄 Calculate to auto-update these values."`
4. Send as `ephemeral=True` — no new view, just an informational embed.

---

## 4. Error Handling

- **Favourite toggle DB failure**: show ephemeral `EmbedBuilder.error`; revert button label
- **Export DB failure**: show ephemeral `EmbedBuilder.error`
- **Import JSON parse error**: show ephemeral `EmbedBuilder.error("Invalid JSON", ...)`
- **Import version mismatch**: show ephemeral `EmbedBuilder.error("Incompatible format", ...)`
- **Import DB failure**: show ephemeral `EmbedBuilder.error`; do not partially commit
- **Statistics with no Calculate done**: button is `disabled=True` — not reachable
- **Auto-save DB failure**: log only; do not surface to user
- **FavoritesView Simulate with dc=None**: keep button disabled; skip silently
- **Simulations history empty**: `build_history_embed` returns embed with "No simulations yet."

---

## 5. Testing

All tests in existing test files for their respective cogs.

| Test | File | Covers |
|------|------|--------|
| `test_favourite_button_pre_checked` | `tests/test_fish_cog.py` (or equivalent) | Button label is "★ Unfavourite" if item already in DB favourites |
| `test_favourite_toggle_adds_to_db` | same | `db.add_favorite` called when toggling from unfavourited |
| `test_export_produces_valid_json` | `tests/test_profile_cog.py` | Export payload has correct keys and version=1 |
| `test_import_restores_profile_fields` | same | `db.update_user` called with correct fields from import JSON |
| `test_import_rejects_invalid_json` | same | Ephemeral error sent for bad JSON |
| `test_statistics_embed_has_fail_npc` | `tests/test_simulator_cog.py` | Fail + NPC rates present in statistics embed |
| `test_statistics_embed_mine_chance` | same | Mine chance field shows location's mineChance value |
| `test_autosave_calls_update_user` | same | `db.update_user` called with correct names after Calculate |
| `test_favorites_simulate_sets_location` | `tests/test_profile_cog.py` | SimulatorView created with correct location_id |
| `test_simulations_tab_queries_history` | same | `db.get_history` called with type="simulation" |
| `test_settings_default_sim_values_embed` | same | Embed shows current_tool, current_bait from user_row |

---

## 6. Out of Scope

- Profit / XP estimates — no sell price or XP data in `data.json`; deferred indefinitely
- Notifications button in Settings — Phase 9
- `fishing_rod` column — legacy, not referenced
- New cogs, new DB tables, new migrations
- Language switching — deferred
