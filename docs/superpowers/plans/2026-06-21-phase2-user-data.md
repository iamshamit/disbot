# Phase 2 — User Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `/profile`, `/favorites`, `/history`, `/settings` commands with full DB persistence, plus enable the Favourite toggle button and history tracking in all Phase 1 encyclopedia cogs.

**Architecture:** Four tasks building bottom-up — DB helpers first, then the profile cog (all four commands live in `cogs/profile.py`), then the Favourite/history integration into the four existing P1 cogs. New embed builders go into `utils/embeds.py` following existing patterns. All commands use `self.bot.db` (a `Database` instance already attached to the bot in `bot.py`).

**Tech Stack:** discord.py 2.x (`discord.ui.View`, `discord.ui.Modal`, `discord.ui.Select`), aiosqlite, zoneinfo (stdlib), pytest + pytest-asyncio.

## Global Constraints

- All user-facing errors use `EmbedBuilder.error(title, description)` and are sent `ephemeral=True`.
- Views must set `timeout=300` and implement `on_timeout` that disables all children and calls `self.message.edit(view=self)`.
- Profile color is `0x5865F2` (blurple) throughout — no rarity color for user commands.
- `discord_id` stored and passed as `str(interaction.user.id)`.
- DB is always available at `self.bot.db` after startup; no guard needed in profile cog (unlike encyclopedia cogs which guard for preload).
- Modal `on_submit` always ends with `await interaction.response.defer()` after editing the message (acks the interaction silently).
- Export and Import buttons exist in ProfileView but are `disabled=True` — Phase 6.
- Simulate button in FavoritesView is `disabled=True` — Phase 3.
- Existing tests must continue to pass after Task 4 — use `db=None` defaults in P1 view constructors so existing tests don't break.
- Test files use `pytest.mark.asyncio` for async tests and `AsyncMock` / `MagicMock` from `unittest.mock`.
- Run the full suite with `pytest tests/ -v` at the end of each task and fix any failures before committing.

---

### Task 1: DB Helpers

**Files:**
- Modify: `utils/db.py`
- Create: `tests/test_db.py`

**Interfaces:**
- Consumes: existing `Database.get_user`, `Database.create_user`, `Database.update_user`, `Database._conn`
- Produces:
  - `Database.get_or_create_user(discord_id: str) -> aiosqlite.Row`
  - `Database.add_favorite(discord_id: str, type: str, item_id: str) -> None`
  - `Database.remove_favorite(discord_id: str, type: str, item_id: str) -> None`
  - `Database.get_favorites(discord_id: str, type: str | None = None) -> list`
  - `Database.add_history(discord_id: str, type: str, item_id: str) -> None`
  - `Database.get_history(discord_id: str, type: str, limit: int = 20) -> list`

- [ ] **Step 1: Write failing tests**

Create `tests/test_db.py`:

```python
import pytest
from pathlib import Path
from utils.db import Database


@pytest.fixture
async def db(tmp_path):
    d = Database(tmp_path / "test.db")
    await d.connect()
    yield d
    await d.close()


# --- get_or_create_user ---

@pytest.mark.asyncio
async def test_get_or_create_user_creates_row(db):
    row = await db.get_or_create_user("111")
    assert row["discord_id"] == "111"

@pytest.mark.asyncio
async def test_get_or_create_user_returns_existing(db):
    await db.get_or_create_user("111")
    await db.update_user("111", fishing_skill=7)
    row = await db.get_or_create_user("111")
    assert row["fishing_skill"] == 7

@pytest.mark.asyncio
async def test_get_or_create_user_idempotent(db):
    await db.get_or_create_user("111")
    await db.get_or_create_user("111")  # no error
    row = await db.get_user("111")
    assert row is not None


# --- add_favorite / remove_favorite / get_favorites ---

@pytest.mark.asyncio
async def test_add_and_get_favorites_by_type(db):
    await db.add_favorite("111", "fish", "goldfish")
    favs = await db.get_favorites("111", "fish")
    assert len(favs) == 1
    assert favs[0]["item_id"] == "goldfish"

@pytest.mark.asyncio
async def test_add_favorite_is_idempotent(db):
    await db.add_favorite("111", "fish", "goldfish")
    await db.add_favorite("111", "fish", "goldfish")
    favs = await db.get_favorites("111", "fish")
    assert len(favs) == 1

@pytest.mark.asyncio
async def test_get_favorites_all_types(db):
    await db.add_favorite("111", "fish", "goldfish")
    await db.add_favorite("111", "location", "ocean")
    favs = await db.get_favorites("111")
    assert len(favs) == 2

@pytest.mark.asyncio
async def test_remove_favorite(db):
    await db.add_favorite("111", "fish", "goldfish")
    await db.remove_favorite("111", "fish", "goldfish")
    favs = await db.get_favorites("111", "fish")
    assert len(favs) == 0

@pytest.mark.asyncio
async def test_remove_favorite_noop_when_missing(db):
    await db.remove_favorite("111", "fish", "nonexistent")  # no error


# --- add_history / get_history ---

@pytest.mark.asyncio
async def test_add_and_get_history(db):
    await db.add_history("111", "fish", "goldfish")
    rows = await db.get_history("111", "fish")
    assert len(rows) == 1
    assert rows[0]["item_id"] == "goldfish"

@pytest.mark.asyncio
async def test_add_history_prunes_to_20(db):
    for i in range(25):
        await db.add_history("111", "fish", f"fish_{i}")
    rows = await db.get_history("111", "fish")
    assert len(rows) == 20

@pytest.mark.asyncio
async def test_get_history_returns_newest_first(db):
    await db.add_history("111", "fish", "first")
    await db.add_history("111", "fish", "second")
    rows = await db.get_history("111", "fish")
    assert rows[0]["item_id"] == "second"

@pytest.mark.asyncio
async def test_get_history_respects_limit(db):
    for i in range(10):
        await db.add_history("111", "fish", f"fish_{i}")
    rows = await db.get_history("111", "fish", limit=3)
    assert len(rows) == 3

@pytest.mark.asyncio
async def test_history_scoped_by_type(db):
    await db.add_history("111", "fish", "goldfish")
    await db.add_history("111", "location", "ocean")
    fish_rows = await db.get_history("111", "fish")
    assert all(r["type"] == "fish" for r in fish_rows)
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_db.py -v
```

Expected: `AttributeError: 'Database' object has no attribute 'get_or_create_user'` (or similar).

- [ ] **Step 3: Implement the six methods**

Append to the `Database` class in `utils/db.py` (after `update_user`):

```python
async def get_or_create_user(self, discord_id: str):
    await self.create_user(discord_id)
    return await self.get_user(discord_id)

async def add_favorite(self, discord_id: str, type: str, item_id: str) -> None:
    logger.debug("DB add_favorite: %s %s %s", discord_id, type, item_id)
    await self._conn.execute(
        "INSERT OR IGNORE INTO favorites (discord_id, type, item_id) VALUES (?, ?, ?)",
        (discord_id, type, item_id),
    )
    await self._conn.commit()

async def remove_favorite(self, discord_id: str, type: str, item_id: str) -> None:
    logger.debug("DB remove_favorite: %s %s %s", discord_id, type, item_id)
    await self._conn.execute(
        "DELETE FROM favorites WHERE discord_id = ? AND type = ? AND item_id = ?",
        (discord_id, type, item_id),
    )
    await self._conn.commit()

async def get_favorites(self, discord_id: str, type: str | None = None) -> list:
    logger.debug("DB get_favorites: %s type=%s", discord_id, type)
    if type is not None:
        async with self._conn.execute(
            "SELECT * FROM favorites WHERE discord_id = ? AND type = ? ORDER BY id",
            (discord_id, type),
        ) as cursor:
            return list(await cursor.fetchall())
    async with self._conn.execute(
        "SELECT * FROM favorites WHERE discord_id = ? ORDER BY type, id",
        (discord_id,),
    ) as cursor:
        return list(await cursor.fetchall())

async def add_history(self, discord_id: str, type: str, item_id: str) -> None:
    logger.debug("DB add_history: %s %s %s", discord_id, type, item_id)
    await self._conn.execute(
        "INSERT INTO history (discord_id, type, item_id) VALUES (?, ?, ?)",
        (discord_id, type, item_id),
    )
    await self._conn.execute(
        """DELETE FROM history WHERE discord_id = ? AND type = ? AND id NOT IN (
            SELECT id FROM history WHERE discord_id = ? AND type = ?
            ORDER BY created_at DESC LIMIT 20
        )""",
        (discord_id, type, discord_id, type),
    )
    await self._conn.commit()

async def get_history(self, discord_id: str, type: str, limit: int = 20) -> list:
    logger.debug("DB get_history: %s type=%s limit=%s", discord_id, type, limit)
    async with self._conn.execute(
        "SELECT * FROM history WHERE discord_id = ? AND type = ? ORDER BY created_at DESC LIMIT ?",
        (discord_id, type, limit),
    ) as cursor:
        return list(await cursor.fetchall())
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_db.py -v
```

