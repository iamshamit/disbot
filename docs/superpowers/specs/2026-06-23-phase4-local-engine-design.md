# Phase 4: Local Simulation Engine + Peak Hours

## Goal

Replace the live Dank Memer simulator API call with a local engine that reproduces the catch-probability formula exactly from `data.json` plus a small committed loot-weight table. Add a **Peak Hours** feature (best UTC hour for a setup) that was infeasible with the live API. Keep a single live API call as a fallback only for cases the local engine cannot compute exactly (Lucky Bait).

## Why

The Phase 3 simulator calls `https://dankmemer.lol/api/bot/fish/simulator` on every Calculate. Peak Hours would need 24 calls per request — too slow and rude to their server. Reverse-engineering (sampling the API with controlled inputs, one variable at a time) proved the formula is exactly recoverable for everything that matters. See "Reverse-Engineering Findings" below for the evidence.

## Architecture

One new module, `fishing_engine.py`, exposes `local_simulate(state, dc, loot_weights) -> dict` returning a dict shaped **identically** to the live API response (`table`, `variants`, `failChance`, `npcChance`). Because the shape matches, the existing `build_sim_results_embed` in `cogs/simulator.py` consumes both local and API results unchanged.

`SimulatorView.Calculate` routes to the engine, falling back to the existing `call_simulator_api` only when Lucky Bait is selected. A new `SimulatorView.PeakHours` button runs the engine across all 24 hours and renders a best-hour table — always local.

A committed static file `data/loot_weights.json` holds the per-location/per-hour total loot weight (a 14×24 grid of small floats), generated once by `scripts/sample_loot_table.py`. It is loaded at startup into `dankmemer_client` alongside the other game data.

## Tech Stack

- Pure-Python engine (no new dependencies) — arithmetic over `data.json`
- discord.py views/buttons (existing Phase 3 pattern)
- `aiohttp` retained only for the Lucky Bait fallback
- Static `data/loot_weights.json` committed to the repo
- Existing `data.json` as the authoritative source for creatures/locations/tools/baits

---

## Reverse-Engineering Findings (validated against 250+ API samples)

The API is **deterministic** (5 identical calls → identical output). All of the following reproduce the live API with **0.00000000% error** unless noted.

### Rarity weights (per eligible creature)

| Rarity | Weight |
|--------|--------|
| Absurdly Common | 18.5 |
| Very Common | 16.5 |
| Common | 14.5 |
| Regular | 10.0 |
| Rare | 6.5 |
| Very Rare | 1.0 |
| Absurdly Rare | 0.075 |

`fish_chance[c] = rarity_weight[c] / total_weight × 100`, where
`total_weight = Σ rarity_weight(eligible fish) + loot_weight(location, hour)`.

Validated: 105/105 fish across all 14 locations matched exactly.

### Eligibility filter

A creature is eligible at `(location, tool, hour)` when **all** hold:
- `location ∈ creature.extra.locations`
- `creature.extra.boss == False` (unless `bosses` flag set — see below)
- `creature.extra.mythical == False` (mythical creatures are excluded; `discoveredCreatures` is always `None` in our payloads)
- `creature.extra.tools[tool].max > 0`
- time-active at `hour` (see below)

### Time window

For `creature.extra.time = {start, end, reversed}`:
- normal: active when `start <= hour <= end` (inclusive both ends)
- reversed: active when `not (start < hour < end)` (endpoints active)
- no `time` field → always active

Validated: 24/24 hours at lake matched exactly.

### failChance

Read directly from `location.extra.failChance` in `data.json`. Validated across all 14 locations.

### npcChance

`base_npc × tool_npc_multiplier`. Base is `0.5%`. The fishing-rod's "+15% chance for NPC encounters" buff yields `0.575%`. Tool NPC multipliers are read from each tool's `extra.buffs` text (e.g. rod 1.15, dynamite 1.25, others 1.0). These are few and stable; capture them as a constant map keyed by tool id, derived from the sampled values:

