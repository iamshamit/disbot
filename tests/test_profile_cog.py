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
    assert call_kwargs.get("fishing_skill") == 0
    assert call_kwargs.get("boss_unlock") == 0

@pytest.mark.asyncio
async def test_reset_confirm_view_cancel_restores_profile():
    from cogs.profile import ResetConfirmView
    db = MagicMock()
    db.get_user = AsyncMock(return_value=make_user_row())
    dc = MagicMock()
    member = make_member()
    view = ResetConfirmView(db, member, dc)
    interaction = make_interaction()
    await view.cancel_btn.callback(interaction)
    interaction.response.edit_message.assert_called_once()


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
    db.get_or_create_user = AsyncMock(return_value=make_user_row(timezone="Asia/Kolkata"))
    member = make_member()
    message = AsyncMock()
    modal = TimezoneModal(db, member, message, "UTC")
    modal.timezone._value = "Asia/Kolkata"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    db.update_user.assert_called_once()
    assert db.update_user.call_args.kwargs.get("timezone") == "Asia/Kolkata"
    db.get_or_create_user.assert_called_once_with("123")