Expected: all 15 tests PASS.

- [ ] **Step 5: Run the full suite to confirm no regressions**

```
pytest tests/ -v
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add utils/db.py tests/test_db.py
git commit -m "feat: add DB helpers for favorites, history, get_or_create_user"
```

---

### Task 2: `/profile` Command

**Files:**
- Modify: `utils/embeds.py` (add `build_profile_embed`)
- Rewrite: `cogs/profile.py`
- Create: `tests/test_profile_cog.py`

**Interfaces:**
- Consumes: `Database.get_or_create_user`, `Database.get_user`, `Database.update_user` (Task 1); `DankMemerGameClient.get_tool`, `DankMemerGameClient.get_bait`; `EmbedBuilder.error`, `EmbedBuilder.warning`
- Produces:
  - `build_profile_embed(user_row, member: discord.Member | discord.User) -> discord.Embed`
  - `ProfileCog` with `/profile` slash command
  - `ProfileView(db, member, dank_client)` — 5 Edit buttons + Reset + Export/Import (disabled)
  - `EditSetupModal`, `EditSkillsModal`, `EditUnlocksModal`, `EditEnvModal`, `EditFavsModal`
  - `ResetConfirmView(db, member, dank_client)`

- [ ] **Step 1: Write failing tests for `build_profile_embed`**

Create `tests/test_profile_cog.py`:

```python
"""Tests for cogs/profile.py and profile embed builders."""
from __future__ import annotations

import pytest
import discord
from unittest.mock import AsyncMock, MagicMock


def make_user_row(**overrides):
    defaults = {
        "discord_id": "123",
        "fishing_rod": "Wooden Rod",
        "current_tool": None,
        "current_bait": None,
        "fishing_skill": 0,
        "luck_skill": 0,
        "efficiency_skill": 0,
        "prestige": 0,
        "coins": 0,
        "boss_unlock": 0,
        "mythical_unlock": 0,
        "favorite_fish": None,
        "favorite_location": None,
        "favorite_tool": None,
        "favorite_bait": None,
        "current_weather": None,
        "current_event": None,
        "timezone": "UTC",
        "theme": "dark",
        "compact_mode": 0,
        "updated_at": "2026-01-01 00:00:00",
    }
    return {**defaults, **overrides}


def make_member(display_name="TestUser", user_id="123"):
    member = MagicMock(spec=discord.Member)
    member.id = int(user_id)
    member.display_name = display_name
    member.display_avatar = MagicMock()
    member.display_avatar.url = "https://example.com/avatar.png"
    return member


def make_mock_bot(db=None, dank_client=None):
    bot = MagicMock()
    bot.db = db or MagicMock()
    bot.dank_client = dank_client or MagicMock()
    return bot


def make_interaction(user_id="123", display_name="TestUser"):
    interaction = MagicMock()
    interaction.response = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.original_response = AsyncMock(return_value=MagicMock())
    member = make_member(display_name, user_id)
    interaction.user = member
    return interaction


# ---------------------------------------------------------------------------
# build_profile_embed
# ---------------------------------------------------------------------------

def test_build_profile_embed_title():
    from utils.embeds import build_profile_embed
    row = make_user_row()
    member = make_member(display_name="FisherKing")
    embed = build_profile_embed(row, member)
    assert embed.title == "FisherKing"

def test_build_profile_embed_color():
    from utils.embeds import build_profile_embed
    row = make_user_row()
    member = make_member()
    embed = build_profile_embed(row, member)
    assert embed.color.value == 0x5865F2

def test_build_profile_embed_setup_field():
    from utils.embeds import build_profile_embed
    row = make_user_row(fishing_rod="Lava Rod", current_tool="Harpoon", current_bait="Glitter Bait")
    member = make_member()
    embed = build_profile_embed(row, member)
    setup_field = next(f for f in embed.fields if "SETUP" in f.name)
    assert "Lava Rod" in setup_field.value
    assert "Harpoon" in setup_field.value
    assert "Glitter Bait" in setup_field.value

def test_build_profile_embed_skills_field():
    from utils.embeds import build_profile_embed
    row = make_user_row(fishing_skill=5, luck_skill=3, efficiency_skill=8, prestige=2, coins=1000)
    member = make_member()
    embed = build_profile_embed(row, member)
    skills_field = next(f for f in embed.fields if "SKILLS" in f.name)
    assert "5" in skills_field.value
    assert "3" in skills_field.value
    assert "1,000" in skills_field.value  # coins formatted with comma

def test_build_profile_embed_unlocks_field():
    from utils.embeds import build_profile_embed
    row = make_user_row(boss_unlock=1, mythical_unlock=0)
    member = make_member()
    embed = build_profile_embed(row, member)
    unlocks_field = next(f for f in embed.fields if "UNLOCK" in f.name)
    assert "✅" in unlocks_field.value  # boss
    assert "❌" in unlocks_field.value  # mythical

def test_build_profile_embed_environment_field():
    from utils.embeds import build_profile_embed
    row = make_user_row(current_weather="Rainy", current_event="Fishing Festival")
    member = make_member()
    embed = build_profile_embed(row, member)
    env_field = next(f for f in embed.fields if "ENV" in f.name.upper())
    assert "Rainy" in env_field.value
    assert "Fishing Festival" in env_field.value

def test_build_profile_embed_favourites_field():
    from utils.embeds import build_profile_embed
    row = make_user_row(favorite_fish="Goldfish", favorite_location="Ocean")
    member = make_member()
    embed = build_profile_embed(row, member)
    fav_field = next(f for f in embed.fields if "FAVOUR" in f.name.upper())
    assert "Goldfish" in fav_field.value
    assert "Ocean" in fav_field.value

def test_build_profile_embed_none_values_show_none():
    from utils.embeds import build_profile_embed
    row = make_user_row()
    member = make_member()
    embed = build_profile_embed(row, member)
    setup_field = next(f for f in embed.fields if "SETUP" in f.name)
    assert "None" in setup_field.value  # current_tool and current_bait are None
```

- [ ] **Step 2: Run to verify failure**

```
pytest tests/test_profile_cog.py::test_build_profile_embed_title -v
```

Expected: `ImportError: cannot import name 'build_profile_embed' from 'utils.embeds'`

- [ ] **Step 3: Add `build_profile_embed` to `utils/embeds.py`**

Append at the bottom of `utils/embeds.py`:

```python
def build_profile_embed(user_row, member) -> discord.Embed:
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

    fs = user_row["fishing_skill"] or 0
    ls = user_row["luck_skill"] or 0
    es = user_row["efficiency_skill"] or 0
    prestige = user_row["prestige"] or 0
    coins = user_row["coins"] or 0
    embed.add_field(
        name="\U0001f4ca SKILLS",
        value=(
            f"Fishing: **{fs}**  ·  Luck: **{ls}**  ·  Efficiency: **{es}**\n"
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

- [ ] **Step 4: Run embed tests**

```
pytest tests/test_profile_cog.py -k "build_profile_embed" -v
```

Expected: all 8 PASS.

- [ ] **Step 5: Write failing tests for the `/profile` command**

Append to `tests/test_profile_cog.py`:

```python
# ---------------------------------------------------------------------------
# ProfileCog — /profile command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_profile_command_sends_embed_and_view():
    from cogs.profile import ProfileCog, ProfileView
    db = MagicMock()
    db.get_or_create_user = AsyncMock(return_value=make_user_row())
    bot = make_mock_bot(db=db)
    cog = ProfileCog(bot)
    interaction = make_interaction()
    await cog.profile.callback(cog, interaction)
    interaction.response.send_message.assert_called_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert "embed" in kwargs
    assert isinstance(kwargs["view"], ProfileView)

@pytest.mark.asyncio
async def test_profile_command_creates_user_if_missing():
    from cogs.profile import ProfileCog
    db = MagicMock()
    db.get_or_create_user = AsyncMock(return_value=make_user_row())
    bot = make_mock_bot(db=db)
    cog = ProfileCog(bot)
    interaction = make_interaction()
    await cog.profile.callback(cog, interaction)
    db.get_or_create_user.assert_called_once_with("123")

