"""Tests for cogs/simulator.py — SimulatorView, ExtrasView, build_sim_results_embed."""
from __future__ import annotations
import json
import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch
import cogs.simulator as sim_mod


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
    location_river = MagicMock()
    location_river.id = "river"
    location_river.name = "Wily River"
    dc.location_by_id = {"river": location_river}
    dc.location_by_name = {"wily river": location_river}

    tool_rod = MagicMock()
    tool_rod.id = "rod"
    tool_rod.name = "Basic Rod"
    dc.tool_by_id = {"rod": tool_rod}
    dc.tool_by_name = {"basic rod": tool_rod}

    bait_worm = MagicMock()
    bait_worm.id = "worm"
    bait_worm.name = "Worm"
    dc.bait_by_id = {"worm": bait_worm}
    dc.bait_by_name = {"worm": bait_worm}

    event_2xtokens = MagicMock()
    event_2xtokens.id = "2xtokens"
    event_2xtokens.name = "Token Clone"
    dc.event_by_id = {"2xtokens": event_2xtokens}
    dc.event_by_name = {"token clone": event_2xtokens}

    fish_bass = MagicMock()
    fish_bass.id = "bass"
    fish_bass.name = "Bass"
    dc.fish_by_id = {"bass": fish_bass}

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
    assert "📈 Peak Hours" not in btn_labels
    assert "🗑️ Delete" in btn_labels
    assert "📊 Statistics" in btn_labels


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
async def test_extras_view_dropdowns_auto_apply():
    from cogs.simulator import SimulatorView, ExtrasView
    from utils.embeds import EmbedBuilder
    db = MagicMock()
    dc = make_dc()
    member = make_member()
    parent = SimulatorView(db, member, dc)
    current_embed = EmbedBuilder.info("Test", "")
    view = ExtrasView(parent, current_embed)
    # Simulate Tuesday toggle
    view._tuesday_sel._values = ["1"]
    interaction = make_interaction()
    await view._on_tuesday(interaction)
    assert parent._angler_tuesday is True
    interaction.response.defer.assert_called_once()

@pytest.mark.asyncio
async def test_extras_view_back_returns_to_parent():
    from cogs.simulator import SimulatorView, ExtrasView
    from utils.embeds import EmbedBuilder
    db = MagicMock()
    dc = make_dc()
    member = make_member()
    parent = SimulatorView(db, member, dc)
    embed = EmbedBuilder.info("Test", "")
    view = ExtrasView(parent, embed)
    back_btn = next(b for b in view.children if isinstance(b, discord.ui.Button) and "Back" in b.label)
    interaction = make_interaction()
    await back_btn.callback(interaction)
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


def test_build_variants_embed_shows_variants():
    from cogs.simulator import _build_variants_embed
    dc = make_dc()
    sim_data = {
        "variants": {
            "bass": [
                {"name": "unique", "type": "unique", "chance": 1.5},
                {"name": "chroma", "type": "chroma", "chance": 0.5},
            ]
        }
    }
    embed = _build_variants_embed(sim_data, dc)
    assert embed.fields, "variants embed should have fields"
    full = " ".join(f.name + " " + f.value for f in embed.fields)
    assert "Bass" in full
    assert "1.5" in full


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


@pytest.mark.asyncio
async def test_simulator_view_skills_btn_opens_picker():
    from cogs.simulator import SimulatorView, SkillsPickerView
    db = MagicMock()
    db.get_or_create_user = AsyncMock(return_value={"skills": None, "boss_unlock": 0,
        "favorite_location": None, "current_tool": None, "current_bait": None, "current_event": None})
    dc = make_dc()
    member = make_member()
    view = SimulatorView(db, member, dc)
    interaction = make_interaction()
    # The skills_btn should edit the message to show a SkillsPickerView
    await view.skills_btn.callback(interaction)
    interaction.response.edit_message.assert_called_once()
    call_kwargs = interaction.response.edit_message.call_args.kwargs
    assert isinstance(call_kwargs.get("view"), SkillsPickerView)


# --- calculate_btn routing ---


def _routing_db():
    db = MagicMock()
    db.get_or_create_user = AsyncMock(return_value=make_user_row(boss_unlock=0))
    db.add_history = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_calculate_always_uses_api(monkeypatch):
    from cogs.simulator import SimulatorView
    dc = make_dc()
    view = SimulatorView(_routing_db(), make_member(), dc,
                         initial_state={"location_id": "river", "tool_id": "rod",
                                        "bait_id": None, "event_id": None, "hour": 12})
    api_called = {"v": False}

    async def fake_api(payload):
        api_called["v"] = True
        return {"failChance": 0, "npcChance": 0, "table": [], "variants": {}}

    monkeypatch.setattr(sim_mod, "call_simulator_api", fake_api)
    await view.calculate_btn.callback(make_interaction())
    assert api_called["v"] is True


