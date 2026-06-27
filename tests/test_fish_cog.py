"""Tests for cogs/fish.py — FishCog, FishView, FishListView."""
from __future__ import annotations

import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import make_creature, make_location

_SENTINEL = object()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_dank_client(creatures=_SENTINEL, locations=_SENTINEL):
    """Build a lightweight stand-in for DankMemerGameClient.
    Pass creatures=[] to simulate empty (unloaded) state.
    """
    if creatures is _SENTINEL:
        creatures = [make_creature()]
    if locations is _SENTINEL:
        locations = [make_location()]
    client = MagicMock()
    client.fish_by_id = {c.id: c for c in creatures}
    client.fish_by_name = {c.name.lower(): c for c in creatures}
    client.location_by_id = {loc.id: loc for loc in locations}

    def get_fish(query):
        if query in client.fish_by_id:
            return client.fish_by_id[query]
        return client.fish_by_name.get(query.lower())

    client.get_fish = get_fish
    return client


def make_mock_bot(dank_client=_SENTINEL, autocomplete=None):
    """Build a lightweight bot mock. Pass dank_client=None to simulate no client loaded."""
    bot = MagicMock()
    bot.dank_client = make_mock_dank_client() if dank_client is _SENTINEL else dank_client
    bot.autocomplete = autocomplete
    return bot


def make_interaction():
    interaction = MagicMock()
    interaction.response = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.original_response = AsyncMock(return_value=MagicMock())
    return interaction


# ---------------------------------------------------------------------------
# FishCog._guard
# ---------------------------------------------------------------------------

def test_guard_true_when_data_loaded():
    from cogs.fish import FishCog
    bot = make_mock_bot()
    cog = FishCog(bot)
    assert cog._guard() is True


def test_guard_false_when_no_dank_client():
    from cogs.fish import FishCog
    bot = make_mock_bot(dank_client=None)
    cog = FishCog(bot)
    assert cog._guard() is False


def test_guard_false_when_fish_by_id_empty():
    from cogs.fish import FishCog
    client = make_mock_dank_client(creatures=[])
    bot = make_mock_bot(dank_client=client)
    cog = FishCog(bot)
    assert cog._guard() is False


# ---------------------------------------------------------------------------
# FishCog.fish command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fish_command_not_loaded_returns_error():
    from cogs.fish import FishCog
    bot = make_mock_bot(dank_client=None)
    cog = FishCog(bot)
    interaction = make_interaction()
    await cog.fish.callback(cog, interaction, name="Goldfish")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_fish_command_not_found_returns_error():
    from cogs.fish import FishCog
    bot = make_mock_bot()
    cog = FishCog(bot)
    interaction = make_interaction()
    await cog.fish.callback(cog, interaction, name="NonExistentFish999")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True
    embed = call_kwargs.kwargs["embed"]
    assert "NonExistentFish999" in embed.description or "NonExistentFish999" in (embed.title or "")


@pytest.mark.asyncio
async def test_fish_command_found_sends_embed_and_view():
    from cogs.fish import FishCog, FishView
    bot = make_mock_bot()
    cog = FishCog(bot)
    interaction = make_interaction()
    await cog.fish.callback(cog, interaction, name="Goldfish")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert "embed" in call_kwargs.kwargs
    assert "view" in call_kwargs.kwargs
    assert isinstance(call_kwargs.kwargs["view"], FishView)


@pytest.mark.asyncio
async def test_fish_command_stores_message_on_view():
    from cogs.fish import FishCog, FishView
    bot = make_mock_bot()
    cog = FishCog(bot)
    interaction = make_interaction()
    mock_msg = MagicMock()
    interaction.original_response = AsyncMock(return_value=mock_msg)
    await cog.fish.callback(cog, interaction, name="Goldfish")
    call_kwargs = interaction.response.send_message.call_args
    view = call_kwargs.kwargs["view"]
    assert view.message is mock_msg


# ---------------------------------------------------------------------------
# FishCog.fishlist command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fishlist_not_loaded_returns_error():
    from cogs.fish import FishCog
    bot = make_mock_bot(dank_client=None)
    cog = FishCog(bot)
    interaction = make_interaction()
    await cog.fishlist.callback(cog, interaction)
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_fishlist_sends_embed_and_view():
    from cogs.fish import FishCog, FishListView
    bot = make_mock_bot()
    cog = FishCog(bot)
    interaction = make_interaction()
    await cog.fishlist.callback(cog, interaction)
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert "embed" in call_kwargs.kwargs
    assert isinstance(call_kwargs.kwargs["view"], FishListView)


# ---------------------------------------------------------------------------
# FishView
# ---------------------------------------------------------------------------

def test_fishview_variants_btn_disabled_when_no_variants():
    from cogs.fish import FishView
    creature = make_creature(variants=[])
    dc = make_mock_dank_client()
    view = FishView(creature, dc)
    variants_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Variants" in item.label
    )
    assert variants_btn.disabled is True