@pytest.mark.asyncio
async def test_profile_view_has_expected_buttons():
    from cogs.profile import ProfileView
    db = MagicMock()
    dc = MagicMock()
    member = make_member()
    view = ProfileView(db, member, dc)
    labels = [item.label for item in view.children if isinstance(item, discord.ui.Button)]
    assert any("Edit Setup" in l for l in labels)
    assert any("Edit Skills" in l for l in labels)
    assert any("Edit Unlocks" in l for l in labels)
    assert any("Reset" in l for l in labels)
    export_btn = next((item for item in view.children if isinstance(item, discord.ui.Button) and "Export" in item.label), None)
    assert export_btn is not None
    assert export_btn.disabled is True
    import_btn = next((item for item in view.children if isinstance(item, discord.ui.Button) and "Import" in item.label), None)
    assert import_btn is not None
    assert import_btn.disabled is True

@pytest.mark.asyncio
async def test_profile_view_edit_setup_btn_sends_modal():
    from cogs.profile import ProfileView, EditSetupModal
    db = MagicMock()
    dc = MagicMock()
    member = make_member()
    view = ProfileView(db, member, dc)
    interaction = make_interaction()
    edit_setup_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Setup" in item.label
    )
    await edit_setup_btn.callback(interaction)
    interaction.response.send_modal.assert_called_once()
    modal = interaction.response.send_modal.call_args.args[0]
    assert isinstance(modal, EditSetupModal)

@pytest.mark.asyncio
async def test_edit_skills_modal_rejects_negative_skill():
    from cogs.profile import EditSkillsModal
    db = MagicMock()
    member = make_member()
    message = AsyncMock()
    modal = EditSkillsModal(db, member, message)
    modal.fishing_skill._value = "-5"
    modal.luck_skill._value = ""
    modal.efficiency_skill._value = ""
    modal.prestige._value = ""
    modal.coins._value = ""
    interaction = make_interaction()
    await modal.on_submit(interaction)
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True
    db.update_user.assert_not_called()

@pytest.mark.asyncio
async def test_edit_skills_modal_saves_valid_values():
    from cogs.profile import EditSkillsModal
    db = MagicMock()
    db.update_user = AsyncMock()
    db.get_user = AsyncMock(return_value=make_user_row(fishing_skill=5))
    member = make_member()
    message = AsyncMock()
    modal = EditSkillsModal(db, member, message)
    modal.fishing_skill._value = "5"
    modal.luck_skill._value = ""
    modal.efficiency_skill._value = ""
    modal.prestige._value = ""
    modal.coins._value = ""
    interaction = make_interaction()
    await modal.on_submit(interaction)
    db.update_user.assert_called_once()
    call_kwargs = db.update_user.call_args.kwargs
    assert call_kwargs.get("fishing_skill") == 5
    interaction.response.defer.assert_called_once()

@pytest.mark.asyncio
async def test_edit_unlocks_modal_rejects_invalid_value():
    from cogs.profile import EditUnlocksModal
    db = MagicMock()
    member = make_member()
    message = AsyncMock()
    modal = EditUnlocksModal(db, member, message)
    modal.boss_unlock._value = "maybe"
    modal.mythical_unlock._value = ""
    interaction = make_interaction()
    await modal.on_submit(interaction)
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

@pytest.mark.asyncio
async def test_edit_unlocks_modal_saves_yes_no():
    from cogs.profile import EditUnlocksModal
    db = MagicMock()
    db.update_user = AsyncMock()
    db.get_user = AsyncMock(return_value=make_user_row(boss_unlock=1))
    member = make_member()
    message = AsyncMock()
    modal = EditUnlocksModal(db, member, message)
    modal.boss_unlock._value = "yes"
    modal.mythical_unlock._value = ""
    interaction = make_interaction()
    await modal.on_submit(interaction)
    db.update_user.assert_called_once()
    assert db.update_user.call_args.kwargs.get("boss_unlock") == 1
    interaction.response.defer.assert_called_once()

@pytest.mark.asyncio
async def test_edit_setup_modal_rejects_invalid_tool():
    from cogs.profile import EditSetupModal
    db = MagicMock()
    dc = MagicMock()
    dc.get_tool = MagicMock(return_value=None)
    member = make_member()
    message = AsyncMock()
    modal = EditSetupModal(db, member, message, dc)
    modal.rod._value = ""
    modal.tool._value = "NotARealTool"
    modal.bait._value = ""
    interaction = make_interaction()
    await modal.on_submit(interaction)
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True
    db.update_user.assert_not_called()

@pytest.mark.asyncio
async def test_reset_confirm_view_has_confirm_and_cancel():
    from cogs.profile import ResetConfirmView
    db = MagicMock()
    dc = MagicMock()
    member = make_member()
    view = ResetConfirmView(db, member, dc)
    labels = [item.label for item in view.children if isinstance(item, discord.ui.Button)]
    assert any("Confirm" in l for l in labels)
    assert any("Cancel" in l for l in labels)
```

- [ ] **Step 6: Run to verify failures**

```
pytest tests/test_profile_cog.py -k "not build_profile_embed" -v
```

Expected: `ImportError: cannot import name 'ProfileCog'` (or similar).

- [ ] **Step 7: Implement `cogs/profile.py`**

Completely replace `cogs/profile.py`:

```python
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from utils.embeds import EmbedBuilder, build_profile_embed


class EditSetupModal(discord.ui.Modal, title="Edit Fishing Setup"):
    rod: discord.ui.TextInput = discord.ui.TextInput(
        label="Fishing Rod", placeholder="e.g. Wooden Rod", required=False, max_length=100
    )
    tool: discord.ui.TextInput = discord.ui.TextInput(
        label="Current Tool", placeholder="e.g. Fishing Rod", required=False, max_length=100
    )
    bait: discord.ui.TextInput = discord.ui.TextInput(
        label="Current Bait", placeholder="e.g. Glitter Bait", required=False, max_length=100
    )

    def __init__(self, db, member, message, dank_client):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message
        self.dc = dank_client

    async def on_submit(self, interaction: discord.Interaction) -> None:
        tool_val = self.tool.value.strip() or None
        bait_val = self.bait.value.strip() or None
        if tool_val and not self.dc.get_tool(tool_val):
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid tool", f"No tool named **{tool_val}** found."),
                ephemeral=True,
            )
            return
        if bait_val and not self.dc.get_bait(bait_val):
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid bait", f"No bait named **{bait_val}** found."),
                ephemeral=True,
            )
            return
        updates: dict = {}
        if self.rod.value.strip():
            updates["fishing_rod"] = self.rod.value.strip()
        if tool_val is not None:
            updates["current_tool"] = tool_val
        if bait_val is not None:
            updates["current_bait"] = bait_val
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await self.message.edit(
            embed=build_profile_embed(user_row, self.member),
            view=ProfileView(self.db, self.member, self.dc),
        )
        await interaction.response.defer()


class EditSkillsModal(discord.ui.Modal, title="Edit Skills"):
    fishing_skill: discord.ui.TextInput = discord.ui.TextInput(
        label="Fishing Skill", placeholder="0+", required=False, max_length=6
    )
    luck_skill: discord.ui.TextInput = discord.ui.TextInput(
        label="Luck Skill", placeholder="0+", required=False, max_length=6
    )
    efficiency_skill: discord.ui.TextInput = discord.ui.TextInput(
        label="Efficiency Skill", placeholder="0+", required=False, max_length=6
    )
    prestige: discord.ui.TextInput = discord.ui.TextInput(
        label="Prestige", placeholder="0+", required=False, max_length=6
    )
    coins: discord.ui.TextInput = discord.ui.TextInput(
        label="Coins", placeholder="0+", required=False, max_length=15
    )

    def __init__(self, db, member, message):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        fields = {
            "fishing_skill": self.fishing_skill.value,
            "luck_skill": self.luck_skill.value,
            "efficiency_skill": self.efficiency_skill.value,
            "prestige": self.prestige.value,
            "coins": self.coins.value,
        }
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
                        f"**{key.replace('_', ' ').title()}** must be a non-negative integer.",
                    ),
                    ephemeral=True,
                )
                return
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await self.message.edit(
            embed=build_profile_embed(user_row, self.member),
            view=ProfileView(self.db, self.member, None),
        )
        await interaction.response.defer()


class EditUnlocksModal(discord.ui.Modal, title="Edit Unlocks"):
    boss_unlock: discord.ui.TextInput = discord.ui.TextInput(
        label="Boss Unlock (yes/no)", placeholder="yes or no", required=False, max_length=3
    )
    mythical_unlock: discord.ui.TextInput = discord.ui.TextInput(
        label="Mythical Unlock (yes/no)", placeholder="yes or no", required=False, max_length=3
    )

    def __init__(self, db, member, message):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        updates: dict = {}
        for key, raw in [("boss_unlock", self.boss_unlock.value), ("mythical_unlock", self.mythical_unlock.value)]:
            if not raw.strip():
                continue
            lower = raw.strip().lower()
            if lower not in ("yes", "no"):
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("Invalid value", "Boss/Mythical Unlock must be **yes** or **no**."),
                    ephemeral=True,
                )
                return
            updates[key] = 1 if lower == "yes" else 0
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await self.message.edit(
            embed=build_profile_embed(user_row, self.member),
            view=ProfileView(self.db, self.member, None),
        )
        await interaction.response.defer()


