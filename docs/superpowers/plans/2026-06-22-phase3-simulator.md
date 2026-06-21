# Phase 3: Simulator + Skills Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken profile skill fields with the real Dank Memer skill system and build a fully interactive `/simulate` command backed by the external Dank Memer simulator API.

**Architecture:** Four sequential tasks: (1) DB foundation and data loading, (2) profile skills overhaul including SkillsPickerView in cogs/simulator.py, (3) the full simulator UI and /simulate command, (4) enable Simulate buttons in existing embeds. Tasks depend on each other in this order.

**Tech Stack:** discord.py 2.4+, aiosqlite, aiohttp (already installed but not in requirements.txt), data.json (local game data file at project root)

## Global Constraints

- Discord View max 5 rows; max 5 buttons per row; max 25 select options per Select
- Select menus cannot live in modals; use `edit_message()` pattern (established in Phase 2)
- Simulator API: `POST https://dankmemer.lol/api/bot/fish/simulator` with headers `Origin: https://dankmemer.lol` and `Referer: https://dankmemer.lol/fishing/simulator` (no auth required)
- Simulator API `skills` field format: `{"zoologist": 3, "haggler": 1}` — base skill name → tier integer; absent key means not unlocked
- `data.json` at project root is the authoritative source for skill metadata (133 entries, 25 base skills, 4 categories: Economy/Nature/Science/Social)
- `aiohttp` is already installed (3.14.1); add it to `requirements.txt`
- All new DB columns use `ALTER TABLE … ADD COLUMN` — no table recreation
- `fishing_skill`, `luck_skill`, `efficiency_skill` columns stay in schema but are abandoned (stop reading/writing them everywhere except the Reset path where we set them to 0 for backwards compat — actually omit them from Reset too, just add `skills=None`)
- Run `pytest` from `E:/disbot` — all 313+ tests must pass after each task
- Follow existing patterns: picker views use `min_values=0`, `_defer` callbacks, `edit_message()` for Save/Cancel

---

## File Map

| File | Task | Change |
|---|---|---|
| `migrations/002_skills_json.sql` | 1 | Create — adds `skills TEXT` column |
| `dankmemer_client.py` | 1 | Add `skill_categories`, `event_by_name`; extract `_parse_skill_categories()` |
| `utils/db.py` | 1 | Update `add_history` to accept optional `data` param |
| `requirements.txt` | 1 | Add `aiohttp>=3.9.0` |
| `tests/test_db.py` | 1 | Add 2 tests for `data` column |
| `utils/embeds.py` | 2, 4 | Task 2: update `build_profile_embed` skills field + `_format_skills` helper; Task 4: update simulation history row |
| `cogs/simulator.py` | 2, 3 | Task 2: add `_picker_embed` + `SkillsPickerView`; Task 3: add full simulator |
| `cogs/profile.py` | 2 | Remove `EditSkillsModal`; add `EditStatsModal`; wire `edit_skills_btn` + `edit_stats_btn`; update `ResetConfirmView`; update all `build_profile_embed` calls |
| `tests/test_profile_cog.py` | 2 | Update `make_user_row`, replace removed modal tests, add new tests |
| `tests/test_simulator_cog.py` | 3 | Create — tests for SimulatorView, ExtrasView, SkillsPickerView, API payload |
| `cogs/fish.py` | 4 | Enable `sim_btn` |
| `cogs/locations.py` | 4 | Enable `sim_btn` with pre-fill + immediate calculate |
| `cogs/tools.py` | 4 | Enable `sim_btn` with pre-fill |
| `cogs/baits.py` | 4 | Enable `sim_btn` with pre-fill |

---

## Task 1: DB Foundation

**Files:**
- Create: `migrations/002_skills_json.sql`
- Modify: `dankmemer_client.py`
- Modify: `utils/db.py`
- Modify: `requirements.txt`
- Modify: `tests/test_db.py`

**Interfaces:**
- Produces:
  - `Database.add_history(discord_id, type, item_id, data=None)` — new optional `data: str | None` param
  - `DankMemerGameClient.skill_categories: dict[str, list[dict]]` — `{"Economy": [{"base": "haggler", "name": "Haggler", "max_tier": 6}, ...], ...}`
  - `DankMemerGameClient.event_by_name: dict[str, Any]` — event name (lowercase) → event object
  - `_parse_skill_categories(items: list) -> dict` — pure function, importable for testing

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_db.py`:

```python
@pytest.mark.asyncio
async def test_add_history_stores_data(db):
    await db.add_history("111", "simulation", "river", data='{"failChance": 12.5}')
    rows = await db.get_history("111", "simulation")
    assert rows[0]["data"] == '{"failChance": 12.5}'

@pytest.mark.asyncio
async def test_add_history_data_defaults_none(db):
    await db.add_history("111", "fish", "goldfish")
    rows = await db.get_history("111", "fish")
    assert rows[0]["data"] is None
```

Also create `tests/test_dankmemer_client.py`:

```python
from dankmemer_client import _parse_skill_categories

def test_parse_skill_categories_groups_by_category():
    items = [
        {"id": "haggler-1", "name": "Haggler I", "extra": {"category": "Economy", "description": ""}},
        {"id": "haggler-2", "name": "Haggler II", "extra": {"category": "Economy", "description": ""}},
        {"id": "zoologist-1", "name": "Zoologist I", "extra": {"category": "Nature", "description": ""}},
    ]
    cats = _parse_skill_categories(items)
    assert "Economy" in cats
    assert "Nature" in cats
    assert cats["Economy"][0]["base"] == "haggler"
    assert cats["Economy"][0]["max_tier"] == 2
    assert cats["Nature"][0]["base"] == "zoologist"
    assert cats["Nature"][0]["max_tier"] == 1

def test_parse_skill_categories_strips_roman_suffix():
    items = [
        {"id": "keen-angler-3", "name": "Keen Angler III", "extra": {"category": "Nature", "description": ""}},
    ]
    cats = _parse_skill_categories(items)
    assert cats["Nature"][0]["name"] == "Keen Angler"

def test_parse_skill_categories_skips_malformed_ids():
    items = [
        {"id": "no-dash", "name": "No Dash", "extra": {"category": "Economy", "description": ""}},
    ]
    cats = _parse_skill_categories(items)
    assert cats == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd E:/disbot && pytest tests/test_db.py::test_add_history_stores_data tests/test_db.py::test_add_history_data_defaults_none tests/test_dankmemer_client.py -v
```
Expected: FAIL — `test_add_history_stores_data` fails because `data` column doesn't exist yet; `_parse_skill_categories` import fails.

- [ ] **Step 3: Create migration**

Create `migrations/002_skills_json.sql`:

```sql
ALTER TABLE users ADD COLUMN skills TEXT DEFAULT NULL;
```

- [ ] **Step 4: Update `utils/db.py` — add `data` param to `add_history`**

Replace lines 118–131 in `utils/db.py` (the `add_history` method):

```python
async def add_history(self, discord_id: str, type: str, item_id: str, data: str | None = None) -> None:
    logger.debug("DB add_history: %s %s %s", discord_id, type, item_id)
    await self._conn.execute(
        "INSERT INTO history (discord_id, type, item_id, data) VALUES (?, ?, ?, ?)",
        (discord_id, type, item_id, data),
    )
    await self._conn.execute(
        """DELETE FROM history WHERE discord_id = ? AND type = ? AND id NOT IN (
            SELECT id FROM history WHERE discord_id = ? AND type = ?
            ORDER BY created_at DESC, id DESC LIMIT 20
        )""",
        (discord_id, type, discord_id, type),
    )
    await self._conn.commit()
```

- [ ] **Step 5: Update `dankmemer_client.py`**

Add `_parse_skill_categories` as a module-level function, add `skill_categories` and `event_by_name` to the class, and call the loader in `preload()`.

Replace the top of `dankmemer_client.py` (keep existing imports, add after them):

```python
import json as _json
import re as _re
from pathlib import Path as _Path


def _parse_skill_categories(items: list) -> dict:
    """Parse raw skill items from data.json into {category: [{base, name, max_tier}]}."""
    cats: dict[str, list[dict]] = {}
    for s in items:
        m = _re.match(r"^(.+)-(\d+)$", s["id"])
        if not m:
            continue
        base, tier = m.group(1), int(m.group(2))
        cat = s["extra"]["category"]
        clean_name = _re.sub(r"\s+(IX|VIII|VII|VI|V|IV|III|II|I)$", "", s["name"])
        if cat not in cats:
            cats[cat] = []
        existing = next((x for x in cats[cat] if x["base"] == base), None)
        if existing:
            existing["max_tier"] = max(existing["max_tier"], tier)
        else:
            cats[cat].append({"base": base, "name": clean_name, "max_tier": tier})
    return cats
