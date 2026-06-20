import pytest
from unittest.mock import MagicMock
from tests.conftest import make_creature, make_location, make_tool, make_bait
import discord


def make_npc(id="fisherman", name="Old Fisherman"):
    npc = MagicMock()
    npc.id = id
    npc.name = name
    return npc


def make_client(creatures=None, locations=None, tools=None, baits=None, npcs=None):
    client = MagicMock()
    client.fish_by_id = {c.id: c for c in (creatures or [])}
    client.location_by_id = {l.id: l for l in (locations or [])}
    client.tool_by_id = {t.id: t for t in (tools or [])}
    client.bait_by_id = {b.id: b for b in (baits or [])}
    client.npc_by_id = {n.id: n for n in (npcs or [])}
    return client


def make_index(client=None):
    from utils.autocomplete import AutocompleteIndex
    return AutocompleteIndex(client or make_client())


# --- _choices helper ---

def test_choices_returns_up_to_25():
    idx = make_index(make_client(
        creatures=[make_creature(id=f"fish_{i}", name=f"Fish {i}") for i in range(30)]
    ))
    results = idx.fish_choices("")
    assert len(results) == 25


def test_choices_filters_case_insensitive():
    idx = make_index(make_client(
        creatures=[
            make_creature(id="gold", name="Goldfish"),
            make_creature(id="trout", name="Rainbow Trout"),
        ]
    ))
    results = idx.fish_choices("gold")
    assert len(results) == 1
    assert results[0].name == "Goldfish"


def test_choices_empty_current_returns_all():
    idx = make_index(make_client(
        creatures=[make_creature(id="a", name="Alpha"), make_creature(id="b", name="Beta")]
    ))
    results = idx.fish_choices("")
    assert len(results) == 2


def test_choices_no_match_returns_empty():
    idx = make_index(make_client(creatures=[make_creature()]))
    results = idx.fish_choices("zzznomatch")
    assert results == []


def test_choices_returns_app_commands_choice():
    idx = make_index(make_client(creatures=[make_creature(name="Goldfish")]))
    results = idx.fish_choices("gold")
    assert isinstance(results[0], discord.app_commands.Choice)
    assert results[0].value == "Goldfish"


# --- fish_choices ---

def test_fish_choices_basic():
    idx = make_index(make_client(
        creatures=[make_creature(id="koi", name="Koi"), make_creature(id="bass", name="Bass")]
    ))
    results = idx.fish_choices("koi")
    assert len(results) == 1
    assert results[0].name == "Koi"


# --- location_choices ---

def test_location_choices_match():
    idx = make_index(make_client(
        locations=[make_location(id="ship", name="Sunken Ship"), make_location(id="reef", name="Coral Reef")]
    ))
    results = idx.location_choices("reef")
    assert len(results) == 1
    assert results[0].name == "Coral Reef"


def test_location_choices_empty_current():
    idx = make_index(make_client(
        locations=[make_location(id="a", name="Loc A"), make_location(id="b", name="Loc B")]
    ))
    results = idx.location_choices("")
    assert len(results) == 2


# --- tool_choices ---

def test_tool_choices_match():
    from tests.conftest import make_tool
    idx = make_index(make_client(
        tools=[make_tool(id="rod", name="Fishing Rod"), make_tool(id="net", name="Cast Net")]
    ))
    results = idx.tool_choices("rod")
    assert len(results) == 1
    assert results[0].name == "Fishing Rod"


def test_tool_choices_case_insensitive():
    from tests.conftest import make_tool
    idx = make_index(make_client(
        tools=[make_tool(id="rod", name="Fishing Rod")]
    ))
    results = idx.tool_choices("FISHING")
    assert len(results) == 1


def test_tool_choices_no_match():
    from tests.conftest import make_tool
    idx = make_index(make_client(tools=[make_tool()]))
    results = idx.tool_choices("xyz")
    assert results == []


# --- bait_choices ---

def test_bait_choices_match():
    from tests.conftest import make_bait
    idx = make_index(make_client(
        baits=[make_bait(id="glitter", name="Glitter Bait"), make_bait(id="worm", name="Worm Bait")]
    ))
    results = idx.bait_choices("glitter")
    assert len(results) == 1
    assert results[0].name == "Glitter Bait"


def test_bait_choices_empty_current():
    from tests.conftest import make_bait
    idx = make_index(make_client(
        baits=[make_bait(id="a", name="Bait A"), make_bait(id="b", name="Bait B")]
    ))
    results = idx.bait_choices("")
    assert len(results) == 2


def test_bait_choices_no_match():
    from tests.conftest import make_bait
    idx = make_index(make_client(baits=[make_bait()]))
    results = idx.bait_choices("zzz")
    assert results == []


# --- npc_choices ---

def test_npc_choices_match():
    idx = make_index(make_client(
        npcs=[make_npc(id="fisherman", name="Old Fisherman"), make_npc(id="trader", name="Sea Trader")]
    ))
    results = idx.npc_choices("fisherman")
    assert len(results) == 1
    assert results[0].name == "Old Fisherman"


def test_npc_choices_empty_current():
    idx = make_index(make_client(
        npcs=[make_npc(id="a", name="NPC A"), make_npc(id="b", name="NPC B")]
    ))
    results = idx.npc_choices("")
    assert len(results) == 2


def test_npc_choices_no_match():
    idx = make_index(make_client(npcs=[make_npc()]))
    results = idx.npc_choices("xyz")
    assert results == []


def test_npc_choices_case_insensitive():
    idx = make_index(make_client(
        npcs=[make_npc(id="fisherman", name="Old Fisherman")]
    ))
    results = idx.npc_choices("OLD")
    assert len(results) == 1
