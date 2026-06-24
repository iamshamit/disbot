"""Tests for cogs/fish.py — FishCog, FishView, FishListView, FishCompareModal."""
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
# FishCog.fishcompare command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fishcompare_not_loaded_returns_error():
    from cogs.fish import FishCog
    bot = make_mock_bot(dank_client=None)
    cog = FishCog(bot)
    interaction = make_interaction()
    await cog.fishcompare.callback(cog, interaction, fish1="Goldfish", fish2="Koi")
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_fishcompare_fish1_not_found():
    from cogs.fish import FishCog
    bot = make_mock_bot()
    cog = FishCog(bot)
    interaction = make_interaction()
    await cog.fishcompare.callback(cog, interaction, fish1="NoSuchFish", fish2="Goldfish")
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_fishcompare_fish2_not_found():
    from cogs.fish import FishCog
    creatures = [
        make_creature(id="goldfish", name="Goldfish"),
        make_creature(id="koi", name="Koi", rarity="Uncommon"),
    ]
    bot = make_mock_bot(dank_client=make_mock_dank_client(creatures=creatures))
    cog = FishCog(bot)
    interaction = make_interaction()
    await cog.fishcompare.callback(cog, interaction, fish1="Goldfish", fish2="NoSuchFish")
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_fishcompare_both_found_sends_embed():
    from cogs.fish import FishCog
    creatures = [
        make_creature(id="goldfish", name="Goldfish"),
        make_creature(id="koi", name="Koi", rarity="Uncommon"),
    ]
    bot = make_mock_bot(dank_client=make_mock_dank_client(creatures=creatures))
    cog = FishCog(bot)
    interaction = make_interaction()
    await cog.fishcompare.callback(cog, interaction, fish1="Goldfish", fish2="Koi")
    interaction.response.send_message.assert_called_once()
    call_kwargs = interaction.response.send_message.call_args
    assert "embed" in call_kwargs.kwargs
    embed = call_kwargs.kwargs["embed"]
    assert "Goldfish" in embed.title
    assert "Koi" in embed.title


# ---------------------------------------------------------------------------
# FishCog autocomplete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fish_autocomplete_returns_empty_when_no_autocomplete():
    from cogs.fish import FishCog
    bot = make_mock_bot(autocomplete=None)
    cog = FishCog(bot)
    interaction = make_interaction()
    result = await cog.fish_autocomplete(interaction, "Gold")
    assert result == []


@pytest.mark.asyncio
async def test_fish_autocomplete_delegates_to_autocomplete_index():
    from cogs.fish import FishCog
    mock_ac = MagicMock()
    expected = [app_choices := discord.app_commands.Choice(name="Goldfish", value="Goldfish")]
    mock_ac.fish_choices = MagicMock(return_value=[expected])
    bot = make_mock_bot(autocomplete=mock_ac)
    cog = FishCog(bot)
    interaction = make_interaction()
    result = await cog.fish_autocomplete(interaction, "Gold")
    mock_ac.fish_choices.assert_called_once_with("Gold")
    assert result == [expected]


@pytest.mark.asyncio
async def test_fishcompare_autocomplete_returns_empty_when_no_autocomplete():
    from cogs.fish import FishCog
    bot = make_mock_bot(autocomplete=None)
    cog = FishCog(bot)
    interaction = make_interaction()
    result = await cog.fishcompare_autocomplete(interaction, "Ko")
    assert result == []


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
    assert any("Compare" in l for l in labels)
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
async def test_fishview_compare_btn_sends_modal():
    from cogs.fish import FishView, FishCompareModal
    creature = make_creature()
    dc = make_mock_dank_client()
    view = FishView(creature, dc)
    interaction = make_interaction()
    await view.compare_btn.callback(interaction)
    interaction.response.send_modal.assert_called_once()
    modal_arg = interaction.response.send_modal.call_args.args[0]
    assert isinstance(modal_arg, FishCompareModal)


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
# FishCompareModal
# ---------------------------------------------------------------------------

