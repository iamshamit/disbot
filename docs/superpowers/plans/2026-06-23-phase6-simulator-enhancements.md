# Phase 6 — Simulator Enhancements & Stubs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up disabled stubs in the simulator and profile cogs, and add simulator statistics + auto-save.

**Architecture:** Two files change — `cogs/simulator.py` gets auto-save + a new StatisticsView; `cogs/profile.py` gets its three disabled stubs wired up plus Export/Import. No new files, no migrations.

**Tech Stack:** discord.py 2.x, aiosqlite, Python 3.12, pytest-asyncio

## Global Constraints

- `fishing_rod` DB column is legacy — never reference it in new code
- `current_tool`, `current_bait`, `favorite_location`, `current_event` store **name strings** (not IDs)
- All primary sends are public (no `ephemeral=True` on primary `send_message`)
- All error embeds use `EmbedBuilder.error(...)` with `ephemeral=True`
- All views: `self.message: discord.Message | None = None`, `on_timeout` disables children then `await self.message.edit(view=self)` guarded with `if self.message: try/except Exception: pass`
- After every `send_message`: `view.message = await interaction.original_response()`
- No new dependencies
- Tests run with: `pytest -x -q` from repo root (currently 365 passing)

---

### Task 1: Simulator auto-save

**Files:**
- Modify: `cogs/simulator.py` (calculate_btn, SimulatorView.__init__)
- Test: `tests/test_simulator_cog.py`

**Interfaces:**
- Consumes: `SimulatorView.dc` (already an attribute), `db.update_user(discord_id, **fields)`
- Produces: nothing — side effect only

- [ ] **Step 1: Write the failing test**

Add to `tests/test_simulator_cog.py`:

```python
@pytest.mark.asyncio
async def test_autosave_calls_update_user_with_names(monkeypatch):
    from cogs.simulator import SimulatorView
    db = MagicMock()
    db.get_or_create_user = AsyncMock(return_value=make_user_row())
    db.add_history = AsyncMock()
    db.update_user = AsyncMock()
    dc = make_dc()
    view = SimulatorView(db, make_member(), dc)
    view._loc_id = "river"
    view._tool_id = "rod"
    view._bait_id = "worm"
    view._event_id = "2xtokens"

    fake_data = {"failChance": 10.0, "npcChance": 2.0, "table": [], "variants": {}}
    monkeypatch.setattr("cogs.simulator.local_simulate", lambda *a, **kw: fake_data)

    inter = make_interaction()
    await view.calculate_btn.callback(view, inter, MagicMock())

    db.update_user.assert_called_once_with(
        "123",
        current_tool="Basic Rod",
        current_bait="Worm",
        favorite_location="Wily River",
        current_event="Token Clone",
    )
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_simulator_cog.py::test_autosave_calls_update_user_with_names -v
```
Expected: FAIL — `AssertionError: Expected call ... not found`

- [ ] **Step 3: Implement auto-save in calculate_btn**

In `cogs/simulator.py`, find `calculate_btn`. After the existing `await self.db.add_history(...)` call, add:

```python
        try:
            await self.db.update_user(
                str(self.member.id),
                current_tool=self.dc.tool_by_id[self._tool_id].name if self._tool_id and self._tool_id in self.dc.tool_by_id else None,
                current_bait=self.dc.bait_by_id[self._bait_id].name if self._bait_id and self._bait_id in self.dc.bait_by_id else None,
                favorite_location=self.dc.location_by_id[self._loc_id].name if self._loc_id and self._loc_id in self.dc.location_by_id else None,
                current_event=self.dc.event_by_id[self._event_id].name if self._event_id and self._event_id in self.dc.event_by_id else None,
            )
        except Exception:
            pass
```

