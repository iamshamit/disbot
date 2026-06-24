from __future__ import annotations
import pytest
from unittest.mock import MagicMock, AsyncMock
from tests.conftest import make_creature, make_tool, make_location


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
async def test_optimizer_no_target_embed_has_best_setup():
    from cogs.intelligence import IntelligenceCog
    dc = _make_dc()
    bot = _make_bot(dc)
    cog = IntelligenceCog(bot)
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 111
    await cog.optimizer.callback(cog, interaction, target=None)
    interaction.response.send_message.assert_called_once()
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert "Best Setup" in embed.title


@pytest.mark.asyncio
async def test_optimizer_with_target_mentions_fish():
    from cogs.intelligence import IntelligenceCog
    dc = _make_dc()
    bot = _make_bot(dc)
    cog = IntelligenceCog(bot)
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.user.id = 111
    await cog.optimizer.callback(cog, interaction, target="Bass")
    embed = interaction.response.send_message.call_args.kwargs["embed"]
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
