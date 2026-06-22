"""
Analyze sampling data to reverse-engineer the simulator formula.

Usage:
    python scripts/analyze_simulator.py
"""

import json
import os
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "sampling_data")
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data.json")


def load(name):
    with open(os.path.join(DATA_DIR, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def load_game_data():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)["data"]


def catches_by_id(result):
    return {c["id"]: c["chance"] for c in result.get("catches", [])}


def sep(title=""):
    print(f"\n{'='*60}")
    if title:
        print(f"  {title}")
        print('='*60)


# ---------------------------------------------------------------------------
# 1. Rarity → weight mapping
# ---------------------------------------------------------------------------
def analyze_rarity(game_data, locations_data):
    sep("RARITY -> BASE WEIGHT")
    # Find baseline (lake, rod, hour=12, no skills)
    lake = next(r for r in locations_data if r["location_id"] == "lake")
    catches = catches_by_id(lake["result"])

    # Map each creature to its rarity
    creatures = {c["id"]: c for c in game_data["creatures"]["items"]}

    # Group catches by rarity
    by_rarity = defaultdict(list)
    for cid, chance in catches.items():
        # Strip variant suffixes (e.g. chroma-bass → bass)
        base_id = cid
        creature = creatures.get(base_id)
        if not creature:
            # Try to find it
            for crid, cr in creatures.items():
                for v in cr["extra"].get("variants", []):
                    if v["id"] == cid:
                        creature = cr
                        break
                if creature:
                    break
        if creature:
            rarity = creature["extra"].get("rarity", "unknown")
            by_rarity[rarity].append((cid, chance))
        else:
            by_rarity["UNKNOWN"].append((cid, chance))

    rarity_order = ["Absurdly Common", "Very Common", "Common", "Regular",
                    "Rare", "Very Rare", "Absurdly Rare"]
    for rarity in rarity_order + ["UNKNOWN"]:
        entries = by_rarity.get(rarity, [])
        if entries:
            chances = [e[1] for e in entries]
            print(f"  {rarity:20s}: {len(entries):3d} creatures | "
                  f"chances min={min(chances):.4f} max={max(chances):.4f} "
                  f"avg={sum(chances)/len(chances):.4f}")
            for cid, ch in sorted(entries, key=lambda x: -x[1])[:3]:
                print(f"    {cid:40s} {ch:.4f}%")

    # Check if all creatures of same rarity have same chance
    print("\n  Checking rarity uniformity (same rarity = same base chance?):")
    for rarity in rarity_order:
        entries = by_rarity.get(rarity, [])
        if len(entries) > 1:
            chances = set(round(e[1], 6) for e in entries)
            uniform = len(chances) == 1
            print(f"  {rarity:20s}: {'UNIFORM' if uniform else 'VARIES'} "
                  f"(values: {sorted(chances)[:5]})")


# ---------------------------------------------------------------------------
# 2. Time effect
# ---------------------------------------------------------------------------
def analyze_time(game_data, time_data):
    sep("TIME EFFECT (hours 0-23, lake + fishing-rod)")
    creatures = {c["id"]: c for c in game_data["creatures"]["items"]}

    baseline = catches_by_id(time_data[12]["result"])  # hour 12

    # Find creatures whose availability changes with time
    print("  Creatures that appear/disappear by hour:")
    all_creature_ids = set()
    for rec in time_data:
        all_creature_ids |= set(catches_by_id(rec["result"]).keys())

    variable = []
    for cid in sorted(all_creature_ids):
        presences = []
        for rec in time_data:
            catches = catches_by_id(rec["result"])
            presences.append(cid in catches)
        if not all(presences) and any(presences):
            # Find time window from data
            creature = creatures.get(cid)
            time_info = creature["extra"].get("time") if creature else None
            active_hours = [h for h, p in enumerate(presences) if p]
            variable.append((cid, active_hours, time_info))

    for cid, active_hours, time_info in variable[:20]:
        print(f"  {cid:40s} active hours: {active_hours}")
        print(f"    {'data.json time:':20s} {time_info}")

    # How does total catch % change with hour?
    print("\n  Total catch % (excl. fail/npc) by hour:")
    for rec in time_data:
        total = sum(catches_by_id(rec["result"]).values())
        fail = rec["result"]["failChance"]
        npc = rec["result"]["npcChance"]
        print(f"  hour {rec['hour']:02d}: {len(catches_by_id(rec['result'])):3d} creatures, "
              f"total={total:.2f}%, fail={fail:.2f}%, npc={npc:.2f}%")


# ---------------------------------------------------------------------------
# 3. Tool effect
# ---------------------------------------------------------------------------
def analyze_tools(game_data, tools_data, locations_data):
    sep("TOOL EFFECT (lake, no bait, hour=12)")
    creatures = {c["id"]: c for c in game_data["creatures"]["items"]}

    rod_catches = catches_by_id(next(r for r in tools_data if r["tool_id"] == "fishing-rod")["result"])

    for rec in tools_data:
        tool_id = rec["tool_id"]
        catches = catches_by_id(rec["result"])
        fail = rec["result"]["failChance"]
        npc = rec["result"]["npcChance"]

        # Compare to rod baseline
        shared = set(catches) & set(rod_catches)
        only_this = set(catches) - set(rod_catches)
        only_rod = set(rod_catches) - set(catches)

        print(f"\n  {rec['tool_name']:25s} fail={fail:.2f}% npc={npc:.2f}% "
              f"creatures={len(catches)}")
        if only_this:
            print(f"    UNIQUE to this tool: {list(only_this)[:5]}")
        if only_rod:
            print(f"    MISSING vs rod:      {list(only_rod)[:5]}")

        # Check ratio for shared creatures
        ratios = []
        for cid in shared:
            if rod_catches[cid] > 0:
                ratios.append(catches[cid] / rod_catches[cid])
        if ratios:
            avg_ratio = sum(ratios) / len(ratios)
            min_r, max_r = min(ratios), max(ratios)
            print(f"    chance ratio vs rod: avg={avg_ratio:.3f} "
                  f"min={min_r:.3f} max={max_r:.3f} "
                  f"{'UNIFORM' if max_r-min_r < 0.01 else 'VARIES'}")


# ---------------------------------------------------------------------------
# 4. Bait effect
# ---------------------------------------------------------------------------
def analyze_baits(game_data, baits_data):
    sep("BAIT EFFECT (lake, fishing-rod, hour=12)")

    no_bait = next(r for r in baits_data if r["bait_id"] is None)
    baseline_catches = catches_by_id(no_bait["result"])
    baseline_fail = no_bait["result"]["failChance"]
    baseline_npc = no_bait["result"]["npcChance"]

    print(f"  Baseline (no bait): fail={baseline_fail}% npc={baseline_npc}% "
          f"creatures={len(baseline_catches)}")

    for rec in baits_data:
        if rec["bait_id"] is None:
            continue
        catches = catches_by_id(rec["result"])
        fail = rec["result"]["failChance"]
        npc = rec["result"]["npcChance"]

        fail_delta = fail - baseline_fail
        npc_delta = npc - baseline_npc

        # Chance deltas for shared creatures
        shared = set(catches) & set(baseline_catches)
        ratios = [catches[c] / baseline_catches[c]
                  for c in shared if baseline_catches[c] > 0]
        avg_ratio = sum(ratios) / len(ratios) if ratios else 1.0

        only_new = set(catches) - set(baseline_catches)
        only_gone = set(baseline_catches) - set(catches)

        print(f"\n  {rec['bait_name']:20s} "
              f"fail={fail:.2f}% ({fail_delta:+.2f}) "
              f"npc={npc:.2f}% ({npc_delta:+.2f}) "
              f"catch_ratio={avg_ratio:.3f}")
        if only_new:
            print(f"    NEW creatures:    {list(only_new)[:5]}")
        if only_gone:
            print(f"    REMOVED creatures: {list(only_gone)[:5]}")


# ---------------------------------------------------------------------------
# 5. Skill effect
# ---------------------------------------------------------------------------
def analyze_skills(game_data, skills_data):
    sep("SKILL EFFECT (lake, fishing-rod, no bait, hour=12)")

    no_skill = next(r for r in skills_data if r["skill"] is None)
    baseline_catches = catches_by_id(no_skill["result"])
    baseline_fail = no_skill["result"]["failChance"]
    baseline_npc = no_skill["result"]["npcChance"]

    # Group by base skill
    by_skill = defaultdict(list)
    for rec in skills_data:
        if rec["skill"]:
            by_skill[rec["skill"]].append(rec)

    for skill_base, tiers in sorted(by_skill.items()):
        tiers_sorted = sorted(tiers, key=lambda r: r["tier"])

        # Detect what this skill changes
        changes = []
        for rec in tiers_sorted:
            catches = catches_by_id(rec["result"])
            fail = rec["result"]["failChance"]
            npc = rec["result"]["npcChance"]

            fail_delta = fail - baseline_fail
            npc_delta = npc - baseline_npc

            shared = set(catches) & set(baseline_catches)
            ratios = [catches[c] / baseline_catches[c]
                      for c in shared if baseline_catches[c] > 0]
            avg_ratio = sum(ratios) / len(ratios) if ratios else 1.0

            only_new = set(catches) - set(baseline_catches)
            only_gone = set(baseline_catches) - set(catches)

            change_str = []
            if abs(fail_delta) > 0.001:
                change_str.append(f"fail{fail_delta:+.3f}")
            if abs(npc_delta) > 0.001:
                change_str.append(f"npc{npc_delta:+.3f}")
            if abs(avg_ratio - 1.0) > 0.001:
                change_str.append(f"catch×{avg_ratio:.3f}")
            if only_new:
                change_str.append(f"+{len(only_new)}new")
            if only_gone:
                change_str.append(f"-{len(only_gone)}gone")
            if not change_str:
                change_str = ["NO CHANGE"]

            changes.append(f"t{rec['tier']}: {', '.join(change_str)}")

        print(f"  {skill_base:35s} {' | '.join(changes)}")


# ---------------------------------------------------------------------------
# 6. Flags effect
# ---------------------------------------------------------------------------
def analyze_flags(flags_data):
    sep("FLAGS EFFECT (lake, fishing-rod, no bait, hour=12)")

    baseline = next(r for r in flags_data if r["flags"] == "baseline")
    baseline_catches = catches_by_id(baseline["result"])
    baseline_fail = baseline["result"]["failChance"]
    baseline_npc = baseline["result"]["npcChance"]

    print(f"  Baseline: fail={baseline_fail}% npc={baseline_npc}%")

    for rec in flags_data:
        if rec["flags"] == "baseline":
            continue
        catches = catches_by_id(rec["result"])
        fail = rec["result"]["failChance"]
        npc = rec["result"]["npcChance"]

        fail_delta = fail - baseline_fail
        npc_delta = npc - baseline_npc
        only_new = set(catches) - set(baseline_catches)
        only_gone = set(baseline_catches) - set(catches)

        print(f"\n  {rec['flags']:20s} "
              f"fail={fail:.2f}% ({fail_delta:+.2f}) "
              f"npc={npc:.2f}% ({npc_delta:+.2f})")
        if only_new:
            print(f"    NEW: {list(only_new)[:5]}")
        if only_gone:
            print(f"    GONE: {list(only_gone)[:5]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    game_data = load_game_data()
    locations_data = load("locations")
    tools_data = load("tools")
    baits_data = load("baits")
    time_data = load("time")
    skills_data = load("skills")
    flags_data = load("flags")

    analyze_rarity(game_data, locations_data)
    analyze_time(game_data, time_data)
    analyze_tools(game_data, tools_data, locations_data)
    analyze_baits(game_data, baits_data)
    analyze_skills(game_data, skills_data)
    analyze_flags(flags_data)


if __name__ == "__main__":
    main()
