"""Tests for cogs/locations.py — LocationsCog, LocationView, LocationsListView, LocationCompareModal."""
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
    """Build a lightweight stand-in for DankMemerGameClient."""
    if creatures is _SENTINEL:
        creatures = [make_creature()]
    if locations is _SENTINEL:
        locations = [make_location()]
    client = MagicMock()
    client.fish_by_id = {c.id: c for c in creatures}
    client.fish_by_name = {c.name.lower(): c for c in creatures}
    client.location_by_id = {loc.id: loc for loc in locations}
    client.location_by_name = {loc.name.lower(): loc for loc in locations}
    client.location_creature_map = {}

    def get_location(query):
        if query in client.location_by_id:
            return client.location_by_id[query]
        return client.location_by_name.get(query.lower())

    client.get_location = get_location
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
# LocationsCog._guard
# ---------------------------------------------------------------------------

def test_guard_true_when_data_loaded():
    from cogs.locations import LocationsCog
    bot = make_mock_bot()
    cog = LocationsCog(bot)
    assert cog._guard() is True


def test_guard_false_when_no_dank_client():
    from cogs.locations import LocationsCog
    bot = make_mock_bot(dank_client=None)
    cog = LocationsCog(bot)
    assert cog._guard() is False


def test_guard_false_when_location_by_id_empty():
    from cogs.locations import LocationsCog
    client = make_mock_dank_client(locations=[])
    bot = make_mock_bot(dank_client=client)
    cog = LocationsCog(bot)
    assert cog._guard() is False


# ---------------------------------------------------------------------------
# LocationsCog.location command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_location_command_not_loaded_returns_error():
    from cogs.locations import LocationsCog
    bot = make_mock_bot(dank_client=None)
    cog = LocationsCog(bot)
    interaction = make_interaction()
    await cog.location.callback(cog, interaction, name="Sunken Ship")
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_location_command_not_found_returns_error():
    from cogs.locations import LocationsCog
    bot = make_mock_bot()
    cog = LocationsCog(bot)
    interaction = make_interaction()
    await cog.location.callback(cog, interaction, name="NoSuchLocation999")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert call_kwargs.kwargs.get("ephemeral") is True
    embed = call_kwargs.kwargs["embed"]
    assert "NoSuchLocation999" in embed.description or "NoSuchLocation999" in (embed.title or "")


@pytest.mark.asyncio
async def test_location_command_found_sends_embed_and_view():
    from cogs.locations import LocationsCog, LocationView
    bot = make_mock_bot()
    cog = LocationsCog(bot)
    interaction = make_interaction()
    await cog.location.callback(cog, interaction, name="Sunken Ship")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert "embed" in call_kwargs.kwargs
    assert "view" in call_kwargs.kwargs
    assert isinstance(call_kwargs.kwargs["view"], LocationView)


@pytest.mark.asyncio
async def test_location_command_stores_message_on_view():
    from cogs.locations import LocationsCog, LocationView
    bot = make_mock_bot()
    cog = LocationsCog(bot)
    interaction = make_interaction()
    mock_msg = MagicMock()
    interaction.original_response = AsyncMock(return_value=mock_msg)
    await cog.location.callback(cog, interaction, name="Sunken Ship")
    call_kwargs = interaction.response.send_message.call_args
    view = call_kwargs.kwargs["view"]
    assert view.message is mock_msg


# ---------------------------------------------------------------------------
# LocationsCog.locations command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_locations_not_loaded_returns_error():
    from cogs.locations import LocationsCog
    bot = make_mock_bot(dank_client=None)
    cog = LocationsCog(bot)
    interaction = make_interaction()
    await cog.locations.callback(cog, interaction)
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_locations_sends_embed_and_view():
    from cogs.locations import LocationsCog, LocationsListView
    bot = make_mock_bot()
    cog = LocationsCog(bot)
    interaction = make_interaction()
    await cog.locations.callback(cog, interaction)
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert "embed" in call_kwargs.kwargs
    assert isinstance(call_kwargs.kwargs["view"], LocationsListView)


