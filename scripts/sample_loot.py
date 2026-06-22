"""Sample specific locations across all 24 hours to map loot weight pattern."""
import json, urllib.request, time as _t
from datetime import datetime, timezone

SIM_URL = "https://dankmemer.lol/api/bot/fish/simulator"
HEADERS = {"Origin": "https://dankmemer.lol", "Referer": "https://dankmemer.lol/fishing/simulator", "Content-Type": "application/json"}

def ts(hour):
    return int(datetime.now(timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0).timestamp()*1000)

def call(loc, hour):
    payload = {"locationID": loc, "toolID": "fishing-rod", "baitsIDs": [], "time": ts(hour),
               "events": [], "bosses": False, "skills": {}, "bonusBossMultiplier": 1,
               "bonusMythicalMultiplier": 1, "forceTrash": False, "mythicalFishID": None,
               "discoveredCreatures": None, "anglerTuesday": False, "invasion": None, "locationWinner": False}
    data = json.dumps(payload).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(SIM_URL, data=data, headers=HEADERS, method="POST")
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt == 2: raise
            _t.sleep(2)

locs = ["deep-ocean", "lake-of-fire", "pond"]
out = {}
for loc in locs:
    out[loc] = []
    for h in range(24):
        res = call(loc, h)
        out[loc].append({"hour": h, "result": res})
        print(f"  {loc} hr{h:02d} fail={res['failChance']}")
        _t.sleep(0.5)

with open("sampling_data/loot_sweep.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print("saved")