```

In `DankMemerGameClient.__init__`, add after `self.event_by_id`:

```python
        self.event_by_name: Dict[str, Any] = {}
        self.skill_categories: Dict[str, list] = {}
```

In `DankMemerGameClient.preload()`, in the events `try` block, add after `self.event_by_id[event.id] = event`:

```python
                self.event_by_name[event.name.lower()] = event
```

At the end of `preload()`, after the location_creature_map loop, add:

```python
        try:
            data_path = _Path(__file__).parent / "data.json"
            raw_skills = _json.loads(data_path.read_text(encoding="utf-8"))["data"]["skills"]["items"]
            self.skill_categories = _parse_skill_categories(raw_skills)
            logger.info("Loaded %d skill categories", len(self.skill_categories))
        except Exception:
            logger.warning("Failed to load skill categories from data.json", exc_info=True)
```

- [ ] **Step 6: Add `aiohttp` to `requirements.txt`**

Append to `requirements.txt`:

```
aiohttp>=3.9.0
```

- [ ] **Step 7: Run tests**

```
cd E:/disbot && pytest tests/test_db.py tests/test_dankmemer_client.py -v
```
Expected: All pass.

- [ ] **Step 8: Run full suite**

```
cd E:/disbot && pytest -x -q
```
Expected: All existing tests pass (313+).

- [ ] **Step 9: Commit**

```bash
git add migrations/002_skills_json.sql dankmemer_client.py utils/db.py requirements.txt tests/test_db.py tests/test_dankmemer_client.py
git commit -m "feat: add skills column migration, skill_categories loader, add_history data param"
```

---

## Task 2: Profile Skills Overhaul

**Files:**
- Modify: `utils/embeds.py`
- Modify: `cogs/simulator.py` (add `_picker_embed` + `SkillsPickerView`)
- Modify: `cogs/profile.py`
- Modify: `tests/test_profile_cog.py`

**Interfaces:**
- Consumes: `DankMemerGameClient.skill_categories` (from Task 1); `Database.update_user` with `skills=` kwarg
- Produces:
  - `build_profile_embed(user_row, member, dc=None)` — updated signature, now reads `user_row["skills"]` JSON
  - `SkillsPickerView(db, member, dc, current_skills: dict, return_fn)` in `cogs/simulator.py`
  - `EditStatsModal(db, member, message, dc=None)` in `cogs/profile.py`

- [ ] **Step 1: Write failing tests**

In `tests/test_profile_cog.py`:

1. Add `skills=None` to `make_user_row` defaults (after `compact_mode`):
```python
        "skills": None,
```

2. Replace `test_build_profile_embed_skills_field` (lines 93–101) with these two tests:

```python
def test_build_profile_embed_skills_shows_no_skills_when_none():
    from utils.embeds import build_profile_embed
    row = make_user_row(skills=None, prestige=2, coins=1000)
    member = make_member()
    embed = build_profile_embed(row, member)
    skills_field = next(f for f in embed.fields if "SKILLS" in f.name)
    assert "No skills unlocked" in skills_field.value
    assert "1,000" in skills_field.value

def test_build_profile_embed_skills_shows_real_skills():
    from utils.embeds import build_profile_embed
    import json
    row = make_user_row(skills=json.dumps({"zoologist": 3, "haggler": 1}))
    member = make_member()
    embed = build_profile_embed(row, member)
    skills_field = next(f for f in embed.fields if "SKILLS" in f.name)
    assert "III" in skills_field.value or "3" in skills_field.value
```

3. Replace `test_edit_skills_modal_rejects_negative_skill` and `test_edit_skills_modal_saves_valid_values` (they test the removed `EditSkillsModal`) with `EditStatsModal` tests:

```python
@pytest.mark.asyncio
async def test_edit_stats_modal_rejects_negative():
    from cogs.profile import EditStatsModal
    db = MagicMock()
    member = make_member()
    message = AsyncMock()
    modal = EditStatsModal(db, member, message)
    modal.prestige._value = "-1"
    modal.coins._value = ""
    interaction = make_interaction()
    await modal.on_submit(interaction)
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True
    db.update_user.assert_not_called()

@pytest.mark.asyncio
async def test_edit_stats_modal_saves_prestige_and_coins():
    from cogs.profile import EditStatsModal
    db = MagicMock()
    db.update_user = AsyncMock()
    db.get_user = AsyncMock(return_value=make_user_row(prestige=5, coins=500))
    member = make_member()
    message = AsyncMock()
    modal = EditStatsModal(db, member, message)
    modal.prestige._value = "5"
    modal.coins._value = "500"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    db.update_user.assert_called_once()
    kwargs = db.update_user.call_args.kwargs
    assert kwargs.get("prestige") == 5
    assert kwargs.get("coins") == 500
```

4. Replace `test_profile_view_has_expected_buttons` to check for "Edit Stats" button and NOT "Edit Skills" modal:

```python
@pytest.mark.asyncio
async def test_profile_view_has_expected_buttons():
    from cogs.profile import ProfileView
    db = MagicMock()
    dc = MagicMock()
    dc.tool_by_id = {}
    dc.bait_by_id = {}
    dc.skill_categories = {}
    member = make_member()
    view = ProfileView(db, member, dc)
    labels = [item.label for item in view.children if isinstance(item, discord.ui.Button)]
    assert any("Edit Setup" in l for l in labels)
    assert any("Edit Skills" in l for l in labels)
    assert any("Edit Stats" in l for l in labels)
    assert any("Edit Unlocks" in l for l in labels)
    assert any("Reset" in l for l in labels)
    export_btn = next((item for item in view.children if isinstance(item, discord.ui.Button) and "Export" in item.label), None)
    assert export_btn is not None
    assert export_btn.disabled is True
```

5. Add SkillsPickerView tests:

```python
@pytest.mark.asyncio
async def test_skills_picker_view_shows_category_tabs():
    from cogs.simulator import SkillsPickerView
    db = MagicMock()
    dc = MagicMock()
    dc.skill_categories = {
        "Economy": [{"base": "haggler", "name": "Haggler", "max_tier": 3}],
        "Nature": [{"base": "zoologist", "name": "Zoologist", "max_tier": 5}],
    }
    member = make_member()
    async def return_fn(inter): pass
    view = SkillsPickerView(db, member, dc, {}, return_fn)
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    labels = [b.label for b in buttons]
    assert "Economy" in labels
    assert "Nature" in labels

@pytest.mark.asyncio
async def test_skills_picker_save_writes_skills_to_db():
    from cogs.simulator import SkillsPickerView
    import json
    db = MagicMock()
    db.update_user = AsyncMock()
    dc = MagicMock()
    dc.skill_categories = {
        "Economy": [{"base": "haggler", "name": "Haggler", "max_tier": 3}],
    }
    member = make_member()
    returned = []
    async def return_fn(inter): returned.append(True)
    view = SkillsPickerView(db, member, dc, {}, return_fn)
    view._pending["haggler"] = 2
    interaction = make_interaction()
    await view._save(interaction)
    db.update_user.assert_called_once()
    written = db.update_user.call_args.kwargs.get("skills")
    assert json.loads(written) == {"haggler": 2}
    assert returned

@pytest.mark.asyncio
async def test_skills_picker_save_removes_tier_zero():
    from cogs.simulator import SkillsPickerView
    import json
    db = MagicMock()
    db.update_user = AsyncMock()
    dc = MagicMock()
    dc.skill_categories = {
        "Economy": [{"base": "haggler", "name": "Haggler", "max_tier": 3}],
    }
    member = make_member()
    async def return_fn(inter): pass
    view = SkillsPickerView(db, member, dc, {"haggler": 2}, return_fn)
    view._pending["haggler"] = 0  # user cleared it
    interaction = make_interaction()
    await view._save(interaction)
    written = db.update_user.call_args.kwargs.get("skills")
    # haggler removed from JSON
    assert "haggler" not in (json.loads(written) if written else {})

@pytest.mark.asyncio
async def test_skills_picker_cancel_calls_return_fn():
    from cogs.simulator import SkillsPickerView
    db = MagicMock()
    dc = MagicMock()
    dc.skill_categories = {}
    member = make_member()
    returned = []
    async def return_fn(inter): returned.append(True)
    view = SkillsPickerView(db, member, dc, {}, return_fn)
    interaction = make_interaction()
    await view._cancel(interaction)
    assert returned
