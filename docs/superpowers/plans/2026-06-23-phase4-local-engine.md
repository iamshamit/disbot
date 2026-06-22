# Phase 4: Local Simulation Engine + Peak Hours Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the live simulator API call with a local engine that reproduces the Dank Memer catch-probability formula exactly, and add a Peak Hours feature that sweeps all 24 UTC hours offline.

**Architecture:** A new pure-Python module `fishing_engine.py` returns a dict shaped identically to the live API (`table`, `variants`, `failChance`, `npcChance`), so the existing `build_sim_results_embed` consumes both unchanged. `SimulatorView.calculate_btn` routes to the engine, falling back to the existing `call_simulator_api` only for baits the engine cannot compute exactly. A committed `data/loot_weights.json` (14 locations × 24 hours of total loot weight) supplies the one piece of data not in `data.json`.

**Tech Stack:** Python 3.12, discord.py 2.4+, pytest, the `dankmemer` library (game data objects), `aiohttp` (fallback only).

**Data refresh note:** the canonical game data (`data.json` contents) is served by `GET https://dankmemer.lol/api/bot/fish/data`. After a Dank Memer game patch, refresh `data.json` from that endpoint and re-run `scripts/generate_loot_table.py` to regenerate `data/loot_weights.json`. (Automating this refresh is out of scope for Phase 4.)

## Global Constraints

