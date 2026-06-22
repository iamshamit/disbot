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
async def test_simulator_view_has_4_selects_and_4_buttons():
    from cogs.simulator import SimulatorView
    db = MagicMock()
    dc = make_dc()
    member = make_member()
    view = SimulatorView(db, member, dc)
    selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
    buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
    assert len(selects) == 4
    assert len(buttons) == 4
    btn_labels = [b.label for b in buttons]
    assert "🔄 Calculate" in btn_labels
    assert "👥 Skills" in btn_labels
    assert "⚙️ Extras" in btn_labels
    assert "📈 Peak Hours" not in btn_labels
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
async def test_calculate_uses_engine_for_local_bait(monkeypatch):
    from cogs.simulator import SimulatorView
    dc = make_dc()
    view = SimulatorView(_routing_db(), make_member(), dc,
                         initial_state={"location_id": "river", "tool_id": "rod",
                                        "bait_id": None, "event_id": None, "hour": 12})
    called = {"engine": False, "api": False}

    def fake_engine(*a, **k):
        called["engine"] = True
        return {"failChance": 10, "npcChance": 0.5, "table": [], "variants": {}}

    async def fake_api(payload):
        called["api"] = True
        return {"failChance": 0, "npcChance": 0, "table": [], "variants": {}}

    monkeypatch.setattr(sim_mod, "local_simulate", fake_engine)
    monkeypatch.setattr(sim_mod, "call_simulator_api", fake_api)
    await view.calculate_btn.callback(make_interaction())
    assert called["engine"] is True
    assert called["api"] is False


@pytest.mark.asyncio
async def test_calculate_uses_api_for_fallback_bait(monkeypatch):
    from cogs.simulator import SimulatorView
    dc = make_dc()
    view = SimulatorView(_routing_db(), make_member(), dc,
                         initial_state={"location_id": "river", "tool_id": "rod",
                                        "bait_id": "lucky-bait", "event_id": None, "hour": 12})
    called = {"engine": False, "api": False}

    def fake_engine(*a, **k):
        called["engine"] = True
        return {"failChance": 10, "npcChance": 0.5, "table": [], "variants": {}}

    async def fake_api(payload):
        called["api"] = True
        return {"failChance": 0, "npcChance": 0, "table": [], "variants": {}}

    monkeypatch.setattr(sim_mod, "local_simulate", fake_engine)
    monkeypatch.setattr(sim_mod, "call_simulator_api", fake_api)
    await view.calculate_btn.callback(make_interaction())
    assert called["api"] is True
    assert called["engine"] is False


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
    assert "14:00" in body
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

    def fake_sim(dc_, *, location_id, tool_id, bait_id, hour, bosses=False, angler_tuesday=False):
        hours_seen.append(hour)
        return {"failChance": 10, "npcChance": 0.5,
                "table": [{"chance": 18.0, "baseChance": 18.0,
                           "value": {"type": "fish-creature", "creatureID": "bass"}}],
                "variants": {}}

    monkeypatch.setattr(sim_mod, "local_simulate", fake_sim)
    db = _routing_db()
    view = PeakHoursView(db, make_member(), dc, initial_loc_id="river", initial_tool_id="rod")
    view._fish_id = "bass"
    await view.show_btn.callback(make_interaction())
    assert sorted(hours_seen) == list(range(24))


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
