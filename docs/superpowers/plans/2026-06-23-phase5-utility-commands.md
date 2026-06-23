# Phase 5 — Utility Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four read-only utility commands (`/rarity`, `/event`, `/time`, `/today`) in a new `cogs/utilities.py` cog.

**Architecture:** All four commands live in `UtilitiesCog` (one new file). Data comes entirely from preloaded `dc.*` dicts and `fishing_engine.creature_eligible` — no live API calls, no DB migrations. The two shared helpers `_catchable_set` and `_upcoming_windows` are module-level functions so all four commands can use them.

**Tech Stack:** discord.py 2.x app_commands, `fishing_engine.creature_eligible` + `RARITY_WEIGHTS`, `datetime.utcnow()`, `utils/db.py:Database.update_user`.

## Global Constraints

- Python 3.12, discord.py 2.x, no new dependencies.
- All commands post publicly (no `ephemeral=True` on the primary response).
- Error embeds use `EmbedBuilder.error(...)` and are always `ephemeral=True`.
- Guard at the top of every command: if `not self.dc.fish_by_id`, respond with ephemeral error "⏳ Data is still loading, please try again in a moment." and return.
- Views use `timeout=300`; `on_timeout` disables all children.
- Delete button: `await interaction.message.delete()` — no defer needed.
- `current_event` in the DB stores the **event name string** (e.g. `"Token Cloning Experiment"`), matching the existing profile cog pattern.
- `creature_eligible(creature, location_id, tool_id, hour, *, bosses, ignore_time)` — exact kwarg names required.
- All tests in `tests/test_utilities_cog.py`. Run full suite with `pytest -x -q` before committing.
- No comments in code unless the WHY is non-obvious.

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `cogs/utilities.py` | All 4 commands + views + embed helpers |
| Create | `tests/test_utilities_cog.py` | 11 tests from spec |

No other files change. `bot.py` auto-discovers all `cogs/*.py` files — no registration needed.

---

## Task 1: Cog scaffold + `/rarity`

**Files:**
- Create: `cogs/utilities.py`
- Create: `tests/test_utilities_cog.py`

**Interfaces:**
- Produces: `UtilitiesCog`, `_catchable_set(dc, hour, location_id=None) -> set[str]`, `_upcoming_windows(dc, hour, location_id=None, ahead=6) -> dict[int, list[str]]`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_utilities_cog.py
from __future__ import annotations
import pytest
import discord
from datetime import time as dt_time
from unittest.mock import AsyncMock, MagicMock, patch
from dankmemer.utils import DotDict


def _make_fish(fid, rarity="Common", locations=None, full_day=True, start_h=0, end_h=6):
    time_data = {"full_day": full_day}
    if not full_day:
        time_data["start"] = dt_time(hour=start_h)
        time_data["end"] = dt_time(hour=end_h)
    extra = DotDict({
        "boss": False, "mythical": False, "rarity": rarity,
        "flavor": "", "locations": locations or ["loc1"],
        "time": time_data, "variants": [],
        "tools": {"fishing-rod": {"max": 1}},
    })
    f = MagicMock()
    f.id = fid
    f.name = fid.capitalize()
    f.extra = extra
    return f


def _make_location(lid, name=None):
    loc = MagicMock()
    loc.id = lid
    loc.name = name or lid.capitalize()
    return loc


def _make_event(eid, name=None, description="Test desc", last=None):
    ev = MagicMock()
    ev.id = eid
    ev.name = name or eid.capitalize()
    ev.imageURL = "https://example.com/img.png"
    ev.extra = {"description": description, "last": last or ["2026-05-15T00:00:00.000Z"]}
    return ev


def _make_dc(fish=None, locations=None, events=None):
    dc = MagicMock()
    fish = fish or [_make_fish("bass")]
    locs = locations or [_make_location("river")]
    evs = events or [_make_event("2xtokens", "Token Cloning")]
    dc.fish_by_id = {f.id: f for f in fish}
    dc.location_by_id = {l.id: l for l in locs}
    dc.event_by_id = {e.id: e for e in evs}
    dc.event_by_name = {e.name.lower(): e for e in evs}
    return dc


def _make_interaction():
    inter = MagicMock()
    inter.response = AsyncMock()
    inter.response.send_message = AsyncMock()
    inter.response.edit_message = AsyncMock()
    inter.response.defer = AsyncMock()
    inter.message = MagicMock()
    inter.message.delete = AsyncMock()
    inter.user = MagicMock()
    inter.user.id = 123
    inter.followup = AsyncMock()
    return inter


