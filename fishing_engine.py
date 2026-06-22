"""Local Dank Memer fishing simulator engine.

Reproduces the live simulator API's catch-probability output from data.json
game data plus the committed loot-weight table. Pure functions — no Discord or
DB imports. See docs/superpowers/specs/2026-06-23-phase4-local-engine-design.md
for the reverse-engineering evidence.
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

# npcChance per tool (sampled, exact). Default 0.50 for unlisted tools.
TOOL_NPC_CHANCE = {
    "fishing-rod": 0.575,
    "dynamite": 0.625,
}
_DEFAULT_NPC = 0.50

# Baits the engine cannot compute exactly -> caller uses the live API.
API_FALLBACK_BAITS = frozenset({
    "lucky-bait", "ghastly-bait", "gift-bait", "work-bait", "farmer-bait",
})

# Baits that change the catch distribution by a derivable transform.
_VINTAGE = "vintage-bait"
_TIMELY = "timely-bait"
_MAGNET = "magnet-bait"
_HEART = "heart-bait"


class FallbackBaitError(Exception):
    """Raised when local_simulate is asked for a bait only the live API can do."""


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
    """Whether a creature's parsed time window includes `hour` (0-23).

    Accepts the dankmemer-library-parsed shape: {full_day} or {start, end} where
    start/end are datetime.time (runtime) or ints (raw). A window where
    start.hour > end.hour spans midnight (this is how the library represents a
    reversed window after swapping). Endpoints are inclusive.
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
    reversed_flag = _get(time_obj, "reversed")
    if sh <= eh:
        return sh <= hour <= eh
    # start.hour > end.hour: two interpretations.
    # reversed=True → genuine midnight-spanning window: active at hour >= sh OR hour <= eh.
    # eh==0 and not reversed → original end=24 was parsed to time(0,0); window is sh..23.
    #   (parse_time_info converts end=24 → time(0,0) but only adds full_day when start=0)
    if reversed_flag:
        return hour >= sh or hour <= eh
    if eh == 0:
        # end=24 sentinel: active from sh through end-of-day (hour 23), NOT wrapping
        return hour >= sh
    # Fallback: treat as midnight-spanning even without reversed flag
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


def _eligible_weight_and_list(dc, location_id, tool_id, hour, *, bosses, ignore_time):
    fish = []
    total_w = 0.0
    for creature in dc.fish_by_id.values():
        if creature_eligible(creature, location_id, tool_id, hour,
                             bosses=bosses, ignore_time=ignore_time):
            w = RARITY_WEIGHTS.get(_get(creature.extra, "rarity"), 0.0)
            fish.append((creature, w))
            total_w += w
    return fish, total_w


def local_simulate(dc, *, location_id, tool_id, bait_id, hour,
                   bosses=False, angler_tuesday=False) -> dict:
    """Compute an API-shaped simulation result locally.

    Returns {failChance, npcChance, table, variants}. The table holds one
    fish-creature entry per eligible creature plus a single aggregate loot
    entry (value.type == "loot"). variants is always {}.
    Raises FallbackBaitError for baits only the live API can compute.
    """
    if bait_id in API_FALLBACK_BAITS:
        raise FallbackBaitError(bait_id)

    location = dc.location_by_id.get(location_id)
    fail = 0 if angler_tuesday else (_get(location.extra, "failChance", 0) if location else 0)
    npc = TOOL_NPC_CHANCE.get(tool_id, _DEFAULT_NPC)
    if bait_id == _HEART:
        npc += 2.0

    ignore_time = bait_id == _TIMELY
    fish, fish_w = _eligible_weight_and_list(
        dc, location_id, tool_id, hour, bosses=bosses, ignore_time=ignore_time
    )

    # Loot weight from the static table (hour-specific).
    loot_w = 0.0
    row = (dc.loot_weights or {}).get(location_id)
    if row and 0 <= hour < len(row):
        loot_w = row[hour]
    if bait_id == _VINTAGE:
        loot_w *= 0.5

    if bait_id == _MAGNET:
        # magnet bait: catch only loot; fish weight effectively removed from pool
        fish_w = 0.0

    total_w = fish_w + loot_w
    table = []
    if total_w > 0:
        if bait_id != _MAGNET:
            for creature, w in fish:
                chance = w / total_w * 100.0
                table.append({
                    "chance": chance,
                    "baseChance": chance,
                    "value": {"type": "fish-creature", "creatureID": creature.id},
                })
        if loot_w > 0:
            loot_pct = loot_w / total_w * 100.0
            table.append({
                "chance": loot_pct,
                "baseChance": loot_pct,
                "value": {"type": "loot"},
            })

    return {"failChance": fail, "npcChance": npc, "table": table, "variants": {}}