# ---------------------------------------------------------------------------
# LocationsCog.locationcompare command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_locationcompare_not_loaded_returns_error():
    from cogs.locations import LocationsCog
    bot = make_mock_bot(dank_client=None)
    cog = LocationsCog(bot)
    interaction = make_interaction()
    await cog.locationcompare.callback(cog, interaction, location1="Sunken Ship", location2="Murky Pond")
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_locationcompare_loc1_not_found():
    from cogs.locations import LocationsCog
    bot = make_mock_bot()
    cog = LocationsCog(bot)
    interaction = make_interaction()
    await cog.locationcompare.callback(cog, interaction, location1="NoSuchPlace", location2="Sunken Ship")
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_locationcompare_loc2_not_found():
    from cogs.locations import LocationsCog
    locs = [
        make_location(id="sunken_ship", name="Sunken Ship"),
        make_location(id="murky_pond", name="Murky Pond"),
    ]
    bot = make_mock_bot(dank_client=make_mock_dank_client(locations=locs))
    cog = LocationsCog(bot)
    interaction = make_interaction()
    await cog.locationcompare.callback(cog, interaction, location1="Sunken Ship", location2="NoSuchPlace")
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_locationcompare_both_found_sends_embed():
    from cogs.locations import LocationsCog
    locs = [
        make_location(id="sunken_ship", name="Sunken Ship"),
        make_location(id="murky_pond", name="Murky Pond"),
    ]
    bot = make_mock_bot(dank_client=make_mock_dank_client(locations=locs))
    cog = LocationsCog(bot)
    interaction = make_interaction()
    await cog.locationcompare.callback(cog, interaction, location1="Sunken Ship", location2="Murky Pond")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert "embed" in call_kwargs.kwargs
    embed = call_kwargs.kwargs["embed"]
    assert "Sunken Ship" in embed.title
    assert "Murky Pond" in embed.title


# ---------------------------------------------------------------------------
# LocationsCog autocomplete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_location_autocomplete_returns_empty_when_no_autocomplete():
    from cogs.locations import LocationsCog
    bot = make_mock_bot(autocomplete=None)
    cog = LocationsCog(bot)
    interaction = make_interaction()
    result = await cog.location_autocomplete(interaction, "Sun")
    assert result == []


@pytest.mark.asyncio
async def test_location_autocomplete_delegates_to_autocomplete_index():
    from cogs.locations import LocationsCog
    mock_ac = MagicMock()
    expected = discord.app_commands.Choice(name="Sunken Ship", value="Sunken Ship")
    mock_ac.location_choices = MagicMock(return_value=[expected])
    bot = make_mock_bot(autocomplete=mock_ac)
    cog = LocationsCog(bot)
    interaction = make_interaction()
    result = await cog.location_autocomplete(interaction, "Sun")
    mock_ac.location_choices.assert_called_once_with("Sun")
    assert result == [expected]


@pytest.mark.asyncio
async def test_locationcompare_autocomplete_returns_empty_when_no_autocomplete():
    from cogs.locations import LocationsCog
    bot = make_mock_bot(autocomplete=None)
    cog = LocationsCog(bot)
    interaction = make_interaction()
    result = await cog.locationcompare_autocomplete(interaction, "Sun")
    assert result == []


# ---------------------------------------------------------------------------
# LocationView
# ---------------------------------------------------------------------------

def test_locationview_timeout_is_300():
    from cogs.locations import LocationView
    loc = make_location()
    dc = make_mock_dank_client()
    view = LocationView(loc, dc)
    assert view.timeout == 300


def test_locationview_has_expected_buttons():
    from cogs.locations import LocationView
    loc = make_location()
    dc = make_mock_dank_client()
    view = LocationView(loc, dc)
    labels = [item.label for item in view.children if isinstance(item, discord.ui.Button)]
    assert any("Compare" in l for l in labels)
    assert any("Delete" in l for l in labels)
    assert any("Open Fish" in l for l in labels)


def test_locationview_no_fish_select_when_no_creatures():
    from cogs.locations import LocationView
    loc = make_location()
    dc = make_mock_dank_client()
    dc.location_creature_map = {}  # no creatures
    view = LocationView(loc, dc)
    selects = [item for item in view.children if isinstance(item, discord.ui.Select)]
    assert len(selects) == 0