def test_fishcomparemodal_stores_first_and_client():
    from cogs.fish import FishCompareModal
    creature = make_creature()
    dc = make_mock_dank_client()
    modal = FishCompareModal(creature, dc)
    assert modal.first is creature
    assert modal.dc is dc


@pytest.mark.asyncio
async def test_fishcomparemodal_on_submit_not_found_sends_ephemeral():
    from cogs.fish import FishCompareModal
    creature = make_creature()
    dc = make_mock_dank_client()
    modal = FishCompareModal(creature, dc)
    modal.second_fish._value = "NonExistentFish"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    interaction.response.send_message.assert_called_once()
    assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_fishcomparemodal_on_submit_found_edits_message():
    from cogs.fish import FishCompareModal, BackToFishView
    c1 = make_creature(id="goldfish", name="Goldfish")
    c2 = make_creature(id="koi", name="Koi", rarity="Uncommon")
    dc = make_mock_dank_client(creatures=[c1, c2])
    modal = FishCompareModal(c1, dc)
    modal.second_fish._value = "Koi"
    interaction = make_interaction()
    await modal.on_submit(interaction)
    interaction.response.edit_message.assert_called_once()
    call_kwargs = interaction.response.edit_message.call_args
    assert isinstance(call_kwargs.kwargs.get("view"), BackToFishView)
    embed = call_kwargs.kwargs["embed"]
    assert "Goldfish" in embed.title
    assert "Koi" in embed.title


# ---------------------------------------------------------------------------
# FishListView
# ---------------------------------------------------------------------------

def test_fishlistview_default_sort_and_filter():
    from cogs.fish import FishListView
    dc = make_mock_dank_client()
    view = FishListView(dc)
    assert view.sort == "alphabetical"
    assert view.rarity_filter == "All"


def test_fishlistview_total_pages_calculated():
    from cogs.fish import FishListView
    # 1 creature → 1 page
    dc = make_mock_dank_client(creatures=[make_creature()])
    view = FishListView(dc)
    assert view.total_pages == 1


def test_fishlistview_total_pages_multiple():
    from cogs.fish import FishListView
    # 25 creatures → ceil(25/10) = 3 pages
    creatures = [make_creature(id=f"fish_{i}", name=f"Fish {i}") for i in range(25)]
    dc = make_mock_dank_client(creatures=creatures)
    view = FishListView(dc)
    assert view.total_pages == 3


def test_fishlistview_build_embed_returns_embed():
    from cogs.fish import FishListView
    dc = make_mock_dank_client()
    view = FishListView(dc)
    embed = view.build_embed()
    assert isinstance(embed, discord.Embed)
    assert "Fish" in embed.title


def test_fishlistview_filter_by_rarity():
    from cogs.fish import FishListView
    creatures = [
        make_creature(id="goldfish", name="Goldfish", rarity="Common"),
        make_creature(id="koi", name="Koi", rarity="Rare"),
    ]
    dc = make_mock_dank_client(creatures=creatures)
    view = FishListView(dc)
    view.rarity_filter = "Rare"
    view._refresh()
    assert len(view.filtered) == 1
    assert view.filtered[0].name == "Koi"


def test_fishlistview_filter_boss_only():
    from cogs.fish import FishListView
    creatures = [
        make_creature(id="goldfish", name="Goldfish", boss=False),
        make_creature(id="kraken", name="Kraken", boss=True, rarity="Absurdly Rare"),
    ]
    dc = make_mock_dank_client(creatures=creatures)
    view = FishListView(dc)
    view.rarity_filter = "Boss"
    view._refresh()
    assert len(view.filtered) == 1
    assert view.filtered[0].name == "Kraken"


def test_fishlistview_filter_mythical_only():
    from cogs.fish import FishListView
    creatures = [
        make_creature(id="goldfish", name="Goldfish", mythical=False),
        make_creature(id="aurora", name="Aurora", mythical=True, rarity="Mythical"),
    ]
    dc = make_mock_dank_client(creatures=creatures)
    view = FishListView(dc)
    view.rarity_filter = "Mythical only"
    view._refresh()
    assert len(view.filtered) == 1
    assert view.filtered[0].name == "Aurora"