| Tool | npcChance |
|------|-----------|
| bare-hand, harpoon, net, idle-fishing-machine, fishing-bow, magnet-fishing-rope | 0.50% |
| fishing-rod | 0.575% |
| dynamite | 0.625% |

### Flags

- `anglerTuesday == True` → `failChance = 0`
- `bosses == True` → include `boss` creatures in the eligible pool
- `locationWinner` → no observed effect on the catch distribution; pass through, no engine effect
- `events` → not modeled in Phase 4 (carried in state, no engine effect); selecting an event does not change local results

### Skills

Confirmed across all 133 skill/tier combinations: **skills have zero effect on the catch distribution.** The engine ignores skills for probability purposes (they are still stored/displayed elsewhere).

### Baits (18 total)

- **10 baits — no effect on catch distribution**: weighted, golden, eyeball, turkey, money, deadly, xp, jerky, omega, heart. (They affect variants/high-quality/rewards/NPC only.) `heart-bait` additionally raises `npcChance` by ~2 percentage points; model that one delta.
- **Proven-exact weight transforms** (verified to reproduce the API exactly):
  - `vintage-bait` — `loot_weight × 0.5` (validated: lake fish % matched to 1e-6)
  - `timely-bait` — eligibility ignores the time filter (all location creatures show), recompute weights
  - `magnet-bait` — all fish weight → 0 (loot-only result)
- **API fallback baits** (route to one live API call, same as Lucky Bait):
  - `lucky-bait` — per-creature luck is pool-dependent and distinguishes creatures byte-identical in `data.json` (koi vs red-arowana). Not computable locally.
  - `ghastly-bait`, `gift-bait`, `work-bait`, `farmer-bait` — observed as a uniform fish-weight reduction **within a single tested pool (lake@12)**, but the effect was not verified to generalize across locations/hours. Treated as fallback until proven. **Implementation step:** the plan includes a validation task that samples these four baits across ≥3 locations and ≥2 hours; any whose effect is a constant loot-weight adjustment gets promoted to a local transform, the rest stay on fallback. This keeps the engine honest — we never ship an approximation as if it were exact.

### Loot

Loot item identities and per-item weights are server-side and time-varying (loot items have their own hidden time windows). **But the total loot weight per `(location, hour)` takes only a few discrete values** and is required for exact fish %. Capture it once into `data/loot_weights.json` as a 14×24 grid. In local mode the catch table shows a single aggregate `Misc Loot: X%` line (no itemized names). Variant/high-quality chances are server-side and omitted in local mode.

---

## Components

### 1. `scripts/sample_loot_table.py` (one-time generator)

Sweeps all 14 locations × 24 hours with a fixed baseline payload (fishing-rod, no bait, no skills, no flags), derives `loot_weight = total_weight − fish_weight` per cell (using the highest-weight eligible fish to solve for `total_weight`), and writes `data/loot_weights.json`:

```json
{ "lake": [3.2, 3.2, 3.2, 3.2, 3.2, 3.2, 5.7, 5.7, ... 24 values], ... }
```

Index = UTC hour 0–23. Committed to the repo. Re-run only after a game patch. Includes retry-on-timeout (the live API occasionally times out). The two existing exploratory scripts (`scripts/sample_simulator.py`, `scripts/analyze_simulator.py`) remain in the repo as the documented evidence trail.

### 2. `fishing_engine.py` (new module)

Pure functions, no Discord or DB imports — independently testable.

- `RARITY_WEIGHTS: dict[str, float]` — the table above
- `TOOL_NPC_CHANCE: dict[str, float]` — the table above
- `_BAIT_LOOT_MULT: dict[str, float]` — vintage/ghastly/gift/work/farmer effective loot adjustments captured from samples
- `is_time_active(time_obj, hour) -> bool`
- `eligible_creatures(creatures, location, tool, hour, *, bosses, ignore_time) -> list`
- `local_simulate(state, dc, loot_weights) -> dict` — returns `{failChance, npcChance, table, variants}` matching the API shape. `table` entries reuse the API's `{chance, baseChance, value:{type, creatureID}}` structure; one aggregate `{value:{type:"loot"}, chance:loot_pct}` line represents loot. `variants` is `{}`.