def test_locationview_fish_select_added_when_creatures_present():
    from cogs.locations import LocationView
    creature = make_creature(id="goldfish", name="Goldfish")
    loc = make_location(id="sunken_ship")
    dc = make_mock_dank_client(creatures=[creature], locations=[loc])
    dc.location_creature_map = {"sunken_ship": [creature]}
    view = LocationView(loc, dc)
    selects = [item for item in view.children if isinstance(item, discord.ui.Select)]
    assert len(selects) == 1
    assert "Fish Pool" in selects[0].placeholder


@pytest.mark.asyncio
async def test_locationview_on_timeout_disables_all_items():
    from cogs.locations import LocationView
    loc = make_location()
    dc = make_mock_dank_client()
    view = LocationView(loc, dc)
    view.message = None
    await view.on_timeout()
    for item in view.children:
        assert item.disabled is True


@pytest.mark.asyncio
async def test_locationview_on_timeout_edits_message():
    from cogs.locations import LocationView
    loc = make_location()
    dc = make_mock_dank_client()
    view = LocationView(loc, dc)
    mock_msg = AsyncMock()
    view.message = mock_msg
    await view.on_timeout()
    mock_msg.edit.assert_called_once_with(view=view)


@pytest.mark.asyncio
async def test_locationview_compare_btn_sends_modal():
    from cogs.locations import LocationView, LocationCompareModal
    loc = make_location()
    dc = make_mock_dank_client()
    view = LocationView(loc, dc)
    interaction = make_interaction()
    await view.compare_btn.callback(interaction)
    interaction.response.send_modal.assert_called_once()
    modal_arg = interaction.response.send_modal.call_args.args[0]
    assert isinstance(modal_arg, LocationCompareModal)


@pytest.mark.asyncio
async def test_locationview_delete_btn_deletes_message():
    from cogs.locations import LocationView
    loc = make_location()
    dc = make_mock_dank_client()
    view = LocationView(loc, dc)
    interaction = make_interaction()
    interaction.message = AsyncMock()
    interaction.message.delete = AsyncMock()
    await view.delete_btn.callback(interaction)
    interaction.message.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_locationview_open_fish_btn_no_selection_sends_ephemeral():
    from cogs.locations import LocationView
    loc = make_location()
    dc = make_mock_dank_client()
    view = LocationView(loc, dc)
    # _selected_creature_id is not set (no fish select added)
    interaction = make_interaction()
    await view.open_fish_btn.callback(interaction)
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


# ---------------------------------------------------------------------------
# LocationCompareModal
# ---------------------------------------------------------------------------

def test_locationcomparemodal_stores_first_and_client():
    from cogs.locations import LocationCompareModal
    loc = make_location()
    dc = make_mock_dank_client()
    modal = LocationCompareModal(loc, dc, location=loc, dank_client_for_back=dc)
    assert modal.first is loc
    assert modal.dc is dc


@pytest.mark.asyncio
async def test_locationcomparemodal_on_submit_not_found_sends_ephemeral():
    from cogs.locations import LocationCompareModal
    loc = make_location()
    dc = make_mock_dank_client()
    modal = LocationCompareModal(loc, dc, location=loc, dank_client_for_back=dc)
    modal.second_loc._value = "NonExistentPlace"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_locationcomparemodal_on_submit_found_edits_message():
    from cogs.locations import LocationCompareModal, BackToLocationView
    loc1 = make_location(id="sunken_ship", name="Sunken Ship")
    loc2 = make_location(id="murky_pond", name="Murky Pond")
    dc = make_mock_dank_client(locations=[loc1, loc2])
    modal = LocationCompareModal(loc1, dc, location=loc1, dank_client_for_back=dc)
    modal.second_loc._value = "Murky Pond"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    interaction.response.edit_message.assert_called_once()
    call_kwargs = interaction.response.edit_message.call_args
    assert isinstance(call_kwargs.kwargs.get("view"), BackToLocationView)
    embed = call_kwargs.kwargs["embed"]
    assert "Sunken Ship" in embed.title
    assert "Murky Pond" in embed.title


# ---------------------------------------------------------------------------
# LocationsListView
# ---------------------------------------------------------------------------

