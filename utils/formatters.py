from __future__ import annotations
from datetime import datetime, timezone, time as dt_time
from typing import Any

RARITY_COLORS: dict[str, int] = {
    "Common":        0x8e9297,
    "Uncommon":      0x57f287,
    "Rare":          0x5865f2,
    "Very Rare":     0xeb459e,
    "Absurdly Rare": 0xed4245,
    "Mythical":      0xffd700,
}
BOSS_COLOR     = 0xff6b35
LOCATION_COLOR = 0x00b4d8
TOOL_COLOR     = 0xff9500
BAIT_COLOR     = 0x95d44a
NPC_COLOR      = 0xb967ff
COMPARE_COLOR  = 0x5865f2

RARITY_EMOJI: dict[str, str] = {
    "Common":        "⚪",
    "Uncommon":      "🟢",
    "Rare":          "🔵",
    "Very Rare":     "🟣",
    "Absurdly Rare": "🔴",
    "Mythical":      "🌟",
}

RARITY_ORDER = ["Common", "Uncommon", "Rare", "Very Rare", "Absurdly Rare", "Mythical"]


def rarity_color(rarity: str, boss: bool = False) -> int:
    if boss:
        return BOSS_COLOR
    return RARITY_COLORS.get(rarity, RARITY_COLORS["Common"])


def rarity_emoji(rarity: str) -> str:
    return RARITY_EMOJI.get(rarity, "⚫")


def rarity_rank(rarity: str) -> int:
    try:
        return RARITY_ORDER.index(rarity)
    except ValueError:
        return -1


def progress_bar(value: int | float, total: int | float, width: int = 20) -> str:
    filled = round((value / total) * width) if total else 0
    filled = max(0, min(filled, width))
    return "█" * filled + "░" * (width - filled)


def availability_bar(start_h: int, end_h: int, full_day: bool) -> str:
    if full_day:
        return "█" * 24
    chars = []
    for h in range(24):
        if start_h <= end_h:
            chars.append("█" if start_h <= h < end_h else "░")
        else:
            chars.append("█" if h >= start_h or h < end_h else "░")
    return "".join(chars)


def is_available_now(creature) -> bool:
    time_data = creature.extra.get("time", {}) if hasattr(creature.extra, "get") else {}
    if time_data.get("full_day"):
        return True
    start = time_data.get("start")
    end = time_data.get("end")
    if not isinstance(start, dt_time) or not isinstance(end, dt_time):
        return True
    now = datetime.now(timezone.utc).time().replace(second=0, microsecond=0)
    if start <= end:
        return start <= now < end
    return now >= start or now < end


def format_time_window(creature) -> str:
    time_data = creature.extra.get("time", {}) if hasattr(creature.extra, "get") else {}
    if time_data.get("full_day"):
        return "All Day"
    start = time_data.get("start")
    end = time_data.get("end")
    if not isinstance(start, dt_time) or not isinstance(end, dt_time):
        return "Unknown"
    start_h, end_h = start.hour, end.hour
    hours = (end_h - start_h) if start_h <= end_h else (24 - start_h + end_h)
    return f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')} UTC · {hours}h"


def winner_mark(a: Any, b: Any, higher_is_better: bool = True) -> tuple[str, str]:
    try:
        a_wins = (a > b) if higher_is_better else (a < b)
        b_wins = (b > a) if higher_is_better else (b < a)
    except TypeError:
        return str(a), str(b)
    if a_wins:
        return f"{a} ✓", str(b)
    if b_wins:
        return str(a), f"{b} ✓"
    return str(a), str(b)
