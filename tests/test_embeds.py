import discord
import pytest
from tests.conftest import make_creature, make_location, make_tool, make_bait
from unittest.mock import MagicMock


def make_mock_client(creatures=None, locations=None, tools=None, baits=None):
    client = MagicMock()
    client.fish_by_id = {c.id: c for c in (creatures or [])}
    client.location_by_id = {l.id: l for l in (locations or [])}
    client.tool_by_id = {t.id: t for t in (tools or [])}
    client.bait_by_id = {b.id: b for b in (baits or [])}
    client.npc_by_id = {}
    return client


# --- Fish embeds ---

def test_build_fish_embed_title(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    assert embed.title == "Goldfish"

def test_build_fish_embed_color_common(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    assert embed.color.value == 0x8e9297

def test_build_fish_embed_color_boss(boss_creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(boss_creature, make_mock_client())
    from utils.formatters import BOSS_COLOR
    assert embed.color.value == BOSS_COLOR

def test_build_fish_embed_has_availability(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    assert "AVAILABILITY" in embed.description

def test_build_fish_embed_no_variants_section(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    assert "VARIANTS" not in embed.description

def test_build_fish_embed_with_variants():
    from utils.embeds import build_fish_embed
    c = make_creature(variants=[{"name": "Chroma", "chance": 2}])
    embed = build_fish_embed(c, make_mock_client())
    assert "VARIANTS" in embed.description

def test_build_fish_embed_resolves_location_names():
    from utils.embeds import build_fish_embed
    loc = make_location(id="loc1", name="Sunken Ship")
    c = make_creature(locations=["loc1"])
    embed = build_fish_embed(c, make_mock_client(locations=[loc]))
    assert "Sunken Ship" in embed.description

def test_build_fish_embed_footer(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    assert embed.footer.text == "Internal ID: goldfish"


# --- Compare embed ---

def test_build_fish_compare_embed_title():
    from utils.embeds import build_fish_compare_embed
    c1 = make_creature(name="Goldfish")
    c2 = make_creature(id="koi", name="Koi", rarity="Rare")
    embed = build_fish_compare_embed(c1, c2)
    assert "Goldfish" in embed.title
    assert "Koi" in embed.title

def test_build_fish_compare_embed_winner_marked():
    from utils.embeds import build_fish_compare_embed
    c1 = make_creature(locations=["a", "b"])
    c2 = make_creature(locations=["a", "b", "c", "d", "e"])
    embed = build_fish_compare_embed(c1, c2)
    # c2 has more locations → should have ✓
    assert "✓" in embed.description


# --- Peak hours embed ---

def test_build_peak_hours_embed_contains_grid(creature):
    from utils.embeds import build_peak_hours_embed
    embed = build_peak_hours_embed(creature)
    assert "00" in embed.description
    assert "23" in embed.description

def test_build_peak_hours_embed_full_day(fullday_creature):
    from utils.embeds import build_peak_hours_embed
    embed = build_peak_hours_embed(fullday_creature)
    assert "All Day" in embed.description


# --- Fishlist embed ---

def test_build_fishlist_embed_title():
    from utils.embeds import build_fishlist_embed
    creatures = [make_creature()]
    embed = build_fishlist_embed(creatures, page=0, total_pages=1, sort="alphabetical", rarity_filter="All")
    assert "Fish" in embed.title

def test_build_fishlist_embed_footer_has_page():
    from utils.embeds import build_fishlist_embed
    creatures = [make_creature()]
    embed = build_fishlist_embed(creatures, page=0, total_pages=3, sort="alphabetical", rarity_filter="All")
    assert "1" in embed.footer.text
    assert "3" in embed.footer.text
