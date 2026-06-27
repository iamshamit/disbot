import discord
import pytest
import json
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


def _all_text(embed):
    """Get all text content from an embed (description + all field values)."""
    parts = []
    if embed.description:
        parts.append(embed.description)
    for f in embed.fields:
        parts.append(f.name or "")
        parts.append(f.value or "")
    return "\n".join(parts)


# --- Fish embeds ---

def test_build_fish_embed_title(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    assert embed.title == "Goldfish"

def test_build_fish_embed_color_common(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    assert embed.color.value == 0x57f287  # Common rarity color

def test_build_fish_embed_color_boss(boss_creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(boss_creature, make_mock_client())
    from utils.formatters import BOSS_COLOR
    assert embed.color.value == BOSS_COLOR

def test_build_fish_embed_has_availability(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    text = _all_text(embed)
    assert "Availability" in text
    assert "Available" in text or "Not available" in text

def test_build_fish_embed_no_variants_section(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    assert "Variants" not in _all_text(embed)

def test_build_fish_embed_with_variants():
    from utils.embeds import build_fish_embed
    c = make_creature(variants=[{"name": "Chroma", "chance": 2}])
    embed = build_fish_embed(c, make_mock_client())
    assert "Variants" in _all_text(embed)

def test_build_fish_embed_resolves_location_names():
    from utils.embeds import build_fish_embed
    loc = make_location(id="loc1", name="Sunken Ship")
    c = make_creature(locations=["loc1"])
    embed = build_fish_embed(c, make_mock_client(locations=[loc]))
    assert "Sunken Ship" in _all_text(embed)

def test_build_fish_embed_footer(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    assert embed.footer.text == "Internal ID: goldfish"



# --- Peak hours embed ---

def test_build_peak_hours_embed_contains_grid(creature):
    from utils.embeds import build_peak_hours_embed
    embed = build_peak_hours_embed(creature)
    desc = embed.description
    assert "00 01 02" in desc   # first row header present
    assert "12 13 14" in desc   # second row header present
    assert "✅" in desc or "❌" in desc  # availability marks present

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

def test_build_fishlist_embed_footer_format():
    from utils.embeds import build_fishlist_embed
    creatures = [make_creature()]
    embed = build_fishlist_embed(creatures, page=0, total_pages=3, sort="alphabetical", rarity_filter="All")
    assert "Page 1 / 3" in embed.footer.text
    assert "Sort: alphabetical" in embed.footer.text
    assert "Rarity: All" in embed.footer.text


# --- Location embeds ---

def test_build_location_embed_title(location):
    from utils.embeds import build_location_embed
    embed = build_location_embed(location, make_mock_client())
    assert "Sunken Ship" in embed.title

def test_build_location_embed_has_stats(location):
    from utils.embeds import build_location_embed
    embed = build_location_embed(location, make_mock_client())
    text = _all_text(embed)
    assert "Fail" in text
    assert "Mines" in text

def test_build_location_embed_rarity_distribution(location):
    from utils.embeds import build_location_embed
    embed = build_location_embed(location, make_mock_client())
    text = _all_text(embed)
    assert "Rarity" in text

def test_build_location_embed_temporary_badge():
    from utils.embeds import build_location_embed
    loc = make_location(temporary=True)
    embed = build_location_embed(loc, make_mock_client())
    assert "Temporary" in _all_text(embed)

def test_build_location_compare_embed_title():
    from utils.embeds import build_location_compare_embed
    l1 = make_location(name="Ocean")
    l2 = make_location(id="lake", name="Lake")
    embed = build_location_compare_embed(l1, l2)
    assert "Ocean" in embed.title
    assert "Lake" in embed.title

def test_build_locations_list_embed_title():
    from utils.embeds import build_locations_list_embed
    locs = [make_location()]
    embed = build_locations_list_embed(locs, 0, 1, "name", "All")
    assert "Location" in embed.title


# --- Tool embeds ---

def test_build_tool_embed_title(tool):
    from utils.embeds import build_tool_embed
    embed = build_tool_embed(tool)
    assert embed.title == "Fishing Rod"

def test_build_tool_embed_has_buffs(tool):
    from utils.embeds import build_tool_embed
    embed = build_tool_embed(tool)
    text = _all_text(embed)
    assert "Buff" in text

def test_build_tool_embed_bait_support(tool):
    from utils.embeds import build_tool_embed
    embed = build_tool_embed(tool)
    text = _all_text(embed)
    assert "\u2705" in text



def test_build_npc_embed_title():
    from utils.embeds import build_npc_embed
    from unittest.mock import MagicMock
    from dankmemer.utils import DotDict
    from dankmemer.routes.npcs import NPC  # may vary; adjust if import path differs
    npc = MagicMock()
    npc.name = "Poseidon"
    npc.imageURL = "https://example.com/npc.png"
    npc.id = "poseidon"
    npc.extra = DotDict({"description": "God of the sea.", "locations": ["loc1"]})
    embed = build_npc_embed(npc)
    assert embed.title == "Poseidon"


# --- History embed — simulation tab ---

def test_build_history_embed_simulation_shows_fail_percent():
    from utils.embeds import build_history_embed

    class FakeRow(dict):
        pass

    row = FakeRow({
        "item_id": "river",
        "data": json.dumps({"failChance": 15.3}),
        "created_at": "2026-01-01 12:00:00",
    })
    rows = [row]
    member = MagicMock()
    member.display_name = "Tester"
    embed = build_history_embed(rows, member, "simulation")
    assert "15.3" in embed.description
    assert "river" in embed.description