# --- build_fish_peak_embed ---

def test_build_fish_peak_embed_marks_best_hour():
    dc = make_dc()
    results = []
    for h in range(24):
        chance = 20.0 if h == 14 else 18.0
        results.append((h, {"failChance": 10, "npcChance": 0.5,
                            "table": [{"chance": chance, "baseChance": chance,
                                       "value": {"type": "fish-creature", "creatureID": "bass"}}],
                            "variants": {}}))
    embed = sim_mod.build_fish_peak_embed("bass", results, dc)
    body = (embed.description or "") + "".join(f.value for f in embed.fields)
    # Peak hour is shown as a Discord timestamp (<t:...:t>) not "14:00" literal
    assert "20.0%" in body
    assert "⭐" in body
    assert "Bass" in embed.title


def test_build_fish_peak_embed_constant_chance():
    dc = make_dc()
    results = [(h, {"failChance": 10, "npcChance": 0.5,
                    "table": [{"chance": 18.0, "baseChance": 18.0,
                               "value": {"type": "fish-creature", "creatureID": "bass"}}],
                    "variants": {}}) for h in range(24)]
    embed = sim_mod.build_fish_peak_embed("bass", results, dc)
    assert "constant" in (embed.description or "").lower()


# --- PeakHoursView ---

@pytest.mark.asyncio
async def test_peak_hours_view_has_3_selects_and_2_buttons():
    from cogs.simulator import PeakHoursView
    dc = make_dc()
    view = PeakHoursView(MagicMock(), make_member(), dc)
    selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    assert len(selects) == 3
    assert len(buttons) == 2
    btn_labels = [b.label for b in buttons]
    assert "📈 Show Peak Hours" in btn_labels
    assert "🗑️ Delete" in btn_labels


@pytest.mark.asyncio
async def test_peak_hours_view_show_btn_sweeps_24_hours(monkeypatch):
    from cogs.simulator import PeakHoursView
    dc = make_dc()
    dc.fish_by_id["bass"].extra = {"locations": ["river"], "tools": {"rod": {"max": 1}},
                                   "boss": False, "mythical": False, "rarity": "Common"}
    hours_seen = []

    async def fake_api(payload):
        hour = (payload["time"] // 3600000) % 24
        hours_seen.append(hour)
        return {"failChance": 10, "npcChance": 0.5,
                "table": [{"chance": 18.0, "baseChance": 18.0,
                           "value": {"type": "fish-creature", "creatureID": "bass"}}],
                "variants": {}}

    monkeypatch.setattr(sim_mod, "call_simulator_api", fake_api)
    db = _routing_db()
    view = PeakHoursView(db, make_member(), dc, initial_loc_id="river", initial_tool_id="rod")
    view._fish_id = "bass"
    await view.show_btn.callback(make_interaction())
    assert sorted(hours_seen) == list(range(24))


# --- auto-save ---

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
    monkeypatch.setattr("cogs.simulator.call_simulator_api", AsyncMock(return_value=fake_data))

    inter = make_interaction()
    await view.calculate_btn.callback(inter)

    db.update_user.assert_called_once_with(
        "123",
        current_tool="Basic Rod",
        current_bait="Worm",
        favorite_location="Wily River",
        current_event="Token Clone",
    )


# --- button layout ---

@pytest.mark.asyncio
async def test_simulator_view_has_no_peak_hours_set_time_in_extras():
    """Peak Hours removed from SimulatorView; Set Time stays in ExtrasView."""
    from cogs.simulator import SimulatorView, ExtrasView
    from utils.embeds import EmbedBuilder
    db = MagicMock()
    dc = make_dc()
    sim_view = SimulatorView(db, make_member(), dc)
    sim_btn_labels = [b.label for b in sim_view.children if isinstance(b, discord.ui.Button)]
    assert "📈 Peak Hours" not in sim_btn_labels
    assert "🕐 Set Time" not in sim_btn_labels

    extras_view = ExtrasView(sim_view, EmbedBuilder.info("Test", ""))
    extras_btn_labels = [b.label for b in extras_view.children if isinstance(b, discord.ui.Button)]
    assert "🕐 Set Time" in extras_btn_labels


# --- Statistics embed ---

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
    monkeypatch.setattr("cogs.simulator.call_simulator_api", AsyncMock(return_value=fake_data))

    inter = make_interaction()
    await view.calculate_btn.callback(inter)

    assert stats_btn.disabled is False
    assert view._last_sim_data == fake_data