- Discord View max 5 rows; max 5 buttons per row; max 25 select options
- Simulator API (fallback only): `POST https://dankmemer.lol/api/bot/fish/simulator` with headers `Origin: https://dankmemer.lol`, `Referer: https://dankmemer.lol/fishing/simulator`, `Content-Type: application/json` (no auth)
- All game data is accessed via the `dankmemer` library objects on `dc` (the `DankMemerGameClient`): `dc.fish_by_id`, `dc.location_by_id`, `dc.tool_by_id`, `dc.bait_by_id`. Each object has `.id`, `.name`, `.extra` (dict-like, use `.extra.get(...)`).
- **The library's `parse_time_info` transforms `creature.extra["time"]`:** raw `{start:int, end:int, reversed:bool}` becomes `{start:dt_time, end:dt_time}` (and `full_day:True` when raw was 0–24). For `reversed:true`, start and end are **swapped** before conversion and the `reversed` key is dropped. So at runtime a reversed window appears as `start.hour > end.hour` (spans midnight). The engine MUST use the parsed shape.
- New static data file lives at `data/loot_weights.json`; no DB schema changes in this phase.
- Rarity weights (verbatim): Absurdly Common 18.5, Very Common 16.5, Common 14.5, Regular 10.0, Rare 6.5, Very Rare 1.0, Absurdly Rare 0.075.
- Tool npcChance (verbatim): fishing-rod 0.575, dynamite 0.625, all other tools 0.50.
- API-fallback baits (verbatim): `lucky-bait`, `ghastly-bait`, `gift-bait`, `work-bait`, `farmer-bait` (minus any promoted to local by Task 2's validation).

---

## File Structure

- `data/loot_weights.json` — **create.** `{location_id: [24 floats]}`, index = UTC hour. Static, committed.
- `scripts/generate_loot_table.py` — **create.** One-time generator: sweeps 14×24 live API calls, derives loot weight per cell, writes `data/loot_weights.json`.
- `fishing_engine.py` — **create.** Pure engine: constants, `is_time_active`, `creature_eligible`, `local_simulate`. No Discord/DB imports.
- `dankmemer_client.py` — **modify.** Load `data/loot_weights.json` in `preload()` into `self.loot_weights`.
- `cogs/simulator.py` — **modify.** Wire `calculate_btn` to the engine + fallback; add `peak_hours_btn` and `build_peak_hours_embed`.
- `tests/test_fishing_engine.py` — **create.** Validates the engine against committed `sampling_data/*.json` fixtures (offline, exact).
- `tests/test_dankmemer_client.py` — **modify.** Loot-weights loader test.
- `tests/test_simulator_cog.py` — **modify.** Routing (engine vs API) + Peak Hours tests.

---

## Task 1: Loot weight table — pure derivation, generator, loader

**Files:**
- Create: `scripts/generate_loot_table.py`
- Create: `data/loot_weights.json` (generated artifact, committed)
- Modify: `dankmemer_client.py` (preload loader, `self.loot_weights` field)
- Test: `tests/test_dankmemer_client.py`

**Interfaces:**
- Consumes: committed `sampling_data/locations.json`, `sampling_data/loot_sweep.json` (already in repo) as offline fixtures for the derivation test.
- Produces:
  - `scripts/generate_loot_table.py` module-level `RARITY_WEIGHTS: dict[str,float]` and `derive_loot_weight(api_result: dict, eligible_weight: float) -> float`
  - `DankMemerGameClient.loot_weights: dict[str, list[float]]` (location id → 24 floats; empty dict if file missing)

- [ ] **Step 1: Write the failing test for `derive_loot_weight`**

In `tests/test_dankmemer_client.py`, add at the top (after existing imports):

```python
import json
from pathlib import Path
from scripts.generate_loot_table import derive_loot_weight, RARITY_WEIGHTS


def _fish_weight_for(api_result, creatures_by_id):
    """Sum rarity weights of the fish-creatures present in an API result."""
    total = 0.0
    for entry in api_result["table"]:
        v = entry["value"]
        if v.get("type") == "fish-creature":
            cid = v["creatureID"]
            rarity = creatures_by_id[cid]["extra"]["rarity"]
            total += RARITY_WEIGHTS[rarity]
    return total


def test_derive_loot_weight_matches_lake_sample():
    root = Path(__file__).resolve().parent.parent
    data = json.loads((root / "data.json").read_text(encoding="utf-8"))["data"]
    creatures_by_id = {c["id"]: c for c in data["creatures"]["items"]}
    locs = json.loads((root / "sampling_data" / "locations.json").read_text(encoding="utf-8"))
    lake = next(r for r in locs if r["location_id"] == "lake")
    fish_w = _fish_weight_for(lake["result"], creatures_by_id)
    loot_w = derive_loot_weight(lake["result"], fish_w)
    # lake @ hour 12 baseline: total weight 85.2, fish 79.5 -> loot 5.7
    assert round(loot_w, 4) == 5.7
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `python -m pytest tests/test_dankmemer_client.py::test_derive_loot_weight_matches_lake_sample -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.generate_loot_table'`.

- [ ] **Step 3: Write `scripts/generate_loot_table.py`**

```python
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
```

- [ ] **Step 4: Run the derivation test to confirm it passes**

Run: `python -m pytest tests/test_dankmemer_client.py::test_derive_loot_weight_matches_lake_sample -v`
Expected: PASS.

- [ ] **Step 5: Generate the loot table (one-time, requires network)**

Run: `python scripts/generate_loot_table.py`
Expected: prints 336 lines (`<loc> hr## loot_w=…`) and `Wrote …/data/loot_weights.json`. Takes ~3–4 minutes.
If the network is unavailable in this environment, note it and skip to Step 6 using the committed `sampling_data/loot_sweep.json` to hand-build a partial file is NOT acceptable — the table must be complete. Re-run when network is available before merging.

- [ ] **Step 6: Verify the generated file shape**

Run: `python -c "import json; d=json.load(open('data/loot_weights.json')); print(len(d), 'locations'); print(all(len(v)==24 for v in d.values()))"`
Expected: `14 locations` then `True`.

- [ ] **Step 7: Write the failing test for the loader**

In `tests/test_dankmemer_client.py`:

```python
def test_loot_weights_loaded_in_preload(monkeypatch):
    """preload() populates loot_weights from data/loot_weights.json."""
    import asyncio
    from dankmemer_client import DankMemerGameClient

    client = DankMemerGameClient()

    async def _noop():
        return None

    # Skip the network parts of preload; only exercise the loot-weights loader.
    monkeypatch.setattr(client, "connect", _noop)

    async def fake_query():
        return []
    class _FakeRoute:
        query = staticmethod(fake_query)
    client._client = type("X", (), {
        "creatures": _FakeRoute(), "locations": _FakeRoute(), "tools": _FakeRoute(),
        "baits": _FakeRoute(), "npcs": _FakeRoute(), "events": _FakeRoute(),
    })()

    asyncio.get_event_loop().run_until_complete(client.preload())
    assert "lake" in client.loot_weights
    assert len(client.loot_weights["lake"]) == 24
```

- [ ] **Step 8: Run it to confirm it fails**

Run: `python -m pytest tests/test_dankmemer_client.py::test_loot_weights_loaded_in_preload -v`
Expected: FAIL — `AssertionError` (`loot_weights` is empty / key missing).

- [ ] **Step 9: Add the loader to `dankmemer_client.py`**

In `__init__`, after `self.location_creature_map = {}` (line 50), add:

```python
        self.loot_weights: Dict[str, list] = {}
```

In `preload()`, after the skill-categories `try/except` block (ends line 155), add:

```python
        try:
            lw_path = _Path(__file__).parent / "data" / "loot_weights.json"
            self.loot_weights = _json.loads(lw_path.read_text(encoding="utf-8"))
            logger.info("Loaded loot weights for %d locations", len(self.loot_weights))
        except Exception:
            logger.warning("Failed to load data/loot_weights.json; local sim loot will read as 0", exc_info=True)
```

- [ ] **Step 10: Run the loader test to confirm it passes**

Run: `python -m pytest tests/test_dankmemer_client.py::test_loot_weights_loaded_in_preload -v`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add scripts/generate_loot_table.py data/loot_weights.json dankmemer_client.py tests/test_dankmemer_client.py
git commit -m "feat: loot weight table generator, static data/loot_weights.json, client loader"
```

---

## Task 2: `fishing_engine.py` — the local engine

**Files:**
- Create: `fishing_engine.py`
- Test: `tests/test_fishing_engine.py`

**Interfaces:**
- Consumes: `DankMemerGameClient.loot_weights` (Task 1); `dc.fish_by_id`, `dc.location_by_id`, `dc.tool_by_id` objects with `.extra.get(...)`.
- Produces (relied on by Task 3 & 4):
  - `RARITY_WEIGHTS: dict[str,float]`, `TOOL_NPC_CHANCE: dict[str,float]`, `API_FALLBACK_BAITS: frozenset[str]`
  - `is_time_active(time_obj, hour: int) -> bool`
  - `creature_eligible(creature, location_id, tool_id, hour, *, bosses, ignore_time) -> bool`
  - `local_simulate(dc, *, location_id, tool_id, bait_id, hour, bosses=False, angler_tuesday=False) -> dict` returning `{"failChance", "npcChance", "table", "variants"}` (API-shaped). Raises `FallbackBaitError` if `bait_id in API_FALLBACK_BAITS`.
  - `class FallbackBaitError(Exception)`

- [ ] **Step 1: Write the failing test for `is_time_active`**

Create `tests/test_fishing_engine.py`:

```python
from datetime import time as dt_time
from fishing_engine import (
    is_time_active, creature_eligible, local_simulate,
    RARITY_WEIGHTS, TOOL_NPC_CHANCE, API_FALLBACK_BAITS, FallbackBaitError,
)


def test_is_time_active_normal_window():
    # parsed normal window 9..16 (start.hour <= end.hour) -> inclusive both ends
    t = {"start": dt_time(hour=9), "end": dt_time(hour=16)}
    assert is_time_active(t, 9) is True
    assert is_time_active(t, 16) is True
    assert is_time_active(t, 8) is False
    assert is_time_active(t, 17) is False


def test_is_time_active_midnight_spanning():
    # parsed reversed window appears as start.hour > end.hour (e.g. 22..15)
    t = {"start": dt_time(hour=22), "end": dt_time(hour=15)}
    assert is_time_active(t, 23) is True
    assert is_time_active(t, 10) is True
    assert is_time_active(t, 22) is True
    assert is_time_active(t, 15) is True
    assert is_time_active(t, 18) is False


def test_is_time_active_full_day_and_missing():
    assert is_time_active({"full_day": True, "start": dt_time(0), "end": dt_time(0)}, 5) is True
    assert is_time_active(None, 5) is True
```

- [ ] **Step 2: Run to confirm failure**

Run: `python -m pytest tests/test_fishing_engine.py::test_is_time_active_normal_window -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fishing_engine'`.

- [ ] **Step 3: Create `fishing_engine.py` with constants + time/eligibility**

```python
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
_TIMELY = "time-bait"
_MAGNET = "magnet-bait"


class FallbackBaitError(Exception):
    """Raised when local_simulate is asked for a bait only the live API can do."""


def _get(obj, key, default=None):
    """Read a key from a dict-like or attribute-like extra object."""
    if obj is None:
        return default
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
    if sh <= eh:
        return sh <= hour <= eh
    return hour >= sh or hour <= eh


def creature_eligible(creature, location_id, tool_id, hour, *, bosses, ignore_time) -> bool:
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
```

- [ ] **Step 4: Run the time tests to confirm they pass**

Run: `python -m pytest tests/test_fishing_engine.py -k is_time_active -v`
Expected: 3 PASS.

- [ ] **Step 5: Write the failing test for `local_simulate` baseline exactness**

Append to `tests/test_fishing_engine.py`. This builds a fake `dc` from `data.json` (running it through the library's `parse_time_info` so the engine sees the real runtime shape) and asserts the engine reproduces the recorded API sample to 1e-6:

```python
import json
from pathlib import Path
from types import SimpleNamespace
from dankmemer.routes.creatures import parse_time_info

_ROOT = Path(__file__).resolve().parent.parent


def _fake_dc():
    data = json.loads((_ROOT / "data.json").read_text(encoding="utf-8"))["data"]
    fish_by_id = {}
    for c in data["creatures"]["items"]:
        extra = dict(c["extra"])
        if "time" in extra and extra["time"]:
            extra["time"] = parse_time_info(dict(extra["time"]))
        fish_by_id[c["id"]] = SimpleNamespace(id=c["id"], name=c["name"], extra=extra)
    location_by_id = {
        l["id"]: SimpleNamespace(id=l["id"], name=l["name"], extra=dict(l["extra"]))
        for l in data["locations"]["items"]
    }
    loot_weights = json.loads((_ROOT / "data" / "loot_weights.json").read_text(encoding="utf-8"))
    return SimpleNamespace(
        fish_by_id=fish_by_id, location_by_id=location_by_id, loot_weights=loot_weights,
    )


def _api_fish(result):
    return {e["value"]["creatureID"]: e["chance"]
            for e in result["table"] if e["value"].get("type") == "fish-creature"}


def _engine_fish(result):
    return {e["value"]["creatureID"]: e["chance"]
            for e in result["table"] if e["value"].get("type") == "fish-creature"}


def test_local_simulate_matches_all_locations_at_hour_12():
    dc = _fake_dc()
    locs = json.loads((_ROOT / "sampling_data" / "locations.json").read_text(encoding="utf-8"))
    for rec in locs:
        loc = rec["location_id"]
        api = _api_fish(rec["result"])
        if not api:
            continue
        out = local_simulate(dc, location_id=loc, tool_id="fishing-rod",
                             bait_id=None, hour=12)
        eng = _engine_fish(out)
        assert set(eng) == set(api), f"{loc}: creature set mismatch"
        for cid, chance in api.items():
            assert abs(eng[cid] - chance) < 1e-6, f"{loc}/{cid}: {eng[cid]} vs {chance}"
        assert out["failChance"] == rec["result"]["failChance"]
        assert abs(out["npcChance"] - rec["result"]["npcChance"]) < 1e-6


def test_local_simulate_matches_lake_all_24_hours():
    dc = _fake_dc()
    time_data = json.loads((_ROOT / "sampling_data" / "time.json").read_text(encoding="utf-8"))
    for rec in time_data:
        hour = rec["hour"]
        api = _api_fish(rec["result"])
        out = local_simulate(dc, location_id="lake", tool_id="fishing-rod",
                             bait_id=None, hour=hour)
        eng = _engine_fish(out)
        assert set(eng) == set(api), f"hour {hour}: creature set mismatch"
        for cid, chance in api.items():
            assert abs(eng[cid] - chance) < 1e-6, f"hour {hour}/{cid}"


def test_local_simulate_angler_tuesday_zeros_fail():
    dc = _fake_dc()
    out = local_simulate(dc, location_id="lake", tool_id="fishing-rod",
                         bait_id=None, hour=12, angler_tuesday=True)
    assert out["failChance"] == 0


def test_local_simulate_npc_chance_by_tool():
    dc = _fake_dc()
    rod = local_simulate(dc, location_id="lake", tool_id="fishing-rod", bait_id=None, hour=12)
    net = local_simulate(dc, location_id="lake", tool_id="net", bait_id=None, hour=12)
    assert abs(rod["npcChance"] - 0.575) < 1e-6
    assert abs(net["npcChance"] - 0.50) < 1e-6


def test_local_simulate_fallback_bait_raises():
    dc = _fake_dc()
    try:
        local_simulate(dc, location_id="lake", tool_id="fishing-rod",
                       bait_id="lucky-bait", hour=12)
        assert False, "expected FallbackBaitError"
    except FallbackBaitError:
        pass
```

- [ ] **Step 6: Run to confirm failure**

Run: `python -m pytest tests/test_fishing_engine.py::test_local_simulate_matches_all_locations_at_hour_12 -v`
Expected: FAIL — `local_simulate` not yet defined / `AttributeError`.

- [ ] **Step 7: Implement `local_simulate` in `fishing_engine.py`**

Append:

```python
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
    if bait_id == "heart-bait":
        npc += 2.0

    ignore_time = bait_id == _TIMELY
    fish, fish_w = _eligible_weight_and_list(
        dc, location_id, tool_id, hour, bosses=bosses, ignore_time=ignore_time
    )

    # Loot weight from the static table (day/night/hour-specific).
    loot_w = 0.0
    row = (dc.loot_weights or {}).get(location_id)
    if row and 0 <= hour < len(row):
        loot_w = row[hour]
    if bait_id == _VINTAGE:
        loot_w *= 0.5

    if bait_id == _MAGNET:
        fish_w = 0.0  # magnet bait: catch only loot

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
```

- [ ] **Step 8: Run the full engine test suite**

Run: `python -m pytest tests/test_fishing_engine.py -v`
Expected: all PASS, including the 14-location and 24-hour exactness checks.

- [ ] **Step 9: Validate the four uncertain baits across pools (promotion decision)**

Run this throwaway check to decide whether ghastly/gift/work/farmer can leave the fallback set. It samples each across 3 locations × 2 hours and reports whether the fish-weight effect is a single constant loot-weight adjustment:

```bash
python - <<'PY'
import json, urllib.request, time
from datetime import datetime, timezone
URL="https://dankmemer.lol/api/bot/fish/simulator"
H={"Origin":"https://dankmemer.lol","Referer":"https://dankmemer.lol/fishing/simulator","Content-Type":"application/json"}
def ts(h): return int(datetime.now(timezone.utc).replace(hour=h,minute=0,second=0,microsecond=0).timestamp()*1000)
def call(loc,h,bait):
    p={"locationID":loc,"toolID":"fishing-rod","baitsIDs":[bait] if bait else [],"time":ts(h),"events":[],"bosses":False,"skills":{},"bonusBossMultiplier":1,"bonusMythicalMultiplier":1,"forceTrash":False,"mythicalFishID":None,"discoveredCreatures":None,"anglerTuesday":False,"invasion":None,"locationWinner":False}
    r=urllib.request.Request(URL,data=json.dumps(p).encode(),headers=H,method="POST")
    with urllib.request.urlopen(r,timeout=30) as x: return json.loads(x.read())
def fm(res): return {e["value"]["creatureID"]:e["chance"] for e in res["table"] if e["value"].get("type")=="fish-creature"}
for bait in ["ghastly-bait","gift-bait","work-bait","farmer-bait"]:
    print(bait)
    for loc in ["lake","deep-ocean","pond"]:
        for h in [12,0]:
            base=fm(call(loc,h,None)); time.sleep(.4)
            b=fm(call(loc,h,bait)); time.sleep(.4)
            shared=set(base)&set(b)
            ratios=[b[c]/base[c] for c in shared if base[c]>0]
            if ratios:
                print(f"  {loc} hr{h}: uniform={max(ratios)-min(ratios)<5e-4} ratio={sum(ratios)/len(ratios):.4f}")
PY
```

Decision rule: if a bait's per-fish ratio is uniform **and** the implied added loot weight (`fish_w*(1/ratio - 1)`) is the same constant across all 6 cells, add a transform for it in `local_simulate` (mirror the `_VINTAGE` pattern with its constant) and remove it from `API_FALLBACK_BAITS`. Otherwise leave it on fallback. **Document the outcome for each of the four baits in the commit message.** Do not guess — if uncertain, leave on fallback.

- [ ] **Step 10: Commit**

```bash
git add fishing_engine.py tests/test_fishing_engine.py
git commit -m "feat: local fishing simulation engine (exact catch %, fail, npc, time/tool filtering, vintage/timely/magnet baits)"
```

---

## Task 3: Wire Calculate to the engine with API fallback

**Files:**
- Modify: `cogs/simulator.py` (`calculate_btn`)
- Test: `tests/test_simulator_cog.py`

**Interfaces:**
- Consumes: `local_simulate`, `API_FALLBACK_BAITS`, `FallbackBaitError` (Task 2); existing `call_simulator_api`, `build_sim_results_embed`.
- Produces: a `calculate_btn` that calls the engine for local baits and the API for fallback baits, feeding the same `build_sim_results_embed`.

- [ ] **Step 1: Write the failing routing tests**

In `tests/test_simulator_cog.py`, reuse the module's existing helpers (`make_member`, `make_dc`, `make_interaction`, `make_user_row`) and add:

```python
import cogs.simulator as sim_mod


def _routing_db():
    db = MagicMock()
    db.get_or_create_user = AsyncMock(return_value=make_user_row(boss_unlock=0))
    db.add_history = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_calculate_uses_engine_for_local_bait(monkeypatch):
    from cogs.simulator import SimulatorView
    dc = make_dc()
    view = SimulatorView(_routing_db(), make_member(), dc,
                         initial_state={"location_id": "river", "tool_id": "rod",
                                        "bait_id": None, "event_id": None, "hour": 12})
    called = {"engine": False, "api": False}

    def fake_engine(*a, **k):
        called["engine"] = True
        return {"failChance": 10, "npcChance": 0.5, "table": [], "variants": {}}

    async def fake_api(payload):
        called["api"] = True
        return {"failChance": 0, "npcChance": 0, "table": [], "variants": {}}

    monkeypatch.setattr(sim_mod, "local_simulate", fake_engine)
    monkeypatch.setattr(sim_mod, "call_simulator_api", fake_api)
    await view.calculate_btn.callback(view, make_interaction())
    assert called["engine"] is True
    assert called["api"] is False


@pytest.mark.asyncio
async def test_calculate_uses_api_for_fallback_bait(monkeypatch):
    from cogs.simulator import SimulatorView
    dc = make_dc()
    view = SimulatorView(_routing_db(), make_member(), dc,
                         initial_state={"location_id": "river", "tool_id": "rod",
                                        "bait_id": "lucky-bait", "event_id": None, "hour": 12})
    called = {"engine": False, "api": False}

    def fake_engine(*a, **k):
        called["engine"] = True
        return {"failChance": 10, "npcChance": 0.5, "table": [], "variants": {}}

    async def fake_api(payload):
        called["api"] = True
        return {"failChance": 0, "npcChance": 0, "table": [], "variants": {}}

    monkeypatch.setattr(sim_mod, "local_simulate", fake_engine)
    monkeypatch.setattr(sim_mod, "call_simulator_api", fake_api)
    await view.calculate_btn.callback(view, make_interaction())
    assert called["api"] is True
    assert called["engine"] is False
```

Note: `make_dc()` has `bait_by_id = {"worm": ...}`, so the pre-filled `bait_id="lucky-bait"` is not in the bait list — `SimulatorView.__init__` clears an incompatible bait only for tool-restricted cases, not unknown ids, so `_bait_id` stays `"lucky-bait"` and routing is exercised correctly. (If a future change clears unknown baits, set `dc.bait_by_id["lucky-bait"] = MagicMock(id="lucky-bait", name="Lucky Bait")`.)

- [ ] **Step 2: Run to confirm failure**

Run: `python -m pytest tests/test_simulator_cog.py -k "calculate_uses" -v`
Expected: FAIL — current `calculate_btn` always calls the API, so `test_calculate_uses_engine_for_local_bait` fails (`api` True / `engine` False).

- [ ] **Step 3: Update imports in `cogs/simulator.py`**

Near the other imports at the top of the file, add:

```python
from fishing_engine import local_simulate, API_FALLBACK_BAITS, FallbackBaitError
```

- [ ] **Step 4: Rewrite `calculate_btn` to route**

Replace the body of `calculate_btn` (currently `cogs/simulator.py:400-420`) with:

```python
    @discord.ui.button(label="🔄 Calculate", style=discord.ButtonStyle.primary, row=4)
    async def calculate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        user_row = await self.db.get_or_create_user(str(self.member.id))
        use_api = self._bait_id in API_FALLBACK_BAITS
        try:
            if use_api:
                data = await call_simulator_api(self._build_payload(user_row))
            else:
                data = local_simulate(
                    self.dc,
                    location_id=self._loc_id,
                    tool_id=self._tool_id,
                    bait_id=self._bait_id,
                    hour=self._hour,
                    bosses=bool(user_row["boss_unlock"]),
                    angler_tuesday=self._angler_tuesday,
                )
        except FallbackBaitError:
            data = await call_simulator_api(self._build_payload(user_row))
        except Exception as exc:
            await interaction.followup.send(
                embed=EmbedBuilder.error("Simulator error", f"Could not calculate: {exc}"),
                ephemeral=True,
            )
            return
        embed = build_sim_results_embed(data, self._current_state(), self.dc)
        self._last_embed = embed
        await interaction.edit_original_response(embed=embed, view=self)
        await self.db.add_history(
            str(self.member.id), "simulation",
            self._loc_id or "unknown",
            data=_json.dumps(data),
        )
```

- [ ] **Step 5: Run the routing tests**

Run: `python -m pytest tests/test_simulator_cog.py -k "calculate_uses" -v`
Expected: both PASS.

- [ ] **Step 6: Run the full simulator + engine suites to check for regressions**

Run: `python -m pytest tests/test_simulator_cog.py tests/test_fishing_engine.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add cogs/simulator.py tests/test_simulator_cog.py
git commit -m "feat: route Calculate to local engine, fall back to API for lucky/weight baits"
```

---

## Task 4: Peak Hours button + embed

**Files:**
- Modify: `cogs/simulator.py` (`build_peak_hours_embed`, `peak_hours_btn`)
- Test: `tests/test_simulator_cog.py`

**Interfaces:**
- Consumes: `local_simulate` (Task 2); existing `SimulatorView` state.
- Produces: `build_peak_hours_embed(results, state, dc) -> discord.Embed` where `results` is `list[tuple[int, dict]]` (hour, sim result); and a `peak_hours_btn` that never calls the API.

- [ ] **Step 1: Write the failing test for `build_peak_hours_embed`**

In `tests/test_simulator_cog.py`:

```python
def test_build_peak_hours_embed_lists_24_hours_and_marks_best():
    import cogs.simulator as sim_mod
    dc = make_dc()
    results = []
    for h in range(24):
        fail = 10 if h != 14 else 8  # hour 14 is best
        results.append((h, {"failChance": fail, "npcChance": 0.5,
                            "table": [{"chance": 20.0, "baseChance": 20.0,
                                       "value": {"type": "fish-creature", "creatureID": "bass"}}],
                            "variants": {}}))
    state = {"location_id": "river", "tool_id": "rod", "bait_id": None, "hour": 12}
    embed = sim_mod.build_peak_hours_embed(results, state, dc)
    body = embed.description + "".join(f.value for f in embed.fields)
    assert "14:00" in body
    # best hour is flagged
    assert "⭐" in body or "best" in body.lower()
```

- [ ] **Step 2: Run to confirm failure**

Run: `python -m pytest tests/test_simulator_cog.py::test_build_peak_hours_embed_lists_24_hours_and_marks_best -v`
Expected: FAIL — `build_peak_hours_embed` not defined.

- [ ] **Step 3: Add `build_peak_hours_embed` to `cogs/simulator.py`**

Add after `build_sim_results_embed` (after `cogs/simulator.py:83`):

```python
def build_peak_hours_embed(results, state, dc) -> discord.Embed:
    """Render a 24-hour fail%/npc% sweep, flagging the lowest-fail hour.

    results: list[tuple[int hour, dict sim_result]].
    """
    loc_id = state.get("location_id")
    loc_name = dc.location_by_id[loc_id].name if loc_id and loc_id in dc.location_by_id else "No Location"

    best_hour = min(results, key=lambda r: r[1].get("failChance", 100))[0] if results else None

    lines = []
    for hour, data in results:
        fail = data.get("failChance", 0)
        npc = data.get("npcChance", 0)
        star = " ⭐" if hour == best_hour else ""
        lines.append(f"`{hour:02d}:00` fail `{fail:>4.1f}%`  npc `{npc:>4.2f}%`{star}")

    embed = discord.Embed(title=f"🕐 Peak Hours — {loc_name}", color=0x5865F2)
    embed.set_author(name="🎣 Simulator")
    embed.description = (
        f"Best hour: **{best_hour:02d}:00 UTC** (lowest fail)\n" if best_hour is not None
        else "No data.\n"
    )
    # Two columns to stay within field limits.
    half = (len(lines) + 1) // 2
    embed.add_field(name="Hours 00–11", value="\n".join(lines[:half]) or "—", inline=True)
    embed.add_field(name="Hours 12–23", value="\n".join(lines[half:]) or "—", inline=True)
    return embed
```

- [ ] **Step 4: Run the embed test**

Run: `python -m pytest tests/test_simulator_cog.py::test_build_peak_hours_embed_lists_24_hours_and_marks_best -v`
Expected: PASS.

- [ ] **Step 5: Write the failing test for `peak_hours_btn` (no API, 24 sims)**

```python
@pytest.mark.asyncio
async def test_peak_hours_btn_runs_24_local_sims_no_api(monkeypatch):
    from cogs.simulator import SimulatorView
    import cogs.simulator as sim_mod
    dc = make_dc()
    view = SimulatorView(_routing_db(), make_member(), dc,
                         initial_state={"location_id": "river", "tool_id": "rod",
                                        "bait_id": None, "event_id": None, "hour": 12})
    hours_seen = []

    def fake_sim(dc_, *, location_id, tool_id, bait_id, hour, bosses=False, angler_tuesday=False):
        hours_seen.append(hour)
        return {"failChance": 10, "npcChance": 0.5, "table": [], "variants": {}}

    api_called = {"v": False}

    async def fake_api(payload):
        api_called["v"] = True
        return {}

    monkeypatch.setattr(sim_mod, "local_simulate", fake_sim)
    monkeypatch.setattr(sim_mod, "call_simulator_api", fake_api)
    await view.peak_hours_btn.callback(view, make_interaction())
    assert sorted(hours_seen) == list(range(24))
    assert api_called["v"] is False
```

- [ ] **Step 6: Run to confirm failure**

Run: `python -m pytest tests/test_simulator_cog.py::test_peak_hours_btn_runs_24_local_sims_no_api -v`
Expected: FAIL — `peak_hours_btn` not defined / `AttributeError`.

- [ ] **Step 7: Add `peak_hours_btn` to `SimulatorView` and move Set Time into Extras**

**Layout constraint:** rows 0–3 of `SimulatorView` hold the four selects; only row 4 is free for buttons (max 5). Row 4 already has 5 buttons (Calculate, Skills, Extras, Set Time, Delete). To add a 6th feature button, relocate **Set Time** out of `SimulatorView` and into `ExtrasView` (whose row 3 currently holds only Save + Cancel — room for more), freeing the row-4 slot for Peak Hours.

First, remove the `set_time_btn` block from `SimulatorView` (`cogs/simulator.py:448-450`):

```python
    @discord.ui.button(label="🕐 Set Time", style=discord.ButtonStyle.secondary, row=4)
    async def set_time_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TimeModal(self))
```

Add, in its place, the Peak Hours button:

```python
    @discord.ui.button(label="📈 Peak Hours", style=discord.ButtonStyle.primary, row=4)
    async def peak_hours_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        user_row = await self.db.get_or_create_user(str(self.member.id))
        bosses = bool(user_row["boss_unlock"])
        results = []
        for hour in range(24):
            data = local_simulate(
                self.dc,
                location_id=self._loc_id,
                tool_id=self._tool_id,
                bait_id=None,  # fallback baits not modeled in the sweep
                hour=hour,
                bosses=bosses,
                angler_tuesday=self._angler_tuesday,
            )
            results.append((hour, data))
        embed = build_peak_hours_embed(results, self._current_state(), self.dc)
        if self._bait_id in API_FALLBACK_BAITS:
            embed.set_footer(text="Note: selected bait's per-fish effect is not modeled in the hourly sweep.")
        self._last_embed = embed
        await interaction.edit_original_response(embed=embed, view=self)
```

Then add a Set Time button to `ExtrasView` on row 3 (next to the existing Save and Cancel buttons — `cogs/simulator.py:245-257`). Insert it before `save_btn`:

```python
    @discord.ui.button(label="🕐 Set Time", style=discord.ButtonStyle.secondary, row=3)
    async def set_time_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TimeModal(self.parent))
```

`ExtrasView.parent` is the `SimulatorView` (set in `ExtrasView.__init__`, line 223), and `TimeModal` already targets `parent._hour` (Phase 3). Row 3 then holds Set Time + Save + Cancel = 3 buttons, within the 5-per-row cap.

- [ ] **Step 8: Update the existing button-layout test**

Moving Set Time breaks `test_simulator_view_has_4_selects_and_5_buttons` (it asserts `"🕐 Set Time" in btn_labels`). In `tests/test_simulator_cog.py`, change that assertion to the new button:

```python
    assert "📈 Peak Hours" in btn_labels
```

(Remove the `assert "🕐 Set Time" in btn_labels` line.) The button count stays 5: Calculate, Skills, Extras, Peak Hours, Delete.

- [ ] **Step 9: Run the peak hours button + layout tests**

Run: `python -m pytest tests/test_simulator_cog.py::test_peak_hours_btn_runs_24_local_sims_no_api tests/test_simulator_cog.py::test_simulator_view_has_4_selects_and_5_buttons -v`
Expected: PASS.

- [ ] **Step 10: Verify the button layout is valid + run the simulator suite**

Run: `python -m pytest tests/test_simulator_cog.py -v`
Expected: all PASS, no `discord` view-construction errors (a "too many components on row" error surfaces as an exception when `SimulatorView` is instantiated in tests). If one appears, move a button to a free row ≤ 4 within the 5-per-row cap.

- [ ] **Step 11: Run the entire test suite**

Run: `python -m pytest -q`
Expected: all PASS.

- [ ] **Step 12: Commit**

```bash
git add cogs/simulator.py tests/test_simulator_cog.py
git commit -m "feat: add Peak Hours 24-hour sweep button + embed, move Set Time into Extras"
```

---

## Self-Review Notes

- **Spec coverage:** loot table (Task 1) · engine constants/time/eligibility/local_simulate (Task 2) · bait taxonomy incl. 4-bait promotion check (Task 2 Step 9) · Calculate routing + fallback (Task 3) · Peak Hours + footnote (Task 4) · error handling (Task 3 Step 4 `except`, Task 1 loader `except`) · testing against committed samples (Tasks 1–4). All spec sections map to a task.
- **Out of scope (per spec):** itemized loot names, variant chances, event/locationWinner/skill distribution effects, response caching, encyclopedia/creature-time/invasion work — none are tasked here.
- **Layout caveat:** Task 4 Step 7 resolves the 5-buttons-per-row limit by moving Set Time into `ExtrasView` row 3 (alongside Save/Cancel).
- **Network caveat:** Task 1 Step 5 and Task 2 Step 9 require live API access. If unavailable, the implementer must flag it and complete those steps before merge — the committed `data/loot_weights.json` must be complete and the four-bait decision must be recorded.
