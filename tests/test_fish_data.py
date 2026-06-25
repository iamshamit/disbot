"""Tests for utils/fish_data.py — pure metadata helpers."""
from __future__ import annotations
from datetime import time as dt_time
from utils.fish_data import is_time_active, creature_eligible, RARITY_WEIGHTS
from tests.conftest import make_creature


# --- is_time_active ---

def test_is_time_active_normal_window():
    t = {"start": dt_time(hour=9), "end": dt_time(hour=16)}
    assert is_time_active(t, 9) is True
    assert is_time_active(t, 16) is True
    assert is_time_active(t, 8) is False
    assert is_time_active(t, 17) is False


def test_is_time_active_midnight_spanning():
    t = {"start": dt_time(hour=22), "end": dt_time(hour=15)}
    assert is_time_active(t, 23) is True
    assert is_time_active(t, 10) is True
    assert is_time_active(t, 22) is True
    assert is_time_active(t, 15) is True
    assert is_time_active(t, 18) is False


def test_is_time_active_full_day():
    assert is_time_active({"full_day": True, "start": dt_time(0), "end": dt_time(0)}, 5) is True


def test_is_time_active_none():
    assert is_time_active(None, 5) is True


def test_is_time_active_no_start_end():
    assert is_time_active({"other": "data"}, 5) is True


def test_is_time_active_reversed_true_start_lt_end():
    t = {"start": dt_time(hour=3), "end": dt_time(hour=10), "reversed": True}
    assert is_time_active(t, 3) is True
    assert is_time_active(t, 7) is True
    assert is_time_active(t, 10) is True
    assert is_time_active(t, 2) is False
    assert is_time_active(t, 11) is False


# --- creature_eligible ---

def test_creature_eligible_basic():
    c = make_creature(id="bass", locations=["ocean"], tools={"rod": {"max": 1}}, full_day=True)
    assert creature_eligible(c, "ocean", "rod", 12, bosses=False, ignore_time=False) is True


def test_creature_eligible_wrong_location():
    c = make_creature(id="bass", locations=["ocean"], tools={"rod": {"max": 1}}, full_day=True)
    assert creature_eligible(c, "lake", "rod", 12, bosses=False, ignore_time=False) is False


def test_creature_eligible_wrong_tool():
    c = make_creature(id="bass", locations=["ocean"], tools={"rod": {"max": 1}}, full_day=True)
    assert creature_eligible(c, "ocean", "net", 12, bosses=False, ignore_time=False) is False


def test_creature_eligible_boss_excluded():
    c = make_creature(id="boss", boss=True, locations=["ocean"], tools={"rod": {"max": 1}}, full_day=True)
    assert creature_eligible(c, "ocean", "rod", 12, bosses=False, ignore_time=False) is False
    assert creature_eligible(c, "ocean", "rod", 12, bosses=True, ignore_time=False) is True


def test_creature_eligible_mythical_excluded():
    c = make_creature(id="myth", mythical=True, locations=["ocean"], tools={"rod": {"max": 1}}, full_day=True)
    assert creature_eligible(c, "ocean", "rod", 12, bosses=False, ignore_time=False) is False


def test_creature_eligible_ignore_time():
    c = make_creature(id="fish", locations=["ocean"], tools={"rod": {"max": 1}},
                      full_day=False, start_h=9, end_h=16)
    assert creature_eligible(c, "ocean", "rod", 5, bosses=False, ignore_time=False) is False
    assert creature_eligible(c, "ocean", "rod", 5, bosses=False, ignore_time=True) is True


def test_creature_eligible_tool_max_zero():
    c = make_creature(id="fish", locations=["ocean"], tools={"rod": {"max": 0}}, full_day=True)
    assert creature_eligible(c, "ocean", "rod", 12, bosses=False, ignore_time=False) is False


# --- RARITY_WEIGHTS ---

def test_rarity_weights_has_all_tiers():
    expected = {"Absurdly Common", "Very Common", "Common", "Regular",
                "Rare", "Very Rare", "Absurdly Rare"}
    assert set(RARITY_WEIGHTS.keys()) == expected