The full `calculate_btn` body after the change ends:
```python
        embed = build_sim_results_embed(data, self._current_state(), self.dc)
        self._last_embed = embed
        await interaction.edit_original_response(embed=embed, view=self)
        await self.db.add_history(
            str(self.member.id), "simulation",
            self._loc_id or "unknown",
            data=_json.dumps(data),
        )
        try:
            await self.db.update_user(
                str(self.member.id),
                current_tool=self.dc.tool_by_id[self._tool_id].name if self._tool_id and self._tool_id in self.dc.tool_by_id else None,
                current_bait=self.dc.bait_by_id[self._bait_id].name if self._bait_id and self._bait_id in self.dc.bait_by_id else None,
                favorite_location=self.dc.location_by_id[self._loc_id].name if self._loc_id and self._loc_id in self.dc.location_by_id else None,
                current_event=self.dc.event_by_id[self._event_id].name if self._event_id and self._event_id in self.dc.event_by_id else None,
            )
        except Exception:
            pass
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_simulator_cog.py -x -q
```
Expected: all simulator tests pass including the new one.

- [ ] **Step 5: Run full suite**

```
pytest -x -q
```
Expected: 366 passed

- [ ] **Step 6: Commit**

```
git add cogs/simulator.py tests/test_simulator_cog.py
git commit -m "feat: auto-save tool/bait/location/event to profile after Calculate"
```

---

### Task 2: Simulator Statistics

**Files:**
- Modify: `cogs/simulator.py`
- Test: `tests/test_simulator_cog.py`

**Interfaces:**
- Consumes: `SimulatorView._last_embed`, `SimulatorView._current_state()`, `SimulatorView.dc`, `SimulatorView.db`
- Produces: `build_statistics_embed(sim_data, state, dc) -> discord.Embed`, `StatisticsView(sim_view, sim_data, dc)`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_simulator_cog.py`:

```python
def test_build_statistics_embed_shows_fail_npc_net():
    from cogs.simulator import build_statistics_embed
    dc = make_dc()
    dc.location_by_id["river"].extra = MagicMock()
    dc.location_by_id["river"].extra.get = lambda k, d=None: 95 if k == "mineChance" else d
    sim_data = {"failChance": 12.0, "npcChance": 3.0, "table": [], "variants": {}}
    state = {"location_id": "river", "hour": 14}
    embed = build_statistics_embed(sim_data, state, dc)
    field_names = [f.name for f in embed.fields]
    assert "❌ Fail" in field_names
    assert "👤 NPC" in field_names
    assert "🎣 Net Catch" in field_names


def test_build_statistics_embed_mine_chance():
    from cogs.simulator import build_statistics_embed
    dc = make_dc()
    dc.location_by_id["river"].extra = MagicMock()
    dc.location_by_id["river"].extra.get = lambda k, d=None: 95 if k == "mineChance" else d
    sim_data = {"failChance": 12.0, "npcChance": 3.0, "table": [], "variants": {}}
    state = {"location_id": "river", "hour": 14}
    embed = build_statistics_embed(sim_data, state, dc)
    mine_field = next(f for f in embed.fields if "Mine" in f.name)
    assert "95" in mine_field.value


def test_build_statistics_embed_rarity_breakdown():
    from cogs.simulator import build_statistics_embed
    dc = make_dc()
    dc.location_by_id["river"].extra = MagicMock()
    dc.location_by_id["river"].extra.get = lambda k, d=None: 0 if k == "mineChance" else d
    dc.fish_by_id["bass"].extra = {"rarity": "Rare", "boss": False}
    sim_data = {
        "failChance": 10.0, "npcChance": 2.0,
        "table": [{"chance": 5.0, "value": {"type": "fish-creature", "creatureID": "bass"}}],
        "variants": {},
    }
    state = {"location_id": None, "hour": 0}
    embed = build_statistics_embed(sim_data, state, dc)
    breakdown_field = next((f for f in embed.fields if "Rarity" in f.name), None)
    assert breakdown_field is not None
    assert "Rare" in breakdown_field.value
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_simulator_cog.py::test_build_statistics_embed_shows_fail_npc_net -v
```
Expected: FAIL — `ImportError: cannot import name 'build_statistics_embed'`

- [ ] **Step 3: Add build_statistics_embed**

Add this module-level function to `cogs/simulator.py` after `build_fish_peak_embed`:

```python
_STATS_RARITY_ORDER = [
    "Absurdly Common", "Very Common", "Common", "Regular",
    "Rare", "Very Rare", "Absurdly Rare",
]


