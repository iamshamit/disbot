"""Tests for cogs/baits.py — BaitsCog, BaitView."""
from __future__ import annotations

import pytest
import discord
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import make_bait

_SENTINEL = object()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_dank_client(baits=_SENTINEL):
    """Build a lightweight stand-in for DankMemerGameClient."""
    if baits is _SENTINEL:
        baits = [make_bait()]
    client = MagicMock()
    client.bait_by_id = {b.id: b for b in baits}
    client.bait_by_name = {b.name.lower(): b for b in baits}

    def get_bait(query):
        if query in client.bait_by_id:
            return client.bait_by_id[query]
        return client.bait_by_name.get(query.lower())

    client.get_bait = get_bait
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
# BaitsCog._guard
# ---------------------------------------------------------------------------

def test_guard_true_when_data_loaded():
    from cogs.baits import BaitsCog
    bot = make_mock_bot()
    cog = BaitsCog(bot)
    assert cog._guard() is True


def test_guard_false_when_no_dank_client():
    from cogs.baits import BaitsCog
    bot = make_mock_bot(dank_client=None)
    cog = BaitsCog(bot)
    assert cog._guard() is False


def test_guard_false_when_bait_by_id_empty():
    from cogs.baits import BaitsCog
    client = make_mock_dank_client(baits=[])
    bot = make_mock_bot(dank_client=client)
    cog = BaitsCog(bot)
    assert cog._guard() is False


# ---------------------------------------------------------------------------
# BaitsCog.bait command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bait_command_not_loaded_returns_error():
    from cogs.baits import BaitsCog
    bot = make_mock_bot(dank_client=None)
    cog = BaitsCog(bot)
    interaction = make_interaction()
    await cog.bait.callback(cog, interaction, name="Glitter Bait")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_bait_command_not_found_returns_error():
    from cogs.baits import BaitsCog
    bot = make_mock_bot()
    cog = BaitsCog(bot)
    interaction = make_interaction()
    await cog.bait.callback(cog, interaction, name="NonExistentBait999")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True
    embed = call_kwargs.kwargs["embed"]
    assert "NonExistentBait999" in embed.description or "NonExistentBait999" in (embed.title or "")


@pytest.mark.asyncio
async def test_bait_command_found_sends_embed_and_view():
    from cogs.baits import BaitsCog, BaitView
    bot = make_mock_bot()
    cog = BaitsCog(bot)
    interaction = make_interaction()
    await cog.bait.callback(cog, interaction, name="Glitter Bait")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert "embed" in call_kwargs.kwargs
    assert "view" in call_kwargs.kwargs
    assert isinstance(call_kwargs.kwargs["view"], BaitView)


@pytest.mark.asyncio
async def test_bait_command_stores_message_on_view():
    from cogs.baits import BaitsCog, BaitView
    bot = make_mock_bot()
    cog = BaitsCog(bot)
    interaction = make_interaction()
    mock_msg = MagicMock()
    interaction.original_response = AsyncMock(return_value=mock_msg)
    await cog.bait.callback(cog, interaction, name="Glitter Bait")
    call_kwargs = interaction.response.send_message.call_args
    view = call_kwargs.kwargs["view"]
    assert view.message is mock_msg


@pytest.mark.asyncio
async def test_bait_command_found_by_id():
    from cogs.baits import BaitsCog, BaitView
    bot = make_mock_bot()
    cog = BaitsCog(bot)
    interaction = make_interaction()
    # "glitter" is the default bait id from make_bait()
    await cog.bait.callback(cog, interaction, name="glitter")
    call_kwargs = interaction.response.send_message.call_args
    assert isinstance(call_kwargs.kwargs["view"], BaitView)


# ---------------------------------------------------------------------------
# BaitsCog autocomplete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bait_autocomplete_returns_empty_when_no_autocomplete():
    from cogs.baits import BaitsCog
    bot = make_mock_bot(autocomplete=None)
    cog = BaitsCog(bot)
    interaction = make_interaction()
    result = await cog.bait_autocomplete(interaction, "Glitter")
    assert result == []


@pytest.mark.asyncio
async def test_bait_autocomplete_delegates_to_autocomplete_index():
    from cogs.baits import BaitsCog
    mock_ac = MagicMock()
    expected = discord.app_commands.Choice(name="Glitter Bait", value="Glitter Bait")
    mock_ac.bait_choices = MagicMock(return_value=[expected])
    bot = make_mock_bot(autocomplete=mock_ac)
    cog = BaitsCog(bot)
    interaction = make_interaction()
    result = await cog.bait_autocomplete(interaction, "Glitter")
    mock_ac.bait_choices.assert_called_once_with("Glitter")
    assert result == [expected]


@pytest.mark.asyncio
@pytest.mark.asyncio
# ---------------------------------------------------------------------------
# BaitView
# ---------------------------------------------------------------------------

def test_baitview_timeout_is_300():
    from cogs.baits import BaitView
    bait = make_bait()
    dc = make_mock_dank_client()
    view = BaitView(bait, dc)
    assert view.timeout == 300


def test_baitview_has_expected_buttons():
    from cogs.baits import BaitView
    bait = make_bait()
    dc = make_mock_dank_client()
    view = BaitView(bait, dc)
    labels = [item.label for item in view.children if isinstance(item, discord.ui.Button)]
    assert any("Delete" in l for l in labels)
    assert any("Simulate" in l for l in labels)


def test_baitview_simulate_btn_is_disabled():
    from cogs.baits import BaitView
    bait = make_bait()
    dc = make_mock_dank_client()
    view = BaitView(bait, dc)
    sim_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Simulate" in item.label
    )
    assert sim_btn.disabled is True


def test_baitview_message_initially_none():
    from cogs.baits import BaitView
    bait = make_bait()
    dc = make_mock_dank_client()
    view = BaitView(bait, dc)
    assert view.message is None


@pytest.mark.asyncio
async def test_baitview_on_timeout_disables_all_items():
    from cogs.baits import BaitView
    bait = make_bait()
    dc = make_mock_dank_client()
    view = BaitView(bait, dc)
    view.message = None
    await view.on_timeout()
    for item in view.children:
        assert item.disabled is True


@pytest.mark.asyncio
async def test_baitview_on_timeout_edits_message():
    from cogs.baits import BaitView
    bait = make_bait()
    dc = make_mock_dank_client()
    view = BaitView(bait, dc)
    mock_msg = AsyncMock()
    view.message = mock_msg
    await view.on_timeout()
    mock_msg.edit.assert_called_once_with(view=view)


@pytest.mark.asyncio
async def test_baitview_on_timeout_no_message_no_error():
    from cogs.baits import BaitView
    bait = make_bait()
    dc = make_mock_dank_client()
    view = BaitView(bait, dc)
    view.message = None
    # Should not raise
    await view.on_timeout()


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_baitview_delete_btn_deletes_message():
    from cogs.baits import BaitView
    bait = make_bait()
    dc = make_mock_dank_client()
    view = BaitView(bait, dc)
    interaction = make_interaction()
    interaction.message = AsyncMock()
    interaction.message.delete = AsyncMock()
    await view.delete_btn.callback(interaction)
    interaction.message.delete.assert_called_once()


# ---------------------------------------------------------------------------
