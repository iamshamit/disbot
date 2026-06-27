"""Tests for cogs/tools.py — ToolsCog, ToolView."""
from __future__ import annotations

import pytest
import discord
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import make_tool

_SENTINEL = object()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_dank_client(tools=_SENTINEL):
    """Build a lightweight stand-in for DankMemerGameClient."""
    if tools is _SENTINEL:
        tools = [make_tool()]
    client = MagicMock()
    client.tool_by_id = {t.id: t for t in tools}
    client.tool_by_name = {t.name.lower(): t for t in tools}

    def get_tool(query):
        if query in client.tool_by_id:
            return client.tool_by_id[query]
        return client.tool_by_name.get(query.lower())

    client.get_tool = get_tool
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
# ToolsCog._guard
# ---------------------------------------------------------------------------

def test_guard_true_when_data_loaded():
    from cogs.tools import ToolsCog
    bot = make_mock_bot()
    cog = ToolsCog(bot)
    assert cog._guard() is True


def test_guard_false_when_no_dank_client():
    from cogs.tools import ToolsCog
    bot = make_mock_bot(dank_client=None)
    cog = ToolsCog(bot)
    assert cog._guard() is False


def test_guard_false_when_tool_by_id_empty():
    from cogs.tools import ToolsCog
    client = make_mock_dank_client(tools=[])
    bot = make_mock_bot(dank_client=client)
    cog = ToolsCog(bot)
    assert cog._guard() is False


# ---------------------------------------------------------------------------
# ToolsCog.tool command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_command_not_loaded_returns_error():
    from cogs.tools import ToolsCog
    bot = make_mock_bot(dank_client=None)
    cog = ToolsCog(bot)
    interaction = make_interaction()
    await cog.tool.callback(cog, interaction, name="Harpoon")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_tool_command_not_found_returns_error():
    from cogs.tools import ToolsCog
    bot = make_mock_bot()
    cog = ToolsCog(bot)
    interaction = make_interaction()
    await cog.tool.callback(cog, interaction, name="NonExistentTool999")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True
    embed = call_kwargs.kwargs["embed"]
    assert "NonExistentTool999" in embed.description or "NonExistentTool999" in (embed.title or "")


@pytest.mark.asyncio
async def test_tool_command_found_sends_embed_and_view():
    from cogs.tools import ToolsCog, ToolView
    bot = make_mock_bot()
    cog = ToolsCog(bot)
    interaction = make_interaction()
    await cog.tool.callback(cog, interaction, name="Fishing Rod")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert "embed" in call_kwargs.kwargs
    assert "view" in call_kwargs.kwargs
    assert isinstance(call_kwargs.kwargs["view"], ToolView)


@pytest.mark.asyncio
async def test_tool_command_stores_message_on_view():
    from cogs.tools import ToolsCog, ToolView
    bot = make_mock_bot()
    cog = ToolsCog(bot)
    interaction = make_interaction()
    mock_msg = MagicMock()
    interaction.original_response = AsyncMock(return_value=mock_msg)
    await cog.tool.callback(cog, interaction, name="Fishing Rod")
    call_kwargs = interaction.response.send_message.call_args
    view = call_kwargs.kwargs["view"]
    assert view.message is mock_msg


@pytest.mark.asyncio
async def test_tool_command_found_by_id():
    from cogs.tools import ToolsCog, ToolView
    bot = make_mock_bot()
    cog = ToolsCog(bot)
    interaction = make_interaction()
    # "rod" is the default tool id from make_tool()
    await cog.tool.callback(cog, interaction, name="rod")
    call_kwargs = interaction.response.send_message.call_args
    assert isinstance(call_kwargs.kwargs["view"], ToolView)


# ---------------------------------------------------------------------------
# ToolView
# ---------------------------------------------------------------------------

def test_toolview_timeout_is_300():
    from cogs.tools import ToolView
    tool = make_tool()
    dc = make_mock_dank_client()
    view = ToolView(tool, dc)
    assert view.timeout == 300


def test_toolview_has_expected_buttons():
    from cogs.tools import ToolView
    tool = make_tool()
    dc = make_mock_dank_client()
    view = ToolView(tool, dc)
    labels = [item.label for item in view.children if isinstance(item, discord.ui.Button)]
    assert any("Delete" in l for l in labels)
    assert any("Simulate" in l for l in labels)


def test_toolview_simulate_btn_is_disabled():
    from cogs.tools import ToolView
    tool = make_tool()
    dc = make_mock_dank_client()
    view = ToolView(tool, dc)
    sim_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Simulate" in item.label
    )
    assert sim_btn.disabled is True


def test_toolview_message_initially_none():
    from cogs.tools import ToolView
    tool = make_tool()
    dc = make_mock_dank_client()
    view = ToolView(tool, dc)
    assert view.message is None


@pytest.mark.asyncio
async def test_toolview_on_timeout_disables_all_items():
    from cogs.tools import ToolView
    tool = make_tool()
    dc = make_mock_dank_client()
    view = ToolView(tool, dc)
    view.message = None
    await view.on_timeout()
    for item in view.children:
        assert item.disabled is True


@pytest.mark.asyncio
async def test_toolview_on_timeout_edits_message():
    from cogs.tools import ToolView
    tool = make_tool()
    dc = make_mock_dank_client()
    view = ToolView(tool, dc)
    mock_msg = AsyncMock()
    view.message = mock_msg
    await view.on_timeout()
    mock_msg.edit.assert_called_once_with(view=view)


@pytest.mark.asyncio
async def test_toolview_on_timeout_no_message_no_error():
    from cogs.tools import ToolView
    tool = make_tool()
    dc = make_mock_dank_client()
    view = ToolView(tool, dc)
    view.message = None
    # Should not raise
    await view.on_timeout()


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_toolview_delete_btn_deletes_message():
    from cogs.tools import ToolView
    tool = make_tool()
    dc = make_mock_dank_client()
    view = ToolView(tool, dc)
    interaction = make_interaction()
    interaction.message = AsyncMock()
    interaction.message.delete = AsyncMock()
    await view.delete_btn.callback(interaction)
    interaction.message.delete.assert_called_once()


# ---------------------------------------------------------------------------