```

6. Update `test_reset_confirm_view_confirm_resets_user` (line 300–314): remove the `fishing_skill == 0` assertion, add `skills` check:

```python
@pytest.mark.asyncio
async def test_reset_confirm_view_confirm_resets_user():
    from cogs.profile import ResetConfirmView
    db = MagicMock()
    db.update_user = AsyncMock()
    db.get_user = AsyncMock(return_value=make_user_row())
    dc = MagicMock()
    member = make_member()
    view = ResetConfirmView(db, member, dc)
    interaction = make_interaction()
    await view.confirm_btn.callback(interaction)
    db.update_user.assert_called_once()
    call_kwargs = db.update_user.call_args.kwargs
    assert call_kwargs.get("boss_unlock") == 0
    assert "skills" in call_kwargs
    assert call_kwargs.get("skills") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd E:/disbot && pytest tests/test_profile_cog.py -v 2>&1 | tail -30
```
Expected: Multiple failures — `EditStatsModal` not found, `build_profile_embed` still shows old fields, etc.

- [ ] **Step 3: Update `utils/embeds.py` — `build_profile_embed` skills display**

Add this helper function in `utils/embeds.py` before `build_profile_embed` (around line 509):

```python
import json as _skills_json

_ROMAN = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX")

def _format_skills(skills_json: str | None, dc=None) -> str:
    if not skills_json:
        return "No skills unlocked"
    try:
        skills = _skills_json.loads(skills_json)
    except (ValueError, TypeError):
        return "No skills unlocked"
    if not skills:
        return "No skills unlocked"
    if dc and getattr(dc, "skill_categories", None):
        cat_parts = {}
        for cat, skill_list in dc.skill_categories.items():
            entries = []
            for s in skill_list:
                tier = skills.get(s["base"], 0)
                if tier > 0:
                    entries.append(f"{s['name']} {_ROMAN[min(tier, 9)]}")
            if entries:
                cat_parts[cat] = entries
        if not cat_parts:
            return "No skills unlocked"
        return "\n".join(f"{cat}: {', '.join(entries)}" for cat, entries in cat_parts.items())
    parts = []
    for base, tier in skills.items():
        if tier > 0:
            parts.append(f"{base.replace('-', ' ').title()} {_ROMAN[min(tier, 9)]}")
    return ", ".join(parts) if parts else "No skills unlocked"
```

Update `build_profile_embed` signature and SKILLS field (lines 510–538):

```python
def build_profile_embed(user_row, member, dc=None) -> discord.Embed:
    embed = discord.Embed(color=0x5865F2)
    embed.set_author(name="\U0001f464 Profile")
    embed.title = getattr(member, "display_name", str(member))
    if hasattr(member, "display_avatar") and member.display_avatar:
        embed.set_thumbnail(url=str(member.display_avatar.url))

    rod = user_row["fishing_rod"] or "Wooden Rod"
    tool = user_row["current_tool"] or "None"
    bait = user_row["current_bait"] or "None"
    embed.add_field(
        name="\U0001f3a3 SETUP",
        value=f"Rod: **{rod}**  ·  Tool: **{tool}**  ·  Bait: **{bait}**",
        inline=False,
    )

    try:
        skills_json = user_row["skills"]
    except (KeyError, IndexError):
        skills_json = None
    prestige = user_row["prestige"] or 0
    coins = user_row["coins"] or 0
    embed.add_field(
        name="\U0001f4ca SKILLS",
        value=(
            f"{_format_skills(skills_json, dc)}\n"
            f"Prestige: **{prestige}**  ·  Coins: **{coins:,}**"
        ),
        inline=False,
    )

    boss = "✅" if user_row["boss_unlock"] else "❌"
    myth = "✅" if user_row["mythical_unlock"] else "❌"
    embed.add_field(
        name="\U0001f513 UNLOCKS",
        value=f"\U0001f451 Boss: {boss}  ·  ✨ Mythical: {myth}",
        inline=False,
    )

    weather = user_row["current_weather"] or "None"
    event = user_row["current_event"] or "None"
    embed.add_field(
        name="\U0001f324️ ENVIRONMENT",
        value=f"Weather: **{weather}**  ·  Event: **{event}**",
        inline=False,
    )

    ff = user_row["favorite_fish"] or "None"
    fl = user_row["favorite_location"] or "None"
    ft = user_row["favorite_tool"] or "None"
    fb = user_row["favorite_bait"] or "None"
    embed.add_field(
        name="⭐ FAVOURITES",
        value=f"Fish: **{ff}**  ·  Location: **{fl}**\nTool: **{ft}**  ·  Bait: **{fb}**",
        inline=False,
    )

    embed.set_footer(text=f"Last updated: {user_row['updated_at'] or 'Never'}")
    return embed
```

- [ ] **Step 4: Add `SkillsPickerView` and `_picker_embed` to `cogs/simulator.py`**

Replace the entire `cogs/simulator.py` with this (keeps the skeleton command, adds picker):

```python
from __future__ import annotations
import json as _json
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder

SKILL_CATEGORIES_ORDER = ["Economy", "Nature", "Science", "Social"]
_ROMAN = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX")


def _picker_embed(title: str) -> discord.Embed:
    return discord.Embed(
        title=title,
        description="Make your selections below, then click **✅ Save**.",
        color=0x5865F2,
    )


class SkillsPickerView(discord.ui.View):
    """
    4-category paginated skills picker. Shared between profile and simulator.
    return_fn: async callable(interaction) → None — called on both Save and Cancel.
    Save first writes pending skills to DB.
    """

    def __init__(self, db, member, dc, current_skills: dict, return_fn):
        super().__init__(timeout=300)
        self.db = db
        self.member = member
        self.dc = dc
        self._current_skills = dict(current_skills)
        self._pending: dict[str, int] = {}
        self._category = next(
            (c for c in SKILL_CATEGORIES_ORDER if c in dc.skill_categories),
            SKILL_CATEGORIES_ORDER[0],
        )
        self._page = 0
        self._return_fn = return_fn
        self._rebuild()

    def _skills_for_cat(self) -> list[dict]:
        return self.dc.skill_categories.get(self._category, [])

    def _page_count(self) -> int:
        return max(1, (len(self._skills_for_cat()) + 2) // 3)

    def _rebuild(self) -> None:
        self.clear_items()

        # Row 0: category tab buttons
        for cat in SKILL_CATEGORIES_ORDER:
            if cat not in self.dc.skill_categories:
                continue
            btn = discord.ui.Button(
                label=cat,
                style=discord.ButtonStyle.primary if cat == self._category else discord.ButtonStyle.secondary,
                row=0,
            )
            btn.callback = self._make_cat_cb(cat)
            self.add_item(btn)

        # Rows 1-3: up to 3 skill selects for current page
        skills = self._skills_for_cat()
        page_skills = skills[self._page * 3 : self._page * 3 + 3]
        for i, skill in enumerate(page_skills):
            base = skill["base"]
            max_tier = skill["max_tier"]
            effective = self._pending.get(base, self._current_skills.get(base, 0))
            placeholder = (
                f"{skill['name']} — {_ROMAN[min(effective, 9)]}"
                if effective > 0
                else f"{skill['name']} — Not Unlocked"
            )
            opts = [discord.SelectOption(label="— Not Unlocked —", value="0")] + [
                discord.SelectOption(label=f"Tier {_ROMAN[t]}", value=str(t))
                for t in range(1, min(max_tier, 9) + 1)
            ]
            sel = discord.ui.Select(
                placeholder=placeholder, options=opts[:25], min_values=0, max_values=1, row=i + 1
            )
            sel.callback = self._make_skill_cb(base, sel)
            self.add_item(sel)

        # Row 4: nav + save/cancel
        page_count = self._page_count()
        prev_btn = discord.ui.Button(
            label="◀", style=discord.ButtonStyle.secondary,
            disabled=self._page == 0, row=4,
        )
        prev_btn.callback = self._prev_page
        self.add_item(prev_btn)

        next_btn = discord.ui.Button(
            label="▶", style=discord.ButtonStyle.secondary,
            disabled=self._page >= page_count - 1, row=4,
        )
        next_btn.callback = self._next_page
        self.add_item(next_btn)

        save_btn = discord.ui.Button(label="✅ Save", style=discord.ButtonStyle.success, row=4)
        save_btn.callback = self._save
        self.add_item(save_btn)

        cancel_btn = discord.ui.Button(label="❌ Cancel", style=discord.ButtonStyle.secondary, row=4)
        cancel_btn.callback = self._cancel
        self.add_item(cancel_btn)

    def _make_cat_cb(self, cat: str):
        async def callback(interaction: discord.Interaction) -> None:
            self._category = cat
            self._page = 0
            self._rebuild()
            await interaction.response.edit_message(view=self)
        return callback

    def _make_skill_cb(self, base: str, sel: discord.ui.Select):
        async def callback(interaction: discord.Interaction) -> None:
            if sel.values:
                self._pending[base] = int(sel.values[0])
            await interaction.response.defer()
        return callback

    async def _prev_page(self, interaction: discord.Interaction) -> None:
        self._page = max(0, self._page - 1)
        self._rebuild()
        await interaction.response.edit_message(view=self)

    async def _next_page(self, interaction: discord.Interaction) -> None:
        self._page = min(self._page_count() - 1, self._page + 1)
        self._rebuild()
        await interaction.response.edit_message(view=self)

    async def _save(self, interaction: discord.Interaction) -> None:
        merged = dict(self._current_skills)
        for base, tier in self._pending.items():
            if tier == 0:
                merged.pop(base, None)
            else:
                merged[base] = tier
        skills_value = _json.dumps(merged) if merged else None
        await self.db.update_user(str(self.member.id), skills=skills_value)
        await self._return_fn(interaction)

    async def _cancel(self, interaction: discord.Interaction) -> None:
        await self._return_fn(interaction)


class SimulatorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="simulate", description="Simulate fishing (coming in Phase 3 Task 3)")
    async def simulate(self, interaction: discord.Interaction):
        embed = EmbedBuilder.info("Simulator", "Full simulator coming soon.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SimulatorCog(bot))
```

- [ ] **Step 5: Update `cogs/profile.py`**

**5a.** Remove `EditSkillsModal` class entirely (lines 72–129).

**5b.** Add `EditStatsModal` after the `FavFishModal` class (around line 66), before the picker views section:

```python
class EditStatsModal(discord.ui.Modal, title="Edit Stats"):
    prestige: discord.ui.TextInput = discord.ui.TextInput(
        label="Prestige", placeholder="0+", required=False, max_length=6
    )
    coins: discord.ui.TextInput = discord.ui.TextInput(
        label="Coins", placeholder="0+", required=False, max_length=15
    )

    def __init__(self, db, member, message, dc=None):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message
        self.dc = dc

    async def on_submit(self, interaction: discord.Interaction) -> None:
        fields = {"prestige": self.prestige.value, "coins": self.coins.value}
        updates: dict = {}
        for key, raw in fields.items():
            if not raw.strip():
                continue
            try:
                val = int(raw.strip())
                if val < 0:
                    raise ValueError
                updates[key] = val
            except ValueError:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error(
                        "Invalid value",
                        f"**{key.title()}** must be a non-negative integer.",
                    ),
                    ephemeral=True,
                )
                return
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await self.message.edit(
            embed=build_profile_embed(user_row, self.member, self.dc),
            view=ProfileView(self.db, self.member, self.dc),
        )
        await interaction.response.defer()
