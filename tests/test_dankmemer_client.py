from dankmemer_client import _parse_skill_categories


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
