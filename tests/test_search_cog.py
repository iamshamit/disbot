"""Tests for cogs/search.py and utils/embeds.emoji_from_url."""
from __future__ import annotations
import discord
from tests.conftest import make_creature, make_location


def test_emoji_from_url_png():
    from utils.embeds import emoji_from_url
    e = emoji_from_url("https://cdn.discordapp.com/emojis/1162188819832000572.png")
    assert isinstance(e, discord.PartialEmoji)
    assert e.id == 1162188819832000572
    assert e.animated is False


def test_emoji_from_url_gif():
    from utils.embeds import emoji_from_url
    e = emoji_from_url("https://cdn.discordapp.com/emojis/1162188818225569802.gif")
    assert isinstance(e, discord.PartialEmoji)
    assert e.id == 1162188818225569802
    assert e.animated is True


def test_emoji_from_url_none():
    from utils.embeds import emoji_from_url
    assert emoji_from_url(None) is None
    assert emoji_from_url("https://example.com/image.png") is None
    assert emoji_from_url("") is None


def test_make_creature_tools_field():
    c = make_creature(tools={"fishing-rod": {"min": 1, "max": 3}})
    assert c.extra.get("tools") == {"fishing-rod": {"min": 1, "max": 3}}


def test_make_location_type_field():
    loc = make_location(loc_type="saltwater")
    assert loc.extra.get("type") == "saltwater"


# ---------------------------------------------------------------------------
# build_search_location_embed + SearchLocationView
# ---------------------------------------------------------------------------

def _make_loc_dc():
    from unittest.mock import MagicMock
    loc_sw1 = make_location(id="beach", name="Beach", failChance=5, mineChance=90,
                             loc_type="saltwater", creatures=["bass", "koi"])
    loc_sw2 = make_location(id="ocean", name="Ocean", failChance=15, mineChance=70,
                             loc_type="saltwater", creatures=["bass"])
    loc_fw = make_location(id="river", name="River", failChance=8, mineChance=60,
                            loc_type="freshwater", creatures=["trout", "koi", "bass"])
    dc = MagicMock()
    dc.location_by_id = {"beach": loc_sw1, "ocean": loc_sw2, "river": loc_fw}
    return dc


def test_build_search_location_embed_shows_all():
    from cogs.search import build_search_location_embed
    dc = _make_loc_dc()
    locs = list(dc.location_by_id.values())
    embed = build_search_location_embed(locs)
    desc = embed.description or ""
    assert "Beach" in desc
    assert "Ocean" in desc
    assert "River" in desc


def test_build_search_location_embed_zero_results():
    from cogs.search import build_search_location_embed
    embed = build_search_location_embed([])
    assert "No locations" in (embed.description or "")


def test_search_location_type_filter_saltwater():
    from cogs.search import SearchLocationView
    dc = _make_loc_dc()
    view = SearchLocationView(dc)
    view.type_filter = "saltwater"
    locs = view._filtered_sorted()
    names = [l.name for l in locs]
    assert "Beach" in names
    assert "Ocean" in names
    assert "River" not in names


def test_search_location_sort_fail_asc():
    from cogs.search import SearchLocationView
    dc = _make_loc_dc()
    view = SearchLocationView(dc)
    view.sort = "fail_asc"
    locs = view._filtered_sorted()
    fails = [l.extra.get("failChance") for l in locs]
    assert fails == sorted(fails)


def test_search_location_sort_fish_count_desc():
    from cogs.search import SearchLocationView
    dc = _make_loc_dc()
    view = SearchLocationView(dc)
    view.sort = "fish_count"
    locs = view._filtered_sorted()
    counts = [len(l.extra.get("creatures", [])) for l in locs]
    assert counts == sorted(counts, reverse=True)