class EditEnvModal(discord.ui.Modal, title="Edit Environment"):
    weather: discord.ui.TextInput = discord.ui.TextInput(
        label="Current Weather", placeholder="e.g. Rainy", required=False, max_length=100
    )
    event: discord.ui.TextInput = discord.ui.TextInput(
        label="Current Event", placeholder="e.g. Fishing Festival", required=False, max_length=100
    )

    def __init__(self, db, member, message):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        updates: dict = {}
        if self.weather.value.strip():
            updates["current_weather"] = self.weather.value.strip()
        if self.event.value.strip():
            updates["current_event"] = self.event.value.strip()
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await self.message.edit(
            embed=build_profile_embed(user_row, self.member),
            view=ProfileView(self.db, self.member, None),
        )
        await interaction.response.defer()


class EditFavsModal(discord.ui.Modal, title="Edit Favourites"):
    fav_fish: discord.ui.TextInput = discord.ui.TextInput(
        label="Favourite Fish", placeholder="e.g. Goldfish", required=False, max_length=100
    )
    fav_location: discord.ui.TextInput = discord.ui.TextInput(
        label="Favourite Location", placeholder="e.g. Sunken Ship", required=False, max_length=100
    )
    fav_tool: discord.ui.TextInput = discord.ui.TextInput(
        label="Favourite Tool", placeholder="e.g. Fishing Rod", required=False, max_length=100
    )
    fav_bait: discord.ui.TextInput = discord.ui.TextInput(
        label="Favourite Bait", placeholder="e.g. Glitter Bait", required=False, max_length=100
    )

    def __init__(self, db, member, message):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        updates: dict = {}
        if self.fav_fish.value.strip():
            updates["favorite_fish"] = self.fav_fish.value.strip()
        if self.fav_location.value.strip():
            updates["favorite_location"] = self.fav_location.value.strip()
        if self.fav_tool.value.strip():
            updates["favorite_tool"] = self.fav_tool.value.strip()
        if self.fav_bait.value.strip():
            updates["favorite_bait"] = self.fav_bait.value.strip()
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await self.message.edit(
            embed=build_profile_embed(user_row, self.member),
            view=ProfileView(self.db, self.member, None),
        )
        await interaction.response.defer()


