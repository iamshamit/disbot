"""Tests for cogs/profile.py and profile embed builders."""
from __future__ import annotations

import json as _json
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
        "skills": None,
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
    row = make_user_row(current_tool="Harpoon", current_bait="Glitter Bait")
    member = make_member()
    embed = build_profile_embed(row, member)
    setup_field = next(f for f in embed.fields if "SETUP" in f.name)
    assert "Harpoon" in setup_field.value
    assert "Glitter Bait" in setup_field.value
    assert "Rod" not in setup_field.value

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
    row = make_user_row(current_event="Fishing Festival")
    member = make_member()
    embed = build_profile_embed(row, member)
    env_field = next(f for f in embed.fields if "ENV" in f.name.upper())
    assert "Fishing Festival" in env_field.value
    assert "Weather" not in env_field.value

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
    assert export_btn.disabled is False

@pytest.mark.asyncio
async def test_profile_view_edit_setup_btn_shows_picker():
    from cogs.profile import ProfileView, EditSetupView
    db = MagicMock()
    dc = MagicMock()
    dc.tool_by_id = {}
    dc.bait_by_id = {}
    member = make_member()
    view = ProfileView(db, member, dc)
    interaction = make_interaction()
    edit_setup_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Setup" in item.label
    )
    await edit_setup_btn.callback(interaction)
    interaction.response.edit_message.assert_called_once()
    kwargs = interaction.response.edit_message.call_args.kwargs
    assert isinstance(kwargs["view"], EditSetupView)

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

@pytest.mark.asyncio
async def test_edit_unlocks_view_has_selects():
    from cogs.profile import EditUnlocksView
    db = MagicMock()
    dc = MagicMock()
    member = make_member()
    view = EditUnlocksView(db, member, dc)
    selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
    assert len(selects) == 2
    placeholders = [s.placeholder for s in selects]
    assert any("Boss" in p for p in placeholders)
    assert any("Mythical" in p for p in placeholders)

@pytest.mark.asyncio
async def test_edit_unlocks_view_save_writes_boss_unlock():
    from cogs.profile import EditUnlocksView
    db = MagicMock()
    db.update_user = AsyncMock()
    db.get_user = AsyncMock(return_value=make_user_row(boss_unlock=1))
    dc = MagicMock()
    member = make_member()
    view = EditUnlocksView(db, member, dc)
    view._boss_sel._values = ["1"]
    interaction = make_interaction()
    await view.save_btn.callback(interaction)
    db.update_user.assert_called_once()
    assert db.update_user.call_args.kwargs.get("boss_unlock") == 1
    interaction.response.edit_message.assert_called_once()

@pytest.mark.asyncio
async def test_edit_setup_view_has_tool_and_bait_selects():
    from cogs.profile import EditSetupView
    db = MagicMock()
    dc = MagicMock()
    dc.tool_by_id = {}
    dc.bait_by_id = {}
    member = make_member()
    view = EditSetupView(db, member, dc)
    selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
    assert len(selects) == 2
    placeholders = [s.placeholder for s in selects]
    assert any("tool" in p.lower() for p in placeholders)
    assert any("bait" in p.lower() for p in placeholders)

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
    assert call_kwargs.get("boss_unlock") == 0
    assert "skills" in call_kwargs
    assert call_kwargs.get("skills") is None

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


# ---------------------------------------------------------------------------
# SkillsPickerView
# ---------------------------------------------------------------------------

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
    selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
    mode_sel = selects[0]
    opt_values = [o.value for o in mode_sel.options]
    assert "summary" in opt_values
    assert "cat:Economy" in opt_values
    assert "cat:Nature" in opt_values

@pytest.mark.asyncio
async def test_skills_picker_autosave_writes_to_db():
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
    view = SkillsPickerView(db, member, dc, {}, return_fn)
    # Simulate selecting tier 2 via the tier callback
    cb = view._make_tier_cb("haggler")
    interaction = make_interaction()
    interaction.data = {"values": ["2"]}
    await cb(interaction)
    db.update_user.assert_called_once()
    written = db.update_user.call_args.kwargs.get("skills")
    assert json.loads(written) == {"haggler": 2}

@pytest.mark.asyncio
async def test_skills_picker_autosave_removes_tier_zero():
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
    cb = view._make_tier_cb("haggler")
    interaction = make_interaction()
    interaction.data = {"values": ["0"]}
    await cb(interaction)
    written = db.update_user.call_args.kwargs.get("skills")
    assert "haggler" not in (json.loads(written) if written else {})

@pytest.mark.asyncio
async def test_skills_picker_done_calls_return_fn():
    from cogs.simulator import SkillsPickerView
    db = MagicMock()
    dc = MagicMock()
    dc.skill_categories = {}
    member = make_member()
    returned = []
    async def return_fn(inter): returned.append(True)
    view = SkillsPickerView(db, member, dc, {}, return_fn)
    interaction = make_interaction()
    await view._done(interaction)
    assert returned


# ---------------------------------------------------------------------------
# Task 3: Profile stub wiring
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_favorites_simulate_btn_opens_simulator():
    from cogs.profile import FavoritesView
    from cogs.simulator import SimulatorView

    db = MagicMock()
    db.get_favorites = AsyncMock(return_value=[])
    user = make_member()
    dc = MagicMock()
    dc.location_by_id = {"river": MagicMock(id="river", name="River")}
    dc.tool_by_id = {}
    dc.bait_by_id = {}
    dc.event_by_id = {}

    view = FavoritesView(db, user, dc, [])
    view.selected_type = "location"
    view.selected_id = "river"

    inter = make_interaction()
    await view.sim_btn.callback(inter)

    inter.response.send_message.assert_awaited_once()
    call_kwargs = inter.response.send_message.call_args
    sent_view = call_kwargs.kwargs.get("view")
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
    await view.sim_tab.callback(inter)

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
    await view.sim_defaults_btn.callback(inter)

    inter.response.send_message.assert_awaited_once()
    call_kwargs = inter.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True
    sent_embed = call_kwargs.kwargs.get("embed")
    assert sent_embed is not None
    assert "Fishing Rod" in str(sent_embed.fields)


# ---------------------------------------------------------------------------
# Task 4: Profile Export / Import
# ---------------------------------------------------------------------------

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
    await view.export_btn.callback(inter)

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

@pytest.mark.asyncio
async def test_import_rejects_wrong_version():
    from cogs.profile import ImportModal
    db = MagicMock()
    member = make_member()
    modal = ImportModal(db, member, MagicMock())
    modal.json_input._value = _json.dumps({"version": 2, "profile": {}, "favorites": []})
    inter = make_interaction()
    await modal.on_submit(inter)
    inter.response.send_message.assert_awaited_once()
    assert inter.response.send_message.call_args.kwargs.get("ephemeral") is True
