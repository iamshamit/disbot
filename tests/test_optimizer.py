from __future__ import annotations
from unittest.mock import MagicMock
from tests.conftest import make_creature, make_tool, make_location


def _make_dc():
    """Two locations, one tool, three fish — enough for all optimizer tests."""
    rod = make_tool(id="fishing-rod", name="Fishing Rod")
    ocean = make_location(id="ocean", name="Ocean")
    lake = make_location(id="lake", name="Lake")
    # Common, ocean-only, available all day
    bass = make_creature(
        id="bass", name="Bass", rarity="Common",
        locations=["ocean"],
        tools={"fishing-rod": {"min": 1, "max": 2}},
        full_day=True,
    )
    # Rare, ocean-only, available hours 0–6 inclusive
    koi = make_creature(
        id="koi", name="Koi", rarity="Rare",
        locations=["ocean"],
        tools={"fishing-rod": {"min": 1, "max": 3}},
        full_day=False, start_h=0, end_h=6,
    )
    # Common, lake-only, available all day
    trout = make_creature(
        id="trout", name="Trout", rarity="Common",
        locations=["lake"],
        tools={"fishing-rod": {"min": 1, "max": 2}},
        full_day=True,
    )
    dc = MagicMock()
    dc.fish_by_id = {"bass": bass, "koi": koi, "trout": trout}
    dc.tool_by_id = {"fishing-rod": rod}
    dc.location_by_id = {"ocean": ocean, "lake": lake}
    return dc


def test_score_setup_sums_rarity_weights():
    from utils.optimizer import score_setup
    from fishing_engine import RARITY_WEIGHTS
    dc = _make_dc()
    # At hour 3: bass (Common=14.5, rod.max=2) + koi (Rare=6.5, rod.max=3)
    score = score_setup(dc, "fishing-rod", "ocean", 3)
    expected = RARITY_WEIGHTS["Common"] * 2 + RARITY_WEIGHTS["Rare"] * 3
    assert abs(score - expected) < 0.001


def test_score_setup_zero_when_no_eligible_fish():
    from utils.optimizer import score_setup
    dc = _make_dc()
    # "net" not in any fish's tools dict → no eligible fish
    score = score_setup(dc, "net", "ocean", 3)
    assert score == 0.0


def test_best_setups_ranked_by_score():
    from utils.optimizer import best_setups
    dc = _make_dc()
    # At hour 3: ocean gets bass+koi (21.0), lake gets only trout (14.5)
    results = best_setups(dc, hour=3, limit=3)
    assert len(results) >= 2
    assert results[0]["location"].id == "ocean"
    assert results[0]["score"] > results[1]["score"]


def test_best_setups_target_filters_correctly():
    from utils.optimizer import best_setups
    # Add a second tool that cannot catch koi (not in koi's tools dict)
    dc = _make_dc()
    net = make_tool(id="net", name="Net")
    dc.tool_by_id["net"] = net
    # koi only has "fishing-rod"; net should be excluded
    results = best_setups(dc, hour=3, target_fish_id="koi")
    tool_ids = [r["tool"].id for r in results]
    assert "fishing-rod" in tool_ids
    assert "net" not in tool_ids


def test_best_setups_target_not_catchable_returns_empty():
    from utils.optimizer import best_setups
    dc = _make_dc()
    # koi window is 0–6; at hour 12 it's outside that window
    results = best_setups(dc, hour=12, target_fish_id="koi")
    assert results == []


def test_session_windows_tracks_opens_and_closes():
    from utils.optimizer import session_windows
    dc = _make_dc()
    # Hours 5, 6, 7 at ocean:
    # h5: bass+koi eligible (koi window 0–6 inclusive → 5 in [0,6])
    # h6: bass+koi eligible (6 in [0,6])
    # h7: only bass (7 > 6, koi window ends)
    windows = session_windows(dc, "ocean", start_hour=5, duration_hours=3)
    assert len(windows) == 3
    # First window: opens = all fish at that hour, closes = empty
    assert "koi" in windows[0]["opens"]
    assert "bass" in windows[0]["opens"]
    assert windows[0]["closes"] == set()
    # Third window: koi closes
    assert "koi" in windows[2]["closes"]
    assert "bass" not in windows[2]["closes"]