def build_statistics_embed(sim_data: dict, state: dict, dc) -> discord.Embed:
    fail = sim_data.get("failChance", 0.0)
    npc = sim_data.get("npcChance", 0.0)
    net = max(0.0, 100.0 - fail - npc)

    loc_id = state.get("location_id")
    mine_str = "—"
    if loc_id and loc_id in dc.location_by_id:
        mine_val = dc.location_by_id[loc_id].extra.get("mineChance", None)
        if mine_val is not None:
            mine_str = f"{mine_val}%"

    rarity_totals: dict[str, float] = {}
    boss_total = 0.0
    for entry in sim_data.get("table", []):
        chance = entry.get("chance", 0.0)
        val = entry.get("value", {})
        if val.get("type") == "fish-creature":
            cid = val.get("creatureID", "")
            fish = dc.fish_by_id.get(cid)
            if fish:
                rarity = fish.extra.get("rarity", "Unknown") if hasattr(fish.extra, "get") else "Unknown"
                rarity_totals[rarity] = rarity_totals.get(rarity, 0.0) + chance
                if (fish.extra.get("boss") if hasattr(fish.extra, "get") else False):
                    boss_total += chance

    variant_lines = []
    for cid, var_list in sim_data.get("variants", {}).items():
        name = dc.fish_by_id[cid].name if cid in dc.fish_by_id else cid
        total_var = sum(v.get("chance", 0.0) for v in var_list if v.get("chance", 0.0) > 0)
        if total_var > 0:
            variant_lines.append(f"✨ **{name}** — {total_var:.1f}%")

    embed = discord.Embed(title="📊 Statistics", color=0x5865F2)
    embed.set_author(name="🎣 Simulator")
    embed.add_field(name="❌ Fail", value=f"{fail:.1f}%", inline=True)
    embed.add_field(name="👤 NPC", value=f"{npc:.1f}%", inline=True)
    embed.add_field(name="🎣 Net Catch", value=f"{net:.1f}%", inline=True)
    embed.add_field(name="⛏️ Mine Chance", value=mine_str, inline=True)
    if boss_total > 0:
        embed.add_field(name="👾 Boss", value=f"{boss_total:.1f}%", inline=True)

    rarity_lines = [
        f"**{r}**: {rarity_totals[r]:.1f}%"
        for r in _STATS_RARITY_ORDER
        if r in rarity_totals
    ]
    if rarity_lines:
        embed.add_field(name="📊 Rarity Breakdown", value="\n".join(rarity_lines), inline=False)
    if variant_lines:
        embed.add_field(name="✨ Variants", value="\n".join(variant_lines[:10]), inline=False)

    loc_name = dc.location_by_id[loc_id].name if loc_id and loc_id in dc.location_by_id else "No location"
    hour = state.get("hour", 0)
    embed.set_footer(text=f"{loc_name} · {hour:02d}:00 UTC")
    return embed
```

- [ ] **Step 4: Run tests to verify embed tests pass**

```
pytest tests/test_simulator_cog.py::test_build_statistics_embed_shows_fail_npc_net tests/test_simulator_cog.py::test_build_statistics_embed_mine_chance tests/test_simulator_cog.py::test_build_statistics_embed_rarity_breakdown -v
```
Expected: 3 passed

- [ ] **Step 5: Add StatisticsView**

Add this class to `cogs/simulator.py` just before `SimulatorView`:

```python
class StatisticsView(discord.ui.View):
    def __init__(self, sim_view: "SimulatorView", sim_data: dict, dc):
        super().__init__(timeout=300)
        self.sim_view = sim_view
        self.sim_data = sim_data
        self.dc = dc
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="← Back", style=discord.ButtonStyle.primary, row=0)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.sim_view._last_embed, view=self.sim_view)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=0)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
```

- [ ] **Step 6: Add _last_sim_data attribute and Statistics button to SimulatorView**

In `SimulatorView.__init__`, add after `self._last_embed: discord.Embed | None = None`:
```python
        self._last_sim_data: dict | None = None