def test_fishlistview_sort_alphabetical():
    from cogs.fish import FishListView
    creatures = [
        make_creature(id="z", name="Zebra Fish"),
        make_creature(id="a", name="Angelfish"),
    ]
    dc = make_mock_dank_client(creatures=creatures)
    view = FishListView(dc)
    view.sort = "alphabetical"
    view._refresh()
    assert view.filtered[0].name == "Angelfish"
    assert view.filtered[1].name == "Zebra Fish"


def test_fishlistview_sort_rarity_asc():
    from cogs.fish import FishListView
    creatures = [
        make_creature(id="koi", name="Koi", rarity="Rare"),
        make_creature(id="goldfish", name="Goldfish", rarity="Common"),
    ]
    dc = make_mock_dank_client(creatures=creatures)
    view = FishListView(dc)
    view.sort = "rarity_asc"
    view._refresh()
    assert view.filtered[0].extra.get("rarity") == "Common"
    assert view.filtered[1].extra.get("rarity") == "Rare"


def test_fishlistview_sort_rarity_desc():
    from cogs.fish import FishListView
    creatures = [
        make_creature(id="goldfish", name="Goldfish", rarity="Common"),
        make_creature(id="koi", name="Koi", rarity="Rare"),
    ]
    dc = make_mock_dank_client(creatures=creatures)
    view = FishListView(dc)
    view.sort = "rarity_desc"
    view._refresh()
    assert view.filtered[0].extra.get("rarity") == "Rare"
    assert view.filtered[1].extra.get("rarity") == "Common"


def test_fishlistview_page_clamped_on_filter():
    from cogs.fish import FishListView
    # 25 creatures all Common, set page to 2, then filter to Rare (0 results → 1 page)
    creatures = [make_creature(id=f"fish_{i}", name=f"Fish {i}", rarity="Common") for i in range(25)]
    dc = make_mock_dank_client(creatures=creatures)
    view = FishListView(dc)
    view.page = 2
    view.rarity_filter = "Rare"
    view._refresh()
    assert view.page == 0  # clamped to 0 when total_pages becomes 1


def test_fishlistview_has_sort_and_rarity_selects():
    from cogs.fish import FishListView
    dc = make_mock_dank_client()
    view = FishListView(dc)
    selects = [item for item in view.children if isinstance(item, discord.ui.Select)]
    assert len(selects) == 2
    placeholders = {s.placeholder for s in selects}
    assert any("Sort" in (p or "") for p in placeholders)
    assert any("Filter" in (p or "") or "Rarity" in (p or "") for p in placeholders)


@pytest.mark.asyncio
async def test_fishlistview_sort_select_callback_updates_sort():
    from cogs.fish import FishListView
    dc = make_mock_dank_client()
    view = FishListView(dc)
    interaction = make_interaction()

    # Set _values on the actual select item to control .values property
    view.sort_select._values = ["rarity_asc"]  # discord.py internal; only safe way to inject select values in tests
    await view.sort_select.callback(interaction)

    assert view.sort == "rarity_asc"
    interaction.response.edit_message.assert_called_once()


@pytest.mark.asyncio
async def test_fishlistview_rarity_select_resets_page_to_zero():
    from cogs.fish import FishListView
    creatures = [make_creature(id=f"fish_{i}", name=f"Fish {i}") for i in range(25)]
    dc = make_mock_dank_client(creatures=creatures)
    view = FishListView(dc)
    view.page = 2

    interaction = make_interaction()
    view.rarity_select._values = ["Uncommon"]  # discord.py internal; only safe way to inject select values in tests
    await view.rarity_select.callback(interaction)

    assert view.page == 0


# ---------------------------------------------------------------------------
# setup()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_setup_adds_cog():
    from cogs.fish import setup, FishCog
    bot = AsyncMock()
    bot.add_cog = AsyncMock()
    await setup(bot)
    bot.add_cog.assert_called_once()
    cog_arg = bot.add_cog.call_args.args[0]
    assert isinstance(cog_arg, FishCog)


