"""Tests for cogs/search.py and utils/embeds.emoji_from_url."""
from __future__ import annotations
import discord
import pytest
from tests.conftest import make_creature, make_location, make_tool


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
# build_search_fish_embed + SearchFishView (Task 6)
# ---------------------------------------------------------------------------

def _make_search_dc():
    from unittest.mock import MagicMock
    from tests.conftest import make_tool
    rod = make_tool(id="fishing-rod", name="Fishing Rod",
                    imageURL="https://cdn.discordapp.com/emojis/1162188819832000572.png")
    net = make_tool(id="net", name="Net",
                    imageURL="https://cdn.discordapp.com/emojis/1162188813259522070.png")
    bass = make_creature(id="bass", name="Bass", rarity="Common",
                         tools={"fishing-rod": {"min": 1, "max": 2}}, full_day=True)
    trout = make_creature(id="trout", name="Trout", rarity="Rare",
                          tools={"net": {"min": 1, "max": 3}}, full_day=True)
    koi = make_creature(id="koi", name="Koi", rarity="Very Rare",
                        tools={"fishing-rod": {"min": 1, "max": 1}}, full_day=True,
                        variants=[{"name": "Gold Koi", "chance": 5}])
    dc = MagicMock()
    dc.fish_by_id = {"bass": bass, "trout": trout, "koi": koi}
    dc.tool_by_id = {"fishing-rod": rod, "net": net}
    dc.location_by_id = {}
    return dc


def test_build_search_fish_embed_shows_fish_names():
    from cogs.search import build_search_fish_embed
    dc = _make_search_dc()
    creatures = list(dc.fish_by_id.values())
    creatures.sort(key=lambda c: c.name.lower())
    embed = build_search_fish_embed(creatures, page=0, total_pages=1, dc=dc)
    desc = embed.description or ""
    assert "Bass" in desc
    assert "Trout" in desc
    assert "Koi" in desc


def test_build_search_fish_embed_zero_results():
    from cogs.search import build_search_fish_embed
    dc = _make_search_dc()
    embed = build_search_fish_embed([], page=0, total_pages=1, dc=dc)
    assert "No fish" in (embed.description or "")


def test_search_fish_view_tool_filter():
    from cogs.search import SearchFishView
    dc = _make_search_dc()
    view = SearchFishView(dc)
    view.tool_filter = "fishing-rod"
    view._refresh()
    ids = [c.id for c in view.filtered]
    assert "bass" in ids
    assert "koi" in ids
    assert "trout" not in ids


def test_search_fish_view_rarity_filter():
    from cogs.search import SearchFishView
    dc = _make_search_dc()
    view = SearchFishView(dc)
    view.rarity_filter = "Rare"
    view._refresh()
    assert len(view.filtered) == 1
    assert view.filtered[0].id == "trout"


def test_search_fish_view_type_filter_variants():
    from cogs.search import SearchFishView
    dc = _make_search_dc()
    view = SearchFishView(dc)
    view.type_filter = "Has Variants"
    view._refresh()
    assert len(view.filtered) == 1
    assert view.filtered[0].id == "koi"


def test_creatures_embed_title():
    from cogs.search import build_search_fish_embed
    dc = _make_search_dc()
    embed = build_search_fish_embed([], page=0, total_pages=1, dc=dc, title="🦎 Creatures")
    assert "Creatures" in embed.title