```

Add a new `@discord.ui.button` method at the end of `SimulatorView` (before `PeakHoursView`):
```python
    @discord.ui.button(label="📊 Statistics", style=discord.ButtonStyle.secondary, disabled=True, row=4)
    async def statistics_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_statistics_embed(self._last_sim_data, self._current_state(), self.dc)
        stats_view = StatisticsView(self, self._last_sim_data, self.dc)
        await interaction.response.edit_message(embed=embed, view=stats_view)
```

In `calculate_btn`, after `self._last_embed = embed`, add:
```python
        self._last_sim_data = data
        self.statistics_btn.disabled = False
```

The relevant section of `calculate_btn` after the change:
```python
        embed = build_sim_results_embed(data, self._current_state(), self.dc)
        self._last_embed = embed
        self._last_sim_data = data
        self.statistics_btn.disabled = False
        await interaction.edit_original_response(embed=embed, view=self)
```

- [ ] **Step 7: Write test for Statistics button**

Add to `tests/test_simulator_cog.py`:

```python
@pytest.mark.asyncio
async def test_statistics_btn_enabled_after_calculate(monkeypatch):
    from cogs.simulator import SimulatorView
    db = MagicMock()
    db.get_or_create_user = AsyncMock(return_value=make_user_row())
    db.add_history = AsyncMock()
    db.update_user = AsyncMock()
    dc = make_dc()
    view = SimulatorView(db, make_member(), dc)

    stats_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Statistics" in item.label
    )
    assert stats_btn.disabled is True

    fake_data = {"failChance": 10.0, "npcChance": 2.0, "table": [], "variants": {}}
    monkeypatch.setattr("cogs.simulator.local_simulate", lambda *a, **kw: fake_data)

    inter = make_interaction()
    await view.calculate_btn.callback(view, inter, MagicMock())

    assert stats_btn.disabled is False
    assert view._last_sim_data == fake_data
```

- [ ] **Step 8: Run full simulator tests**

```
pytest tests/test_simulator_cog.py -x -q
```
Expected: all tests pass (including new ones)

- [ ] **Step 9: Run full suite**

```
pytest -x -q
```
Expected: 371 passed (366 + 4 new + 1 for enabled-after-calculate)

- [ ] **Step 10: Commit**

```
git add cogs/simulator.py tests/test_simulator_cog.py
git commit -m "feat: add Statistics view with mine chance, rarity breakdown, and boss% to simulator"
```

---

### Task 3: Profile stub wiring

**Files:**
- Modify: `cogs/profile.py`
- Test: `tests/test_profile_cog.py`

**Interfaces:**
- Consumes: `SimulatorView(db, user, dc, initial_state)` from `cogs.simulator` (imported inline)
- Produces: wired `sim_btn`, `sim_tab`, `sim_defaults_btn`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_profile_cog.py`:

