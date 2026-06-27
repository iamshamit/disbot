from __future__ import annotations
from utils.fish_data import creature_eligible, RARITY_WEIGHTS


def score_setup(dc, tool_id: str, location_id: str, hour: int) -> float:
    """Expected rare-quality score for a tool+location+hour combo.

    Weights each eligible fish by RARITY_WEIGHTS (rarity desirability only —
    per-cast quantity is intentionally excluded so tool ranking reflects what
    fish are available, not raw catch count).
    """
    total = 0.0
    for fish in dc.fish_by_id.values():
        if creature_eligible(fish, location_id, tool_id, hour, bosses=False, ignore_time=False):
            rarity = fish.extra.get("rarity", "")
            total += RARITY_WEIGHTS.get(rarity, 0.0)
    return total


def best_setups(dc, hour: int, target_fish_id: str | None = None, limit: int = 3) -> list[dict]:
    """Top tool+location combos ranked by score.

    If target_fish_id given, only returns combos where that fish is eligible.
    Boss targets use bosses=True for the target check only; scoring always uses bosses=False.
    """
    target_fish = dc.fish_by_id.get(target_fish_id) if target_fish_id else None
    is_boss_target = bool(target_fish.extra.get("boss", False)) if target_fish else False

    results = []
    for tool_id in dc.tool_by_id:
        for loc_id in dc.location_by_id:
            if target_fish is not None:
                if not creature_eligible(
                    target_fish, loc_id, tool_id, hour,
                    bosses=is_boss_target, ignore_time=False,
                ):
                    continue
            score = score_setup(dc, tool_id, loc_id, hour)
            if score == 0.0 and target_fish is None:
                continue
            results.append({
                "tool": dc.tool_by_id[tool_id],
                "location": dc.location_by_id[loc_id],
                "score": score,
                "target_eligible": target_fish is not None,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def session_windows(dc, location_id: str, start_hour: int, duration_hours: int) -> list[dict]:
    """Per-hour fish availability at a location across a session window."""
    windows = []
    prev_fish_ids: set[str] = set()

    for delta in range(duration_hours):
        hour = (start_hour + delta) % 24
        fish_ids: set[str] = set()
        for tool_id in dc.tool_by_id:
            for fish in dc.fish_by_id.values():
                if creature_eligible(fish, location_id, tool_id, hour, bosses=False, ignore_time=False):
                    fish_ids.add(fish.id)

        if delta == 0:
            opens = fish_ids.copy()
            closes: set[str] = set()
        else:
            opens = fish_ids - prev_fish_ids
            closes = prev_fish_ids - fish_ids

        windows.append({
            "hour": hour,
            "fish_ids": fish_ids,
            "opens": opens,
            "closes": closes,
        })
        prev_fish_ids = fish_ids

    return windows
