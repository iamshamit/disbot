"""
Simulator API sampler — reverse-engineering experiment.

Runs controlled API calls varying one input at a time, saves results to
sampling_data/ as JSON for analysis.

Usage:
    python scripts/sample_simulator.py [--dry-run] [--experiment NAME]

Experiments (run all by default):
    determinism   — same payload 5x to check if API is deterministic
    locations     — baseline across all 14 locations
    tools         — all tools at one location
    baits         — all baits at one location + fishing-rod
    time          — all 24 UTC hours at one location + fishing-rod
    skills        — each skill at each tier in isolation
    flags         — bosses, anglerTuesday, locationWinner toggles
"""

import argparse
import json
import os
import re
import sys
import time as _time
import urllib.request
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SIM_URL = "https://dankmemer.lol/api/bot/fish/simulator"
SIM_HEADERS = {
    "Origin": "https://dankmemer.lol",
    "Referer": "https://dankmemer.lol/fishing/simulator",
    "Content-Type": "application/json",
}

# Baseline constants used when a variable is held fixed
BASE_LOCATION = "lake"
BASE_TOOL = "fishing-rod"
BASE_HOUR = 12
DELAY = 0.6  # seconds between requests (be polite)

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data.json")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "sampling_data")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_data():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)["data"]


def ts_for_hour(hour: int) -> int:
    """UTC timestamp (ms) for today at the given hour."""
    now = datetime.now(timezone.utc)
    t = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    return int(t.timestamp() * 1000)


def make_payload(
    location=BASE_LOCATION,
    tool=BASE_TOOL,
    baits=None,
    hour=BASE_HOUR,
    events=None,
    skills=None,
    bosses=False,
    angler_tuesday=False,
    loc_winner=False,
) -> dict:
    return {
        "locationID": location,
        "toolID": tool,
        "baitsIDs": baits or [],
        "time": ts_for_hour(hour),
        "events": events or [],
        "bosses": bosses,
        "skills": skills or {},
        "bonusBossMultiplier": 1,
        "bonusMythicalMultiplier": 1,
        "forceTrash": False,
        "mythicalFishID": None,
        "discoveredCreatures": None,
        "anglerTuesday": angler_tuesday,
        "invasion": None,
        "locationWinner": loc_winner,
    }