```python
@pytest.mark.asyncio
async def test_favorites_simulate_btn_opens_simulator():
    from cogs.profile import FavoritesView
    from cogs.simulator import SimulatorView

    db = MagicMock()
    db.get_favorites = AsyncMock(return_value=[])
    user = make_member()
    dc = MagicMock()
    dc.location_by_id = {"river": MagicMock(id="river", name="River")}

    view = FavoritesView(db, user, dc, [])
    view.selected_type = "location"
    view.selected_id = "river"

    inter = make_interaction()
    await view.sim_btn.callback(view, inter, MagicMock())

    inter.response.send_message.assert_awaited_once()
    call_kwargs = inter.response.send_message.call_args
    sent_view = call_kwargs.kwargs.get("view") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs.get("view")
    assert isinstance(sent_view, SimulatorView)
    assert sent_view._loc_id == "river"


@pytest.mark.asyncio
async def test_simulations_tab_queries_history():
    from cogs.profile import HistoryView

    db = MagicMock()
    db.get_history = AsyncMock(return_value=[])
    user = make_member()
    view = HistoryView(db, user)

    inter = make_interaction()
    await view.sim_tab.callback(view, inter, MagicMock())

    db.get_history.assert_awaited_once_with("123", "simulation")


@pytest.mark.asyncio
async def test_settings_default_sim_values_shows_embed():
    from cogs.profile import SettingsView

    db = MagicMock()
    db.get_or_create_user = AsyncMock(return_value=make_user_row(
        current_tool="Fishing Rod", current_bait="Worm",
        favorite_location="River", current_event=None,
    ))
    member = make_member()
    view = SettingsView(db, member)

    inter = make_interaction()
    await view.sim_defaults_btn.callback(view, inter, MagicMock())

    inter.response.send_message.assert_awaited_once()
    call_kwargs = inter.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True
    sent_embed = call_kwargs.kwargs.get("embed")
    assert sent_embed is not None
    assert "Fishing Rod" in str(sent_embed.fields)
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_profile_cog.py::test_favorites_simulate_btn_opens_simulator tests/test_profile_cog.py::test_simulations_tab_queries_history tests/test_profile_cog.py::test_settings_default_sim_values_shows_embed -v
```
Expected: FAIL

- [ ] **Step 3: Wire FavoritesView.sim_btn**

In `cogs/profile.py`, find `_update_action_buttons` in `FavoritesView` and update it:

```python
    def _update_action_buttons(self):
        has = self.selected_id is not None
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.label in (
                "\U0001f517 Open", "\U0001f5d1️ Remove", "\U0001f3ae Simulate"
            ):
                item.disabled = not has
```

Replace the `sim_btn` stub with the full implementation:

```python
    @discord.ui.button(label="\U0001f3ae Simulate", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.simulator import SimulatorView
        initial_state: dict = {}
        if self.selected_type == "location":
            initial_state["location_id"] = self.selected_id
        elif self.selected_type == "tool":
            initial_state["tool_id"] = self.selected_id
        view = SimulatorView(self.db, self.user, self.dc, initial_state=initial_state)
        embed = EmbedBuilder.info("🎣 Simulator", "Select your options and click **🔄 Calculate**.")
        await interaction.response.send_message(embed=embed, view=view)
```

- [ ] **Step 4: Wire HistoryView.sim_tab**

Replace the `sim_tab` stub body (currently `pass`) with:

```python
    @discord.ui.button(label="\U0001f3ae Simulations", style=discord.ButtonStyle.secondary, row=0)
    async def sim_tab(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "simulation")
```

Remove `disabled=True` from the decorator.

- [ ] **Step 5: Wire SettingsView.sim_defaults_btn**

Replace the `sim_defaults_btn` stub with:

```python
    @discord.ui.button(label="\U0001f3ae Default Sim Values", style=discord.ButtonStyle.secondary, row=1)
    async def sim_defaults_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_or_create_user(str(self.member.id))
        tool = user_row["current_tool"] or "None"
        bait = user_row["current_bait"] or "None"
        location = user_row["favorite_location"] or "None"
        event = user_row["current_event"] or "None"
        embed = discord.Embed(title="\U0001f3ae Default Sim Values", color=0x5865F2)
        embed.add_field(name="Tool", value=tool, inline=True)
        embed.add_field(name="Bait", value=bait, inline=True)
        embed.add_field(name="Location", value=location, inline=True)
        embed.add_field(name="Event", value=event, inline=True)
        embed.set_footer(text="Run /simulate and click \U0001f504 Calculate to auto-update these values.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
```

