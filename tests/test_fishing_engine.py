"""Tests for fishing_engine.py — TDD order: time/eligibility first, then local_simulate."""
from datetime import time as dt_time
from fishing_engine import (
    is_time_active, creature_eligible, local_simulate,
    RARITY_WEIGHTS, TOOL_NPC_CHANCE, API_FALLBACK_BAITS, FallbackBaitError,
)


def test_is_time_active_normal_window():
    # parsed normal window 9..16 (start.hour <= end.hour) -> inclusive both ends
    t = {"start": dt_time(hour=9), "end": dt_time(hour=16)}
    assert is_time_active(t, 9) is True
    assert is_time_active(t, 16) is True
    assert is_time_active(t, 8) is False
    assert is_time_active(t, 17) is False


def test_is_time_active_midnight_spanning():
    # parsed reversed window appears as start.hour > end.hour (e.g. 22..15)
    t = {"start": dt_time(hour=22), "end": dt_time(hour=15)}
    assert is_time_active(t, 23) is True
    assert is_time_active(t, 10) is True
    assert is_time_active(t, 22) is True
    assert is_time_active(t, 15) is True
    assert is_time_active(t, 18) is False


def test_is_time_active_full_day_and_missing():
    assert is_time_active({"full_day": True, "start": dt_time(0), "end": dt_time(0)}, 5) is True
    assert is_time_active(None, 5) is True


# ---------------------------------------------------------------------------
# local_simulate integration tests — use committed fixtures, no live API calls
# ---------------------------------------------------------------------------

import json
from pathlib import Path
from types import SimpleNamespace
from dankmemer.routes.creatures import parse_time_info

_ROOT = Path(__file__).resolve().parent.parent


def _fake_dc():
    data = json.loads((_ROOT / "data.json").read_text(encoding="utf-8"))["data"]
    fish_by_id = {}
    for c in data["creatures"]["items"]:
        extra = dict(c["extra"])
        if "time" in extra and extra["time"]:
            extra["time"] = parse_time_info(dict(extra["time"]))
        fish_by_id[c["id"]] = SimpleNamespace(id=c["id"], name=c["name"], extra=extra)
    location_by_id = {
        l["id"]: SimpleNamespace(id=l["id"], name=l["name"], extra=dict(l["extra"]))
        for l in data["locations"]["items"]
    }
    loot_weights = json.loads((_ROOT / "data" / "loot_weights.json").read_text(encoding="utf-8"))
    return SimpleNamespace(
        fish_by_id=fish_by_id, location_by_id=location_by_id, loot_weights=loot_weights,
    )


def _api_fish(result):
    return {e["value"]["creatureID"]: e["chance"]
            for e in result["table"] if e["value"].get("type") == "fish-creature"}


def _engine_fish(result):
    return {e["value"]["creatureID"]: e["chance"]
            for e in result["table"] if e["value"].get("type") == "fish-creature"}


def test_local_simulate_matches_all_locations_at_hour_12():
    dc = _fake_dc()
    locs = json.loads((_ROOT / "sampling_data" / "locations.json").read_text(encoding="utf-8"))
    for rec in locs:
        loc = rec["location_id"]
        api = _api_fish(rec["result"])
        if not api:
            continue
        out = local_simulate(dc, location_id=loc, tool_id="fishing-rod",
                             bait_id=None, hour=12)
        eng = _engine_fish(out)
        assert set(eng) == set(api), f"{loc}: creature set mismatch — extra={set(eng)-set(api)}, missing={set(api)-set(eng)}"
        for cid, chance in api.items():
            assert abs(eng[cid] - chance) < 1e-6, f"{loc}/{cid}: {eng[cid]} vs {chance}"
        assert out["failChance"] == rec["result"]["failChance"]
        assert abs(out["npcChance"] - rec["result"]["npcChance"]) < 1e-6


def test_local_simulate_matches_lake_all_24_hours():
    dc = _fake_dc()
    time_data = json.loads((_ROOT / "sampling_data" / "time.json").read_text(encoding="utf-8"))
    for rec in time_data:
        hour = rec["hour"]
        api = _api_fish(rec["result"])
        out = local_simulate(dc, location_id="lake", tool_id="fishing-rod",
                             bait_id=None, hour=hour)
        eng = _engine_fish(out)
        assert set(eng) == set(api), f"hour {hour}: creature set mismatch — extra={set(eng)-set(api)}, missing={set(api)-set(eng)}"
        for cid, chance in api.items():
            assert abs(eng[cid] - chance) < 1e-6, f"hour {hour}/{cid}"


def test_local_simulate_angler_tuesday_zeros_fail():
    dc = _fake_dc()
    out = local_simulate(dc, location_id="lake", tool_id="fishing-rod",
                         bait_id=None, hour=12, angler_tuesday=True)
    assert out["failChance"] == 0


def test_local_simulate_npc_chance_by_tool():
    dc = _fake_dc()
    rod = local_simulate(dc, location_id="lake", tool_id="fishing-rod", bait_id=None, hour=12)
    net = local_simulate(dc, location_id="lake", tool_id="net", bait_id=None, hour=12)
    assert abs(rod["npcChance"] - 0.575) < 1e-6
    assert abs(net["npcChance"] - 0.50) < 1e-6


def test_local_simulate_time_bait_ignores_time_filter():
    # bluegill: normal window start=2..end=15 — inactive at hour 16 without time-bait
    dc = _fake_dc()
    without = local_simulate(dc, location_id="lake", tool_id="fishing-rod", bait_id=None, hour=16)
    with_time = local_simulate(dc, location_id="lake", tool_id="fishing-rod", bait_id="time-bait", hour=16)
    without_ids = {e["value"]["creatureID"] for e in without["table"] if e["value"].get("type") == "fish-creature"}
    with_ids = {e["value"]["creatureID"] for e in with_time["table"] if e["value"].get("type") == "fish-creature"}
    assert "bluegill" not in without_ids, "bluegill should be time-gated at hour 16"
    assert "bluegill" in with_ids, "time-bait should override time filter"


def test_local_simulate_fallback_bait_raises():
    dc = _fake_dc()
    try:
        local_simulate(dc, location_id="lake", tool_id="fishing-rod",
                       bait_id="lucky-bait", hour=12)
        assert False, "expected FallbackBaitError"
    except FallbackBaitError:
        pass