# ---------------------------------------------------------------------------
# FishView — Favourite button
# ---------------------------------------------------------------------------

def test_fishview_fav_btn_disabled_when_no_db():
    from cogs.fish import FishView
    creature = make_creature()
    dc = make_mock_dank_client()
    view = FishView(creature, dc)  # no db/user_id — existing call style
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Favour" in item.label
    )
    assert fav_btn.disabled is True


def test_fishview_fav_btn_enabled_when_db_provided():
    from cogs.fish import FishView
    creature = make_creature()
    dc = make_mock_dank_client()
    db = MagicMock()
    view = FishView(creature, dc, db=db, user_id="123", is_faved=False)
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Favour" in item.label
    )
    assert fav_btn.disabled is False


def test_fishview_fav_btn_label_unfavourite_when_faved():
    from cogs.fish import FishView
    creature = make_creature()
    dc = make_mock_dank_client()
    db = MagicMock()
    view = FishView(creature, dc, db=db, user_id="123", is_faved=True)
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and ("Favourite" in item.label or "Unfavourite" in item.label)
    )
    assert "Unfavourite" in fav_btn.label or "💛" in fav_btn.label


@pytest.mark.asyncio
async def test_fishview_fav_btn_adds_favourite():
    from cogs.fish import FishView
    creature = make_creature(id="goldfish")
    dc = make_mock_dank_client()
    db = MagicMock()
    db.add_favorite = AsyncMock()
    db.remove_favorite = AsyncMock()
    view = FishView(creature, dc, db=db, user_id="123", is_faved=False)
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and "Favour" in item.label
    )
    interaction = make_interaction()
    await fav_btn.callback(interaction)
    db.add_favorite.assert_called_once_with("123", "fish", "goldfish")
    interaction.response.edit_message.assert_called_once()


@pytest.mark.asyncio
async def test_fishview_fav_btn_removes_when_already_faved():
    from cogs.fish import FishView
    creature = make_creature(id="goldfish")
    dc = make_mock_dank_client()
    db = MagicMock()
    db.add_favorite = AsyncMock()
    db.remove_favorite = AsyncMock()
    view = FishView(creature, dc, db=db, user_id="123", is_faved=True)
    fav_btn = next(
        item for item in view.children
        if isinstance(item, discord.ui.Button) and ("Favourite" in item.label or "Unfavourite" in item.label)
    )
    interaction = make_interaction()
    await fav_btn.callback(interaction)
    db.remove_favorite.assert_called_once_with("123", "fish", "goldfish")


@pytest.mark.asyncio
async def test_fish_command_writes_history():
    from cogs.fish import FishCog
    db = MagicMock()
    db.get_favorites = AsyncMock(return_value=[])
    db.add_history = AsyncMock()
    bot = make_mock_bot()
    bot.db = db
    cog = FishCog(bot)
    interaction = make_interaction()
    interaction.user.id = "123"
    await cog.fish.callback(cog, interaction, name="Goldfish")
    db.add_history.assert_called_once_with("123", "fish", "goldfish")


# ---------------------------------------------------------------------------
# FishView — Simulate button
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fish_view_sim_btn_is_enabled_when_db_present():
    from cogs.fish import FishView
    dc = MagicMock()
    dc.tool_by_id = {}
    dc.bait_by_id = {}
    dc.location_by_id = {}
    dc.event_by_id = {}
    dc.skill_categories = {}
    db = MagicMock()
    creature = MagicMock()
    creature.extra = {"rarity": "Common", "boss": False, "mythical": False}
    view = FishView(creature, dc, db=db, user_id="123")
    sim_btn = next((b for b in view.children if isinstance(b, discord.ui.Button) and "Simulate" in b.label), None)
    assert sim_btn is not None
    assert sim_btn.disabled is False


# ---------------------------------------------------------------------------
# build_fish_embed — TOOLS section (Task 2)
# ---------------------------------------------------------------------------