Remove `disabled=True` from the decorator.

- [ ] **Step 6: Run profile tests**

```
pytest tests/test_profile_cog.py -x -q
```
Expected: all pass

- [ ] **Step 7: Run full suite**

```
pytest -x -q
```
Expected: 374 passed

- [ ] **Step 8: Commit**

```
git add cogs/profile.py tests/test_profile_cog.py
git commit -m "feat: wire FavoritesView Simulate, Simulations tab, and Default Sim Values"
```

---

### Task 4: Profile Export / Import

**Files:**
- Modify: `cogs/profile.py`
- Test: `tests/test_profile_cog.py`

**Interfaces:**
- Consumes: `db.get_or_create_user`, `db.get_favorites`, `db.update_user`, `db.add_favorite`
- Produces: wired `export_btn`, `import_btn`; new `ImportModal`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_profile_cog.py`:

```python
import json as _json

@pytest.mark.asyncio
async def test_export_sends_json_file():
    from cogs.profile import ProfileView

    db = MagicMock()
    db.get_or_create_user = AsyncMock(return_value=make_user_row(
        current_tool="Fishing Rod", current_bait="Worm",
    ))
    db.get_favorites = AsyncMock(return_value=[])
    member = make_member()
    dc = MagicMock()
    view = ProfileView(db, member, dc)

    inter = make_interaction()
    await view.export_btn.callback(view, inter, MagicMock())

    inter.response.send_message.assert_awaited_once()
    call_kwargs = inter.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True
    sent_file = call_kwargs.kwargs.get("file")
    assert sent_file is not None
    # Read the file content and verify it's valid JSON with version=1
    sent_file.fp.seek(0)
    payload = _json.loads(sent_file.fp.read())
    assert payload["version"] == 1
    assert "profile" in payload
    assert payload["profile"]["current_tool"] == "Fishing Rod"


@pytest.mark.asyncio
async def test_import_restores_profile_fields():
    from cogs.profile import ProfileView

    db = MagicMock()
    db.get_or_create_user = AsyncMock(return_value=make_user_row())
    db.update_user = AsyncMock()
    db.add_favorite = AsyncMock()
    member = make_member()
    dc = MagicMock()
    view = ProfileView(db, member, dc)

    payload = {
        "version": 1,
        "profile": {
            "current_tool": "Fishing Rod",
            "current_bait": "Worm",
            "favorite_location": "River",
            "current_event": None,
            "fishing_skill": 2,
            "luck_skill": 1,
            "efficiency_skill": 0,
            "prestige": 0,
            "coins": 500,
            "boss_unlock": 1,
            "mythical_unlock": 0,
            "skills": None,
            "timezone": "UTC",
            "theme": "dark",
            "compact_mode": 0,
        },
        "favorites": [{"type": "fish", "item_id": "bass"}],
    }

    inter = make_interaction()
    # Simulate the modal submit directly
    from cogs.profile import ImportModal
    modal = ImportModal(db, member, inter.message)
    modal.json_input.default = _json.dumps(payload)

    # Manually call on_submit with the mocked interaction
    inter2 = make_interaction()
    inter2.data = {"components": [{"components": [{"value": _json.dumps(payload)}]}]}
    # Set the text input value directly
    modal.json_input._value = _json.dumps(payload)
    await modal.on_submit(inter2)

    db.update_user.assert_awaited_once()
    call_kwargs = db.update_user.call_args
    assert call_kwargs.kwargs.get("current_tool") == "Fishing Rod"
    assert call_kwargs.kwargs.get("coins") == 500
    db.add_favorite.assert_awaited_once_with("123", "fish", "bass")