def test_locationslistview_default_sort_and_filter():
    from cogs.locations import LocationsListView
    dc = make_mock_dank_client()
    view = LocationsListView(dc)
    assert view.sort == "name"
    assert view.filter_ == "All"


def test_locationslistview_total_pages_one_location():
    from cogs.locations import LocationsListView
    dc = make_mock_dank_client(locations=[make_location()])
    view = LocationsListView(dc)
    assert view.total_pages == 1


def test_locationslistview_total_pages_multiple():
    from cogs.locations import LocationsListView
    # 17 locations → ceil(17/8) = 3 pages
    locs = [make_location(id=f"loc_{i}", name=f"Location {i}") for i in range(17)]
    dc = make_mock_dank_client(locations=locs)
    view = LocationsListView(dc)
    assert view.total_pages == 3


def test_locationslistview_build_embed_returns_embed():
    from cogs.locations import LocationsListView
    dc = make_mock_dank_client()
    view = LocationsListView(dc)
    embed = view.build_embed()
    assert isinstance(embed, discord.Embed)


def test_locationslistview_filter_active_only():
    from cogs.locations import LocationsListView
    locs = [
        make_location(id="a", name="Active Place", disabled=False, temporary=False),
        make_location(id="b", name="Temp Place", disabled=False, temporary=True),
        make_location(id="c", name="Disabled Place", disabled=True, temporary=False),
    ]
    dc = make_mock_dank_client(locations=locs)
    view = LocationsListView(dc)
    view.filter_ = "Active"
    view._refresh()
    assert len(view.filtered) == 1
    assert view.filtered[0].name == "Active Place"


def test_locationslistview_filter_temporary():
    from cogs.locations import LocationsListView
    locs = [
        make_location(id="a", name="Permanent", disabled=False, temporary=False),
        make_location(id="b", name="Seasonal", disabled=False, temporary=True),
    ]
    dc = make_mock_dank_client(locations=locs)
    view = LocationsListView(dc)
    view.filter_ = "Temporary"
    view._refresh()
    assert len(view.filtered) == 1
    assert view.filtered[0].name == "Seasonal"


def test_locationslistview_filter_disabled():
    from cogs.locations import LocationsListView
    locs = [
        make_location(id="a", name="Active", disabled=False),
        make_location(id="b", name="Gone", disabled=True),
    ]
    dc = make_mock_dank_client(locations=locs)
    view = LocationsListView(dc)
    view.filter_ = "Disabled"
    view._refresh()
    assert len(view.filtered) == 1
    assert view.filtered[0].name == "Gone"


def test_locationslistview_sort_by_name():
    from cogs.locations import LocationsListView
    locs = [
        make_location(id="z", name="Zebra Bay"),
        make_location(id="a", name="Aqua Cove"),
    ]
    dc = make_mock_dank_client(locations=locs)
    view = LocationsListView(dc)
    view.sort = "name"
    view._refresh()
    assert view.filtered[0].name == "Aqua Cove"
    assert view.filtered[1].name == "Zebra Bay"


def test_locationslistview_sort_by_fail_chance():
    from cogs.locations import LocationsListView
    locs = [
        make_location(id="a", name="Dangerous", failChance=50),
        make_location(id="b", name="Safe", failChance=5),
    ]
    dc = make_mock_dank_client(locations=locs)
    view = LocationsListView(dc)
    view.sort = "fail_chance"
    view._refresh()
    assert view.filtered[0].name == "Safe"
    assert view.filtered[1].name == "Dangerous"


def test_locationslistview_sort_by_mine_chance():
    from cogs.locations import LocationsListView
    locs = [
        make_location(id="a", name="Low Mine", mineChance=2),
        make_location(id="b", name="High Mine", mineChance=20),
    ]
    dc = make_mock_dank_client(locations=locs)
    view = LocationsListView(dc)
    view.sort = "mine_chance"
    view._refresh()
    assert view.filtered[0].name == "High Mine"
    assert view.filtered[1].name == "Low Mine"