# ── /rarity ─────────────────────────────────────────────────────────────────

def test_rarity_embed_has_7_fields():
    import cogs.utilities as u
    dc = _make_dc()
    with patch("cogs.utilities._utc_hour", return_value=12):
        embed = u._build_rarity_embed(dc, hour=12)
    assert len(embed.fields) == 7
    field_names = [f.name for f in embed.fields]
    for tier in ["Absurdly Common", "Very Common", "Common", "Regular",
                 "Rare", "Very Rare", "Absurdly Rare"]:
        assert tier in field_names


def test_rarity_currently_catchable_uses_utc_hour():
    import cogs.utilities as u
    dc = _make_dc(fish=[_make_fish("bass", full_day=True)])
    embed = u._build_rarity_embed(dc, hour=5)
    # bass is full_day=True so it should be in "Common" now count
    common_field = next(f for f in embed.fields if f.name == "Common")
    assert "Now: **1**" in common_field.value
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_utilities_cog.py -x -q
```
Expected: `ModuleNotFoundError` or `ImportError` — `cogs.utilities` does not exist yet.

- [ ] **Step 3: Create `cogs/utilities.py` with scaffold, helpers, and `/rarity`**

```python
# cogs/utilities.py
from __future__ import annotations
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands

from fishing_engine import creature_eligible, RARITY_WEIGHTS
from utils.embeds import EmbedBuilder

_PRELOAD_MSG = "⏳ Data is still loading, please try again in a moment."

_RARITY_ORDER = [
    "Absurdly Common", "Very Common", "Common", "Regular",
    "Rare", "Very Rare", "Absurdly Rare",
]


def _utc_hour() -> int:
    return datetime.utcnow().hour


def _catchable_set(dc, hour: int, location_id: str | None = None) -> set[str]:
    """Fish IDs catchable with fishing-rod (no bosses) at hour, across all or one location."""
    loc_ids = [location_id] if location_id else list(dc.location_by_id.keys())
    found: set[str] = set()
    for fish in dc.fish_by_id.values():
        for lid in loc_ids:
            if creature_eligible(fish, lid, "fishing-rod", hour, bosses=False, ignore_time=False):
                found.add(fish.id)
                break
    return found


def _upcoming_windows(dc, hour: int, location_id: str | None = None, ahead: int = 6) -> dict[int, list[str]]:
    """Fish names newly available at each of the next `ahead` hours vs current hour."""
    current = _catchable_set(dc, hour, location_id)
    windows: dict[int, list[str]] = {}
    for delta in range(1, ahead + 1):
        fhour = (hour + delta) % 24
        future = _catchable_set(dc, fhour, location_id)
        newly_open = sorted(dc.fish_by_id[fid].name for fid in (future - current))
        if newly_open:
            windows[fhour] = newly_open
    return windows


def _build_rarity_embed(dc, hour: int) -> discord.Embed:
    by_rarity: dict[str, list[str]] = {r: [] for r in _RARITY_ORDER}
    for fish in dc.fish_by_id.values():
        r = fish.extra.get("rarity", "")
        if r in by_rarity:
            by_rarity[r].append(fish.id)
    catchable = _catchable_set(dc, hour)
    embed = discord.Embed(title="Rarity Tiers", color=0x5865F2)
    for rarity in _RARITY_ORDER:
        fish_ids = by_rarity[rarity]
        total = len(fish_ids)
        now = sum(1 for fid in fish_ids if fid in catchable)
        weight = RARITY_WEIGHTS[rarity]
        embed.add_field(
            name=rarity,
            value=f"Weight: **{weight}** · Total: **{total}** · Now: **{now}**",
            inline=False,
        )
    embed.set_footer(text=f"UTC hour: {hour:02d}:00")
    return embed


class UtilitiesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.dc = bot.dank_client

    @app_commands.command(name="rarity", description="Show rarity tiers and how many fish are catchable right now.")
    async def rarity(self, interaction: discord.Interaction):
        if not self.dc.fish_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not ready", _PRELOAD_MSG), ephemeral=True
            )
            return
        hour = _utc_hour()
        embed = _build_rarity_embed(self.dc, hour)
        view = _DeleteView()
        await interaction.response.send_message(embed=embed, view=view)