```

**5c.** Update `ProfileView.edit_skills_btn` to open `SkillsPickerView`:

```python
    @discord.ui.button(label="📊 Edit Skills", style=discord.ButtonStyle.secondary, row=0)
    async def edit_skills_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.simulator import SkillsPickerView
        user_row = await self.db.get_user(str(self.member.id))
        try:
            current_skills = _json.loads(user_row["skills"]) if user_row["skills"] else {}
        except (ValueError, TypeError, KeyError, IndexError):
            current_skills = {}

        async def return_fn(inter: discord.Interaction) -> None:
            fresh_row = await self.db.get_user(str(self.member.id))
            await inter.response.edit_message(
                embed=build_profile_embed(fresh_row, self.member, self.dc),
                view=ProfileView(self.db, self.member, self.dc),
            )

        await interaction.response.edit_message(
            embed=_picker_embed("📊 Edit Skills"),
            view=SkillsPickerView(self.db, self.member, self.dc, current_skills, return_fn),
        )
```

Add `import json as _json` at the top of `cogs/profile.py` (after `from __future__ import annotations`).

**5d.** Add `edit_stats_btn` to `ProfileView` (after `reset_btn` on row 1):

```python
    @discord.ui.button(label="📈 Edit Stats", style=discord.ButtonStyle.secondary, row=1)
    async def edit_stats_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            EditStatsModal(self.db, self.member, interaction.message, self.dc)
        )
