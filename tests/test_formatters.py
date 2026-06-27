import pytest
from utils.formatters import (
    rarity_color, rarity_emoji, rarity_rank,
    progress_bar, availability_bar,
    is_available_now, format_time_window, winner_mark,
    BOSS_COLOR, LOCATION_COLOR, TOOL_COLOR, BAIT_COLOR, NPC_COLOR, COMPARE_COLOR,
)
from tests.conftest import make_creature


def test_rarity_color_common():
    assert rarity_color("Common") == 0x57f287

def test_rarity_color_boss_overrides():
    assert rarity_color("Common", boss=True) == BOSS_COLOR

def test_rarity_color_unknown_returns_default():
    assert rarity_color("Unknown") == rarity_color("Common")  # falls back to Common colour

def test_rarity_emoji_known():
    assert rarity_emoji("Rare") == "🟡"

def test_rarity_emoji_unknown():
    result = rarity_emoji("Alien Tier")
    assert isinstance(result, str) and len(result) > 0

def test_rarity_rank_order():
    assert rarity_rank("Absurdly Common") < rarity_rank("Very Common") < rarity_rank("Common")
    assert rarity_rank("Common") < rarity_rank("Regular") < rarity_rank("Rare")
    assert rarity_rank("Rare") < rarity_rank("Very Rare") < rarity_rank("Absurdly Rare")

def test_rarity_rank_unknown():
    assert rarity_rank("Unknown") == -1

def test_progress_bar_full():
    bar = progress_bar(20, 20, width=20)
    assert bar == "█" * 20

def test_progress_bar_empty():
    bar = progress_bar(0, 20, width=20)
    assert bar == "░" * 20

def test_progress_bar_half():
    bar = progress_bar(10, 20, width=20)
    assert bar == "█" * 10 + "░" * 10

def test_progress_bar_zero_total():
    bar = progress_bar(0, 0, width=10)
    assert bar == "░" * 10

def test_availability_bar_length():
    bar = availability_bar(0, 6, full_day=False)
    assert len(bar) == 24

def test_availability_bar_full_day():
    bar = availability_bar(0, 0, full_day=True)
    assert bar == "█" * 24

def test_availability_bar_first_6_hours():
    bar = availability_bar(0, 6, full_day=False)
    assert bar[:6] == "█" * 6
    assert bar[6:] == "░" * 18

def test_availability_bar_wraps_midnight():
    # 22:00 to 02:00 — hours 22,23,0,1 are available
    bar = availability_bar(22, 2, full_day=False)
    assert bar[22] == "█"
    assert bar[23] == "█"
    assert bar[0] == "█"
    assert bar[1] == "█"
    assert bar[2] == "░"
    assert bar[10] == "░"

def test_is_available_now_full_day():
    c = make_creature(full_day=True)
    assert is_available_now(c) is True

def test_is_available_now_missing_time():
    from dankmemer.utils import DotDict
    from dankmemer.routes.creatures import Creature
    c = Creature(id="x", name="X", imageURL="", extra=DotDict({"time": {}}))
    assert is_available_now(c) is True  # unknown → assume available

def test_format_time_window_full_day():
    c = make_creature(full_day=True)
    assert format_time_window(c) == "All Day"

def test_format_time_window_normal():
    c = make_creature(start_h=0, end_h=6, full_day=False)
    assert format_time_window(c) == "00:00–06:00 UTC · 6h"

def test_winner_mark_higher_wins():
    a, b = winner_mark(10, 5)
    assert "✓" in a
    assert "✓" not in b

def test_winner_mark_lower_wins():
    a, b = winner_mark(3, 7, higher_is_better=False)
    assert "✓" in a
    assert "✓" not in b

def test_winner_mark_tie():
    a, b = winner_mark(5, 5)
    assert "✓" not in a
    assert "✓" not in b