class _DeleteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilitiesCog(bot))
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_utilities_cog.py::test_rarity_embed_has_7_fields tests/test_utilities_cog.py::test_rarity_currently_catchable_uses_utc_hour -v
```
Expected: 2 PASSED.

- [ ] **Step 5: Run full suite to check no regressions**

```
pytest -x -q
```
Expected: 355 passed (353 existing + 2 new).

- [ ] **Step 6: Commit**

```
git add cogs/utilities.py tests/test_utilities_cog.py
git commit -m "feat: add UtilitiesCog scaffold and /rarity command"
```

---

## Task 2: `/event`

**Files:**
- Modify: `cogs/utilities.py`
- Modify: `tests/test_utilities_cog.py`

**Interfaces:**
- Consumes: `UtilitiesCog`, `_DeleteView`, `_make_event` helper from test file
- Produces: `EventOverviewView`, `EventDetailView`, `_build_event_overview_pages`, `_build_event_detail_embed`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_utilities_cog.py`:

```python
# ── /event ──────────────────────────────────────────────────────────────────

def test_event_overview_paginates():
    import cogs.utilities as u
    events = [_make_event(f"ev{i}", f"Event {i}") for i in range(8)]
    pages = u._build_event_overview_pages(events, active_event=None)
    assert len(pages) == 2  # 8 events, 5 per page → 2 pages
    assert "1/2" in (pages[0].footer.text or "")


def test_event_overview_stars_active_event():
    import cogs.utilities as u
    events = [
        _make_event("ev1", "Alpha Event"),
        _make_event("ev2", "Beta Event"),
    ]
    pages = u._build_event_overview_pages(events, active_event="Alpha Event")
    body = " ".join(f.name for f in pages[0].fields)
    assert "⭐" in body
    # Beta should not have a star
    beta_field = next(f for f in pages[0].fields if "Beta" in f.name)
    assert "⭐" not in beta_field.name


def test_event_detail_shows_description():
    import cogs.utilities as u
    ev = _make_event("ev1", "Great Event", description="Full event description here.")
    embed = u._build_event_detail_embed(ev, active_event=None)
    assert "Full event description here." in (embed.description or "")
    assert embed.title == "Great Event"


@pytest.mark.asyncio
async def test_event_set_current_updates_profile():
    import cogs.utilities as u
    db = MagicMock()
    db.update_user = AsyncMock()
    ev = _make_event("ev1", "Great Event")
    view = u.EventDetailView(db, ev, user_id="999")
    interaction = _make_interaction()
    set_btn = next(b for b in view.children if isinstance(b, discord.ui.Button) and "Set" in b.label)
    await set_btn.callback(interaction)
    db.update_user.assert_called_once_with("999", current_event="Great Event")
    assert set_btn.disabled is True
    assert set_btn.label == "✅ Set"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_utilities_cog.py::test_event_overview_paginates tests/test_utilities_cog.py::test_event_overview_stars_active_event tests/test_utilities_cog.py::test_event_detail_shows_description tests/test_utilities_cog.py::test_event_set_current_updates_profile -x -q
```
Expected: all FAIL with `AttributeError` — functions not yet defined.

- [ ] **Step 3: Add event embed helpers and views to `cogs/utilities.py`**

Add these functions and classes before the `UtilitiesCog` class:

