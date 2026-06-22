"""
One-time generator for data/loot_weights.json.

Sweeps every location x every UTC hour against the live simulator API with a
fixed baseline payload (fishing-rod, no bait, no skills, no flags), derives the
total loot weight per cell, and writes the committed static table.

Re-run ONLY after a Dank Memer game patch:
    python scripts/generate_loot_table.py
"""
import json
import urllib.request
import time as _time
from datetime import datetime, timezone
from pathlib import Path

SIM_URL = "https://dankmemer.lol/api/bot/fish/simulator"
HEADERS = {
    "Origin": "https://dankmemer.lol",
    "Referer": "https://dankmemer.lol/fishing/simulator",
    "Content-Type": "application/json",
}

RARITY_WEIGHTS = {
    "Absurdly Common": 18.5,
    "Very Common": 16.5,
    "Common": 14.5,
    "Regular": 10.0,
    "Rare": 6.5,
    "Very Rare": 1.0,
    "Absurdly Rare": 0.075,
}

ROOT = Path(__file__).resolve().parent.parent


def derive_loot_weight(api_result: dict, eligible_weight: float) -> float:
    """Recover the total loot weight from one API result.

    total_weight is solved from the highest-weight fish present:
        chance = rarity_weight / total_weight * 100
    loot_weight = total_weight - eligible_weight.
    Returns 0.0 when no fish are present (cannot solve; loot-only pools).
    """
    best_w = 0.0
    best_chance = 0.0
    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))["data"]
    creatures_by_id = {c["id"]: c for c in data["creatures"]["items"]}
    for entry in api_result["table"]:
        v = entry["value"]
        if v.get("type") == "fish-creature":
            cid = v["creatureID"]
            w = RARITY_WEIGHTS[creatures_by_id[cid]["extra"]["rarity"]]
            if w > best_w:
                best_w = w
                best_chance = entry["chance"]
    if best_chance <= 0:
        return 0.0
    total_weight = best_w / (best_chance / 100.0)
    return total_weight - eligible_weight


def _ts(hour: int) -> int:
    now = datetime.now(timezone.utc)
    return int(now.replace(hour=hour, minute=0, second=0, microsecond=0).timestamp() * 1000)


def _call(location: str, hour: int) -> dict:
    payload = {
        "locationID": location, "toolID": "fishing-rod", "baitsIDs": [], "time": _ts(hour),
        "events": [], "bosses": False, "skills": {}, "bonusBossMultiplier": 1,
        "bonusMythicalMultiplier": 1, "forceTrash": False, "mythicalFishID": None,
        "discoveredCreatures": None, "anglerTuesday": False, "invasion": None, "locationWinner": False,
    }
    body = json.dumps(payload).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(SIM_URL, data=body, headers=HEADERS, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except Exception:
            if attempt == 2:
                raise
            _time.sleep(2 + attempt * 2)


def main() -> None:
    data = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))["data"]
    creatures_by_id = {c["id"]: c for c in data["creatures"]["items"]}
    location_ids = [l["id"] for l in data["locations"]["items"]]

    out: dict[str, list[float]] = {}
    for loc in location_ids:
        row: list[float] = []
        for hour in range(24):
            result = _call(loc, hour)
            fish_w = sum(
                RARITY_WEIGHTS[creatures_by_id[e["value"]["creatureID"]]["extra"]["rarity"]]
                for e in result["table"] if e["value"].get("type") == "fish-creature"
            )
            row.append(round(derive_loot_weight(result, fish_w), 6))
            print(f"  {loc} hr{hour:02d} loot_w={row[-1]}")
            _time.sleep(0.5)
        out[loc] = row

    dest = ROOT / "data" / "loot_weights.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {dest}")


if __name__ == "__main__":
    main()