class ResetConfirmView(discord.ui.View):
    def __init__(self, db, member, dank_client):
        super().__init__(timeout=60)
        self.db = db
        self.member = member
        self.dc = dank_client

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]

    @discord.ui.button(label="✅ Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(self.member.id)
        await self.db.update_user(
            user_id,
            fishing_rod="Wooden Rod",
            current_tool=None,
            current_bait=None,
            fishing_skill=0,
            luck_skill=0,
            efficiency_skill=0,
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
            embed=build_profile_embed(user_row, self.member),
            view=ProfileView(self.db, self.member, self.dc),
        )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_user(str(self.member.id))
        await interaction.response.edit_message(
            embed=build_profile_embed(user_row, self.member),
            view=ProfileView(self.db, self.member, self.dc),
        )


class ProfileView(discord.ui.View):
    def __init__(self, db, member, dank_client):
        super().__init__(timeout=300)
        self.db = db
        self.member = member
        self.dc = dank_client
        self.message: discord.Message | None = None
        # Disable stub buttons
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.label in ("📤 Export", "📥 Import"):
                item.disabled = True

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="✏️ Edit Setup", style=discord.ButtonStyle.secondary, row=0)
    async def edit_setup_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            EditSetupModal(self.db, self.member, interaction.message, self.dc)
        )

    @discord.ui.button(label="📊 Edit Skills", style=discord.ButtonStyle.secondary, row=0)
    async def edit_skills_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            EditSkillsModal(self.db, self.member, interaction.message)
        )

    @discord.ui.button(label="🔓 Edit Unlocks", style=discord.ButtonStyle.secondary, row=0)
    async def edit_unlocks_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            EditUnlocksModal(self.db, self.member, interaction.message)
        )

    @discord.ui.button(label="🌤️ Edit Env", style=discord.ButtonStyle.secondary, row=0)
    async def edit_env_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            EditEnvModal(self.db, self.member, interaction.message)
        )

    @discord.ui.button(label="⭐ Edit Favs", style=discord.ButtonStyle.secondary, row=0)
    async def edit_favs_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            EditFavsModal(self.db, self.member, interaction.message)
        )

    @discord.ui.button(label="🔄 Reset", style=discord.ButtonStyle.danger, row=1)
    async def reset_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=EmbedBuilder.warning("Reset Profile", "This will clear all your data. Are you sure?"),
            view=ResetConfirmView(self.db, self.member, self.dc),
        )

    @discord.ui.button(label="📤 Export", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def export_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="📥 Import", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def import_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View and edit your fishing profile")
    async def profile(self, interaction: discord.Interaction):
        user_row = await self.bot.db.get_or_create_user(str(interaction.user.id))
        embed = build_profile_embed(user_row, interaction.user)
        view = ProfileView(self.bot.db, interaction.user, self.bot.dank_client)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
```

- [ ] **Step 8: Run all profile tests**

```
pytest tests/test_profile_cog.py -v
```

Expected: all tests PASS.

- [ ] **Step 9: Run the full suite**

```
pytest tests/ -v
```

Expected: all green.

- [ ] **Step 10: Commit**

```bash
git add utils/embeds.py cogs/profile.py tests/test_profile_cog.py
git commit -m "feat: implement /profile command with edit modals and reset flow"
```

---

### Task 3: `/favorites`, `/history`, and `/settings` Commands

**Files:**
- Modify: `utils/embeds.py` (add `build_favorites_embed`, `build_history_embed`, `build_settings_embed`)
- Modify: `cogs/profile.py` (add three commands, three views, `TimezoneModal`)
- Modify: `tests/test_profile_cog.py` (add tests)

**Interfaces:**
- Consumes: `Database.get_favorites`, `Database.remove_favorite`, `Database.get_history`, `Database.get_or_create_user`, `Database.update_user` (Task 1); all P1 embed builders (`build_fish_embed`, `build_location_embed`, `build_tool_embed`, `build_bait_embed`)
- Produces:
  - `build_favorites_embed(favs_by_type: dict[str, list[str]], member) -> discord.Embed`
  - `build_history_embed(rows: list, member, tab: str) -> discord.Embed`
  - `build_settings_embed(user_row) -> discord.Embed`
  - `FavoritesView(db, user, dank_client, fav_rows)`
  - `HistoryView(db, user)`
  - `SettingsView(db, member)`
  - `TimezoneModal(db, member, message, current_tz: str)`
  - `/favorites`, `/history`, `/settings` commands on `ProfileCog`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_profile_cog.py`:

```python
# ---------------------------------------------------------------------------
# build_favorites_embed
# ---------------------------------------------------------------------------

def test_build_favorites_embed_shows_fish():
    from utils.embeds import build_favorites_embed
    by_type = {"fish": ["goldfish", "koi"], "location": [], "tool": [], "bait": []}
    member = make_member()
    embed = build_favorites_embed(by_type, member)
    fish_field = next(f for f in embed.fields if "Fish" in f.name)
    assert "goldfish" in fish_field.value
    assert "koi" in fish_field.value

def test_build_favorites_embed_empty_shows_none():
    from utils.embeds import build_favorites_embed
    by_type = {"fish": [], "location": [], "tool": [], "bait": []}
    member = make_member()
    embed = build_favorites_embed(by_type, member)
    fish_field = next(f for f in embed.fields if "Fish" in f.name)
    assert "None" in fish_field.value


# ---------------------------------------------------------------------------
# build_history_embed
# ---------------------------------------------------------------------------

def test_build_history_embed_lists_items():
    from utils.embeds import build_history_embed
    rows = [{"item_id": "goldfish", "created_at": "2026-01-01 00:00:00"}]
    member = make_member()
    embed = build_history_embed(rows, member, "fish")
    assert "goldfish" in embed.description

def test_build_history_embed_empty_state():
    from utils.embeds import build_history_embed
    member = make_member()
    embed = build_history_embed([], member, "fish")
    assert "nothing" in embed.description.lower() or "no " in embed.description.lower()


# ---------------------------------------------------------------------------
# build_settings_embed
# ---------------------------------------------------------------------------

def test_build_settings_embed_shows_timezone():
    from utils.embeds import build_settings_embed
    row = make_user_row(timezone="Asia/Kolkata")
    embed = build_settings_embed(row)
    assert "Asia/Kolkata" in embed.description

def test_build_settings_embed_shows_theme():
    from utils.embeds import build_settings_embed
    row = make_user_row(theme="light")
    embed = build_settings_embed(row)
    assert "Light" in embed.description or "light" in embed.description

def test_build_settings_embed_shows_compact():
    from utils.embeds import build_settings_embed
    row = make_user_row(compact_mode=1)
    embed = build_settings_embed(row)
    assert "On" in embed.description


# ---------------------------------------------------------------------------
# /favorites command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_favorites_command_sends_embed():
    from cogs.profile import ProfileCog, FavoritesView
    db = MagicMock()
    db.get_favorites = AsyncMock(return_value=[])
    bot = make_mock_bot(db=db)
    cog = ProfileCog(bot)
    interaction = make_interaction()
    await cog.favorites.callback(cog, interaction)
    interaction.response.send_message.assert_called_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert "embed" in kwargs
    assert isinstance(kwargs["view"], FavoritesView)

@pytest.mark.asyncio
async def test_favorites_remove_btn_removes_item():
    from cogs.profile import FavoritesView
    db = MagicMock()
    db.remove_favorite = AsyncMock()
    db.get_favorites = AsyncMock(return_value=[])
    dc = MagicMock()
    dc.fish_by_id = {}
    dc.location_by_id = {}
    dc.tool_by_id = {}
    dc.bait_by_id = {}
    member = make_member()
    fav_rows = [{"type": "fish", "item_id": "goldfish"}]
    view = FavoritesView(db, member, dc, fav_rows)
    view.selected_type = "fish"
    view.selected_id = "goldfish"
    interaction = make_interaction()
    await view.remove_btn.callback(interaction)
    db.remove_favorite.assert_called_once_with("123", "fish", "goldfish")
    interaction.response.edit_message.assert_called_once()


# ---------------------------------------------------------------------------
# /history command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_history_command_sends_embed():
    from cogs.profile import ProfileCog, HistoryView
    db = MagicMock()
    db.get_history = AsyncMock(return_value=[])
    bot = make_mock_bot(db=db)
    cog = ProfileCog(bot)
    interaction = make_interaction()
    await cog.history.callback(cog, interaction)
    interaction.response.send_message.assert_called_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert isinstance(kwargs["view"], HistoryView)


# ---------------------------------------------------------------------------
# /settings command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_settings_command_sends_embed():
    from cogs.profile import ProfileCog, SettingsView
    db = MagicMock()
    db.get_or_create_user = AsyncMock(return_value=make_user_row())
    bot = make_mock_bot(db=db)
    cog = ProfileCog(bot)
    interaction = make_interaction()
    await cog.settings.callback(cog, interaction)
    interaction.response.send_message.assert_called_once()
    kwargs = interaction.response.send_message.call_args.kwargs
    assert isinstance(kwargs["view"], SettingsView)

@pytest.mark.asyncio
async def test_timezone_modal_rejects_invalid_tz():
    from cogs.profile import TimezoneModal
    db = MagicMock()
    member = make_member()
    message = AsyncMock()
    modal = TimezoneModal(db, member, message, "UTC")
    modal.timezone._value = "NotATimezone/Fake"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True
    db.update_user.assert_not_called()

@pytest.mark.asyncio
async def test_timezone_modal_saves_valid_tz():
    from cogs.profile import TimezoneModal
    db = MagicMock()
    db.update_user = AsyncMock()
    db.get_user = AsyncMock(return_value=make_user_row(timezone="Asia/Kolkata"))
    member = make_member()
    message = AsyncMock()
    modal = TimezoneModal(db, member, message, "UTC")
    modal.timezone._value = "Asia/Kolkata"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    db.update_user.assert_called_once()
    assert db.update_user.call_args.kwargs.get("timezone") == "Asia/Kolkata"
```

- [ ] **Step 2: Run to verify failures**

```
pytest tests/test_profile_cog.py -k "favorites or history or settings or build_favorites or build_history or build_settings or timezone" -v
```

Expected: `ImportError` / attribute errors.

- [ ] **Step 3: Add embed builders to `utils/embeds.py`**

Append to `utils/embeds.py`:

```python
def build_favorites_embed(favs_by_type: dict, member) -> discord.Embed:
    embed = discord.Embed(title="⭐ Your Favourites", color=0x5865F2)
    embed.set_author(name="⭐ Favourites")
    if hasattr(member, "display_avatar") and member.display_avatar:
        embed.set_thumbnail(url=str(member.display_avatar.url))
    type_labels = {
        "fish": ("\U0001f420 Fish", "fish"),
        "location": ("\U0001f4cd Locations", "location"),
        "tool": ("\U0001f527 Tools", "tool"),
        "bait": ("\U0001fab1 Baits", "bait"),
    }
    for key, (label, _) in type_labels.items():
        items = favs_by_type.get(key, [])
        value = ", ".join(items[:10]) if items else "None"
        embed.add_field(name=label, value=value, inline=False)
    if not any(favs_by_type.get(k) for k in favs_by_type):
        embed.description = (
            "You haven’t favourited anything yet.\n"
            "Use the ⭐ button on any `/fish`, `/location`, `/tool`, or `/bait` embed."
        )
    return embed


def _relative_time(ts_str: str | None) -> str:
    if not ts_str:
        return "unknown"
    try:
        from datetime import datetime
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        delta = datetime.utcnow() - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return "just now"
        mins = secs // 60
        if mins < 60:
            return f"{mins}m ago"
        hours = mins // 60
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except (ValueError, TypeError):
        return str(ts_str)


def build_history_embed(rows: list, member, tab: str) -> discord.Embed:
    tab_labels = {
        "fish": "\U0001f420 Fish",
        "location": "\U0001f4cd Locations",
        "simulation": "\U0001f3ae Simulations",
        "command": "\U0001f4ac Commands",
    }
    embed = discord.Embed(
        title=f"\U0001f4dc Recent — {tab_labels.get(tab, tab)}",
        color=0x5865F2,
    )
    embed.set_author(name="\U0001f4dc History")
    if not rows:
        embed.description = f"No {tab} history yet."
        return embed
    lines = []
    for i, row in enumerate(rows, 1):
        item_id = row["item_id"] or "?"
        ts = _relative_time(row.get("created_at"))
        lines.append(f"`{i:>2}.` **{item_id}** — {ts}")
    embed.description = "\n".join(lines)
    return embed


def build_settings_embed(user_row) -> discord.Embed:
    tz = user_row["timezone"] or "UTC"
    theme = (user_row["theme"] or "dark").capitalize()
    compact = "On" if user_row["compact_mode"] else "Off"
    embed = discord.Embed(title="⚙️ Settings", color=0x5865F2)
    embed.set_author(name="⚙️ Settings")
    embed.description = (
        f"\U0001f30d **Timezone:** {tz}\n"
        f"\U0001f319 **Theme:** {theme}\n"
        f"\U0001f4c4 **Compact Mode:** {compact}\n"
        f"\U0001f514 **Notification Preferences:** *Coming in Phase 6*\n"
        f"\U0001f3ae **Default Simulator Values:** *Coming in Phase 3*"
    )
    return embed
```

- [ ] **Step 4: Run embed tests**

```
pytest tests/test_profile_cog.py -k "build_favorites or build_history or build_settings" -v
```

Expected: all PASS.

- [ ] **Step 5: Add views and commands to `cogs/profile.py`**

Add the following after `ProfileView` and before `ProfileCog` in `cogs/profile.py`:

```python
def _group_favs(rows) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {"fish": [], "location": [], "tool": [], "bait": []}
    for row in rows:
        t = row["type"]
        if t in result:
            result[t].append(row["item_id"])
    return result


class FavoritesView(discord.ui.View):
    def __init__(self, db, user, dank_client, fav_rows):
        super().__init__(timeout=300)
        self.db = db
        self.user = user
        self.dc = dank_client
        self.selected_type: str | None = None
        self.selected_id: str | None = None
        self.message: discord.Message | None = None
        self._build_select(fav_rows)
        self._update_action_buttons()

    def _build_select(self, fav_rows):
        for item in list(self.children):
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)
        TYPE_EMOJI = {"fish": "\U0001f420", "location": "\U0001f4cd", "tool": "\U0001f527", "bait": "\U0001fab1"}
        options = []
        for row in fav_rows[:25]:
            emoji = TYPE_EMOJI.get(row["type"], "⭐")
            label = f"{emoji} {row['item_id']}"
            value = f"{row['type']}:{row['item_id']}"
            options.append(discord.SelectOption(label=label[:100], value=value))
        if not options:
            return
        select = discord.ui.Select(placeholder="Choose a favourite to view…", options=options, row=0)
        select.callback = self._on_select
        self.add_item(select)

    def _update_action_buttons(self):
        has = self.selected_id is not None
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.label in ("\U0001f517 Open", "\U0001f5d1️ Remove"):
                item.disabled = not has

    async def _on_select(self, interaction: discord.Interaction) -> None:
        select = next(c for c in self.children if isinstance(c, discord.ui.Select))
        value = select.values[0]
        self.selected_type, self.selected_id = value.split(":", 1)
        self._update_action_buttons()
        favs = await self.db.get_favorites(str(self.user.id))
        by_type = _group_favs(favs)
        from utils.embeds import build_favorites_embed
        embed = build_favorites_embed(by_type, self.user)
        embed.set_footer(text=f"Selected: {self.selected_id} — click Open to view or Remove to delete")
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="\U0001f517 Open", style=discord.ButtonStyle.primary, disabled=True, row=1)
    async def open_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        from utils.embeds import build_fish_embed, build_location_embed, build_tool_embed, build_bait_embed
        embed = None
        if self.selected_type == "fish":
            item = self.dc.fish_by_id.get(self.selected_id)
            if item:
                embed = build_fish_embed(item, self.dc)
        elif self.selected_type == "location":
            item = self.dc.location_by_id.get(self.selected_id)
            if item:
                embed = build_location_embed(item, self.dc)
        elif self.selected_type == "tool":
            item = self.dc.tool_by_id.get(self.selected_id)
            if item:
                embed = build_tool_embed(item)
        elif self.selected_type == "bait":
            item = self.dc.bait_by_id.get(self.selected_id)
            if item:
                embed = build_bait_embed(item)
        if embed is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", "This item no longer exists in the game data."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="\U0001f5d1️ Remove", style=discord.ButtonStyle.danger, disabled=True, row=1)
    async def remove_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.db.remove_favorite(str(self.user.id), self.selected_type, self.selected_id)
        self.selected_type = None
        self.selected_id = None
        favs = await self.db.get_favorites(str(self.user.id))
        by_type = _group_favs(favs)
        self._build_select(favs)
        self._update_action_buttons()
        from utils.embeds import build_favorites_embed
        embed = build_favorites_embed(by_type, self.user)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="\U0001f3ae Simulate", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass


class HistoryView(discord.ui.View):
    def __init__(self, db, user):
        super().__init__(timeout=300)
        self.db = db
        self.user = user
        self.current_tab = "fish"
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    async def _switch_tab(self, interaction: discord.Interaction, tab: str) -> None:
        self.current_tab = tab
        rows = await self.db.get_history(str(self.user.id), tab)
        from utils.embeds import build_history_embed
        embed = build_history_embed(rows, self.user, tab)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="\U0001f420 Fish", style=discord.ButtonStyle.primary, row=0)
    async def fish_tab(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "fish")

    @discord.ui.button(label="\U0001f4cd Locations", style=discord.ButtonStyle.secondary, row=0)
    async def location_tab(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "location")

    @discord.ui.button(label="\U0001f3ae Simulations", style=discord.ButtonStyle.secondary, disabled=True, row=0)
    async def sim_tab(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="\U0001f4ac Commands", style=discord.ButtonStyle.secondary, row=0)
    async def command_tab(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "command")


class TimezoneModal(discord.ui.Modal, title="Set Timezone"):
    timezone: discord.ui.TextInput = discord.ui.TextInput(
        label="IANA Timezone",
        placeholder="e.g. UTC, Asia/Kolkata, America/New_York",
        min_length=2,
        max_length=50,
    )

    def __init__(self, db, member, message, current_tz: str):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message
        self.timezone.default = current_tz

    async def on_submit(self, interaction: discord.Interaction) -> None:
        tz_str = self.timezone.value.strip()
        try:
            ZoneInfo(tz_str)
        except (ZoneInfoNotFoundError, KeyError):
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "Invalid timezone",
                    f"Unknown timezone **{tz_str}**. Use an IANA name like `UTC` or `Asia/Kolkata`.",
                ),
                ephemeral=True,
            )
            return
        await self.db.update_user(str(self.member.id), timezone=tz_str)
        user_row = await self.db.get_user(str(self.member.id))
        from utils.embeds import build_settings_embed
        await self.message.edit(
            embed=build_settings_embed(user_row),
            view=SettingsView(self.db, self.member),
        )
        await interaction.response.defer()


class SettingsView(discord.ui.View):
    def __init__(self, db, member):
        super().__init__(timeout=300)
        self.db = db
        self.member = member
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="\U0001f30d Set Timezone", style=discord.ButtonStyle.secondary, row=0)
    async def timezone_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_user(str(self.member.id))
        current_tz = (user_row["timezone"] if user_row else None) or "UTC"
        await interaction.response.send_modal(
            TimezoneModal(self.db, self.member, interaction.message, current_tz)
        )

    @discord.ui.button(label="\U0001f319 Theme: Dark", style=discord.ButtonStyle.secondary, row=0)
    async def theme_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_user(str(self.member.id))
        current = (user_row["theme"] if user_row else None) or "dark"
        new_theme = "light" if current == "dark" else "dark"
        await self.db.update_user(str(self.member.id), theme=new_theme)
        button.label = f"{'🌕' if new_theme == 'light' else '🌑'} Theme: {'Light' if new_theme == 'light' else 'Dark'}"
        user_row = await self.db.get_user(str(self.member.id))
        from utils.embeds import build_settings_embed
        await interaction.response.edit_message(embed=build_settings_embed(user_row), view=self)

    @discord.ui.button(label="\U0001f4c4 Compact: Off", style=discord.ButtonStyle.secondary, row=0)
    async def compact_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_user(str(self.member.id))
        current = bool(user_row["compact_mode"] if user_row else False)
        new_val = not current
        await self.db.update_user(str(self.member.id), compact_mode=int(new_val))
        button.label = f"\U0001f4c4 Compact: {'On' if new_val else 'Off'}"
        user_row = await self.db.get_user(str(self.member.id))
        from utils.embeds import build_settings_embed
        await interaction.response.edit_message(embed=build_settings_embed(user_row), view=self)

    @discord.ui.button(label="\U0001f514 Notifications", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def notif_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="\U0001f3ae Default Sim Values", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def sim_defaults_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass
```

Then add the three commands to `ProfileCog` (inside the class, after the `profile` command):

```python
    @app_commands.command(name="favorites", description="View and manage your favourited fish, locations, tools, and baits")
    async def favorites(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        fav_rows = await self.bot.db.get_favorites(user_id)
        by_type = _group_favs(fav_rows)
        from utils.embeds import build_favorites_embed
        embed = build_favorites_embed(by_type, interaction.user)
        view = FavoritesView(self.bot.db, interaction.user, self.bot.dank_client, fav_rows)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="history", description="View recently viewed fish, locations, and simulations")
    async def history(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        rows = await self.bot.db.get_history(user_id, "fish")
        from utils.embeds import build_history_embed
        embed = build_history_embed(rows, interaction.user, "fish")
        view = HistoryView(self.bot.db, interaction.user)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="settings", description="Configure your personal preferences")
    async def settings(self, interaction: discord.Interaction):
        user_row = await self.bot.db.get_or_create_user(str(interaction.user.id))
        from utils.embeds import build_settings_embed
        embed = build_settings_embed(user_row)
        view = SettingsView(self.bot.db, interaction.user)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
```

- [ ] **Step 6: Run all profile tests**

```
pytest tests/test_profile_cog.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Run the full suite**

```
pytest tests/ -v
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add utils/embeds.py cogs/profile.py tests/test_profile_cog.py
git commit -m "feat: implement /favorites, /history, /settings commands"
```

---

### Task 4: Favourite Toggle Button + History Writing in P1 Cogs

**Files:**
- Modify: `cogs/fish.py`
- Modify: `cogs/locations.py`
- Modify: `cogs/tools.py`
- Modify: `cogs/baits.py`
- Modify: `tests/test_fish_cog.py`
- Modify: `tests/test_locations_cog.py`
- Modify: `tests/test_tools_cog.py`
- Modify: `tests/test_baits_cog.py`

**Interfaces:**
- Consumes: `Database.add_favorite`, `Database.remove_favorite`, `Database.get_favorites`, `Database.add_history` (Task 1)
- Produces: Favourite toggle button active in `FishView`, `LocationView`, `ToolView`, `BaitView`; history rows written on every successful lookup

**Design decisions (read before implementing):**

1. Each P1 view gets two new optional constructor params: `db=None` and `user_id=None`. When `db is None`, the Favourite button stays `disabled=True`. This preserves all existing tests which construct views without a db.

2. Initial favourite state: in the cog command (which is async), query `db.get_favorites(user_id, type)` before constructing the view, then pass `is_faved: bool` to the view. The view sets the button label accordingly.

3. History writing: fire-and-forget in the cog command after a successful lookup, wrapped in `try/except` so a DB error never blocks the response.

4. Views that spawn other views (e.g. `BackToFishView` → `FishView`) need to carry `db` and `user_id` through. The spawned `FishView` starts with `is_faved=False` (acceptable — user must re-click if they want to unfavourite from the compare-back flow).

5. `LocationView` spawns an ephemeral `FishView` via the "Open Fish" button; that ephemeral view also gets `db` and `user_id`.

- [ ] **Step 1: Write new failing tests**

Append to `tests/test_fish_cog.py`:

```python
# ---------------------------------------------------------------------------
# FishView — Favourite button
# ---------------------------------------------------------------------------

def test_fishview_fav_btn_disabled_when_no_db():
    from cogs.fish import FishView
    creature = make_creature()
    dc = make_mock_dank_client()
    view = FishView(creature, dc)  # no db/user_id — existing call style
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Favour" in item.label
    )
    assert fav_btn.disabled is True

