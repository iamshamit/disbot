"""Tests for cogs/tools.py — ToolsCog, ToolView, ToolCompareModal."""
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
# ToolsCog.toolcompare command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_toolcompare_not_loaded_returns_error():
    from cogs.tools import ToolsCog
    bot = make_mock_bot(dank_client=None)
    cog = ToolsCog(bot)
    interaction = make_interaction()
    await cog.toolcompare.callback(cog, interaction)
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_toolcompare_sends_embed_with_all_tools():
    from cogs.tools import ToolsCog
    tools = [
        make_tool(id="rod", name="Fishing Rod"),
        make_tool(id="harpoon", name="Harpoon", buffs=[{"name": "+30% Rare"}]),
    ]
    client = make_mock_dank_client(tools=tools)
    bot = make_mock_bot(dank_client=client)
    cog = ToolsCog(bot)
    interaction = make_interaction()
    await cog.toolcompare.callback(cog, interaction)
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert "embed" in call_kwargs.kwargs
    embed = call_kwargs.kwargs["embed"]
    # Both tool names should appear in the comparison table
    assert "Fishing Rod" in embed.description
    assert "Harpoon" in embed.description


@pytest.mark.asyncio
async def test_toolcompare_single_tool():
    from cogs.tools import ToolsCog
    bot = make_mock_bot()
    cog = ToolsCog(bot)
    interaction = make_interaction()
    await cog.toolcompare.callback(cog, interaction)
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    embed = call_kwargs.kwargs["embed"]
    assert isinstance(embed, discord.Embed)


# ---------------------------------------------------------------------------
# ToolsCog autocomplete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_autocomplete_returns_empty_when_no_autocomplete():
    from cogs.tools import ToolsCog
    bot = make_mock_bot(autocomplete=None)
    cog = ToolsCog(bot)
    interaction = make_interaction()
    result = await cog.tool_autocomplete(interaction, "Rod")
    assert result == []


@pytest.mark.asyncio
async def test_tool_autocomplete_delegates_to_autocomplete_index():
    from cogs.tools import ToolsCog
    mock_ac = MagicMock()
    expected = discord.app_commands.Choice(name="Fishing Rod", value="Fishing Rod")
    mock_ac.tool_choices = MagicMock(return_value=[expected])
    bot = make_mock_bot(autocomplete=mock_ac)
    cog = ToolsCog(bot)
    interaction = make_interaction()
    result = await cog.tool_autocomplete(interaction, "Rod")
    mock_ac.tool_choices.assert_called_once_with("Rod")
    assert result == [expected]


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
    assert any("Compare" in l for l in labels)
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
async def test_toolview_compare_btn_sends_modal():
    from cogs.tools import ToolView, ToolCompareModal
    tool = make_tool()
    dc = make_mock_dank_client()
    view = ToolView(tool, dc)
    interaction = make_interaction()
    await view.compare_btn.callback(interaction)
    interaction.response.send_modal.assert_called_once()
    modal_arg = interaction.response.send_modal.call_args.args[0]
    assert isinstance(modal_arg, ToolCompareModal)


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
# ToolCompareModal
# ---------------------------------------------------------------------------

def test_toolcomparemodal_stores_first_and_client():
    from cogs.tools import ToolCompareModal
    tool = make_tool()
    dc = make_mock_dank_client()
    modal = ToolCompareModal(tool, dc)
    assert modal.first is tool
    assert modal.dc is dc


@pytest.mark.asyncio
async def test_toolcomparemodal_on_submit_not_found_sends_ephemeral():
    from cogs.tools import ToolCompareModal
    tool = make_tool()
    dc = make_mock_dank_client()
    modal = ToolCompareModal(tool, dc)
    modal.second_tool._value = "NonExistentTool"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_toolcomparemodal_on_submit_not_found_embed_contains_name():
    from cogs.tools import ToolCompareModal
    tool = make_tool()
    dc = make_mock_dank_client()
    modal = ToolCompareModal(tool, dc)
    modal.second_tool._value = "GhostTool"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert "GhostTool" in (embed.description or "") or "GhostTool" in (embed.title or "")


@pytest.mark.asyncio
async def test_toolcomparemodal_on_submit_found_edits_message():
    from cogs.tools import ToolCompareModal
    t1 = make_tool(id="rod", name="Fishing Rod")
    t2 = make_tool(id="harpoon", name="Harpoon", buffs=[{"name": "+30% Rare"}])
    dc = make_mock_dank_client(tools=[t1, t2])
    modal = ToolCompareModal(t1, dc)
    modal.second_tool._value = "Harpoon"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    interaction.response.edit_message.assert_called_once()
    call_kwargs = interaction.response.edit_message.call_args
    # view=None per brief spec
    assert call_kwargs.kwargs.get("view") is None
    embed = call_kwargs.kwargs["embed"]
    assert "Fishing Rod" in embed.description
    assert "Harpoon" in embed.description


@pytest.mark.asyncio
async def test_toolcomparemodal_on_submit_strips_whitespace():
    from cogs.tools import ToolCompareModal
    t1 = make_tool(id="rod", name="Fishing Rod")
    t2 = make_tool(id="harpoon", name="Harpoon")
    dc = make_mock_dank_client(tools=[t1, t2])
    modal = ToolCompareModal(t1, dc)
    modal.second_tool._value = "  Harpoon  "
    interaction = make_interaction()
    await modal.on_submit(interaction)
    # Should resolve to "Harpoon" after strip — edit_message called (found)
    interaction.response.edit_message.assert_called_once()


# ---------------------------------------------------------------------------
# setup()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_setup_adds_cog():
    from cogs.tools import setup, ToolsCog
    bot = AsyncMock()
    bot.add_cog = AsyncMock()
    await setup(bot)
    bot.add_cog.assert_called_once()
    cog_arg = bot.add_cog.call_args.args[0]
    assert isinstance(cog_arg, ToolsCog)


# ---------------------------------------------------------------------------
# ToolView — Favourite button
# ---------------------------------------------------------------------------

def test_toolview_fav_btn_disabled_when_no_db():
    from cogs.tools import ToolView
    tool = make_tool()
    dc = make_mock_dank_client()
    view = ToolView(tool, dc)  # no db/user_id — existing call style
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Favour" in item.label
    )
    assert fav_btn.disabled is True


def test_toolview_fav_btn_enabled_when_db_provided():
    from cogs.tools import ToolView
    tool = make_tool()
    dc = MagicMock()
    db = MagicMock()
    view = ToolView(tool, dc, db=db, user_id="123", is_faved=False)
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Favour" in item.label
    )
    assert fav_btn.disabled is False


@pytest.mark.asyncio
async def test_tool_command_writes_history():
    from cogs.tools import ToolsCog
    db = MagicMock()
    db.get_favorites = AsyncMock(return_value=[])
    db.add_history = AsyncMock()
    bot = make_mock_bot()
    bot.db = db
    cog = ToolsCog(bot)
    interaction = make_interaction()
    interaction.user.id = "123"
    await cog.tool.callback(cog, interaction, name="Fishing Rod")
    db.add_history.assert_called_once_with("123", "tool", "rod")