def call_api(payload: dict, dry_run: bool = False) -> dict | None:
    if dry_run:
        print(f"    [DRY-RUN] would POST {json.dumps(payload)[:120]}...")
        return None
    data = json.dumps(payload).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(SIM_URL, data=data, headers=SIM_HEADERS, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            if attempt == 2:
                raise
            print(f"    [retry {attempt+1}/3 after {exc.__class__.__name__}]")
            _time.sleep(2 + attempt * 2)


def save(name: str, records: list):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    print(f"  -> saved {len(records)} records to {path}")


def run(label: str, payload: dict, dry_run: bool) -> dict | None:
    print(f"  {label}")
    result = call_api(payload, dry_run)
    if not dry_run:
        _time.sleep(DELAY)
    return result


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------
def exp_determinism(dry_run: bool):
    print("\n[1/7] Determinism check — same payload x5")
    payload = make_payload()
    records = []
    for i in range(5):
        result = run(f"run {i+1}/5", payload, dry_run)
        if result:
            records.append({"run": i + 1, "payload": payload, "result": result})
    if not dry_run:
        save("determinism", records)
        # Quick analysis
        fail_chances = [r["result"]["failChance"] for r in records]
        print(f"  failChance across 5 runs: {fail_chances}")
        if len(set(fail_chances)) == 1:
            print("  DETERMINISTIC — all identical")
        else:
            print("  NON-DETERMINISTIC — values differ!")


def exp_locations(data, dry_run: bool):
    print("\n[2/7] Location sweep — baseline at each location")
    locations = [(l["id"], l["name"]) for l in data["locations"]["items"]]
    records = []
    for loc_id, loc_name in locations:
        payload = make_payload(location=loc_id)
        result = run(f"{loc_name} ({loc_id})", payload, dry_run)
        if result:
            records.append({"location_id": loc_id, "location_name": loc_name,
                            "payload": payload, "result": result})
    if not dry_run:
        save("locations", records)


def exp_tools(data, dry_run: bool):
    print("\n[3/7] Tool sweep — each tool at lake")
    tools = [(t["id"], t["name"]) for t in data["tools"]["items"]]
    records = []
    for tool_id, tool_name in tools:
        payload = make_payload(tool=tool_id)
        result = run(f"{tool_name} ({tool_id})", payload, dry_run)
        if result:
            records.append({"tool_id": tool_id, "tool_name": tool_name,
                            "payload": payload, "result": result})
    if not dry_run:
        save("tools", records)


def exp_baits(data, dry_run: bool):
    print("\n[4/7] Bait sweep — each bait at lake + fishing-rod")
    baits = [(b["id"], b["name"]) for b in data["baits"]["items"]]
    records = []
    # Baseline: no bait
    payload = make_payload()
    result = run("(no bait)", payload, dry_run)
    if result:
        records.append({"bait_id": None, "bait_name": "(none)",
                        "payload": payload, "result": result})
    for bait_id, bait_name in baits:
        payload = make_payload(baits=[bait_id])
        result = run(f"{bait_name} ({bait_id})", payload, dry_run)
        if result:
            records.append({"bait_id": bait_id, "bait_name": bait_name,
                            "payload": payload, "result": result})
    if not dry_run:
        save("baits", records)


def exp_time(dry_run: bool):
    print("\n[5/7] Time sweep — hours 0-23 at lake + fishing-rod")
    records = []
    for hour in range(24):
        payload = make_payload(hour=hour)
        result = run(f"hour {hour:02d}:00 UTC", payload, dry_run)
        if result:
            records.append({"hour": hour, "payload": payload, "result": result})
    if not dry_run:
        save("time", records)


def exp_skills(data, dry_run: bool):
    print("\n[6/7] Skill sweep — each skill at each tier in isolation")
    skills_raw = data["skills"]["items"]
    # Build {base: max_tier}
    skill_map: dict[str, int] = {}
    for s in skills_raw:
        m = re.match(r"^(.+)-(\d+)$", s["id"])
        if m:
            base, tier = m.group(1), int(m.group(2))
            skill_map[base] = max(skill_map.get(base, 0), tier)

    records = []
    # Baseline: no skills
    payload = make_payload()
    result = run("(no skills)", payload, dry_run)
    if result:
        records.append({"skill": None, "tier": None, "payload": payload, "result": result})

    for base, max_tier in skill_map.items():
        for tier in range(1, max_tier + 1):
            skill_id = f"{base}-{tier}"
            payload = make_payload(skills={skill_id: tier})
            result = run(f"{skill_id}", payload, dry_run)
            if result:
                records.append({"skill": base, "tier": tier, "skill_id": skill_id,
                                "payload": payload, "result": result})
    if not dry_run:
        save("skills", records)


def exp_flags(dry_run: bool):
    print("\n[7/7] Flag sweep — bosses / anglerTuesday / locationWinner")
    records = []
    for label, kwargs in [
        ("baseline",         {}),
        ("bosses=True",      {"bosses": True}),
        ("anglerTuesday",    {"angler_tuesday": True}),
        ("locationWinner",   {"loc_winner": True}),
        ("all flags",        {"bosses": True, "angler_tuesday": True, "loc_winner": True}),
    ]:
        payload = make_payload(**kwargs)
        result = run(label, payload, dry_run)
        if result:
            records.append({"flags": label, "payload": payload, "result": result})
    if not dry_run:
        save("flags", records)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
EXPERIMENTS = {
    "determinism": lambda data, dr: exp_determinism(dr),
    "locations":   lambda data, dr: exp_locations(data, dr),
    "tools":       lambda data, dr: exp_tools(data, dr),
    "baits":       lambda data, dr: exp_baits(data, dr),
    "time":        lambda data, dr: exp_time(dr),
    "skills":      lambda data, dr: exp_skills(data, dr),
    "flags":       lambda data, dr: exp_flags(dr),
}


def main():
    parser = argparse.ArgumentParser(description="Dank Memer simulator API sampler")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be called, don't actually call")
    parser.add_argument("--experiment", choices=list(EXPERIMENTS.keys()), help="Run a single experiment")
    args = parser.parse_args()

    data = load_data()

    to_run = [args.experiment] if args.experiment else list(EXPERIMENTS.keys())

    # Count expected calls
    if not args.dry_run:
        locations_n = len(data["locations"]["items"])
        tools_n = len(data["tools"]["items"])
        baits_n = len(data["baits"]["items"]) + 1  # +1 for no-bait baseline
        time_n = 24
        skills_raw = data["skills"]["items"]
        skill_map: dict[str, int] = {}
        for s in skills_raw:
            m = re.match(r"^(.+)-(\d+)$", s["id"])
            if m:
                base, tier = m.group(1), int(m.group(2))
                skill_map[base] = max(skill_map.get(base, 0), tier)
        skills_n = sum(skill_map.values()) + 1  # +1 for no-skills baseline
        flags_n = 5
        det_n = 5
        total = det_n + locations_n + tools_n + baits_n + time_n + skills_n + flags_n
        print(f"Estimated {total} API calls (~{total * DELAY:.0f}s). Starting in 3s... Ctrl+C to abort.")
        _time.sleep(3)

    start = _time.time()
    for name in to_run:
        EXPERIMENTS[name](data, args.dry_run)

    elapsed = _time.time() - start
    print(f"\nDone in {elapsed:.1f}s. Results in {OUT_DIR}/")


if __name__ == "__main__":
    main()