def _make_dc_with_tool():
    from unittest.mock import MagicMock
    from tests.conftest import make_tool, make_location
    dc = MagicMock()
    rod = make_tool(id="fishing-rod", name="Fishing Rod",
                    imageURL="https://cdn.discordapp.com/emojis/1162188819832000572.png")
    harpoon = make_tool(id="harpoon", name="Harpoon",
                        imageURL="https://cdn.discordapp.com/emojis/1162188817135046757.png")
    loc_low = make_location(id="loc_low", name="Easy Beach", failChance=5, loc_type="saltwater")
    loc_high = make_location(id="loc_high", name="Hard Ocean", failChance=20, loc_type="saltwater")
    dc.tool_by_id = {"fishing-rod": rod, "harpoon": harpoon}
    dc.location_by_id = {"loc_low": loc_low, "loc_high": loc_high}
    return dc


def test_fish_embed_tools_section_present():
    from utils.embeds import build_fish_embed
    dc = _make_dc_with_tool()
    c = make_creature(
        tools={"fishing-rod": {"min": 1, "max": 1}, "harpoon": {"min": 1, "max": 3}},
        locations=["loc_low", "loc_high"],
    )
    embed = build_fish_embed(c, dc)
    assert "TOOLS" in (embed.description or "")
    assert "Fishing Rod" in (embed.description or "")
    assert "Harpoon" in (embed.description or "")


def test_fish_embed_best_tool_marked():
    from utils.embeds import build_fish_embed
    dc = _make_dc_with_tool()
    c = make_creature(
        tools={"fishing-rod": {"min": 1, "max": 1}, "harpoon": {"min": 1, "max": 3}},
        locations=["loc_low"],
    )
    embed = build_fish_embed(c, dc)
    desc = embed.description or ""
    # Harpoon has max=3, Fishing Rod has max=1 — only Harpoon should be marked Best
    harpoon_line = next((l for l in desc.splitlines() if "Harpoon" in l), "")
    rod_line = next((l for l in desc.splitlines() if "Fishing Rod" in l), "")
    assert "⭐" in harpoon_line
    assert "⭐" not in rod_line


def test_fish_embed_best_location_lowest_fail():
    from utils.embeds import build_fish_embed
    dc = _make_dc_with_tool()
    c = make_creature(
        tools={"fishing-rod": {"min": 1, "max": 1}},
        locations=["loc_low", "loc_high"],
    )
    embed = build_fish_embed(c, dc)
    desc = embed.description or ""
    # Best Location = loc_low (failChance=5), not loc_high (failChance=20)
    assert "Easy Beach" in desc
    assert "Best Location" in desc


# ---------------------------------------------------------------------------
# build_fish_compare_embed — Best Tool + Max Catch rows (Task 4)
# ---------------------------------------------------------------------------

def test_fishcompare_embed_best_tool_row():
    from utils.embeds import build_fish_compare_embed
    from unittest.mock import MagicMock
    from tests.conftest import make_tool
    rod = make_tool(id="fishing-rod", name="Fishing Rod")
    net = make_tool(id="net", name="Net")
    dc = MagicMock()
    dc.tool_by_id = {"fishing-rod": rod, "net": net}
    c1 = make_creature(id="bass", name="Bass", tools={"fishing-rod": {"min": 1, "max": 3}})
    c2 = make_creature(id="koi", name="Koi", tools={"net": {"min": 1, "max": 1}})
    embed = build_fish_compare_embed(c1, c2, dc)
    label_field = embed.fields[0].value
    assert "Best Tool" in label_field
    assert "Max Catch" in label_field


def test_fishcompare_embed_no_dc_shows_dash():
    from utils.embeds import build_fish_compare_embed
    c1 = make_creature(id="bass", name="Bass", tools={"fishing-rod": {"min": 1, "max": 3}})
    c2 = make_creature(id="koi", name="Koi", tools={})
    embed = build_fish_compare_embed(c1, c2)
    label_field = embed.fields[0].value
    # Best Tool row exists even without dc
    assert "Best Tool" in label_field