def test_fishview_fav_btn_enabled_when_db_provided():
    from cogs.fish import FishView
    creature = make_creature()
    dc = make_mock_dank_client()
    db = MagicMock()
    view = FishView(creature, dc, db=db, user_id="123", is_faved=False)
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Favour" in item.label
    )
    assert fav_btn.disabled is False

def test_fishview_fav_btn_label_unfavourite_when_faved():
    from cogs.fish import FishView
    creature = make_creature()
    dc = make_mock_dank_client()
    db = MagicMock()
    view = FishView(creature, dc, db=db, user_id="123", is_faved=True)
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Favour" in item.label
    )
    assert "Unfavourite" in fav_btn.label or "💛" in fav_btn.label

@pytest.mark.asyncio
async def test_fishview_fav_btn_adds_favourite():
    from cogs.fish import FishView
    creature = make_creature(id="goldfish")
    dc = make_mock_dank_client()
    db = MagicMock()
    db.add_favorite = AsyncMock()
    db.remove_favorite = AsyncMock()
    view = FishView(creature, dc, db=db, user_id="123", is_faved=False)
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Favour" in item.label
    )
    interaction = make_interaction()
    await fav_btn.callback(interaction)
    db.add_favorite.assert_called_once_with("123", "fish", "goldfish")
    interaction.response.edit_message.assert_called_once()