def test_fishview_variants_btn_enabled_when_variants_exist():
    from cogs.fish import FishView
    creature = make_creature(variants=[{"name": "Chroma", "chance": 2}])
    dc = make_mock_dank_client()
    view = FishView(creature, dc)
    variants_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Variants" in item.label
    )
    assert variants_btn.disabled is False


def test_fishview_has_expected_buttons():
    from cogs.fish import FishView
    creature = make_creature()
    dc = make_mock_dank_client()
    view = FishView(creature, dc)
    labels = [item.label for item in view.children if isinstance(item, discord.ui.Button)]
    assert any("Peak Hours" in l for l in labels)
    assert any("Delete" in l for l in labels)
    assert any("Locations" in l for l in labels)


def test_fishview_timeout_is_300():
    from cogs.fish import FishView
    creature = make_creature()
    dc = make_mock_dank_client()
    view = FishView(creature, dc)
    assert view.timeout == 300


@pytest.mark.asyncio
async def test_fishview_on_timeout_disables_all_items():
    from cogs.fish import FishView
    creature = make_creature()
    dc = make_mock_dank_client()
    view = FishView(creature, dc)
    view.message = None
    await view.on_timeout()
    for item in view.children:
        assert item.disabled is True


@pytest.mark.asyncio
async def test_fishview_on_timeout_edits_message():
    from cogs.fish import FishView
    creature = make_creature()
    dc = make_mock_dank_client()
    view = FishView(creature, dc)
    mock_msg = AsyncMock()
    view.message = mock_msg
    await view.on_timeout()
    mock_msg.edit.assert_called_once_with(view=view)


@pytest.mark.asyncio
async def test_fishview_peak_btn_edits_with_peak_embed():
    from cogs.fish import FishView
    creature = make_creature()
    dc = make_mock_dank_client()
    view = FishView(creature, dc)
    interaction = make_interaction()
    await view.peak_btn.callback(interaction)
    interaction.response.edit_message.assert_called_once()
    call_kwargs = interaction.response.edit_message.call_args
    embed = call_kwargs.kwargs["embed"]
    assert "Peak Hours" in embed.title


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_fishview_locations_btn_shows_location_detail():
    from cogs.fish import FishView
    creature = make_creature(locations=["sunken_ship"])
    location = make_location(id="sunken_ship", name="Sunken Ship", failChance=15)
    dc = make_mock_dank_client(creatures=[creature], locations=[location])
    view = FishView(creature, dc)
    interaction = make_interaction()
    await view.locations_btn.callback(interaction)
    interaction.response.edit_message.assert_called_once()
    call_kwargs = interaction.response.edit_message.call_args
    embed = call_kwargs.kwargs["embed"]
    assert "LOCATION DETAILS" in embed.description
    assert "Sunken Ship" in embed.description


@pytest.mark.asyncio
async def test_fishview_variants_btn_shows_variants_detail():
    from cogs.fish import FishView
    creature = make_creature(variants=[{"name": "Chroma", "chance": 2}])
    dc = make_mock_dank_client(creatures=[creature])
    view = FishView(creature, dc)
    interaction = make_interaction()
    await view.variants_btn.callback(interaction)
    interaction.response.edit_message.assert_called_once()
    call_kwargs = interaction.response.edit_message.call_args
    embed = call_kwargs.kwargs["embed"]
    assert "VARIANTS DETAIL" in embed.description
    assert "Chroma" in embed.description


@pytest.mark.asyncio
async def test_fishview_delete_btn_deletes_message():
    from cogs.fish import FishView
    creature = make_creature()
    dc = make_mock_dank_client()
    view = FishView(creature, dc)
    interaction = make_interaction()
    interaction.message = AsyncMock()
    interaction.message.delete = AsyncMock()
    await view.delete_btn.callback(interaction)
    interaction.message.delete.assert_called_once()


# ---------------------------------------------------------------------------
# BackToFishView
# ---------------------------------------------------------------------------

def test_backtofishview_has_back_button():
    from cogs.fish import BackToFishView
    creature = make_creature()
    dc = make_mock_dank_client()
    view = BackToFishView(creature, dc)
    labels = [item.label for item in view.children if isinstance(item, discord.ui.Button)]
    assert any("Back" in l for l in labels)


@pytest.mark.asyncio
async def test_backtofishview_back_btn_returns_to_fish_view():
    from cogs.fish import BackToFishView, FishView
    creature = make_creature()
    dc = make_mock_dank_client()
    view = BackToFishView(creature, dc)
    interaction = make_interaction()
    await view.back_btn.callback(interaction)
    interaction.response.edit_message.assert_called_once()
    call_kwargs = interaction.response.edit_message.call_args
    assert isinstance(call_kwargs.kwargs["view"], FishView)


# ---------------------------------------------------------------------------
