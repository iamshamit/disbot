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
