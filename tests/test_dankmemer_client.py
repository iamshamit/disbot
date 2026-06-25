import json
import pytest
from pathlib import Path
from scripts.generate_loot_table import derive_loot_weight, RARITY_WEIGHTS
from dankmemer_client import _parse_skill_categories


def _fish_weight_for(api_result, creatures_by_id):
    """Sum rarity weights of the fish-creatures present in an API result."""
    total = 0.0
    for entry in api_result["table"]:
        v = entry["value"]
        if v.get("type") == "fish-creature":
            cid = v["creatureID"]
            rarity = creatures_by_id[cid]["extra"]["rarity"]
            total += RARITY_WEIGHTS[rarity]
    return total


def test_derive_loot_weight_matches_lake_sample():
    root = Path(__file__).resolve().parent.parent
    data = json.loads((root / "data.json").read_text(encoding="utf-8"))["data"]
    creatures_by_id = {c["id"]: c for c in data["creatures"]["items"]}
    locs = json.loads((root / "sampling_data" / "locations.json").read_text(encoding="utf-8"))
    lake = next(r for r in locs if r["location_id"] == "lake")
    fish_w = _fish_weight_for(lake["result"], creatures_by_id)
    loot_w = derive_loot_weight(lake["result"], fish_w)
    # lake @ hour 12 baseline: total weight 85.2, fish 79.5 -> loot 5.7
    assert round(loot_w, 4) == 5.7


def test_parse_skill_categories_groups_by_category():
    items = [
        {"id": "haggler-1", "name": "Haggler I", "extra": {"category": "Economy", "description": ""}},
        {"id": "haggler-2", "name": "Haggler II", "extra": {"category": "Economy", "description": ""}},
        {"id": "zoologist-1", "name": "Zoologist I", "extra": {"category": "Nature", "description": ""}},
    ]
    cats = _parse_skill_categories(items)
    assert "Economy" in cats
    assert "Nature" in cats
    assert cats["Economy"][0]["base"] == "haggler"
    assert cats["Economy"][0]["max_tier"] == 2
    assert cats["Nature"][0]["base"] == "zoologist"
    assert cats["Nature"][0]["max_tier"] == 1


def test_parse_skill_categories_strips_roman_suffix():
    items = [
        {"id": "keen-angler-3", "name": "Keen Angler III", "extra": {"category": "Nature", "description": ""}},
    ]
    cats = _parse_skill_categories(items)
    assert cats["Nature"][0]["name"] == "Keen Angler"


def test_parse_skill_categories_skips_malformed_ids():
    items = [
        {"id": "no-dash", "name": "No Dash", "extra": {"category": "Economy", "description": ""}},
    ]
    cats = _parse_skill_categories(items)
    assert cats == {}
