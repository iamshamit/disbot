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