```

**5e.** Update `ResetConfirmView.confirm_btn` — replace `fishing_skill=0, luck_skill=0, efficiency_skill=0` with `skills=None` and remove the old skill fields:

```python
    @discord.ui.button(label="✅ Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(self.member.id)
        await self.db.update_user(
            user_id,
            fishing_rod="Wooden Rod",
            current_tool=None,
            current_bait=None,
            skills=None,
            prestige=0,
            coins=0,
            boss_unlock=0,
            mythical_unlock=0,
            favorite_fish=None,
            favorite_location=None,
            favorite_tool=None,
            favorite_bait=None,
            current_weather=None,
            current_event=None,
        )
        user_row = await self.db.get_user(user_id)
        await interaction.response.edit_message(
            embed=build_profile_embed(user_row, self.member, self.dc),
            view=ProfileView(self.db, self.member, self.dc),
        )
```

**5f.** Update ALL calls to `build_profile_embed` in `cogs/profile.py` to pass `self.dc` as third argument. Find every occurrence of `build_profile_embed(user_row, self.member)` and replace with `build_profile_embed(user_row, self.member, self.dc)`. There are ~10 occurrences across `EditSetupView`, `EditUnlocksView`, `EditEnvView`, `EditFavsView`, `ResetConfirmView` — update them all.

Also update the `ProfileCog.profile` callback call (which uses `member` not `self.member`) to pass `self.bot.dank_client`.

- [ ] **Step 6: Run failing tests**

```
cd E:/disbot && pytest tests/test_profile_cog.py -v 2>&1 | tail -30
```
Expected: All new tests pass.

- [ ] **Step 7: Run full suite**

```
cd E:/disbot && pytest -x -q
```
Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add utils/embeds.py cogs/simulator.py cogs/profile.py tests/test_profile_cog.py
git commit -m "feat: profile skills overhaul — real skill display, EditStatsModal, SkillsPickerView"
```

---

## Task 3: Simulator Core

**Files:**
- Modify: `cogs/simulator.py` (expand from Task 2's skeleton)
- Create: `tests/test_simulator_cog.py`

**Interfaces:**
- Consumes: `SkillsPickerView` (from Task 2); `Database.add_history(data=...)` (from Task 1); `DankMemerGameClient.skill_categories`, `event_by_name`, `location_by_name`, `tool_by_name`, `bait_by_name`, `fish_by_id`, `bait_by_id` (from Task 1)
- Produces:
  - `call_simulator_api(payload: dict) -> dict` — async, raises on HTTP error
  - `build_sim_results_embed(data: dict, state: dict, dc) -> discord.Embed`
  - `SimulatorView(db, member, dc, initial_state=None)` — main interactive view
  - `ExtrasView(parent: SimulatorView, current_embed: discord.Embed)` — extras sub-view
  - `TimeModal(parent: SimulatorView)` — hour input modal
  - `SimulatorCog.simulate` — the `/simulate` slash command

- [ ] **Step 1: Write failing tests**

Create `tests/test_simulator_cog.py`:

```python
"""Tests for cogs/simulator.py — SimulatorView, ExtrasView, build_sim_results_embed."""
from __future__ import annotations
import json
import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch


def make_member(user_id="123", display_name="Tester"):
    m = MagicMock(spec=discord.Member)
    m.id = int(user_id)
    m.display_name = display_name
    return m


def make_interaction():
    inter = MagicMock()
    inter.response = AsyncMock()
    inter.response.edit_message = AsyncMock()
    inter.response.send_message = AsyncMock()
    inter.response.send_modal = AsyncMock()
    inter.response.defer = AsyncMock()
    inter.followup = AsyncMock()
    inter.edit_original_response = AsyncMock()
    inter.message = MagicMock()
    inter.message.delete = AsyncMock()
    inter.user = make_member()
    return inter


def make_dc():
    dc = MagicMock()
    dc.location_by_id = {"river": MagicMock(id="river", name="Wily River")}
    dc.location_by_name = {"wily river": dc.location_by_id["river"]}
    dc.tool_by_id = {"rod": MagicMock(id="rod", name="Basic Rod")}
    dc.tool_by_name = {"basic rod": dc.tool_by_id["rod"]}
    dc.bait_by_id = {"worm": MagicMock(id="worm", name="Worm")}
    dc.bait_by_name = {"worm": dc.bait_by_id["worm"]}
    dc.event_by_id = {"2xtokens": MagicMock(id="2xtokens", name="Token Clone")}
    dc.event_by_name = {"token clone": dc.event_by_id["2xtokens"]}
    dc.fish_by_id = {"bass": MagicMock(id="bass", name="Bass")}
    dc.skill_categories = {
        "Economy": [{"base": "haggler", "name": "Haggler", "max_tier": 3}],
    }
    return dc


def make_user_row(**kw):
    defaults = {
        "discord_id": "123", "fishing_rod": "Wooden Rod",
        "current_tool": None, "current_bait": None,
        "boss_unlock": 0, "mythical_unlock": 0,
        "favorite_location": None, "current_event": None,
        "skills": None, "prestige": 0, "coins": 0,
        "favorite_fish": None, "favorite_tool": None, "favorite_bait": None,
        "current_weather": None, "updated_at": "2026-01-01",
        "fishing_skill": 0, "luck_skill": 0, "efficiency_skill": 0,
        "timezone": "UTC", "theme": "dark", "compact_mode": 0,
    }
    return {**defaults, **kw}


# --- SimulatorView ---

@pytest.mark.asyncio
async def test_simulator_view_has_4_selects_and_5_buttons():
    from cogs.simulator import SimulatorView
    db = MagicMock()
    dc = make_dc()
    member = make_member()
    view = SimulatorView(db, member, dc)
    selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    assert len(selects) == 4
    assert len(buttons) == 5
    btn_labels = [b.label for b in buttons]
    assert "🔄 Calculate" in btn_labels
    assert "👥 Skills" in btn_labels
    assert "⚙️ Extras" in btn_labels
    assert "🕐 Set Time" in btn_labels
    assert "🗑️ Delete" in btn_labels


@pytest.mark.asyncio
async def test_simulator_view_build_payload_uses_profile_defaults():
    from cogs.simulator import SimulatorView
    db = MagicMock()
    dc = make_dc()
    member = make_member()
    initial_state = {"location_id": "river", "tool_id": "rod", "bait_id": None, "event_id": None, "hour": 14}
    view = SimulatorView(db, member, dc, initial_state=initial_state)
    user_row = make_user_row(boss_unlock=1, skills=json.dumps({"haggler": 2}))
    payload = view._build_payload(user_row)
    assert payload["locationID"] == "river"
    assert payload["toolID"] == "rod"
    assert payload["bosses"] is True
    assert payload["skills"] == {"haggler": 2}
    assert payload["anglerTuesday"] is False


@pytest.mark.asyncio
async def test_simulator_view_delete_btn_deletes_message():
    from cogs.simulator import SimulatorView
    db = MagicMock()
    dc = make_dc()
    member = make_member()
    view = SimulatorView(db, member, dc)
    delete_btn = next(b for b in view.children if isinstance(b, discord.ui.Button) and b.label == "🗑️ Delete")
    interaction = make_interaction()
    await delete_btn.callback(interaction)
    interaction.message.delete.assert_called_once()


# --- ExtrasView ---

@pytest.mark.asyncio
async def test_extras_view_save_updates_parent_state():
    from cogs.simulator import SimulatorView, ExtrasView
    from utils.embeds import EmbedBuilder
    db = MagicMock()
    dc = make_dc()
    member = make_member()
    parent = SimulatorView(db, member, dc)
    current_embed = EmbedBuilder.info("Test", "")
    view = ExtrasView(parent, current_embed)
    view._tuesday_sel._values = ["1"]
    view._winner_sel._values = ["1"]
    interaction = make_interaction()
    await view.save_btn.callback(interaction)
    assert parent._angler_tuesday is True
    assert parent._loc_winner is True
    interaction.response.edit_message.assert_called_once()


@pytest.mark.asyncio
async def test_extras_view_cancel_restores_without_change():
    from cogs.simulator import SimulatorView, ExtrasView
    from utils.embeds import EmbedBuilder
    db = MagicMock()
    dc = make_dc()
    member = make_member()
    parent = SimulatorView(db, member, dc)
    embed = EmbedBuilder.info("Test", "")
    view = ExtrasView(parent, embed)
    interaction = make_interaction()
    await view.cancel_btn.callback(interaction)
    assert parent._angler_tuesday is False  # unchanged
    interaction.response.edit_message.assert_called_once()


# --- build_sim_results_embed ---

def test_build_sim_results_embed_shows_fail_and_npc():
    from cogs.simulator import build_sim_results_embed
    dc = make_dc()
    data = {
        "failChance": 12.5,
        "npcChance": 5.0,
        "table": [
            {"chance": 20.0, "baseChance": 15.0, "value": {"type": "fish-creature", "creatureID": "bass"}},
            {"chance": 5.0, "baseChance": 5.0, "value": {"type": "loot", "item": 244}},
        ],
        "variants": {},
    }
    state = {"location_id": "river", "tool_id": "rod", "bait_id": None, "event_id": None, "hour": 10}
    embed = build_sim_results_embed(data, state, dc)
    full_text = " ".join(f.value for f in embed.fields) + (embed.description or "")
    assert "12.5" in full_text
    assert "5.0" in full_text
    assert "Bass" in full_text
    assert "Misc Loot" in full_text


def test_build_sim_results_embed_shows_variants():
    from cogs.simulator import build_sim_results_embed
    dc = make_dc()
    data = {
        "failChance": 0,
        "npcChance": 0,
        "table": [],
        "variants": {
            "bass": [
                {"name": "unique", "type": "unique", "chance": 1.5},
                {"name": "chroma", "type": "chroma", "chance": 0.5},
            ]
        },
    }
    state = {"location_id": "river", "tool_id": None, "bait_id": None, "event_id": None, "hour": 0}
    embed = build_sim_results_embed(data, state, dc)
    variant_field = next((f for f in embed.fields if "Variant" in f.name), None)
    assert variant_field is not None
    assert "Bass" in variant_field.value
    assert "1.5" in variant_field.value


# --- call_simulator_api ---

@pytest.mark.asyncio
async def test_call_simulator_api_posts_correct_headers():
    from cogs.simulator import call_simulator_api
    fake_response = {"failChance": 10, "npcChance": 5, "table": [], "variants": {}}
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = AsyncMock(return_value=fake_response)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    with patch("cogs.simulator.aiohttp.ClientSession", return_value=mock_session):
        result = await call_simulator_api({"locationID": "river"})
    assert result["failChance"] == 10
    call_kwargs = mock_session.post.call_args
    headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
    assert headers.get("Origin") == "https://dankmemer.lol"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd E:/disbot && pytest tests/test_simulator_cog.py -v 2>&1 | tail -20
```
Expected: Most fail — `SimulatorView`, `ExtrasView`, `call_simulator_api`, `build_sim_results_embed` not yet defined.

- [ ] **Step 3: Implement the full simulator in `cogs/simulator.py`**

Replace `cogs/simulator.py` with the complete implementation (keep `SkillsPickerView` from Task 2, add everything below it):

```python
from __future__ import annotations
import json as _json
from datetime import datetime, timezone
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder

SKILL_CATEGORIES_ORDER = ["Economy", "Nature", "Science", "Social"]
_ROMAN = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX")
_SIM_URL = "https://dankmemer.lol/api/bot/fish/simulator"
_SIM_HEADERS = {
    "Origin": "https://dankmemer.lol",
    "Referer": "https://dankmemer.lol/fishing/simulator",
    "Content-Type": "application/json",
}


def _picker_embed(title: str) -> discord.Embed:
    return discord.Embed(
        title=title,
        description="Make your selections below, then click **✅ Save**.",
        color=0x5865F2,
    )


async def call_simulator_api(payload: dict) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.post(_SIM_URL, json=payload, headers=_SIM_HEADERS) as resp:
            resp.raise_for_status()
            return await resp.json()


def build_sim_results_embed(data: dict, state: dict, dc) -> discord.Embed:
    fail = data.get("failChance", 0)
    npc = data.get("npcChance", 0)

    loc_id = state.get("location_id")
    loc_name = dc.location_by_id[loc_id].name if loc_id and loc_id in dc.location_by_id else "No Location"
    hour = state.get("hour", 0)

    embed = discord.Embed(title=f"🎣 {loc_name}", color=0x5865F2)
    embed.set_author(name="🎣 Simulator")
    embed.description = f"Hour: **{hour:02d}:00 UTC**"
    embed.add_field(name="❌ Fail", value=f"{fail:.1f}%", inline=True)
    embed.add_field(name="👤 NPC", value=f"{npc:.1f}%", inline=True)

    table = sorted(data.get("table", []), key=lambda x: x.get("chance", 0), reverse=True)
    lines = []
    for entry in table[:20]:
        chance = entry.get("chance", 0)
        base = entry.get("baseChance", chance)
        val = entry.get("value", {})
        if val.get("type") == "fish-creature":
            cid = val.get("creatureID", "")
            name = dc.fish_by_id[cid].name if cid in dc.fish_by_id else cid
        elif val.get("type") == "fish-bait":
            bid = val.get("baitID", "")
            name = dc.bait_by_id[bid].name if bid in dc.bait_by_id else bid
        else:
            name = "Misc Loot"
        lines.append(f"`{chance:5.1f}%` (base `{base:.1f}%`) {name}")
    if lines:
        embed.add_field(name="📊 Catch Table", value="\n".join(lines), inline=False)

    var_lines = []
    for cid, var_list in data.get("variants", {}).items():
        name = dc.fish_by_id[cid].name if cid in dc.fish_by_id else cid
        parts = [f"{v['type'].capitalize()}: {v['chance']:.1f}%" for v in var_list if v.get("chance", 0) > 0]
        if parts:
            var_lines.append(f"**{name}** — {' · '.join(parts)}")
    if var_lines:
        embed.add_field(name="✨ Variants", value="\n".join(var_lines[:10]), inline=False)

    return embed


# SkillsPickerView  (defined here; imported by cogs/profile.py)

class SkillsPickerView(discord.ui.View):
    def __init__(self, db, member, dc, current_skills: dict, return_fn):
        super().__init__(timeout=300)
        self.db = db
        self.member = member
        self.dc = dc
        self._current_skills = dict(current_skills)
        self._pending: dict[str, int] = {}
        self._category = next(
            (c for c in SKILL_CATEGORIES_ORDER if c in dc.skill_categories),
            SKILL_CATEGORIES_ORDER[0],
        )
        self._page = 0
        self._return_fn = return_fn
        self._rebuild()

    def _skills_for_cat(self) -> list[dict]:
        return self.dc.skill_categories.get(self._category, [])

    def _page_count(self) -> int:
        return max(1, (len(self._skills_for_cat()) + 2) // 3)

    def _rebuild(self) -> None:
        self.clear_items()
        for cat in SKILL_CATEGORIES_ORDER:
            if cat not in self.dc.skill_categories:
                continue
            btn = discord.ui.Button(
                label=cat,
                style=discord.ButtonStyle.primary if cat == self._category else discord.ButtonStyle.secondary,
                row=0,
            )
            btn.callback = self._make_cat_cb(cat)
            self.add_item(btn)

        skills = self._skills_for_cat()
        page_skills = skills[self._page * 3 : self._page * 3 + 3]
        for i, skill in enumerate(page_skills):
            base = skill["base"]
            max_tier = skill["max_tier"]
            effective = self._pending.get(base, self._current_skills.get(base, 0))
            placeholder = (
                f"{skill['name']} — {_ROMAN[min(effective, 9)]}"
                if effective > 0
                else f"{skill['name']} — Not Unlocked"
            )
            opts = [discord.SelectOption(label="— Not Unlocked —", value="0")] + [
                discord.SelectOption(label=f"Tier {_ROMAN[t]}", value=str(t))
                for t in range(1, min(max_tier, 9) + 1)
            ]
            sel = discord.ui.Select(
                placeholder=placeholder, options=opts[:25], min_values=0, max_values=1, row=i + 1
            )
            sel.callback = self._make_skill_cb(base, sel)
            self.add_item(sel)

        page_count = self._page_count()
        prev_btn = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary, disabled=self._page == 0, row=4)
        prev_btn.callback = self._prev_page
        self.add_item(prev_btn)
        next_btn = discord.ui.Button(label="▶", style=discord.ButtonStyle.secondary, disabled=self._page >= page_count - 1, row=4)
        next_btn.callback = self._next_page
        self.add_item(next_btn)
        save_btn = discord.ui.Button(label="✅ Save", style=discord.ButtonStyle.success, row=4)
        save_btn.callback = self._save
        self.add_item(save_btn)
        cancel_btn = discord.ui.Button(label="❌ Cancel", style=discord.ButtonStyle.secondary, row=4)
        cancel_btn.callback = self._cancel
        self.add_item(cancel_btn)

    def _make_cat_cb(self, cat: str):
        async def callback(interaction: discord.Interaction) -> None:
            self._category = cat
            self._page = 0
            self._rebuild()
            await interaction.response.edit_message(view=self)
        return callback

    def _make_skill_cb(self, base: str, sel: discord.ui.Select):
        async def callback(interaction: discord.Interaction) -> None:
            if sel.values:
                self._pending[base] = int(sel.values[0])
            await interaction.response.defer()
        return callback

    async def _prev_page(self, interaction: discord.Interaction) -> None:
        self._page = max(0, self._page - 1)
        self._rebuild()
        await interaction.response.edit_message(view=self)

    async def _next_page(self, interaction: discord.Interaction) -> None:
        self._page = min(self._page_count() - 1, self._page + 1)
        self._rebuild()
        await interaction.response.edit_message(view=self)

    async def _save(self, interaction: discord.Interaction) -> None:
        merged = dict(self._current_skills)
        for base, tier in self._pending.items():
            if tier == 0:
                merged.pop(base, None)
            else:
                merged[base] = tier
        await self.db.update_user(str(self.member.id), skills=_json.dumps(merged) if merged else None)
        await self._return_fn(interaction)

    async def _cancel(self, interaction: discord.Interaction) -> None:
        await self._return_fn(interaction)


class TimeModal(discord.ui.Modal, title="Set UTC Hour"):
    hour: discord.ui.TextInput = discord.ui.TextInput(
        label="UTC Hour (0–23)", placeholder="e.g. 14", required=True, max_length=2
    )

    def __init__(self, parent: "SimulatorView"):
        super().__init__()
        self.parent = parent

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            h = int(self.hour.value.strip())
            if not (0 <= h <= 23):
                raise ValueError
            self.parent._hour = h
            await interaction.response.defer()
        except ValueError:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid hour", "Enter a whole number between 0 and 23."),
                ephemeral=True,
            )


class ExtrasView(discord.ui.View):
    def __init__(self, parent: "SimulatorView", current_embed: discord.Embed):
        super().__init__(timeout=120)
        self.parent = parent
        self.current_embed = current_embed

        yn = [
            discord.SelectOption(label="✅ Yes", value="1"),
            discord.SelectOption(label="❌ No", value="0"),
        ]
        self._tuesday_sel = discord.ui.Select(placeholder="📅 Angler Tuesday…", options=yn, min_values=0, max_values=1, row=0)
        self._tuesday_sel.callback = self._defer
        self.add_item(self._tuesday_sel)

        self._invasion_sel = discord.ui.Select(placeholder="⚔️ Active Invasion…", options=yn, min_values=0, max_values=1, row=1)
        self._invasion_sel.callback = self._defer
        self.add_item(self._invasion_sel)

        self._winner_sel = discord.ui.Select(placeholder="🏆 Location Winner…", options=yn, min_values=0, max_values=1, row=2)
        self._winner_sel.callback = self._defer
        self.add_item(self._winner_sel)

    async def _defer(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="✅ Save", style=discord.ButtonStyle.success, row=3)
    async def save_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._tuesday_sel.values:
            self.parent._angler_tuesday = self._tuesday_sel.values[0] == "1"
        if self._invasion_sel.values:
            self.parent._invasion = self._invasion_sel.values[0] == "1"
        if self._winner_sel.values:
            self.parent._loc_winner = self._winner_sel.values[0] == "1"
        await interaction.response.edit_message(embed=self.current_embed, view=self.parent)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary, row=3)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.current_embed, view=self.parent)


class SimulatorView(discord.ui.View):
    def __init__(self, db, member, dc, initial_state: dict | None = None):
        super().__init__(timeout=300)
        self.db = db
        self.member = member
        self.dc = dc
        self._loc_id: str | None = None
        self._tool_id: str | None = None
        self._bait_id: str | None = None
        self._event_id: str | None = None
        self._hour: int = datetime.now(timezone.utc).hour
        self._angler_tuesday: bool = False
        self._invasion: bool = False
        self._loc_winner: bool = False
        self._last_embed: discord.Embed | None = None
        if initial_state:
            self._loc_id = initial_state.get("location_id")
            self._tool_id = initial_state.get("tool_id")
            self._bait_id = initial_state.get("bait_id")
            self._event_id = initial_state.get("event_id")
            self._hour = initial_state.get("hour", self._hour)
        self._build_selects()

    def _build_selects(self) -> None:
        for item in list(self.children):
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)

        loc_opts = [discord.SelectOption(label="— No Location —", value="__none__")] + [
            discord.SelectOption(label=l.name, value=l.id)
            for l in sorted(self.dc.location_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._loc_sel = discord.ui.Select(placeholder="📍 Location…", options=loc_opts, min_values=0, max_values=1, row=0)
        self._loc_sel.callback = self._on_select
        self.add_item(self._loc_sel)

        tool_opts = [discord.SelectOption(label="— No Tool —", value="__none__")] + [
            discord.SelectOption(label=t.name, value=t.id)
            for t in sorted(self.dc.tool_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._tool_sel = discord.ui.Select(placeholder="🔧 Tool…", options=tool_opts, min_values=0, max_values=1, row=1)
        self._tool_sel.callback = self._on_select
        self.add_item(self._tool_sel)

        bait_opts = [discord.SelectOption(label="— No Bait —", value="__none__")] + [
            discord.SelectOption(label=b.name, value=b.id)
            for b in sorted(self.dc.bait_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._bait_sel = discord.ui.Select(placeholder="🪱 Bait…", options=bait_opts, min_values=0, max_values=1, row=2)
        self._bait_sel.callback = self._on_select
        self.add_item(self._bait_sel)

        event_opts = [discord.SelectOption(label="— No Event —", value="__none__")] + [
            discord.SelectOption(label=e.name, value=e.id)
            for e in sorted(self.dc.event_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._event_sel = discord.ui.Select(placeholder="🎉 Event…", options=event_opts, min_values=0, max_values=1, row=3)
        self._event_sel.callback = self._on_select
        self.add_item(self._event_sel)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        if self._loc_sel.values:
            v = self._loc_sel.values[0]
            self._loc_id = None if v == "__none__" else v
        if self._tool_sel.values:
            v = self._tool_sel.values[0]
            self._tool_id = None if v == "__none__" else v
        if self._bait_sel.values:
            v = self._bait_sel.values[0]
            self._bait_id = None if v == "__none__" else v
        if self._event_sel.values:
            v = self._event_sel.values[0]
            self._event_id = None if v == "__none__" else v
        await interaction.response.defer()

    def _build_payload(self, user_row) -> dict:
        try:
            skills = _json.loads(user_row["skills"]) if user_row["skills"] else {}
        except (ValueError, TypeError, KeyError, IndexError):
            skills = {}
        now = datetime.now(timezone.utc)
        ts = int(now.replace(hour=self._hour, minute=0, second=0, microsecond=0).timestamp() * 1000)
        return {
            "locationID": self._loc_id,
            "toolID": self._tool_id,
            "baitsIDs": [self._bait_id] if self._bait_id else [],
            "time": ts,
            "events": [self._event_id] if self._event_id else [],
            "bosses": bool(user_row["boss_unlock"]),
            "skills": skills,
            "bonusBossMultiplier": 1,
            "bonusMythicalMultiplier": 1,
            "forceTrash": False,
            "mythicalFishID": None,
            "discoveredCreatures": None,
            "anglerTuesday": self._angler_tuesday,
            "invasion": None,
            "locationWinner": self._loc_winner,
        }

    def _current_state(self) -> dict:
        return {
            "location_id": self._loc_id,
            "tool_id": self._tool_id,
            "bait_id": self._bait_id,
            "event_id": self._event_id,
            "hour": self._hour,
        }

    @discord.ui.button(label="🔄 Calculate", style=discord.ButtonStyle.primary, row=4)
    async def calculate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        user_row = await self.db.get_or_create_user(str(self.member.id))
        payload = self._build_payload(user_row)
        try:
            data = await call_simulator_api(payload)
        except Exception as exc:
            await interaction.followup.send(
                embed=EmbedBuilder.error("API Error", f"Simulator request failed: {exc}"),
                ephemeral=True,
            )
            return
        embed = build_sim_results_embed(data, self._current_state(), self.dc)
        self._last_embed = embed
        await interaction.edit_original_response(embed=embed, view=self)
        await self.db.add_history(
            str(self.member.id), "simulation",
            self._loc_id or "unknown",
            data=_json.dumps(data),
        )

    @discord.ui.button(label="👥 Skills", style=discord.ButtonStyle.secondary, row=4)
    async def skills_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_user(str(self.member.id))
        try:
            current_skills = _json.loads(user_row["skills"]) if user_row["skills"] else {}
        except (ValueError, TypeError, KeyError, IndexError):
            current_skills = {}
        sim_embed = self._last_embed or EmbedBuilder.info("Simulator", "Click 🔄 Calculate to see results.")
        sim_view = self

        async def return_fn(inter: discord.Interaction) -> None:
            await inter.response.edit_message(embed=sim_embed, view=sim_view)

        await interaction.response.edit_message(
            embed=_picker_embed("👥 Skills"),
            view=SkillsPickerView(self.db, self.member, self.dc, current_skills, return_fn),
        )

    @discord.ui.button(label="⚙️ Extras", style=discord.ButtonStyle.secondary, row=4)
    async def extras_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_embed = self._last_embed or EmbedBuilder.info("Simulator", "Click 🔄 Calculate to see results.")
        await interaction.response.edit_message(
            embed=_picker_embed("⚙️ Extras"),
            view=ExtrasView(self, current_embed),
        )

    @discord.ui.button(label="🕐 Set Time", style=discord.ButtonStyle.secondary, row=4)
    async def set_time_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TimeModal(self))

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=4)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class SimulatorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="simulate", description="Simulate a fishing attempt with your current setup")
    async def simulate(self, interaction: discord.Interaction):
        dc = self.bot.dank_client
        db = self.bot.db
        if not dc or not dc.fish_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not ready", "Game data still loading."), ephemeral=True
            )
            return
        if not db:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not available", "Database unavailable."), ephemeral=True
            )
            return

        user_row = await db.get_or_create_user(str(interaction.user.id))

        loc_id = None
        if user_row["favorite_location"]:
            loc = dc.location_by_name.get(user_row["favorite_location"].lower())
            if loc:
                loc_id = loc.id

        tool_id = None
        if user_row["current_tool"]:
            tool = dc.tool_by_name.get(user_row["current_tool"].lower())
            if tool:
                tool_id = tool.id

        bait_id = None
        if user_row["current_bait"]:
            bait = dc.bait_by_name.get(user_row["current_bait"].lower())
            if bait:
                bait_id = bait.id

        event_id = None
        if user_row["current_event"]:
            ev = dc.event_by_name.get(user_row["current_event"].lower())
            if ev:
                event_id = ev.id

        initial_state = {
            "location_id": loc_id,
            "tool_id": tool_id,
            "bait_id": bait_id,
            "event_id": event_id,
            "hour": datetime.now(timezone.utc).hour,
        }
        view = SimulatorView(db, interaction.user, dc, initial_state=initial_state)
        embed = EmbedBuilder.info("🎣 Simulator", "Select your options and click **🔄 Calculate**.")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SimulatorCog(bot))
```

- [ ] **Step 4: Run tests**

```
cd E:/disbot && pytest tests/test_simulator_cog.py -v
```
Expected: All pass.

- [ ] **Step 5: Run full suite**

```
cd E:/disbot && pytest -x -q
```
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add cogs/simulator.py tests/test_simulator_cog.py
git commit -m "feat: implement SimulatorView, ExtrasView, TimeModal, SkillsPickerView, /simulate command"
```

---

## Task 4: Enable Simulate Buttons + History Display

**Files:**
- Modify: `cogs/fish.py`
- Modify: `cogs/locations.py`
- Modify: `cogs/tools.py`
- Modify: `cogs/baits.py`
- Modify: `utils/embeds.py`

**Interfaces:**
- Consumes: `SimulatorView`, `call_simulator_api`, `build_sim_results_embed` from `cogs/simulator.py` (Task 3); `Database.add_history(data=...)` (Task 1)
- Produces: Active Simulate buttons in all 4 embeds; simulation history rows that show `fail%`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_fish_cog.py` (check current file for existing test structure, then add):

```python
@pytest.mark.asyncio
async def test_fish_view_sim_btn_is_enabled_when_db_present():
    from cogs.fish import FishView
    dc = MagicMock()
    dc.tool_by_id = {}
    dc.bait_by_id = {}
    dc.location_by_id = {}
    dc.event_by_id = {}
    dc.skill_categories = {}
    db = MagicMock()
    creature = MagicMock()
    creature.extra = {"rarity": "Common", "boss": False, "mythical": False}
    view = FishView(creature, dc, db=db, user_id="123")
    sim_btn = next((b for b in view.children if isinstance(b, discord.ui.Button) and "Simulate" in b.label), None)
    assert sim_btn is not None
    assert sim_btn.disabled is False
```

Add to `tests/test_locations_cog.py`:

```python
@pytest.mark.asyncio
async def test_location_view_sim_btn_is_enabled_when_db_present():
    from cogs.locations import LocationView
    dc = MagicMock()
    dc.location_creature_map = {}
    dc.tool_by_id = {}
    dc.bait_by_id = {}
    dc.location_by_id = {}
    dc.event_by_id = {}
    dc.skill_categories = {}
    db = MagicMock()
    loc = MagicMock()
    loc.id = "river"
    loc.name = "River"
    view = LocationView(loc, dc, db=db, user_id="123")
    sim_btn = next((b for b in view.children if isinstance(b, discord.ui.Button) and "Simulate" in b.label), None)
    assert sim_btn is not None
    assert sim_btn.disabled is False
```

Add to `tests/test_embeds.py` (find existing history embed tests, add):

```python
def test_build_history_embed_simulation_shows_fail_percent():
    from utils.embeds import build_history_embed
    import json
    row = {
        "item_id": "river",
        "data": json.dumps({"failChance": 15.3}),
        "created_at": "2026-01-01 12:00:00",
    }
    # Use a simple object that supports item access
    class FakeRow(dict):
        pass
    rows = [FakeRow(row)]
    member = MagicMock()
    member.display_name = "Tester"
    embed = build_history_embed(rows, member, "simulation")
    assert "15.3" in embed.description
    assert "river" in embed.description
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd E:/disbot && pytest tests/test_fish_cog.py::test_fish_view_sim_btn_is_enabled_when_db_present tests/test_locations_cog.py::test_location_view_sim_btn_is_enabled_when_db_present tests/test_embeds.py::test_build_history_embed_simulation_shows_fail_percent -v
```
Expected: FAIL.

- [ ] **Step 3: Update `cogs/fish.py` — enable Simulate button**

Find `sim_btn` in `FishView` (currently `disabled=True`, line ~170) and replace:

```python
    @discord.ui.button(label="🎮 Simulate", style=discord.ButtonStyle.secondary, row=1)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.db:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not available", "Simulator requires database connection."),
                ephemeral=True,
            )
            return
        from cogs.simulator import SimulatorView
        from utils.embeds import EmbedBuilder as _EB
        view = SimulatorView(self.db, interaction.user, self.dc)
        embed = _EB.info("🎣 Simulator", "Select your options and click **🔄 Calculate**.")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
```

Also remove `disabled=True` from the decorator.

Also update the `__init__` guard that disables the button when `db is None` — change it to enable/disable `sim_btn` the same way `fav_btn` is handled:

```python
        sim_btn_item = next(
            (item for item in self.children if isinstance(item, discord.ui.Button) and "Simulate" in item.label),
            None,
        )
        if sim_btn_item:
            sim_btn_item.disabled = db is None
```

- [ ] **Step 4: Update `cogs/locations.py` — enable Simulate button with pre-fill + immediate calculate**

Find `sim_btn` in `LocationView` (line ~182) and replace:

```python
    @discord.ui.button(label="🎮 Simulate", style=discord.ButtonStyle.secondary, row=1)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.db:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not available", "Simulator requires database connection."),
                ephemeral=True,
            )
            return
        from cogs.simulator import SimulatorView, call_simulator_api, build_sim_results_embed
        import json as _json
        from datetime import datetime, timezone
        from utils.embeds import EmbedBuilder as _EB

        dc = self.dc
        db = self.db
        user_row = await db.get_or_create_user(self.user_id)
        tool_id = None
        if user_row["current_tool"]:
            t = dc.tool_by_name.get(user_row["current_tool"].lower())
            if t:
                tool_id = t.id
        bait_id = None
        if user_row["current_bait"]:
            b = dc.bait_by_name.get(user_row["current_bait"].lower())
            if b:
                bait_id = b.id

        initial_state = {
            "location_id": self.loc.id,
            "tool_id": tool_id,
            "bait_id": bait_id,
            "event_id": None,
            "hour": datetime.now(timezone.utc).hour,
        }
        view = SimulatorView(db, interaction.user, dc, initial_state=initial_state)
        await interaction.response.defer(ephemeral=True)
        try:
            payload = view._build_payload(user_row)
            data = await call_simulator_api(payload)
            embed = build_sim_results_embed(data, view._current_state(), dc)
            view._last_embed = embed
            await db.add_history(str(interaction.user.id), "simulation", self.loc.id, data=_json.dumps(data))
        except Exception:
            embed = _EB.info("🎣 Simulator", "Select your options and click **🔄 Calculate**.")
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
```

Remove `disabled=True` from the decorator. Add the same enable/disable guard in `LocationView.__init__`:

```python
        sim_btn_item = next(
            (item for item in self.children if isinstance(item, discord.ui.Button) and "Simulate" in item.label),
            None,
        )
        if sim_btn_item:
            sim_btn_item.disabled = db is None
```

- [ ] **Step 5: Update `cogs/tools.py` — enable Simulate button with pre-fill tool**

Find `sim_btn` in `ToolView` (line ~96) and replace:

```python
    @discord.ui.button(label="🎮 Simulate", style=discord.ButtonStyle.secondary)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.db:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not available", "Simulator requires database connection."),
                ephemeral=True,
            )
            return
        from cogs.simulator import SimulatorView
        from utils.embeds import EmbedBuilder as _EB
        from datetime import datetime, timezone

        user_row = await self.db.get_or_create_user(self.user_id)
        initial_state = {
            "location_id": None,
            "tool_id": self.tool.id,
            "bait_id": None,
            "event_id": None,
            "hour": datetime.now(timezone.utc).hour,
        }
        view = SimulatorView(self.db, interaction.user, self.dc, initial_state=initial_state)
        embed = _EB.info("🎣 Simulator", "Select your options and click **🔄 Calculate**.")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
```

Remove `disabled=True`. Add guard in `ToolView.__init__`:

```python
        sim_btn_item = next(
            (item for item in self.children if isinstance(item, discord.ui.Button) and "Simulate" in item.label),
            None,
        )
        if sim_btn_item:
            sim_btn_item.disabled = db is None
```

- [ ] **Step 6: Update `cogs/baits.py` — enable Simulate button with pre-fill bait**

Find `sim_btn` in `BaitView` (line ~96) and replace:

```python
    @discord.ui.button(label="🎮 Simulate", style=discord.ButtonStyle.secondary)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.db:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not available", "Simulator requires database connection."),
                ephemeral=True,
            )
            return
        from cogs.simulator import SimulatorView
        from utils.embeds import EmbedBuilder as _EB
        from datetime import datetime, timezone

        user_row = await self.db.get_or_create_user(self.user_id)
        initial_state = {
            "location_id": None,
            "tool_id": None,
            "bait_id": self.bait.id,
            "event_id": None,
            "hour": datetime.now(timezone.utc).hour,
        }
        view = SimulatorView(self.db, interaction.user, self.dc, initial_state=initial_state)
        embed = _EB.info("🎣 Simulator", "Select your options and click **🔄 Calculate**.")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
```

Remove `disabled=True`. Add guard in `BaitView.__init__`:

```python
        sim_btn_item = next(
            (item for item in self.children if isinstance(item, discord.ui.Button) and "Simulate" in item.label),
            None,
        )
        if sim_btn_item:
            sim_btn_item.disabled = db is None
```

Note: `BaitView` stores the bait as `self.bait`. Confirm the attribute name by reading the `BaitView.__init__` — it stores `bait` as `self.bait` (from `def __init__(self, bait, ...)`).

- [ ] **Step 7: Update `utils/embeds.py` — simulation history rows show fail%**

Find `build_history_embed` (line ~614) and update the `for` loop body to handle simulation rows differently:

```python
    lines = []
    for i, row in enumerate(rows, 1):
        item_id = row["item_id"] or "?"
        ts = _relative_time(row["created_at"])
        if tab == "simulation":
            fail_pct = ""
            try:
                import json as _hj
                d = _hj.loads(row["data"] or "{}")
                fail_pct = f"  ❌ {d.get('failChance', 0):.1f}%"
            except Exception:
                pass
            lines.append(f"`{i:>2}.` **{item_id}**{fail_pct} — {ts}")
        else:
            lines.append(f"`{i:>2}.` **{item_id}** — {ts}")
    embed.description = "\n".join(lines)
```

- [ ] **Step 8: Run tests**

```
cd E:/disbot && pytest tests/test_fish_cog.py tests/test_locations_cog.py tests/test_tools_cog.py tests/test_baits_cog.py tests/test_embeds.py -v 2>&1 | tail -30
```
Expected: New tests pass, no regressions.

- [ ] **Step 9: Run full suite**

```
cd E:/disbot && pytest -x -q
```
Expected: All tests pass.

- [ ] **Step 10: Commit**

```bash
git add cogs/fish.py cogs/locations.py cogs/tools.py cogs/baits.py utils/embeds.py tests/test_fish_cog.py tests/test_locations_cog.py tests/test_embeds.py
git commit -m "feat: enable Simulate buttons in fish/location/tool/bait, show fail% in simulation history"
```