@pytest.mark.asyncio
async def test_fishview_fav_btn_removes_when_already_faved():
    from cogs.fish import FishView
    creature = make_creature(id="goldfish")
    dc = make_mock_dank_client()
    db = MagicMock()
    db.add_favorite = AsyncMock()
    db.remove_favorite = AsyncMock()
    view = FishView(creature, dc, db=db, user_id="123", is_faved=True)
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Favour" in item.label
    )
    interaction = make_interaction()
    await fav_btn.callback(interaction)
    db.remove_favorite.assert_called_once_with("123", "fish", "goldfish")

@pytest.mark.asyncio
async def test_fish_command_writes_history():
    from cogs.fish import FishCog
    db = MagicMock()
    db.get_favorites = AsyncMock(return_value=[])
    db.add_history = AsyncMock()
    bot = make_mock_bot()
    bot.db = db
    cog = FishCog(bot)
    interaction = make_interaction()
    await cog.fish.callback(cog, interaction, name="Goldfish")
    db.add_history.assert_called_once_with("123", "fish", "goldfish")
```

Add equivalent tests to `tests/test_tools_cog.py` and `tests/test_baits_cog.py`. For tools, the type is `"tool"` and item ID is `tool.id`. For baits, the type is `"bait"`.

For `tests/test_tools_cog.py`, append:

```python
@pytest.mark.asyncio
async def test_tool_command_writes_history():
    from cogs.tools import ToolsCog
    db = MagicMock()
    db.get_favorites = AsyncMock(return_value=[])
    db.add_history = AsyncMock()
    # bot with db
    bot = make_mock_bot()  # use the helper already in that file
    bot.db = db
    cog = ToolsCog(bot)
    interaction = make_interaction()
    await cog.tool.callback(cog, interaction, name="Fishing Rod")
    db.add_history.assert_called_once_with(str(interaction.user.id), "tool", "rod")

def test_toolview_fav_btn_enabled_when_db_provided():
    from cogs.tools import ToolView
    tool = make_tool()
    dc = MagicMock()
    db = MagicMock()
    view = ToolView(tool, dc, db=db, user_id="123", is_faved=False)
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Favour" in item.label
    )
    assert fav_btn.disabled is False
```

For `tests/test_baits_cog.py`, append (read the file first to use its existing `make_mock_bot` / `make_interaction` helpers):

```python
@pytest.mark.asyncio
async def test_bait_command_writes_history():
    from cogs.baits import BaitsCog
    db = MagicMock()
    db.get_favorites = AsyncMock(return_value=[])
    db.add_history = AsyncMock()
    bot = make_mock_bot()
    bot.db = db
    cog = BaitsCog(bot)
    interaction = make_interaction()
    await cog.bait.callback(cog, interaction, name="Glitter Bait")
    db.add_history.assert_called_once_with(str(interaction.user.id), "bait", "glitter")

def test_baitview_fav_btn_enabled_when_db_provided():
    from cogs.baits import BaitView
    bait = make_bait()
    dc = MagicMock()
    db = MagicMock()
    view = BaitView(bait, dc, db=db, user_id="123", is_faved=False)
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Favour" in item.label
    )
    assert fav_btn.disabled is False
```

- [ ] **Step 2: Run to verify failures**

```
pytest tests/test_fish_cog.py -k "fav" -v
```

Expected: `TypeError: FishView.__init__() got unexpected keyword argument 'db'`.

- [ ] **Step 3: Update `cogs/fish.py`**

Change `FishView.__init__` signature and fav button:

```python
class FishView(discord.ui.View):
    def __init__(self, creature, dank_client, db=None, user_id=None, is_faved=False):
        super().__init__(timeout=300)
        self.creature = creature
        self.dc = dank_client
        self.db = db
        self.user_id = user_id
        self._is_faved = is_faved
        if not (creature.extra.get("variants") or []):
            self.variants_btn.disabled = True
        # Configure fav button
        fav_btn = next(
            item for item in self.children
            if isinstance(item, discord.ui.Button) and "Favour" in item.label
        )
        if db is None:
            fav_btn.disabled = True
        else:
            fav_btn.disabled = False
            if is_faved:
                fav_btn.label = "💛 Unfavourite"
                fav_btn.style = discord.ButtonStyle.primary
        self.message: discord.Message | None = None
```

Change the `fav_btn` callback:

```python
    @discord.ui.button(label="⭐ Favourite", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def fav_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._is_faved:
            await self.db.remove_favorite(self.user_id, "fish", self.creature.id)
            self._is_faved = False
            button.label = "⭐ Favourite"
            button.style = discord.ButtonStyle.secondary
        else:
            await self.db.add_favorite(self.user_id, "fish", self.creature.id)
            self._is_faved = True
            button.label = "💛 Unfavourite"
            button.style = discord.ButtonStyle.primary
        await interaction.response.edit_message(view=self)
```

Update `BackToFishView` to carry `db` and `user_id` through:

```python
class BackToFishView(discord.ui.View):
    def __init__(self, creature, dank_client, db=None, user_id=None):
        super().__init__(timeout=300)
        self.creature = creature
        self.dc = dank_client
        self.db = db
        self.user_id = user_id

    # on_timeout unchanged

    @discord.ui.button(label="↩ Back", style=discord.ButtonStyle.secondary)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = FishView(self.creature, self.dc, db=self.db, user_id=self.user_id)
        await interaction.response.edit_message(
            embed=build_fish_embed(self.creature, self.dc), view=view
        )
```

Update `FishCompareModal` to carry `db` and `user_id`:

```python
class FishCompareModal(discord.ui.Modal, title="Compare Fish"):
    # TextInput unchanged

    def __init__(self, first_creature, dank_client, db=None, user_id=None):
        super().__init__()
        self.first = first_creature
        self.dc = dank_client
        self.db = db
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # ... existing not-found logic unchanged ...
        await interaction.response.edit_message(
            embed=build_fish_compare_embed(self.first, second),
            view=BackToFishView(creature=self.first, dank_client=self.dc, db=self.db, user_id=self.user_id)
        )
```

Update `FishView.compare_btn` to pass `db` and `user_id` to the modal:

```python
    @discord.ui.button(label="⚔️ Compare", style=discord.ButtonStyle.primary, row=1)
    async def compare_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            FishCompareModal(self.creature, self.dc, db=self.db, user_id=self.user_id)
        )
