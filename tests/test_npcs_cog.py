"""Tests for cogs/npcs.py — NpcsCog."""
from __future__ import annotations

import pytest
import discord
from unittest.mock import AsyncMock, MagicMock

from dankmemer.routes.npcs import NPC
from dankmemer.utils import DotDict

_SENTINEL = object()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_npc(
    id="bob",
    name="Bob the Fisherman",
    imageURL="https://example.com/bob.png",
    description="A weathered fisherman.",
    locations=None,
):
    extra = DotDict({
        "description": description,
        "locations": locations or ["Sunken Ship"],
    })
    return NPC(id=id, name=name, imageURL=imageURL, extra=extra)


def make_mock_dank_client(npcs=_SENTINEL):
    """Build a lightweight stand-in for DankMemerGameClient."""
    if npcs is _SENTINEL:
        npcs = [make_npc()]
    client = MagicMock()
    client.npc_by_id = {n.id: n for n in npcs}
    client.npc_by_name = {n.name.lower(): n for n in npcs}

    def get_npc(query):
        if query in client.npc_by_id:
            return client.npc_by_id[query]
        return client.npc_by_name.get(query.lower())

    client.get_npc = get_npc
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
# NpcsCog._guard
# ---------------------------------------------------------------------------

def test_guard_true_when_data_loaded():
    from cogs.npcs import NpcsCog
    bot = make_mock_bot()
    cog = NpcsCog(bot)
    assert cog._guard() is True


def test_guard_false_when_no_dank_client():
    from cogs.npcs import NpcsCog
    bot = make_mock_bot(dank_client=None)
    cog = NpcsCog(bot)
    assert cog._guard() is False


def test_guard_false_when_npc_by_id_empty():
    from cogs.npcs import NpcsCog
    client = make_mock_dank_client(npcs=[])
    bot = make_mock_bot(dank_client=client)
    cog = NpcsCog(bot)
    assert cog._guard() is False


# ---------------------------------------------------------------------------
# NpcsCog.npc command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_npc_command_not_loaded_returns_error():
    from cogs.npcs import NpcsCog
    bot = make_mock_bot(dank_client=None)
    cog = NpcsCog(bot)
    interaction = make_interaction()
    await cog.npc.callback(cog, interaction, name="Bob the Fisherman")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_npc_command_not_found_returns_error():
    from cogs.npcs import NpcsCog
    bot = make_mock_bot()
    cog = NpcsCog(bot)
    interaction = make_interaction()
    await cog.npc.callback(cog, interaction, name="NonExistentNPC999")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True
    embed = call_kwargs.kwargs["embed"]
    assert "NonExistentNPC999" in (embed.description or "") or "NonExistentNPC999" in (embed.title or "")


@pytest.mark.asyncio
async def test_npc_command_found_sends_embed():
    from cogs.npcs import NpcsCog
    bot = make_mock_bot()
    cog = NpcsCog(bot)
    interaction = make_interaction()
    await cog.npc.callback(cog, interaction, name="Bob the Fisherman")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert "embed" in call_kwargs.kwargs
    embed = call_kwargs.kwargs["embed"]
    assert isinstance(embed, discord.Embed)


@pytest.mark.asyncio
async def test_npc_command_found_embed_title_is_npc_name():
    from cogs.npcs import NpcsCog
    bot = make_mock_bot()
    cog = NpcsCog(bot)
    interaction = make_interaction()
    await cog.npc.callback(cog, interaction, name="Bob the Fisherman")
    call_kwargs = interaction.response.send_message.call_args
    embed = call_kwargs.kwargs["embed"]
    assert embed.title == "Bob the Fisherman"


@pytest.mark.asyncio
async def test_npc_command_found_by_id():
    from cogs.npcs import NpcsCog
    bot = make_mock_bot()
    cog = NpcsCog(bot)
    interaction = make_interaction()
    # "bob" is the default npc id from make_npc()
    await cog.npc.callback(cog, interaction, name="bob")
    call_kwargs = interaction.response.send_message.call_args
    assert "embed" in call_kwargs.kwargs


@pytest.mark.asyncio
async def test_npc_command_no_view_sent():
    """NpcsCog sends no view (unlike BaitsCog or ToolsCog)."""
    from cogs.npcs import NpcsCog
    bot = make_mock_bot()
    cog = NpcsCog(bot)
    interaction = make_interaction()
    await cog.npc.callback(cog, interaction, name="Bob the Fisherman")
    call_kwargs = interaction.response.send_message.call_args
    assert "view" not in call_kwargs.kwargs


# ---------------------------------------------------------------------------
# NpcsCog autocomplete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_npc_autocomplete_returns_empty_when_no_autocomplete():
    from cogs.npcs import NpcsCog
    bot = make_mock_bot(autocomplete=None)
    cog = NpcsCog(bot)
    interaction = make_interaction()
    result = await cog.npc_autocomplete(interaction, "Bob")
    assert result == []


@pytest.mark.asyncio
async def test_npc_autocomplete_delegates_to_autocomplete_index():
    from cogs.npcs import NpcsCog
    mock_ac = MagicMock()
    expected = discord.app_commands.Choice(name="Bob the Fisherman", value="Bob the Fisherman")
    mock_ac.npc_choices = MagicMock(return_value=[expected])
    bot = make_mock_bot(autocomplete=mock_ac)
    cog = NpcsCog(bot)
    interaction = make_interaction()
    result = await cog.npc_autocomplete(interaction, "Bob")
    mock_ac.npc_choices.assert_called_once_with("Bob")
    assert result == [expected]


# ---------------------------------------------------------------------------
# setup()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_setup_adds_cog():
    from cogs.npcs import setup, NpcsCog
    bot = AsyncMock()
    bot.add_cog = AsyncMock()
    await setup(bot)
    bot.add_cog.assert_called_once()
    cog_arg = bot.add_cog.call_args.args[0]
    assert isinstance(cog_arg, NpcsCog)
