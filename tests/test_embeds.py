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
    assert "▐" in embed.description  # bar prefix
    assert "▌" in embed.description  # bar suffix

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
    # c2 has more locations → its column field value should contain ✓
    assert any("✓" in f.value for f in embed.fields)

def test_build_fish_compare_embed_uses_fields():
    from utils.embeds import build_fish_compare_embed
    c1 = make_creature(name="Goldfish")
    c2 = make_creature(id="koi", name="Koi", rarity="Rare")
    embed = build_fish_compare_embed(c1, c2)
    assert len(embed.fields) == 3  # labels + c1 + c2
    assert embed.fields[1].name == "Goldfish"
    assert embed.fields[2].name == "Koi"


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
    assert "Filter: All" in embed.footer.text


# --- Location embeds ---

def test_build_location_embed_title(location):
    from utils.embeds import build_location_embed
    embed = build_location_embed(location, make_mock_client())
    assert embed.title == "Sunken Ship"

def test_build_location_embed_has_stats(location):
    from utils.embeds import build_location_embed
    embed = build_location_embed(location, make_mock_client())
    assert "Fail" in embed.description
    assert "Mine" in embed.description

def test_build_location_embed_rarity_distribution(location):
    from utils.embeds import build_location_embed
    embed = build_location_embed(location, make_mock_client())
    assert "RARITY" in embed.description

def test_build_location_embed_temporary_badge():
    from utils.embeds import build_location_embed
    loc = make_location(temporary=True)
    embed = build_location_embed(loc, make_mock_client())
    assert "Temporary" in embed.description

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
    assert "BUFF" in embed.description

def test_build_tool_embed_bait_support(tool):
    from utils.embeds import build_tool_embed
    embed = build_tool_embed(tool)
    assert "✅" in embed.description

def test_build_toolcompare_embed_contains_all_tools():
    from utils.embeds import build_toolcompare_embed
    t1 = make_tool(name="Rod")
    t2 = make_tool(id="harpoon", name="Harpoon", baits=False, usage=50)
    embed = build_toolcompare_embed([t1, t2])
    assert "Rod" in embed.description
    assert "Harpoon" in embed.description


# --- Bait embeds ---

def test_build_bait_embed_title(bait):
    from utils.embeds import build_bait_embed
    embed = build_bait_embed(bait)
    assert embed.title == "Glitter Bait"

def test_build_bait_embed_explanation(bait):
    from utils.embeds import build_bait_embed
    embed = build_bait_embed(bait)
    assert "Rare catch" in embed.description

def test_build_bait_compare_embed_title():
    from utils.embeds import build_bait_compare_embed
    b1 = make_bait(name="Glitter")
    b2 = make_bait(id="gold", name="Gold Bait", explanation="Doubles Mythical catch.", idle=False, usage=10)
    embed = build_bait_compare_embed(b1, b2)
    assert "Glitter" in embed.title and "Gold Bait" in embed.title


# --- NPC embeds ---

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