```python
_EVENT_PAGE_SIZE = 5


def _build_event_overview_pages(events: list, active_event: str | None) -> list[discord.Embed]:
    total_pages = max(1, (len(events) + _EVENT_PAGE_SIZE - 1) // _EVENT_PAGE_SIZE)
    pages = []
    for page_idx in range(total_pages):
        chunk = events[page_idx * _EVENT_PAGE_SIZE: (page_idx + 1) * _EVENT_PAGE_SIZE]
        embed = discord.Embed(title="Fishing Events", color=0x5865F2)
        for ev in chunk:
            last_dates = ev.extra.get("last", [])
            last_str = last_dates[0][:10] if last_dates else "Unknown"
            desc = ev.extra.get("description", "")
            desc_short = (desc[:80] + "…") if len(desc) > 80 else desc
            star = "⭐ " if ev.name == active_event else ""
            embed.add_field(
                name=f"{star}{ev.name}",
                value=f"{desc_short}\nLast seen: **{last_str}**",
                inline=False,
            )
        embed.set_footer(text=f"Page {page_idx + 1}/{total_pages}")
        pages.append(embed)
    return pages


def _build_event_detail_embed(event, active_event: str | None) -> discord.Embed:
    embed = discord.Embed(
        title=event.name,
        description=event.extra.get("description", ""),
        color=0x5865F2,
    )
    embed.set_thumbnail(url=event.imageURL)
    last_dates = event.extra.get("last", [])[:3]
    if last_dates:
        embed.add_field(
            name="Last Seen",
            value="\n".join(d[:10] for d in last_dates),
            inline=False,
        )
    if event.name == active_event:
        embed.set_footer(text="Active")
    return embed


class EventOverviewView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed]):
        super().__init__(timeout=300)
        self.pages = pages
        self.page = 0
        self._sync()

    def _sync(self) -> None:
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= len(self.pages) - 1

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._sync()
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._sync()
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=0)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class EventDetailView(discord.ui.View):
    def __init__(self, db, event, user_id: str):
        super().__init__(timeout=300)
        self.db = db
        self.event = event
        self.user_id = user_id

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]

    @discord.ui.button(label="⭐ Set as Current", style=discord.ButtonStyle.primary, row=0)
    async def set_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.db.update_user(self.user_id, current_event=self.event.name)
        except Exception:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Failed to save", "Could not update your profile."),
                ephemeral=True,
            )
            return
        button.label = "✅ Set"
        button.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=0)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
```

- [ ] **Step 4: Add `/event` command and autocomplete to `UtilitiesCog`**

Add inside `UtilitiesCog`, after the `rarity` command:

```python
    @app_commands.command(name="event", description="Browse fishing events or view a specific event.")
    @app_commands.describe(name="Event name — leave blank for an overview of all events")
    async def event(self, interaction: discord.Interaction, name: str | None = None):
        if not self.dc.event_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not ready", _PRELOAD_MSG), ephemeral=True
            )
            return
        if name:
            event_obj = self.dc.event_by_name.get(name.lower())
            if event_obj is None:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("Not found", f"No event named **{name}** found."),
                    ephemeral=True,
                )
                return
            user_row = await self.db.get_or_create_user(str(interaction.user.id))
            embed = _build_event_detail_embed(event_obj, user_row["current_event"])
            await interaction.response.send_message(
                embed=embed,
                view=EventDetailView(self.db, event_obj, str(interaction.user.id)),
            )
        else:
            user_row = await self.db.get_or_create_user(str(interaction.user.id))
            events = sorted(self.dc.event_by_id.values(), key=lambda e: e.name)
            pages = _build_event_overview_pages(events, user_row["current_event"])
            await interaction.response.send_message(embed=pages[0], view=EventOverviewView(pages))

    @event.autocomplete("name")
    async def event_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=e.name, value=e.name)
            for e in self.dc.event_by_id.values()
            if current.lower() in e.name.lower()
        ][:25]
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_utilities_cog.py -k "event" -v
```
Expected: 4 PASSED.

- [ ] **Step 6: Run full suite**

```
pytest -x -q
```
Expected: 359 passed.

- [ ] **Step 7: Commit**

```
git add cogs/utilities.py tests/test_utilities_cog.py
git commit -m "feat: add /event command with overview, detail, and set-as-current"
```

---

## Task 3: `/time`

**Files:**
- Modify: `cogs/utilities.py`
- Modify: `tests/test_utilities_cog.py`

**Interfaces:**
- Consumes: `_catchable_set`, `_upcoming_windows`, `_utc_hour`
- Produces: `TimeView`, `_build_time_embed(dc, hour, location_id)`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_utilities_cog.py`:

```python
# ── /time ────────────────────────────────────────────────────────────────────

def test_time_default_shows_all_locations():
    import cogs.utilities as u
    # bass is full_day → always catchable
    dc = _make_dc(fish=[_make_fish("bass", full_day=True)], locations=[_make_location("river")])
    embed = u._build_time_embed(dc, hour=12, location_id=None)
    assert "1" in (embed.description or "")  # 1 fish catchable