```

Update the `FishCog.fish` command to query fav state, pass to view, and write history:

```python
    @app_commands.command(name="fish", description="Look up a fish by name")
    @app_commands.describe(name="Fish name")
    async def fish(self, interaction: discord.Interaction, name: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        creature = self.bot.dank_client.get_fish(name)
        if creature is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND_MSG.format(name=name)),
                ephemeral=True,
            )
            return
        user_id = str(interaction.user.id)
        is_faved = False
        if self.bot.db:
            try:
                favs = await self.bot.db.get_favorites(user_id, "fish")
                is_faved = any(f["item_id"] == creature.id for f in favs)
                await self.bot.db.add_history(user_id, "fish", creature.id)
            except Exception:
                pass
        view = FishView(creature, self.bot.dank_client, db=self.bot.db, user_id=user_id, is_faved=is_faved)
        embed = build_fish_embed(creature, self.bot.dank_client)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
```

- [ ] **Step 4: Update `cogs/tools.py`**

Apply the same pattern to `ToolView` and `ToolsCog.tool`:

```python
class ToolView(discord.ui.View):
    def __init__(self, tool, dank_client, db=None, user_id=None, is_faved=False):
        super().__init__(timeout=300)
        self.tool = tool
        self.dc = dank_client
        self.db = db
        self.user_id = user_id
        self._is_faved = is_faved
        fav_btn = next(
            item for item in self.children
            if isinstance(item, discord.ui.Button) and "Favour" in item.label
        )
        if db is None:
            fav_btn.disabled = True
        else:
            fav_btn.disabled = False
            if is_faved:
                fav_btn.label = "💛 Unfavourite"
                fav_btn.style = discord.ButtonStyle.primary
        self.message: discord.Message | None = None
```

Add fav button before the Simulate button in `ToolView`:

```python
    @discord.ui.button(label="⭐ Favourite", style=discord.ButtonStyle.secondary, disabled=True)
    async def fav_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._is_faved:
            await self.db.remove_favorite(self.user_id, "tool", self.tool.id)
            self._is_faved = False
            button.label = "⭐ Favourite"
            button.style = discord.ButtonStyle.secondary
        else:
            await self.db.add_favorite(self.user_id, "tool", self.tool.id)
            self._is_faved = True
            button.label = "💛 Unfavourite"
            button.style = discord.ButtonStyle.primary
        await interaction.response.edit_message(view=self)
```

Update `ToolsCog.tool` command:

```python
    @app_commands.command(name="tool", description="Look up a fishing tool")
    @app_commands.describe(name="Tool name")
    async def tool(self, interaction: discord.Interaction, name: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        t = self.bot.dank_client.get_tool(name)
        if t is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=name)),
                ephemeral=True,
            )
            return
        user_id = str(interaction.user.id)
        is_faved = False
        if self.bot.db:
            try:
                favs = await self.bot.db.get_favorites(user_id, "tool")
                is_faved = any(f["item_id"] == t.id for f in favs)
                await self.bot.db.add_history(user_id, "tool", t.id)
            except Exception:
                pass
        view = ToolView(t, self.bot.dank_client, db=self.bot.db, user_id=user_id, is_faved=is_faved)
        embed = build_tool_embed(t)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
```

- [ ] **Step 5: Update `cogs/baits.py`**

Apply the same pattern to `BaitView` and `BaitsCog.bait`. Type is `"bait"`, item ID is `bait.id`:

```python
class BaitView(discord.ui.View):
    def __init__(self, bait, dank_client, db=None, user_id=None, is_faved=False):
        super().__init__(timeout=300)
        self.bait = bait
        self.dc = dank_client
        self.db = db
        self.user_id = user_id
        self._is_faved = is_faved
        fav_btn = next(
            item for item in self.children
            if isinstance(item, discord.ui.Button) and "Favour" in item.label
        )
        if db is None:
            fav_btn.disabled = True
        else:
            fav_btn.disabled = False
            if is_faved:
                fav_btn.label = "💛 Unfavourite"
                fav_btn.style = discord.ButtonStyle.primary
        self.message: discord.Message | None = None

    # on_timeout unchanged

    @discord.ui.button(label="⭐ Favourite", style=discord.ButtonStyle.secondary, disabled=True)
    async def fav_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._is_faved:
            await self.db.remove_favorite(self.user_id, "bait", self.bait.id)
            self._is_faved = False
            button.label = "⭐ Favourite"
            button.style = discord.ButtonStyle.secondary
        else:
            await self.db.add_favorite(self.user_id, "bait", self.bait.id)
            self._is_faved = True
            button.label = "💛 Unfavourite"
            button.style = discord.ButtonStyle.primary
        await interaction.response.edit_message(view=self)
```

Update `BaitsCog.bait` command identically to the fish/tool pattern (type=`"bait"`, item_id=`b.id`).

- [ ] **Step 6: Update `cogs/locations.py`**

`LocationView` and `LocationsCog.location` follow the same pattern (type=`"location"`, item_id=`location.id`). The `LocationView.__init__` already takes `location` and `dank_client`; add `db=None, user_id=None, is_faved=False`. The fav button wires up to add/remove `"location"` type favourites.

The "Open Fish" ephemeral in `LocationView` constructs a `FishView` — pass `db` and `user_id` there too:

```python
# Inside LocationView's open_fish handler (wherever it sends the fish embed):
view = FishView(fish_creature, self.dc, db=self.db, user_id=self.user_id)
```

Update `LocationsCog.location` command to query fav state and write history for the location:

```python
user_id = str(interaction.user.id)
is_faved = False
if self.bot.db:
    try:
        favs = await self.bot.db.get_favorites(user_id, "location")
        is_faved = any(f["item_id"] == location.id for f in favs)
        await self.bot.db.add_history(user_id, "location", location.id)
    except Exception:
        pass
view = LocationView(location, self.bot.dank_client, db=self.bot.db, user_id=user_id, is_faved=is_faved)
```

- [ ] **Step 7: Run all tests**

```
pytest tests/ -v
```

Expected: all green. Existing tests that construct `FishView(creature, dc)` still pass because `db=None` default leaves fav button disabled — same as before.

- [ ] **Step 8: Commit**

```bash
git add cogs/fish.py cogs/locations.py cogs/tools.py cogs/baits.py \
        tests/test_fish_cog.py tests/test_locations_cog.py \
        tests/test_tools_cog.py tests/test_baits_cog.py
git commit -m "feat: enable favourite toggle button and history writing in P1 cogs"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| `/profile` — view all profile fields | Task 2 |
| `/profile` — Edit Setup/Skills/Unlocks/Env/Favs modals | Task 2 |
| `/profile` — Reset with confirmation | Task 2 |
| `/profile` — Export/Import disabled | Task 2 |
| `/favorites` — view by type, select, Open, Remove | Task 3 |
| `/favorites` — Simulate disabled | Task 3 |
| `/history` — Fish/Locations/Commands tabs, 20-item cap | Task 3 |
| `/settings` — Timezone (validated), Theme toggle, Compact toggle | Task 3 |
| `/settings` — Notif/Sim-defaults disabled | Task 3 |
| Favourite button toggle in `/fish` | Task 4 |
| Favourite button toggle in `/location` | Task 4 |
| Favourite button toggle in `/tool` | Task 4 |
| Favourite button toggle in `/bait` | Task 4 |
| History row written on `/fish` lookup | Task 4 |
| History row written on `/location` lookup | Task 4 |
| History row written on `/tool` lookup | Task 4 |
| History row written on `/bait` lookup | Task 4 |
| DB: get_or_create_user | Task 1 |
| DB: add/remove/get_favorites | Task 1 |
| DB: add/get_history (with 20-row prune) | Task 1 |
| All views: 300s timeout, disable-on-timeout | Tasks 2–4 |
| All errors: ephemeral EmbedBuilder.error | Tasks 2–4 |

**Placeholder scan:** Clean — no TBDs or "similar to" references.

**Type consistency:** All `discord_id` params are `str`. `get_favorites` returns `list[aiosqlite.Row]` (dict-like). `build_profile_embed` signature matches its call sites. `ProfileView(db, member, dank_client)` signature consistent across all callers.