@pytest.mark.asyncio
async def test_import_rejects_invalid_json():
    from cogs.profile import ImportModal

    db = MagicMock()
    member = make_member()
    modal = ImportModal(db, member, MagicMock())
    modal.json_input._value = "not valid json {"

    inter = make_interaction()
    await modal.on_submit(inter)

    inter.response.send_message.assert_awaited_once()
    call_kwargs = inter.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_profile_cog.py::test_export_sends_json_file tests/test_profile_cog.py::test_import_restores_profile_fields tests/test_profile_cog.py::test_import_rejects_invalid_json -v
```
Expected: FAIL

- [ ] **Step 3: Add import io to profile.py**

At the top of `cogs/profile.py`, add `import io` to the imports:

```python
from __future__ import annotations
import io
import json as _json
import discord
from discord import app_commands
from discord.ext import commands
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from utils.embeds import EmbedBuilder, build_profile_embed
```

- [ ] **Step 4: Add ImportModal**

Add this class to `cogs/profile.py` before `ProfileView` (or near other Modal classes):

```python
_IMPORT_PROFILE_KEYS = (
    "current_tool", "current_bait", "favorite_location", "current_event",
    "fishing_skill", "luck_skill", "efficiency_skill", "prestige", "coins",
    "boss_unlock", "mythical_unlock", "skills", "timezone", "theme", "compact_mode",
)


class ImportModal(discord.ui.Modal, title="Import Profile"):
    json_input: discord.ui.TextInput = discord.ui.TextInput(
        label="Paste your profile JSON",
        style=discord.TextStyle.paragraph,
        max_length=4000,
    )

    def __init__(self, db, member, message):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.json_input.value
        try:
            payload = _json.loads(raw)
        except Exception:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid JSON", "Could not parse the pasted data."),
                ephemeral=True,
            )
            return
        if payload.get("version") != 1:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Incompatible format", "This export was made with an unsupported version."),
                ephemeral=True,
            )
            return
        profile = payload.get("profile", {})
        update_fields = {k: profile[k] for k in _IMPORT_PROFILE_KEYS if k in profile}
        try:
            await self.db.update_user(str(self.member.id), **update_fields)
            for fav in payload.get("favorites", []):
                await self.db.add_favorite(str(self.member.id), fav["type"], fav["item_id"])
        except Exception as exc:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Import failed", f"Could not restore profile: {exc}"),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=EmbedBuilder.info("Profile Imported", "Your profile has been restored."),
            ephemeral=True,
        )
```

- [ ] **Step 5: Wire export_btn and import_btn in ProfileView**

Replace the `export_btn` stub with:

```python
    @discord.ui.button(label="📤 Export", style=discord.ButtonStyle.secondary, row=1)
    async def export_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(self.member.id)
        try:
            user_row = await self.db.get_or_create_user(user_id)
            fav_rows = await self.db.get_favorites(user_id)
        except Exception as exc:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Export failed", f"Could not read profile: {exc}"),
                ephemeral=True,
            )
            return
        payload = {
            "version": 1,
            "profile": {k: user_row[k] for k in _IMPORT_PROFILE_KEYS},
            "favorites": [{"type": r["type"], "item_id": r["item_id"]} for r in fav_rows],
        }
        raw = _json.dumps(payload, indent=2).encode()
        await interaction.response.send_message(
            embed=EmbedBuilder.info("Profile Exported", "Your profile data is attached."),
            file=discord.File(io.BytesIO(raw), filename="profile.json"),
            ephemeral=True,
        )
```

Replace the `import_btn` stub with:

```python
    @discord.ui.button(label="📥 Import", style=discord.ButtonStyle.secondary, row=1)
    async def import_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ImportModal(self.db, self.member, interaction.message)
        )
```

Remove `disabled=True` from both button decorators.

- [ ] **Step 6: Run profile tests**

```
pytest tests/test_profile_cog.py -x -q
```
Expected: all pass

- [ ] **Step 7: Run full suite**

```
pytest -x -q
```
Expected: 377 passed

- [ ] **Step 8: Commit**

```
git add cogs/profile.py tests/test_profile_cog.py
git commit -m "feat: implement profile Export/Import with JSON file attachment and modal restore"
```
