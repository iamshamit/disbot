"""Pure metadata helpers for Dank Memer fishing data.

Reads creature.extra fields (locations, tools, boss, mythical, time windows)
from data.json game data. No API calls, no simulation — just eligibility
checks and constants used by the optimizer, utilities, and simulator.
"""
from __future__ import annotations

RARITY_WEIGHTS = {
    "Absurdly Common": 18.5,
    "Very Common": 16.5,
    "Common": 14.5,
    "Regular": 10.0,
    "Rare": 6.5,
    "Very Rare": 1.0,
    "Absurdly Rare": 0.075,
}


def _get(obj, key, default=None):
    """Read a key from a dict-like or attribute-like extra object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    if hasattr(obj, "get"):
        return obj.get(key, default)
    return getattr(obj, key, default)


def is_time_active(time_obj, hour: int) -> bool:
    """Whether a creature's parsed time window includes ``hour`` (0-23).

    Accepts the dankmemer-library-parsed shape: ``{full_day}`` or
    ``{start, end}`` where start/end are ``datetime.time`` (runtime) or ints
    (raw).  A window where ``start.hour > end.hour`` spans midnight (this is
    how the library represents a reversed window after swapping).  Endpoints
    are inclusive.
    """
    if not time_obj:
        return True
    if _get(time_obj, "full_day"):
        return True
    start = _get(time_obj, "start")
    end = _get(time_obj, "end")
    if start is None or end is None:
        return True
    sh = start.hour if hasattr(start, "hour") else int(start)
    eh = end.hour if hasattr(end, "hour") else int(end)
    reversed_flag = bool(_get(time_obj, "reversed", False))
    if sh <= eh:
        return sh <= hour <= eh
    if reversed_flag:
        return hour >= sh or hour <= eh
    if eh == 0:
        return hour >= sh
    return hour >= sh or hour <= eh


def creature_eligible(creature, location_id, tool_id, hour, *, bosses, ignore_time) -> bool:
    """Return True if this creature is eligible for the given location/tool/hour."""
    extra = creature.extra
    if location_id not in (_get(extra, "locations") or []):
        return False
    if _get(extra, "boss", False) and not bosses:
        return False
    if _get(extra, "mythical", False):
        return False
    tools = _get(extra, "tools") or {}
    tool_compat = _get(tools, tool_id) or {}
    if (_get(tool_compat, "max", 0) or 0) <= 0:
        return False
    if ignore_time:
        return True
    return is_time_active(_get(extra, "time"), hour)
