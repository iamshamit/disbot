from __future__ import annotations
import pytest
from unittest.mock import MagicMock, AsyncMock
from tests.conftest import make_creature, make_tool, make_location
import cogs.intelligence as _intel


def _make_dc():
    rod = make_tool(id="fishing-rod", name="Fishing Rod")
    ocean = make_location(id="ocean", name="Ocean")
    bass = make_creature(
        id="bass", name="Bass", rarity="Common",
        locations=["ocean"],
        tools={"fishing-rod": {"min": 1, "max": 2}},
        full_day=True,
    )
    dc = MagicMock()
    dc.fish_by_id = {"bass": bass}
    dc.tool_by_id = {"fishing-rod": rod}
    dc.location_by_id = {"ocean": ocean}
    dc.bait_by_id = {}
    dc.get_fish = lambda name: bass if name.lower() == "bass" else None
    return dc


def _make_bot(dc):
    bot = MagicMock()
    bot.dank_client = dc
    bot.db = None
    bot.autocomplete = MagicMock()
    bot.autocomplete.fish_choices = MagicMock(return_value=[])
    return bot


@pytest.mark.asyncio
async def test_optimizer_cached_result_sends_embed():
    """With a pre-populated cache the optimizer returns instantly via send_message."""
    from cogs.intelligence import IntelligenceCog, _opt_cache
    dc = _make_dc()
    bot = _make_bot(dc)
    cog = IntelligenceCog(bot)
    bass = dc.fish_by_id["bass"]

    # Pre-populate cache so the command takes the fast (non-defer) path
    hour = 0
    cache_key = (bass.id, hour)
    _opt_cache[cache_key] = [
        {"tool": dc.tool_by_id["fishing-rod"], "bait": None, "loc_id": "ocean",
         "timely": False, "chance": 25.0}
    ]

    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 111

    import cogs.intelligence as _m
    orig = _m._utc_hour
    _m._utc_hour = lambda: hour
    try:
        await cog.optimizer.callback(cog, interaction, target="Bass")
    finally:
        _m._utc_hour = orig
        del _opt_cache[cache_key]

    interaction.response.send_message.assert_called_once()
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert "Bass" in embed.title


@pytest.mark.asyncio
async def test_optimizer_with_target_mentions_fish():
    """Optimizer with an uncached target defers and calls followup."""
    from cogs.intelligence import IntelligenceCog, _opt_cache
    dc = _make_dc()
    bot = _make_bot(dc)
    cog = IntelligenceCog(bot)
    bass = dc.fish_by_id["bass"]

    # Ensure cache is empty for this test
    hour = 1
    _opt_cache.pop((bass.id, hour), None)

    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.user.id = 111

    import cogs.intelligence as _m
    orig_hour = _m._utc_hour
    orig_run = _m._run_fish_optimizer
    _m._utc_hour = lambda: hour
    _m._run_fish_optimizer = AsyncMock(return_value=[
        {"tool": dc.tool_by_id["fishing-rod"], "bait": None, "loc_id": "ocean",
         "timely": False, "chance": 22.0}
    ])
    try:
        await cog.optimizer.callback(cog, interaction, target="Bass")
    finally:
        _m._utc_hour = orig_hour
        _m._run_fish_optimizer = orig_run
        _opt_cache.pop((bass.id, hour), None)

    interaction.response.defer.assert_called_once()
    interaction.edit_original_response.assert_called_once()
    embed = interaction.edit_original_response.call_args.kwargs["embed"]
    assert "Bass" in embed.title


@pytest.mark.asyncio
async def test_optimizer_target_not_found_returns_error():
    from cogs.intelligence import IntelligenceCog
    dc = _make_dc()
    bot = _make_bot(dc)
    cog = IntelligenceCog(bot)
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 111
    await cog.optimizer.callback(cog, interaction, target="UnknownFish")
    call_kwargs = interaction.response.send_message.call_args.kwargs
    assert call_kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_planner_embed_shows_session_structure():
    from cogs.intelligence import IntelligenceCog
    dc = _make_dc()
    bot = _make_bot(dc)
    cog = IntelligenceCog(bot)
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 111
    await cog.planner.callback(cog, interaction, location="Ocean", hours=3)
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert "Session Plan" in embed.title
    field_names = [f.name for f in embed.fields]
    assert any("Catchable" in n for n in field_names)
    assert any("setup" in n.lower() for n in field_names)


@pytest.mark.asyncio
async def test_planner_no_fish_returns_message():
    from cogs.intelligence import IntelligenceCog
    rod = make_tool(id="fishing-rod", name="Fishing Rod")
    ocean = make_location(id="ocean", name="Ocean")
    bass = make_creature(
        id="bass", name="Bass", rarity="Common",
        locations=["lake"],   # NOT ocean — nothing eligible at ocean
        tools={"fishing-rod": {"min": 1, "max": 2}},
        full_day=True,
    )
    dc = MagicMock()
    dc.fish_by_id = {"bass": bass}
    dc.tool_by_id = {"fishing-rod": rod}
    dc.location_by_id = {"ocean": ocean}
    dc.bait_by_id = {}
    dc.get_fish = lambda name: None
    bot = MagicMock()
    bot.dank_client = dc
    bot.db = None
    bot.autocomplete = None
    cog = IntelligenceCog(bot)
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 111
    await cog.planner.callback(cog, interaction, location="Ocean", hours=3)
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert "No fish" in (embed.description or "")