`local_simulate` raises/sentinels for any fallback bait so the caller knows to use the API fallback (the caller checks the bait id against `_API_FALLBACK_BAITS` before dispatch; the engine also guards defensively).

### 3. `cogs/simulator.py` wiring

- `_API_FALLBACK_BAITS: frozenset` — `{lucky-bait, ghastly-bait, gift-bait, work-bait, farmer-bait}` minus any promoted to local by the validation task.
- `SimulatorView.calculate_btn`: if `self._bait_id in _API_FALLBACK_BAITS` → existing `call_simulator_api` path; else `local_simulate(...)`. Both feed `build_sim_results_embed` unchanged. History recording unchanged.
- New `SimulatorView.peak_hours_btn` (row 4): runs `local_simulate` for hours 0–23 with the current setup. Fallback baits are ignored for the sweep (computed on the baseline distribution) with a footnote, since a 24-call API sweep is exactly what Phase 4 avoids. Builds a results embed via a new `build_peak_hours_embed(results, state, dc)`.
- `build_peak_hours_embed`: a table of `hour | fail% | npc% | top-fish%` (or a compact best-hours summary), highlighting the lowest-fail hour. ≤ 24 rows, within embed limits.

### 4. `dankmemer_client` loader

Load `data/loot_weights.json` in `preload()` into `self.loot_weights: dict[str, list[float]]`. Missing file → log a clear error and leave the dict empty; `local_simulate` then treats loot_weight as 0 (fish % slightly high) rather than crashing.

---

## Data Flow

```
User clicks Calculate
  → SimulatorView reads its state (loc, tool, bait, hour, flags)
  → fallback bait? ─ yes → call_simulator_api(payload) ─┐
                     no  → local_simulate(state, dc, lw) ─┤
                                                       ▼
                                       build_sim_results_embed(dict) → edit message

User clicks Peak Hours
  → for hour in 0..23: local_simulate(state@hour)
  → build_peak_hours_embed(results) → edit message   (0 API calls)
```

---

## Error Handling

- **Fallback-bait API call fails** (network/HTTP): show the existing `EmbedBuilder.error("API Error", ...)` — same as Phase 3.
- **`loot_weights.json` missing**: engine uses loot_weight 0; results still render (fish % marginally inflated). Logged at startup.
- **Unknown location/tool in state**: engine returns empty table; embed shows "No Location"/no creatures, matching current behavior for unset state.
- **Empty eligible pool** (e.g. magnet-fishing-rope, which catches no fish): table contains only the loot line — valid, matches API.

---

## Testing

`tests/test_fishing_engine.py` (new), using the captured sample files in `sampling_data/` as golden fixtures:

- `is_time_active` — normal, reversed, boundary hours, no-time
- `eligible_creatures` — location/tool/boss/mythical/time filters
- `local_simulate` reproduces **exact** fish % for a baseline lake@12 sample (assert each fish within 1e-6 of the recorded API value)
- `local_simulate` matches the 24-hour lake time sweep (all hours)
- `npcChance` per tool; `failChance` per location
- `anglerTuesday` → fail 0; `bosses` adds boss creatures
- vintage / timely / magnet bait transforms match their samples
- fallback baits (lucky + any unpromoted of ghastly/gift/work/farmer) route to fallback (engine raises/sentinels)

`tests/test_simulator_cog.py` (extend):
- Calculate with a local bait calls the engine, not the API (monkeypatch both; assert which fires)
- Calculate with a fallback bait calls the API
- Peak Hours produces a 24-row embed and never calls the API

No live API calls in the test suite — all assertions run against committed sample fixtures.

---

## Out of Scope (Phase 4)

- Itemized loot names and per-item loot chances in local mode (aggregate line only)
- Variant / high-quality chance breakdown in local mode
- Modeling event effects, `locationWinner`, or skills on the distribution (confirmed no/!modeled effect)
- Caching API responses (the local engine removes the need)
- The encyclopedia expansion, creature time-window display, and invasion object (separate future phases)