def test_time_select_filters_to_location():
    import cogs.utilities as u
    fish_river = _make_fish("bass", full_day=True, locations=["river"])
    fish_lake = _make_fish("trout", full_day=True, locations=["lake"])
    dc = _make_dc(
        fish=[fish_river, fish_lake],
        locations=[_make_location("river"), _make_location("lake")],
    )
    embed = u._build_time_embed(dc, hour=12, location_id="river")
    field_names = [f.name for f in embed.fields]
    assert "Catchable Now" in field_names
    catchable_field = next(f for f in embed.fields if f.name == "Catchable Now")
    assert "Bass" in catchable_field.value
    assert "Trout" not in catchable_field.value


def test_time_upcoming_windows_next_6h():
    import cogs.utilities as u
    # bass: available only hours 5..10
    bass = _make_fish("bass", full_day=False, start_h=5, end_h=10, locations=["river"])
    dc = _make_dc(fish=[bass], locations=[_make_location("river")])
    # At hour 4, bass is NOT catchable. At hour 5 it becomes available.
    windows = u._upcoming_windows(dc, hour=4, location_id=None, ahead=6)
    assert 5 in windows
    assert "Bass" in windows[5]
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_utilities_cog.py -k "time" -x -q
```
Expected: 3 FAIL with `AttributeError` — `_build_time_embed` not defined.

- [ ] **Step 3: Add `_build_time_embed` and `TimeView` to `cogs/utilities.py`**

Add before `UtilitiesCog`:

```python
def _build_time_embed(dc, hour: int, location_id: str | None) -> discord.Embed:
    if location_id:
        loc = dc.location_by_id.get(location_id)
        loc_name = loc.name if loc else location_id
        catchable_names = sorted(
            dc.fish_by_id[fid].name for fid in _catchable_set(dc, hour, location_id)
        )
        embed = discord.Embed(title=f"{loc_name} — {hour:02d}:00 UTC", color=0x5865F2)
        embed.add_field(
            name="Catchable Now",
            value="\n".join(catchable_names) if catchable_names else "No fish catchable at this hour.",
            inline=False,
        )
    else:
        total = len(_catchable_set(dc, hour))
        embed = discord.Embed(
            title=f"Current UTC — {hour:02d}:00",
            description=f"**{total}** fish catchable across all locations right now.",
            color=0x5865F2,
        )
    windows = _upcoming_windows(dc, hour, location_id)
    if windows:
        lines = [f"**{fh:02d}:00** — {', '.join(names)}" for fh, names in sorted(windows.items())]
        embed.add_field(name="Upcoming Windows (next 6h)", value="\n".join(lines), inline=False)
    else:
        embed.add_field(
            name="Upcoming Windows (next 6h)",
            value="No new windows in the next 6 hours.",
            inline=False,
        )
    return embed


class TimeView(discord.ui.View):
    def __init__(self, dc):
        super().__init__(timeout=300)
        self.dc = dc
        self._loc_id: str | None = None
        loc_opts = [
            discord.SelectOption(label=loc.name, value=loc.id)
            for loc in sorted(dc.location_by_id.values(), key=lambda l: l.name)
        ]
        self._loc_sel = discord.ui.Select(
            placeholder="Filter by location…",
            options=loc_opts,
            min_values=0,
            max_values=1,
            row=0,
        )
        self._loc_sel.callback = self._on_select
        self.add_item(self._loc_sel)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]

    async def _on_select(self, interaction: discord.Interaction) -> None:
        self._loc_id = self._loc_sel.values[0] if self._loc_sel.values else None
        embed = _build_time_embed(self.dc, _utc_hour(), self._loc_id)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=1)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
```

- [ ] **Step 4: Add `/time` command to `UtilitiesCog`**

Add after the `event` command inside `UtilitiesCog`:

```python
    @app_commands.command(name="time", description="Show which fish are catchable right now and upcoming windows.")
    async def time(self, interaction: discord.Interaction):
        if not self.dc.fish_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not ready", _PRELOAD_MSG), ephemeral=True
            )
            return
        hour = _utc_hour()
        embed = _build_time_embed(self.dc, hour, None)
        await interaction.response.send_message(embed=embed, view=TimeView(self.dc))
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_utilities_cog.py -k "time" -v
```
Expected: 3 PASSED.

- [ ] **Step 6: Run full suite**

```
pytest -x -q
```
Expected: 362 passed.

- [ ] **Step 7: Commit**

```
git add cogs/utilities.py tests/test_utilities_cog.py
git commit -m "feat: add /time command with location filter and upcoming windows"
```

---

## Task 4: `/today`

**Files:**
- Modify: `cogs/utilities.py`
- Modify: `tests/test_utilities_cog.py`

**Interfaces:**
- Consumes: `_catchable_set`, `_utc_hour`, `db.get_or_create_user`
- Produces: `_build_today_embed(dc, db_row, hour)`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_utilities_cog.py`:

```python
# ── /today ───────────────────────────────────────────────────────────────────

def test_today_shows_active_event_from_profile():
    import cogs.utilities as u
    dc = _make_dc(fish=[_make_fish("bass", full_day=True)], locations=[_make_location("river")])
    db_row = {"current_event": "Token Cloning Experiment"}
    embed = u._build_today_embed(dc, db_row, hour=10)
    active_field = next((f for f in embed.fields if f.name == "Active Event"), None)
    assert active_field is not None
    assert "Token Cloning Experiment" in active_field.value


def test_today_top_3_locations():
    import cogs.utilities as u
    locs = [_make_location(f"loc{i}") for i in range(5)]
    # bass is in loc0, loc1, loc2 only
    bass = _make_fish("bass", full_day=True, locations=["loc0", "loc1", "loc2"])
    dc = _make_dc(fish=[bass], locations=locs)
    embed = u._build_today_embed(dc, db_row=None, hour=10)
    top_field = next((f for f in embed.fields if f.name == "Top Locations"), None)
    assert top_field is not None
    lines = top_field.value.strip().split("\n")
    assert len(lines) <= 3
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_utilities_cog.py -k "today" -x -q
```
Expected: 2 FAIL with `AttributeError` — `_build_today_embed` not defined.

- [ ] **Step 3: Add `_build_today_embed` and `/today` command**

Add `_build_today_embed` before `UtilitiesCog`:

```python
def _build_today_embed(dc, db_row, hour: int) -> discord.Embed:
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    embed = discord.Embed(title=f"Today's Fishing — {date_str} UTC", color=0x5865F2)
    embed.add_field(name="Current Time", value=f"{hour:02d}:00 UTC", inline=True)
    if db_row is None:
        active_value = "unavailable"
    elif db_row["current_event"]:
        active_value = db_row["current_event"]
    else:
        active_value = "None set — use `/event` to set one"
    embed.add_field(name="Active Event", value=active_value, inline=True)
    current_set = _catchable_set(dc, hour)
    embed.add_field(name="Catchable Right Now", value=f"{len(current_set)} fish", inline=True)
    loc_counts = sorted(
        ((loc.name, len(_catchable_set(dc, hour, loc.id))) for loc in dc.location_by_id.values()),
        key=lambda x: x[1],
        reverse=True,
    )
    embed.add_field(
        name="Top Locations",
        value="\n".join(f"{name} — {count} fish" for name, count in loc_counts[:3]),
        inline=False,
    )
    upcoming_lines = []
    for delta in range(1, 4):
        fhour = (hour + delta) % 24
        future_set = _catchable_set(dc, fhour)
        opened = len(future_set - current_set)
        closed = len(current_set - future_set)
        if opened == 0 and closed == 0:
            continue
        parts = []
        if opened:
            parts.append(f"+{opened} open")
        if closed:
            parts.append(f"{closed} close")
        upcoming_lines.append(f"**{fhour:02d}:00** — {', '.join(parts)}")
    if upcoming_lines:
        embed.add_field(name="Upcoming (next 3h)", value="\n".join(upcoming_lines), inline=False)
    embed.set_footer(text="Update your setup with /profile")
    return embed
```

Add `/today` command inside `UtilitiesCog`, after `/time`:

```python
    @app_commands.command(name="today", description="Daily summary: current fish, top locations, and active event.")
    async def today(self, interaction: discord.Interaction):
        if not self.dc.fish_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not ready", _PRELOAD_MSG), ephemeral=True
            )
            return
        hour = _utc_hour()
        try:
            db_row = await self.db.get_or_create_user(str(interaction.user.id))
        except Exception:
            db_row = None
        embed = _build_today_embed(self.dc, db_row, hour)
        await interaction.response.send_message(embed=embed, view=_DeleteView())
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_utilities_cog.py -k "today" -v
```
Expected: 2 PASSED.

- [ ] **Step 5: Run full suite**

```
pytest -x -q
```
Expected: 364 passed (353 + 11 new).

- [ ] **Step 6: Commit**

```
git add cogs/utilities.py tests/test_utilities_cog.py
git commit -m "feat: add /today command with daily fishing summary"
```