def test_locationslistview_page_clamped_on_filter():
    from cogs.locations import LocationsListView
    # 17 active locations → 3 pages; switch to Disabled (0 results → 1 page)
    locs = [make_location(id=f"loc_{i}", name=f"Location {i}", disabled=False, temporary=False) for i in range(17)]
    dc = make_mock_dank_client(locations=locs)
    view = LocationsListView(dc)
    view.page = 2
    view.filter_ = "Disabled"
    view._refresh()
    assert view.page == 0


def test_locationslistview_has_sort_and_filter_selects():
    from cogs.locations import LocationsListView
    dc = make_mock_dank_client()
    view = LocationsListView(dc)
    selects = [item for item in view.children if isinstance(item, discord.ui.Select)]
    assert len(selects) == 2
    placeholders = {s.placeholder for s in selects}
    assert any("Sort" in (p or "") for p in placeholders)
    assert any("Filter" in (p or "") for p in placeholders)


@pytest.mark.asyncio
async def test_locationslistview_sort_select_callback_updates_sort():
    from cogs.locations import LocationsListView
    dc = make_mock_dank_client()
    view = LocationsListView(dc)
    interaction = make_interaction()
    # discord.py internal: inject values via _values fallback
    view.sort_select._values = ["fish_count"]
    await view.sort_select.callback(interaction)
    assert view.sort == "fish_count"
    interaction.response.edit_message.assert_called_once()


@pytest.mark.asyncio
async def test_locationslistview_filter_select_resets_page_to_zero():
    from cogs.locations import LocationsListView
    locs = [make_location(id=f"loc_{i}", name=f"Location {i}") for i in range(17)]
    dc = make_mock_dank_client(locations=locs)
    view = LocationsListView(dc)
    view.page = 2
    interaction = make_interaction()
    # discord.py internal: inject values via _values fallback
    view.filter_select._values = ["Active"]
    await view.filter_select.callback(interaction)
    assert view.page == 0


# ---------------------------------------------------------------------------
# setup()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_setup_adds_cog():
    from cogs.locations import setup, LocationsCog
    bot = AsyncMock()
    bot.add_cog = AsyncMock()
    await setup(bot)
    bot.add_cog.assert_called_once()
    cog_arg = bot.add_cog.call_args.args[0]
    assert isinstance(cog_arg, LocationsCog)


# ---------------------------------------------------------------------------
# LocationView — Favourite button
# ---------------------------------------------------------------------------

def test_locationview_fav_btn_disabled_when_no_db():
    from cogs.locations import LocationView
    loc = make_location()
    dc = make_mock_dank_client()
    view = LocationView(loc, dc)  # no db/user_id — existing call style
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Favour" in item.label
    )
    assert fav_btn.disabled is True


def test_locationview_fav_btn_enabled_when_db_provided():
    from cogs.locations import LocationView
    loc = make_location()
    dc = make_mock_dank_client()
    db = MagicMock()
    view = LocationView(loc, dc, db=db, user_id="123", is_faved=False)
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Favour" in item.label
    )
    assert fav_btn.disabled is False


@pytest.mark.asyncio
async def test_location_command_writes_history():
    from cogs.locations import LocationsCog
    db = MagicMock()
    db.get_favorites = AsyncMock(return_value=[])
    db.add_history = AsyncMock()
    bot = make_mock_bot()
    bot.db = db
    cog = LocationsCog(bot)
    interaction = make_interaction()
    interaction.user.id = "123"
    await cog.location.callback(cog, interaction, name="Sunken Ship")
    db.add_history.assert_called_once_with("123", "location", "sunken_ship")


# ---------------------------------------------------------------------------
# LocationView — Simulate button
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_location_view_sim_btn_is_enabled_when_db_present():
    from cogs.locations import LocationView
    dc = MagicMock()
    dc.location_creature_map = {}
    dc.tool_by_id = {}
    dc.bait_by_id = {}
    dc.location_by_id = {}
    dc.event_by_id = {}
    dc.skill_categories = {}
    db = MagicMock()
    loc = MagicMock()
    loc.id = "river"
    loc.name = "River"
    view = LocationView(loc, dc, db=db, user_id="123")
    sim_btn = next((b for b in view.children if isinstance(b, discord.ui.Button) and "Simulate" in b.label), None)
    assert sim_btn is not None
    assert sim_btn.disabled is False
