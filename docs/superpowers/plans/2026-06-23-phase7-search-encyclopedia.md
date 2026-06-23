# Phase 7 — Search & Discovery + Encyclopedia Enhancements

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/searchfish`, `/searchlocation`, `/creatures` commands; fill in missing `/fish` TOOLS section, `/tool` SUPPORTED FISH section, `/fishcompare` Best Tool row; and add Tool + Type filter rows to `/fishlist`.

**Architecture:** All new data comes from the already-loaded `DankMemerGameClient` dicts (`fish_by_id`, `tool_by_id`, `location_by_id`). No new DB tables. Bot auto-loads all `cogs/*.py` files, so creating `cogs/search.py` is sufficient registration. `build_tool_embed` gains a `dc` optional param; all existing callers updated.

**Tech Stack:** discord.py 2.x, Python 3.12, pytest-asyncio, dankmemer>=1.0.0rc2

## ⚠️ Simulator cleanup — pre-confirmed no-op

The spec says to remove "disabled weather selects" at lines 484/700 in `cogs/simulator.py`. Investigation shows those lines are:
- Line 484: bait select disabled when the chosen tool doesn't support bait (e.g. Bare Hand) — **legitimate feature, keep**
- Line 700: fish select in PeakHoursView disabled until location+tool are chosen — **legitimate feature, keep**

Neither is weather-related. There is nothing to clean up. Do not modify `cogs/simulator.py`.

## Global Constraints

- discord.py 2.x patterns: Views with `self.message`, `on_timeout` disables children + edits message in try/except, `interaction.original_response()` for storing message
- All `discord.SelectOption` for game items use `emoji=emoji_from_url(item.imageURL)` (returns `None` gracefully — Discord renders no emoji rather than crashing)
- `emoji_from_url` lives in `utils/embeds.py`, imported from there
- `is_available_now`, `rarity_rank`, `rarity_emoji` all live in `utils/formatters.py`
- No weather mechanic in Dank Memer — do not add any weather feature
- No `fishing_rod` DB column — use `current_tool`, `current_bait`
- Preload guard pattern: `if not dc.fish_by_id: await interaction.response.send_message(embed=EmbedBuilder.error("Loading", "⏳ Data is still loading…"), ephemeral=True); return`
- `build_tool_embed(tool, dc=None)` — `dc` optional; callers in `cogs/tools.py` pass `self.bot.dank_client`
- `build_fish_compare_embed(c1, c2, dc=None)` — `dc` optional; callers pass dank_client
- Test runner: `python -m pytest tests/<file>.py -v`

---

### Task 1: `emoji_from_url` helper + fixture updates

**Files:**
- Modify: `utils/embeds.py` (top of file, after imports)
- Modify: `tests/conftest.py` (add `tools` kwarg to `make_creature`, `type` kwarg to `make_location`)
- Create: `tests/test_search_cog.py`

**Interfaces:**
- Produces: `emoji_from_url(url: str | None) -> discord.PartialEmoji | None` in `utils/embeds.py`
- Produces: `make_creature(..., tools=None)` — `tools` kwarg adds `{"rod": {"min": 1, "max": 3}}` style dict to `extra.tools`
- Produces: `make_location(..., loc_type="saltwater")` — `loc_type` kwarg adds `"type"` key to `extra`

- [ ] **Step 1: Write failing tests**

In `tests/test_search_cog.py`:

```python
"""Tests for cogs/search.py and utils/embeds.emoji_from_url."""
from __future__ import annotations
import discord
import pytest
from tests.conftest import make_creature, make_location, make_tool


def test_emoji_from_url_png():
    from utils.embeds import emoji_from_url
    e = emoji_from_url("https://cdn.discordapp.com/emojis/1162188819832000572.png")
    assert isinstance(e, discord.PartialEmoji)
    assert e.id == 1162188819832000572
    assert e.animated is False


def test_emoji_from_url_gif():
    from utils.embeds import emoji_from_url
    e = emoji_from_url("https://cdn.discordapp.com/emojis/1162188818225569802.gif")
    assert isinstance(e, discord.PartialEmoji)
    assert e.id == 1162188818225569802
    assert e.animated is True


def test_emoji_from_url_none():
    from utils.embeds import emoji_from_url
    assert emoji_from_url(None) is None
    assert emoji_from_url("https://example.com/image.png") is None
    assert emoji_from_url("") is None


def test_make_creature_tools_field():
    c = make_creature(tools={"fishing-rod": {"min": 1, "max": 3}})
    assert c.extra.get("tools") == {"fishing-rod": {"min": 1, "max": 3}}


def test_make_location_type_field():
    loc = make_location(loc_type="saltwater")
    assert loc.extra.get("type") == "saltwater"
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_search_cog.py -v
```
Expected: FAIL — `ImportError: cannot import name 'emoji_from_url'` and `TypeError` for unknown kwargs

- [ ] **Step 3: Add `emoji_from_url` to `utils/embeds.py`**

Add after the existing imports at the top (after line `_SEP = "───..."`):

```python
import re as _re


def emoji_from_url(url: str | None) -> discord.PartialEmoji | None:
    if not url:
        return None
    m = _re.search(r'/emojis/(\d+)\.(png|gif)$', url)
    if not m:
        return None
    return discord.PartialEmoji(name='_', id=int(m.group(1)), animated=m.group(2) == 'gif')
```

- [ ] **Step 4: Update `tests/conftest.py` — add `tools` to `make_creature`**

In `make_creature`, add `tools=None` parameter and add `"tools": tools or {}` to the `extra` DotDict:

```python
def make_creature(
    id="goldfish",
    name="Goldfish",
    imageURL="https://cdn.discordapp.com/emojis/1109186607120130049.png",
    rarity="Common",
    boss=False,
    mythical=False,
    flavor="A shiny fish.",
    locations=None,
    start_h=0,
    end_h=6,
    full_day=False,
    variants=None,
    tools=None,
):
    time_data = {"full_day": full_day}
    if not full_day:
        time_data["start"] = dt_time(hour=start_h)
        time_data["end"] = dt_time(hour=end_h)
    extra = DotDict({
        "boss": boss,
        "mythical": mythical,
        "rarity": rarity,
        "flavor": flavor,
        "locations": locations or ["loc1"],
        "time": time_data,
        "variants": variants or [],
        "tools": tools or {},
    })
    return Creature(id=id, name=name, imageURL=imageURL, extra=extra)
```

Note: `imageURL` default updated to a real CDN URL so `emoji_from_url` tests work on creatures too.

- [ ] **Step 5: Update `tests/conftest.py` — add `loc_type` to `make_location`**

Add `loc_type="saltwater"` parameter and `"type": loc_type` to the extra DotDict:

```python
def make_location(
    id="sunken_ship",
    name="Sunken Ship",
    imageURL="https://cdn.discordapp.com/emojis/1157173307263688754.png",
    bannerURL="https://example.com/banner.png",
    thumbnailURL="https://example.com/thumb.png",
    creatures=None,
    disabled=False,
    temporary=False,
    failChance=10,
    mineChance=5,
    npcs=None,
    rarity_fish=None,
    loc_type="saltwater",
):
    extra = DotDict({
        "bannerURL": bannerURL,
        "thumbnailURL": thumbnailURL,
        "creatures": creatures or ["goldfish"],
        "disabled": disabled,
        "temporary": temporary,
        "failChance": failChance,
        "mineChance": mineChance,
        "npcs": npcs or [],
        "days": [],
        "type": loc_type,
    })
    return Location(
        id=id,
        name=name,
        imageURL=imageURL,
        extra=extra,
        rarityFish=rarity_fish or {"Common": ["goldfish"]},
        variantsData={},
    )
```

- [ ] **Step 6: Run tests to verify they pass**

```
python -m pytest tests/test_search_cog.py -v
```
Expected: 5 PASSED

- [ ] **Step 7: Run full suite to verify no regressions**

```
python -m pytest tests/ -q
```
Expected: all existing tests still pass (conftest changes are backward-compatible — `tools=None` defaults to `{}`)

- [ ] **Step 8: Commit**

```bash
git add utils/embeds.py tests/conftest.py tests/test_search_cog.py
git commit -m "feat: add emoji_from_url helper, update test fixtures with tools/type fields"
```

---

### Task 2: `/fish` embed — TOOLS section + Best Location

**Files:**
- Modify: `utils/embeds.py` — update `build_fish_embed`
- Modify: `tests/test_fish_cog.py` — add 2 tests
- Modify: `tests/test_embeds.py` — if embed tests exist there, add there; otherwise add to test_fish_cog.py

**Interfaces:**
- Consumes: `emoji_from_url` from Task 1 (already in `utils/embeds.py`)
- Consumes: `make_creature(tools=...)` from Task 1
- `build_fish_embed(creature, dank_client)` — signature unchanged; adds TOOLS section to embed output

- [ ] **Step 1: Write failing tests in `tests/test_fish_cog.py`**

Add at the bottom of the file:

```python
# ---------------------------------------------------------------------------
# build_fish_embed — TOOLS section (Task 2)
# ---------------------------------------------------------------------------

def _make_dc_with_tool():
    from unittest.mock import MagicMock
    from tests.conftest import make_tool, make_location
    dc = MagicMock()
    rod = make_tool(id="fishing-rod", name="Fishing Rod",
                    imageURL="https://cdn.discordapp.com/emojis/1162188819832000572.png")
    harpoon = make_tool(id="harpoon", name="Harpoon",
                        imageURL="https://cdn.discordapp.com/emojis/1162188817135046757.png")
    loc_low = make_location(id="loc_low", name="Easy Beach", failChance=5, loc_type="saltwater")
    loc_high = make_location(id="loc_high", name="Hard Ocean", failChance=20, loc_type="saltwater")
    dc.tool_by_id = {"fishing-rod": rod, "harpoon": harpoon}
    dc.location_by_id = {"loc_low": loc_low, "loc_high": loc_high}
    return dc


def test_fish_embed_tools_section_present():
    from utils.embeds import build_fish_embed
    dc = _make_dc_with_tool()
    c = make_creature(
        tools={"fishing-rod": {"min": 1, "max": 1}, "harpoon": {"min": 1, "max": 3}},
        locations=["loc_low", "loc_high"],
    )
    embed = build_fish_embed(c, dc)
    assert "TOOLS" in (embed.description or "")
    assert "Fishing Rod" in (embed.description or "")
    assert "Harpoon" in (embed.description or "")


def test_fish_embed_best_tool_marked():
    from utils.embeds import build_fish_embed
    dc = _make_dc_with_tool()
    c = make_creature(
        tools={"fishing-rod": {"min": 1, "max": 1}, "harpoon": {"min": 1, "max": 3}},
        locations=["loc_low"],
    )
    embed = build_fish_embed(c, dc)
    desc = embed.description or ""
    # Harpoon has max=3, Fishing Rod has max=1 — only Harpoon should be marked Best
    harpoon_line = next((l for l in desc.splitlines() if "Harpoon" in l), "")
    rod_line = next((l for l in desc.splitlines() if "Fishing Rod" in l), "")
    assert "⭐" in harpoon_line
    assert "⭐" not in rod_line


def test_fish_embed_best_location_lowest_fail():
    from utils.embeds import build_fish_embed
    dc = _make_dc_with_tool()
    c = make_creature(
        tools={"fishing-rod": {"min": 1, "max": 1}},
        locations=["loc_low", "loc_high"],
    )
    embed = build_fish_embed(c, dc)
    desc = embed.description or ""
    # Best Location = loc_low (failChance=5), not loc_high (failChance=20)
    assert "Easy Beach" in desc
    assert "Best Location" in desc
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_fish_cog.py::test_fish_embed_tools_section_present tests/test_fish_cog.py::test_fish_embed_best_tool_marked tests/test_fish_cog.py::test_fish_embed_best_location_lowest_fail -v
```
Expected: FAIL — TOOLS section not yet in embed

- [ ] **Step 3: Update `build_fish_embed` in `utils/embeds.py`**

After the Variants section (after `lines += ["", _SEP]` at line ~106), add the TOOLS + Best Location section before the final `lines += ["", _SEP]`. Replace the final two lines of build_fish_embed:

```python
    # Remove the existing final `lines += ["", _SEP]` and replace with:

    # Tools section
    tools_data = extra.get("tools") or {}
    if tools_data and dank_client.tool_by_id:
        best_max = max((v.get("max", 0) for v in tools_data.values()), default=0)
        tool_lines = []
        for tid, catch in tools_data.items():
            t = dank_client.tool_by_id.get(tid)
            if t is None:
                continue
            lo, hi = catch.get("min", 0), catch.get("max", 0)
            star = "  ⭐ Best" if hi == best_max and best_max > 0 else ""
            tool_lines.append(f"**{t.name}** — {lo}–{hi}{star}")
        if tool_lines:
            lines += ["", _SEP, f"**🔧 TOOLS  ({len(tool_lines)})**"]
            lines.extend(tool_lines)

    # Best Location
    loc_ids = extra.get("locations") or []
    best_loc = None
    best_fail = None
    for lid in loc_ids:
        loc = dank_client.location_by_id.get(lid)
        if loc is None:
            continue
        fail = loc.extra.get("failChance", 100) if hasattr(loc.extra, "get") else 100
        if best_fail is None or fail < best_fail or (fail == best_fail and loc.name < best_loc.name):
            best_fail = fail
            best_loc = loc
    if best_loc is not None:
        lines += ["", f"📍 **Best Location:** {best_loc.name}  (fail: {best_fail}%)"]

    lines += ["", _SEP]
    embed.description = "\n".join(lines)[:4096]
    embed.set_footer(text=f"Internal ID: {creature.id}")
    return embed
```

**Important:** The existing code already ends with:
```python
    lines += ["", _SEP]
    embed.description = "\n".join(lines)[:4096]
    embed.set_footer(text=f"Internal ID: {creature.id}")
    return embed
```
Replace those 3 lines with the full block above.

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_fish_cog.py -v
```
Expected: all pass including 3 new tests

- [ ] **Step 5: Commit**

```bash
git add utils/embeds.py tests/test_fish_cog.py
git commit -m "feat: add TOOLS section and Best Location to /fish embed"
```

---

### Task 3: `/tool` embed — SUPPORTED FISH section

**Files:**
- Modify: `utils/embeds.py` — update `build_tool_embed` signature and add FISH section
- Modify: `cogs/tools.py` — update `build_tool_embed(t)` call to `build_tool_embed(t, self.bot.dank_client)`
- Modify: `tests/test_tools_cog.py` — add 2 tests

**Interfaces:**
- Consumes: `rarity_rank` from `utils/formatters.py` (already imported in embeds.py)
- Consumes: `make_creature(tools=...)` from Task 1
- `build_tool_embed(tool, dc=None)` — signature gains optional `dc`; callers in `cogs/tools.py` pass dank_client

- [ ] **Step 1: Write failing tests in `tests/test_tools_cog.py`**

Add at the bottom of the file:

```python
# ---------------------------------------------------------------------------
# build_tool_embed — SUPPORTED FISH section (Task 3)
# ---------------------------------------------------------------------------

def _make_dc_with_fish():
    from unittest.mock import MagicMock
    from tests.conftest import make_creature
    dc = MagicMock()
    bass = make_creature(id="bass", name="Bass", rarity="Common",
                         tools={"rod": {"min": 1, "max": 2}})
    koi = make_creature(id="koi", name="Koi", rarity="Very Rare",
                        tools={"rod": {"min": 1, "max": 1}})
    dc.fish_by_id = {"bass": bass, "koi": koi}
    return dc


def test_tool_embed_fish_section_present():
    from utils.embeds import build_tool_embed
    from tests.conftest import make_tool
    t = make_tool(id="rod", name="Fishing Rod")
    dc = _make_dc_with_fish()
    embed = build_tool_embed(t, dc)
    assert "SUPPORTED FISH" in (embed.description or "")
    assert "Bass" in (embed.description or "")
    assert "Koi" in (embed.description or "")


def test_tool_embed_best_fish_is_highest_rarity():
    from utils.embeds import build_tool_embed
    from tests.conftest import make_tool
    t = make_tool(id="rod", name="Fishing Rod")
    dc = _make_dc_with_fish()
    embed = build_tool_embed(t, dc)
    desc = embed.description or ""
    # Koi is Very Rare (rank 3), Bass is Common (rank 0) — Koi should be Best
    assert "Best" in desc
    best_line = next((l for l in desc.splitlines() if "Best" in l), "")
    assert "Koi" in best_line


def test_tool_embed_no_dc_no_fish_section():
    from utils.embeds import build_tool_embed
    from tests.conftest import make_tool
    t = make_tool(id="rod", name="Fishing Rod")
    embed = build_tool_embed(t)
    assert "SUPPORTED FISH" not in (embed.description or "")
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_tools_cog.py::test_tool_embed_fish_section_present tests/test_tools_cog.py::test_tool_embed_best_fish_is_highest_rarity tests/test_tools_cog.py::test_tool_embed_no_dc_no_fish_section -v
```
Expected: FAIL

- [ ] **Step 3: Update `build_tool_embed` in `utils/embeds.py`**

Change signature from `def build_tool_embed(tool) -> discord.Embed:` to `def build_tool_embed(tool, dc=None) -> discord.Embed:`.

Before the final `embed.description = "\n".join(lines)[:4096]` line, add:

```python
    # Supported Fish section (only when dc provided)
    if dc is not None:
        supported = [
            (f, f.extra.get("tools", {}).get(tool.id, {}))
            for f in dc.fish_by_id.values()
            if tool.id in f.extra.get("tools", {})
        ]
        if supported:
            supported.sort(key=lambda fc: fc[0].name.lower())
            best_fish = max(supported, key=lambda fc: rarity_rank(fc[0].extra.get("rarity", "Common")))[0]
            best_rarity = best_fish.extra.get("rarity", "Common")
            best_catch = supported[[fc[0].id for fc in supported].index(best_fish.id)][1]
            bc_lo, bc_hi = best_catch.get("min", 0), best_catch.get("max", 0)
            lines += ["", _SEP, f"**🐟 SUPPORTED FISH  ({len(supported)})**"]
            lines.append(
                f"Best: **{best_fish.name}** ({best_rarity}) — catches {bc_lo}–{bc_hi}"
            )
            for fish, catch in supported[:12]:
                lo, hi = catch.get("min", 0), catch.get("max", 0)
                lines.append(f"**{fish.name}** — {lo}–{hi}")
            if len(supported) > 12:
                lines.append(f"… and {len(supported) - 12} more")
```

- [ ] **Step 4: Update caller in `cogs/tools.py`**

Find the line `embed = build_tool_embed(t)` (around line 161) and change it to:

```python
        embed = build_tool_embed(t, self.bot.dank_client)
```

- [ ] **Step 5: Run tests to verify they pass**

```
python -m pytest tests/test_tools_cog.py -v
```
Expected: all pass including 3 new tests

- [ ] **Step 6: Run full suite to ensure no regressions**

```
python -m pytest tests/ -q
```
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add utils/embeds.py cogs/tools.py tests/test_tools_cog.py
git commit -m "feat: add SUPPORTED FISH section to /tool embed"
```

---

### Task 4: `/fishcompare` embed — Best Tool + Max Catch rows

**Files:**
- Modify: `utils/embeds.py` — update `build_fish_compare_embed` with `dc=None` param + 2 new rows
- Modify: `cogs/fish.py` — update both callers of `build_fish_compare_embed` to pass `dc`
- Modify: `tests/test_fish_cog.py` — add 2 tests

**Interfaces:**
- `build_fish_compare_embed(c1, c2, dc=None)` — `dc` optional; if omitted, Best Tool row shows "—"
- Callers:
  - `FishCompareModal.on_submit` → has `self.dc` → pass as third arg
  - `FishCog.fishcompare` → has `self.bot.dank_client` → pass as third arg

- [ ] **Step 1: Write failing tests in `tests/test_fish_cog.py`**

Add at the bottom:

```python
# ---------------------------------------------------------------------------
# build_fish_compare_embed — Best Tool + Max Catch rows (Task 4)
# ---------------------------------------------------------------------------

def test_fishcompare_embed_best_tool_row():
    from utils.embeds import build_fish_compare_embed
    from unittest.mock import MagicMock
    from tests.conftest import make_tool
    rod = make_tool(id="fishing-rod", name="Fishing Rod")
    net = make_tool(id="net", name="Net")
    dc = MagicMock()
    dc.tool_by_id = {"fishing-rod": rod, "net": net}
    c1 = make_creature(id="bass", name="Bass", tools={"fishing-rod": {"min": 1, "max": 3}})
    c2 = make_creature(id="koi", name="Koi", tools={"net": {"min": 1, "max": 1}})
    embed = build_fish_compare_embed(c1, c2, dc)
    label_field = embed.fields[0].value
    assert "Best Tool" in label_field
    assert "Max Catch" in label_field


def test_fishcompare_embed_no_dc_shows_dash():
    from utils.embeds import build_fish_compare_embed
    c1 = make_creature(id="bass", name="Bass", tools={"fishing-rod": {"min": 1, "max": 3}})
    c2 = make_creature(id="koi", name="Koi", tools={})
    embed = build_fish_compare_embed(c1, c2)
    label_field = embed.fields[0].value
    # Best Tool row exists even without dc
    assert "Best Tool" in label_field
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_fish_cog.py::test_fishcompare_embed_best_tool_row tests/test_fish_cog.py::test_fishcompare_embed_no_dc_shows_dash -v
```
Expected: FAIL

- [ ] **Step 3: Update `build_fish_compare_embed` in `utils/embeds.py`**

Change signature to `def build_fish_compare_embed(c1, c2, dc=None) -> discord.Embed:`.

Add a helper inside the function and extend `_col`:

```python
def build_fish_compare_embed(c1, c2, dc=None) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚔️  {c1.name}  vs  {c2.name}",
        color=COMPARE_COLOR,
    )
    embed.set_author(name="⚔️ Fish Compare")

    r1, r2 = c1.extra.get("rarity", "Common"), c2.extra.get("rarity", "Common")
    rank1, rank2 = rarity_rank(r1), rarity_rank(r2)
    l1 = len(c1.extra.get("locations") or [])
    l2 = len(c2.extra.get("locations") or [])
    var1 = len(c1.extra.get("variants") or [])
    var2 = len(c2.extra.get("variants") or [])

    def _best_tool_info(c):
        tools_data = c.extra.get("tools") or {}
        if not tools_data:
            return "—", 0
        best_max = max(v.get("max", 0) for v in tools_data.values())
        best_ids = [tid for tid, v in tools_data.items() if v.get("max", 0) == best_max]
        if dc and best_ids and best_ids[0] in dc.tool_by_id:
            name = dc.tool_by_id[best_ids[0]].name
        else:
            name = best_ids[0] if best_ids else "—"
        return name, best_max

    bt1_name, bt1_max = _best_tool_info(c1)
    bt2_name, bt2_max = _best_tool_info(c2)

    def _col(c, other):
        ex, ox = c.extra, other.extra
        rarity = ex.get("rarity", "Common")
        rr = rarity_rank(rarity)
        orr = rarity_rank(ox.get("rarity", "Common"))
        locs = len(ex.get("locations") or [])
        olocs = len(ox.get("locations") or [])
        varis = len(ex.get("variants") or [])
        ovaris = len(ox.get("variants") or [])
        bt_name, bt_max = _best_tool_info(c)
        _, o_max = _best_tool_info(other)
        bt_mark = " ✓" if bt_max > o_max or (bt_max == o_max and bt_max > 0) else ""
        mc_mark = " ✓" if bt_max > o_max else ""
        return "\n".join([
            f"{rarity_emoji(rarity)} {rarity}" + (" ✓" if rr > orr else ""),
            "✅" if ex.get("boss") else "❌",
            "✅" if ex.get("mythical") else "❌",
            format_time_window(c),
            str(locs) + (" ✓" if locs > olocs else ""),
            str(varis) + (" ✓" if varis > ovaris else ""),
            bt_name + bt_mark,
            str(bt_max) + mc_mark,
        ])

    embed.add_field(
        name="​",
        value="**Rarity**\n**Boss**\n**Mythical**\n**Window**\n**Locations**\n**Variants**\n**Best Tool**\n**Max Catch**",
        inline=True,
    )
    embed.add_field(name=c1.name, value=_col(c1, c2), inline=True)
    embed.add_field(name=c2.name, value=_col(c2, c1), inline=True)
    return embed
```

- [ ] **Step 4: Update callers in `cogs/fish.py`**

There are two callers:

**In `FishCompareModal.on_submit`** (around line 44):
```python
        await interaction.response.edit_message(
            embed=build_fish_compare_embed(self.first, second, self.dc),
            view=BackToFishView(creature=self.first, dank_client=self.dc, db=self.db, user_id=self.user_id),
        )
```

**In `FishCog.fishcompare`** (around line 340):
```python
        await interaction.response.send_message(embed=build_fish_compare_embed(c1, c2, self.bot.dank_client))
```

- [ ] **Step 5: Run tests to verify they pass**

```
python -m pytest tests/test_fish_cog.py -v
```
Expected: all pass including 2 new tests

- [ ] **Step 6: Commit**

```bash
git add utils/embeds.py cogs/fish.py tests/test_fish_cog.py
git commit -m "feat: add Best Tool and Max Catch rows to /fishcompare embed"
```

---

### Task 5: `FishListView` — Tool filter (row 3) + Type flags filter (row 4)

**Files:**
- Modify: `cogs/fish.py` — add `tool_filter`, `type_filter` attrs + 2 new `@discord.ui.select` callbacks + update `_refresh()`
- Modify: `utils/embeds.py` — update `build_fishlist_embed` to accept and show new filter params
- Modify: `tests/test_fish_cog.py` — add 2 tests

**Interfaces:**
- Consumes: `emoji_from_url` from Task 1 (already in `utils/embeds.py`, must import in `cogs/fish.py`)
- Consumes: `is_available_now` from `utils/formatters.py` (already imported in `utils/embeds.py`; must import in `cogs/fish.py` for `FishListView._refresh`)
- `build_fishlist_embed(creatures, page, total_pages, sort, rarity_filter, tool_filter="All", type_filter="All")` — signature gains two optional kwargs

- [ ] **Step 1: Write failing tests in `tests/test_fish_cog.py`**

Add at the bottom:

```python
# ---------------------------------------------------------------------------
# FishListView — new filters (Task 5)
# ---------------------------------------------------------------------------

def _make_fishlist_dc():
    from unittest.mock import MagicMock
    from tests.conftest import make_tool
    rod = make_tool(id="fishing-rod", name="Fishing Rod",
                    imageURL="https://cdn.discordapp.com/emojis/1162188819832000572.png")
    net = make_tool(id="net", name="Net",
                    imageURL="https://cdn.discordapp.com/emojis/1162188813259522070.png")
    c_rod = make_creature(id="bass", name="Bass",
                          tools={"fishing-rod": {"min": 1, "max": 2}}, full_day=True)
    c_net = make_creature(id="trout", name="Trout",
                          tools={"net": {"min": 1, "max": 3}}, full_day=True)
    c_both = make_creature(id="koi", name="Koi",
                           tools={"fishing-rod": {"min": 1, "max": 1}, "net": {"min": 1, "max": 2}},
                           full_day=True)
    dc = MagicMock()
    dc.fish_by_id = {"bass": c_rod, "trout": c_net, "koi": c_both}
    dc.tool_by_id = {"fishing-rod": rod, "net": net}
    return dc


def test_fishlist_tool_filter_narrows_results():
    from cogs.fish import FishListView
    dc = _make_fishlist_dc()
    view = FishListView(dc)
    view.tool_filter = "fishing-rod"
    view._refresh()
    ids = [c.id for c in view.filtered]
    assert "bass" in ids
    assert "koi" in ids
    assert "trout" not in ids


def test_fishlist_type_filter_available_now():
    from cogs.fish import FishListView
    dc = _make_fishlist_dc()
    view = FishListView(dc)
    view.type_filter = "Available Now"
    view._refresh()
    # All 3 creatures are full_day=True → all should pass Available Now filter
    assert len(view.filtered) == 3


def test_fishlist_type_filter_has_variants():
    from cogs.fish import FishListView
    dc = _make_fishlist_dc()
    c_variant = make_creature(id="variant_fish", name="Variant Fish",
                               variants=[{"name": "Gold", "chance": 5}], full_day=True)
    dc.fish_by_id["variant_fish"] = c_variant
    view = FishListView(dc)
    view.type_filter = "Has Variants"
    view._refresh()
    assert len(view.filtered) == 1
    assert view.filtered[0].id == "variant_fish"
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_fish_cog.py::test_fishlist_tool_filter_narrows_results tests/test_fish_cog.py::test_fishlist_type_filter_available_now tests/test_fish_cog.py::test_fishlist_type_filter_has_variants -v
```
Expected: FAIL — `FishListView` has no `tool_filter`

- [ ] **Step 3: Update `cogs/fish.py` — FishListView**

Add import at the top of `cogs/fish.py`:
```python
from utils.embeds import (
    EmbedBuilder,
    build_fish_embed,
    build_fish_compare_embed,
    build_peak_hours_embed,
    build_fishlist_embed,
    emoji_from_url,
)
from utils.formatters import rarity_rank, is_available_now
```

Replace the entire `FishListView` class with:

```python
class FishListView(DynamicPaginationView):
    ITEMS_PER_PAGE = 10

    def __init__(self, dank_client):
        super().__init__()
        self.dc = dank_client
        self.sort = "alphabetical"
        self.rarity_filter = "All"
        self.tool_filter = "All"
        self.type_filter = "All"
        # Override tool select options with actual tool data
        for item in self.children:
            if isinstance(item, discord.ui.Select) and "Tool" in (item.placeholder or ""):
                item.options = [
                    discord.SelectOption(label="All tools", value="All", default=True)
                ] + [
                    discord.SelectOption(
                        label=t.name,
                        value=t.id,
                        emoji=emoji_from_url(t.imageURL),
                    )
                    for t in sorted(self.dc.tool_by_id.values(), key=lambda x: x.name)
                ]
        self._refresh()

    def _refresh(self):
        creatures = list(self.dc.fish_by_id.values())
        if self.rarity_filter == "Boss":
            creatures = [c for c in creatures if c.extra.get("boss")]
        elif self.rarity_filter == "Mythical only":
            creatures = [c for c in creatures if c.extra.get("mythical")]
        elif self.rarity_filter != "All":
            creatures = [c for c in creatures if c.extra.get("rarity") == self.rarity_filter]
        if self.tool_filter != "All":
            creatures = [c for c in creatures if self.tool_filter in c.extra.get("tools", {})]
        if self.type_filter == "Has Variants":
            creatures = [c for c in creatures if c.extra.get("variants")]
        elif self.type_filter == "Available Now":
            creatures = [c for c in creatures if is_available_now(c)]
        elif self.type_filter == "Boss":
            creatures = [c for c in creatures if c.extra.get("boss")]
        elif self.type_filter == "Mythical":
            creatures = [c for c in creatures if c.extra.get("mythical")]

        if self.sort == "alphabetical":
            creatures.sort(key=lambda c: c.name.lower())
        elif self.sort == "rarity_asc":
            creatures.sort(key=lambda c: rarity_rank(c.extra.get("rarity", "Common")))
        elif self.sort == "rarity_desc":
            creatures.sort(key=lambda c: -rarity_rank(c.extra.get("rarity", "Common")))

        self.filtered = creatures
        self.total_pages = max(1, (len(creatures) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        self.page = min(self.page, self.total_pages - 1)
        self._refresh_page_btn()

    def build_embed(self) -> discord.Embed:
        return build_fishlist_embed(
            self.filtered, self.page, self.total_pages, self.sort, self.rarity_filter,
            tool_filter=self.tool_filter, type_filter=self.type_filter,
        )

    @discord.ui.select(
        placeholder="📊 Sort ▾",
        row=1,
        options=[
            discord.SelectOption(label="Alphabetical", value="alphabetical", default=True),
            discord.SelectOption(label="Rarity (Common → Mythical)", value="rarity_asc"),
            discord.SelectOption(label="Rarity (Mythical → Common)", value="rarity_desc"),
        ],
    )
    async def sort_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.sort = select.values[0]
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.select(
        placeholder="🔍 Filter Rarity ▾",
        row=2,
        options=[
            discord.SelectOption(label="All", value="All", default=True),
            discord.SelectOption(label="⚪ Common", value="Common"),
            discord.SelectOption(label="🟢 Uncommon", value="Uncommon"),
            discord.SelectOption(label="🔵 Rare", value="Rare"),
            discord.SelectOption(label="🟣 Very Rare", value="Very Rare"),
            discord.SelectOption(label="🔴 Absurdly Rare", value="Absurdly Rare"),
            discord.SelectOption(label="🌟 Mythical", value="Mythical"),
            discord.SelectOption(label="👑 Boss only", value="Boss"),
            discord.SelectOption(label="✨ Mythical flag only", value="Mythical only"),
        ],
    )
    async def rarity_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.rarity_filter = select.values[0]
        self.page = 0
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.select(
        placeholder="🔧 Filter Tool ▾",
        row=3,
        options=[discord.SelectOption(label="All tools", value="All", default=True)],
    )
    async def tool_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.tool_filter = select.values[0]
        self.page = 0
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.select(
        placeholder="🏷️ Filter Type ▾",
        row=4,
        options=[
            discord.SelectOption(label="All", value="All", default=True),
            discord.SelectOption(label="✨ Has Variants", value="Has Variants"),
            discord.SelectOption(label="✅ Available Now", value="Available Now"),
            discord.SelectOption(label="👑 Boss", value="Boss"),
            discord.SelectOption(label="⭐ Mythical", value="Mythical"),
        ],
    )
    async def type_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.type_filter = select.values[0]
        self.page = 0
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
```

- [ ] **Step 4: Update `build_fishlist_embed` in `utils/embeds.py`**

Change signature to:
```python
def build_fishlist_embed(
    creatures: list,
    page: int,
    total_pages: int,
    sort: str,
    rarity_filter: str,
    tool_filter: str = "All",
    type_filter: str = "All",
) -> discord.Embed:
```

Update the footer line from:
```python
    embed.set_footer(text=f"Page {page + 1} / {total_pages}  ·  Sort: {sort}  ·  Filter: {rarity_filter}")
```
to:
```python
    active = [f"Sort: {sort}", f"Rarity: {rarity_filter}"]
    if tool_filter != "All":
        active.append(f"Tool: {tool_filter}")
    if type_filter != "All":
        active.append(f"Type: {type_filter}")
    embed.set_footer(text=f"Page {page + 1} / {total_pages}  ·  " + "  ·  ".join(active))
```

- [ ] **Step 5: Run tests to verify they pass**

```
python -m pytest tests/test_fish_cog.py -v
```
Expected: all pass including 3 new tests

- [ ] **Step 6: Run full suite**

```
python -m pytest tests/ -q
```
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add cogs/fish.py utils/embeds.py tests/test_fish_cog.py
git commit -m "feat: add Tool filter and Type flags filter rows to /fishlist"
```

---

### Task 6: `cogs/search.py` — `SearchFishView` + `/searchfish` + `/creatures`

**Files:**
- Create: `cogs/search.py`
- Modify: `tests/test_search_cog.py` — add SearchFishView + embed tests

**Interfaces:**
- Consumes: `emoji_from_url` from `utils/embeds.py` (Task 1)
- Consumes: `is_available_now`, `rarity_rank`, `rarity_emoji` from `utils/formatters.py`
- Consumes: `DynamicPaginationView` from `utils/views.py`
- Produces: `SearchFishView`, `build_search_fish_embed`, `SearchCog` with `/searchfish` and `/creatures`

- [ ] **Step 1: Write failing tests in `tests/test_search_cog.py`**

Add to the existing file:

```python
# ---------------------------------------------------------------------------
# build_search_fish_embed + SearchFishView (Task 6)
# ---------------------------------------------------------------------------

def _make_search_dc():
    from unittest.mock import MagicMock
    from tests.conftest import make_tool
    rod = make_tool(id="fishing-rod", name="Fishing Rod",
                    imageURL="https://cdn.discordapp.com/emojis/1162188819832000572.png")
    net = make_tool(id="net", name="Net",
                    imageURL="https://cdn.discordapp.com/emojis/1162188813259522070.png")
    bass = make_creature(id="bass", name="Bass", rarity="Common",
                         tools={"fishing-rod": {"min": 1, "max": 2}}, full_day=True)
    trout = make_creature(id="trout", name="Trout", rarity="Rare",
                          tools={"net": {"min": 1, "max": 3}}, full_day=True)
    koi = make_creature(id="koi", name="Koi", rarity="Very Rare",
                        tools={"fishing-rod": {"min": 1, "max": 1}}, full_day=True,
                        variants=[{"name": "Gold Koi", "chance": 5}])
    dc = MagicMock()
    dc.fish_by_id = {"bass": bass, "trout": trout, "koi": koi}
    dc.tool_by_id = {"fishing-rod": rod, "net": net}
    dc.location_by_id = {}
    return dc


def test_build_search_fish_embed_shows_fish_names():
    from cogs.search import build_search_fish_embed
    dc = _make_search_dc()
    creatures = list(dc.fish_by_id.values())
    creatures.sort(key=lambda c: c.name.lower())
    embed = build_search_fish_embed(creatures, page=0, total_pages=1, dc=dc)
    desc = embed.description or ""
    assert "Bass" in desc
    assert "Trout" in desc
    assert "Koi" in desc


def test_build_search_fish_embed_zero_results():
    from cogs.search import build_search_fish_embed
    dc = _make_search_dc()
    embed = build_search_fish_embed([], page=0, total_pages=1, dc=dc)
    assert "No fish" in (embed.description or "")


def test_search_fish_view_tool_filter():
    from cogs.search import SearchFishView
    dc = _make_search_dc()
    view = SearchFishView(dc)
    view.tool_filter = "fishing-rod"
    view._refresh()
    ids = [c.id for c in view.filtered]
    assert "bass" in ids
    assert "koi" in ids
    assert "trout" not in ids


def test_search_fish_view_rarity_filter():
    from cogs.search import SearchFishView
    dc = _make_search_dc()
    view = SearchFishView(dc)
    view.rarity_filter = "Rare"
    view._refresh()
    assert len(view.filtered) == 1
    assert view.filtered[0].id == "trout"


def test_search_fish_view_type_filter_variants():
    from cogs.search import SearchFishView
    dc = _make_search_dc()
    view = SearchFishView(dc)
    view.type_filter = "Has Variants"
    view._refresh()
    assert len(view.filtered) == 1
    assert view.filtered[0].id == "koi"


def test_creatures_embed_title():
    from cogs.search import build_search_fish_embed
    dc = _make_search_dc()
    embed = build_search_fish_embed([], page=0, total_pages=1, dc=dc, title="🦎 Creatures")
    assert "Creatures" in embed.title
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_search_cog.py -v -k "search_fish or creatures"
```
Expected: FAIL — `cogs/search.py` doesn't exist yet

- [ ] **Step 3: Create `cogs/search.py`**

```python
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder, emoji_from_url
from utils.views import DynamicPaginationView
from utils.formatters import is_available_now, rarity_rank, rarity_emoji

_PRELOAD_GUARD_MSG = "⏳ Data is still loading, please try again in a moment."


def build_search_fish_embed(
    creatures: list,
    page: int,
    total_pages: int,
    dc,
    title: str = "🔍 Fish Search",
) -> discord.Embed:
    embed = discord.Embed(title=title, color=0x5865f2)
    embed.set_author(name="🔍 Search")
    if not creatures:
        embed.description = "No fish match these filters."
        embed.set_footer(text="0 results")
        return embed
    ITEMS = 10
    page_slice = creatures[page * ITEMS: page * ITEMS + ITEMS]
    lines = []
    for c in page_slice:
        rarity = c.extra.get("rarity", "Common")
        rem = rarity_emoji(rarity)
        locs = len(c.extra.get("locations") or [])
        lines.append(f"{rem} **{c.name}**  ·  {rarity}  ·  {locs} loc{'s' if locs != 1 else ''}")
    embed.description = "\n".join(lines)
    embed.set_footer(text=f"Page {page + 1} / {total_pages}  ·  {len(creatures)} results")
    return embed


class SearchFishView(DynamicPaginationView):
    ITEMS_PER_PAGE = 10

    def __init__(self, dank_client, title: str = "🔍 Fish Search"):
        super().__init__()
        self.dc = dank_client
        self.title = title
        self.rarity_filter = "All"
        self.tool_filter = "All"
        self.type_filter = "All"
        # Override tool select options with actual data
        for item in self.children:
            if isinstance(item, discord.ui.Select) and "Tool" in (item.placeholder or ""):
                item.options = [
                    discord.SelectOption(label="All tools", value="All", default=True)
                ] + [
                    discord.SelectOption(
                        label=t.name,
                        value=t.id,
                        emoji=emoji_from_url(t.imageURL),
                    )
                    for t in sorted(self.dc.tool_by_id.values(), key=lambda x: x.name)
                ]
        self._refresh()

    def _refresh(self):
        creatures = list(self.dc.fish_by_id.values())
        if self.rarity_filter == "Boss":
            creatures = [c for c in creatures if c.extra.get("boss")]
        elif self.rarity_filter == "Mythical":
            creatures = [c for c in creatures if c.extra.get("mythical")]
        elif self.rarity_filter != "All":
            creatures = [c for c in creatures if c.extra.get("rarity") == self.rarity_filter]
        if self.tool_filter != "All":
            creatures = [c for c in creatures if self.tool_filter in c.extra.get("tools", {})]
        if self.type_filter == "Has Variants":
            creatures = [c for c in creatures if c.extra.get("variants")]
        elif self.type_filter == "Available Now":
            creatures = [c for c in creatures if is_available_now(c)]
        creatures.sort(key=lambda c: c.name.lower())
        self.filtered = creatures
        self.total_pages = max(1, (len(creatures) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        self.page = min(self.page, self.total_pages - 1)
        self._refresh_page_btn()

    def build_embed(self) -> discord.Embed:
        return build_search_fish_embed(
            self.filtered, self.page, self.total_pages, self.dc, title=self.title
        )

    @discord.ui.select(
        placeholder="🔍 Filter Rarity ▾",
        row=1,
        options=[
            discord.SelectOption(label="All", value="All", default=True),
            discord.SelectOption(label="⚪ Common", value="Common"),
            discord.SelectOption(label="🟢 Uncommon", value="Uncommon"),
            discord.SelectOption(label="🔵 Rare", value="Rare"),
            discord.SelectOption(label="🟣 Very Rare", value="Very Rare"),
            discord.SelectOption(label="🔴 Absurdly Rare", value="Absurdly Rare"),
            discord.SelectOption(label="🌟 Mythical", value="Mythical"),
            discord.SelectOption(label="👑 Boss", value="Boss"),
        ],
    )
    async def rarity_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.rarity_filter = select.values[0]
        self.page = 0
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.select(
        placeholder="🔧 Filter Tool ▾",
        row=2,
        options=[discord.SelectOption(label="All tools", value="All", default=True)],
    )
    async def tool_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.tool_filter = select.values[0]
        self.page = 0
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.select(
        placeholder="🏷️ Filter Type ▾",
        row=3,
        options=[
            discord.SelectOption(label="All", value="All", default=True),
            discord.SelectOption(label="✨ Has Variants", value="Has Variants"),
            discord.SelectOption(label="✅ Available Now", value="Available Now"),
        ],
    )
    async def type_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.type_filter = select.values[0]
        self.page = 0
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=4)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class SearchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _guard(self) -> bool:
        return bool(self.bot.dank_client and self.bot.dank_client.fish_by_id)

    @app_commands.command(name="searchfish", description="Search fish with multiple filters")
    async def searchfish(self, interaction: discord.Interaction):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        view = SearchFishView(self.bot.dank_client)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="creatures", description="Browse all creatures")
    async def creatures(self, interaction: discord.Interaction):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        view = SearchFishView(self.bot.dank_client, title="🦎 Creatures")
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SearchCog(bot))
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_search_cog.py -v
```
Expected: all pass

- [ ] **Step 5: Run full suite**

```
python -m pytest tests/ -q
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add cogs/search.py tests/test_search_cog.py
git commit -m "feat: add /searchfish and /creatures commands with SearchFishView"
```

---

### Task 7: `cogs/search.py` — `SearchLocationView` + `/searchlocation`

**Files:**
- Modify: `cogs/search.py` — add `SearchLocationView`, `build_search_location_embed`, `/searchlocation` command
- Modify: `tests/test_search_cog.py` — add SearchLocationView tests

**Interfaces:**
- Consumes: `emoji_from_url` from `utils/embeds.py`
- Produces: `SearchLocationView`, `build_search_location_embed`
- `/searchlocation` added to `SearchCog`

- [ ] **Step 1: Write failing tests in `tests/test_search_cog.py`**

Add at the bottom:

```python
# ---------------------------------------------------------------------------
# build_search_location_embed + SearchLocationView (Task 7)
# ---------------------------------------------------------------------------

def _make_loc_dc():
    from unittest.mock import MagicMock
    loc_sw1 = make_location(id="beach", name="Beach", failChance=5, mineChance=90,
                             loc_type="saltwater", creatures=["bass", "koi"])
    loc_sw2 = make_location(id="ocean", name="Ocean", failChance=15, mineChance=70,
                             loc_type="saltwater", creatures=["bass"])
    loc_fw = make_location(id="river", name="River", failChance=8, mineChance=60,
                            loc_type="freshwater", creatures=["trout", "koi", "bass"])
    dc = MagicMock()
    dc.location_by_id = {"beach": loc_sw1, "ocean": loc_sw2, "river": loc_fw}
    return dc


def test_build_search_location_embed_shows_all():
    from cogs.search import build_search_location_embed
    dc = _make_loc_dc()
    locs = list(dc.location_by_id.values())
    embed = build_search_location_embed(locs)
    desc = embed.description or ""
    assert "Beach" in desc
    assert "Ocean" in desc
    assert "River" in desc


def test_build_search_location_embed_zero_results():
    from cogs.search import build_search_location_embed
    embed = build_search_location_embed([])
    assert "No locations" in (embed.description or "")


def test_search_location_type_filter_saltwater():
    from cogs.search import SearchLocationView
    dc = _make_loc_dc()
    view = SearchLocationView(dc)
    view.type_filter = "saltwater"
    locs = view._filtered_sorted()
    names = [l.name for l in locs]
    assert "Beach" in names
    assert "Ocean" in names
    assert "River" not in names


def test_search_location_sort_fail_asc():
    from cogs.search import SearchLocationView
    dc = _make_loc_dc()
    view = SearchLocationView(dc)
    view.sort = "fail_asc"
    locs = view._filtered_sorted()
    fails = [l.extra.get("failChance") for l in locs]
    assert fails == sorted(fails)


def test_search_location_sort_fish_count_desc():
    from cogs.search import SearchLocationView
    dc = _make_loc_dc()
    view = SearchLocationView(dc)
    view.sort = "fish_count"
    locs = view._filtered_sorted()
    counts = [len(l.extra.get("creatures", [])) for l in locs]
    assert counts == sorted(counts, reverse=True)
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_search_cog.py -v -k "location"
```
Expected: FAIL

- [ ] **Step 3: Add `SearchLocationView` and `/searchlocation` to `cogs/search.py`**

Add after `SearchFishView` class and before `SearchCog`:

```python
def build_search_location_embed(locations: list) -> discord.Embed:
    embed = discord.Embed(title="🔍 Location Search", color=0x00b4d8)
    embed.set_author(name="🔍 Search")
    if not locations:
        embed.description = "No locations match these filters."
        embed.set_footer(text="0 locations")
        return embed
    lines = []
    for loc in locations:
        extra = loc.extra if hasattr(loc, "extra") else {}
        fish_count = len(extra.get("creatures") or []) if hasattr(extra, "get") else 0
        fail = extra.get("failChance", 0) if hasattr(extra, "get") else 0
        mine = extra.get("mineChance", 0) if hasattr(extra, "get") else 0
        loc_type = extra.get("type", "") if hasattr(extra, "get") else ""
        type_badge = "🌊" if loc_type == "saltwater" else "🏞️"
        lines.append(
            f"{type_badge} **{loc.name}**  ·  🐟 {fish_count}  ·  💀 {fail}%  ·  ⛏️ {mine}%"
        )
    embed.description = "\n".join(lines)
    embed.set_footer(text=f"{len(locations)} location{'s' if len(locations) != 1 else ''}")
    return embed


class SearchLocationView(discord.ui.View):
    def __init__(self, dank_client):
        super().__init__(timeout=300)
        self.dc = dank_client
        self.type_filter = "All"
        self.sort = "name"
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    def _filtered_sorted(self) -> list:
        locs = list(self.dc.location_by_id.values())
        if self.type_filter != "All":
            locs = [l for l in locs if (l.extra.get("type") if hasattr(l.extra, "get") else None) == self.type_filter]
        if self.sort == "fish_count":
            locs.sort(key=lambda l: -len(l.extra.get("creatures") or []))
        elif self.sort == "fail_asc":
            locs.sort(key=lambda l: l.extra.get("failChance", 0) if hasattr(l.extra, "get") else 0)
        elif self.sort == "mine_desc":
            locs.sort(key=lambda l: -(l.extra.get("mineChance", 0) if hasattr(l.extra, "get") else 0))
        else:
            locs.sort(key=lambda l: l.name.lower())
        return locs

    def build_embed(self) -> discord.Embed:
        return build_search_location_embed(self._filtered_sorted())

    @discord.ui.select(
        placeholder="🌊 Filter Type ▾",
        row=0,
        options=[
            discord.SelectOption(label="All types", value="All", default=True),
            discord.SelectOption(label="🌊 Saltwater", value="saltwater"),
            discord.SelectOption(label="🏞️ Freshwater", value="freshwater"),
        ],
    )
    async def type_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.type_filter = select.values[0]
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.select(
        placeholder="📊 Sort ▾",
        row=1,
        options=[
            discord.SelectOption(label="By Name", value="name", default=True),
            discord.SelectOption(label="By Fish Count ↓", value="fish_count"),
            discord.SelectOption(label="By Fail Chance ↑", value="fail_asc"),
            discord.SelectOption(label="By Mine Chance ↓", value="mine_desc"),
        ],
    )
    async def sort_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.sort = select.values[0]
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=2)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
```

Add `/searchlocation` command inside `SearchCog`, after the `creatures` command:

```python
    @app_commands.command(name="searchlocation", description="Search locations with filters")
    async def searchlocation(self, interaction: discord.Interaction):
        if not self.bot.dank_client or not self.bot.dank_client.location_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        view = SearchLocationView(self.bot.dank_client)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_search_cog.py -v
```
Expected: all pass

- [ ] **Step 5: Run full suite**

```
python -m pytest tests/ -q
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add cogs/search.py tests/test_search_cog.py
git commit -m "feat: add /searchlocation command with SearchLocationView"
```

---

## Self-Review Checklist (completed inline)

1. **Spec coverage:**
   - ✅ `emoji_from_url` helper → Task 1
   - ✅ `/fish` TOOLS + Best Location section → Task 2
   - ✅ `/tool` SUPPORTED FISH section → Task 3
   - ✅ `/fishcompare` Best Tool + Max Catch → Task 4
   - ✅ `/fishlist` Tool filter (row 3) + Type flags (row 4) → Task 5
   - ✅ `/searchfish` command → Task 6
   - ✅ `/creatures` command → Task 6
   - ✅ `/searchlocation` command → Task 7
   - ✅ Simulator cleanup → pre-confirmed no-op (see header), no task needed

2. **Type consistency:**
   - `build_fish_compare_embed(c1, c2, dc=None)` used in Task 4 and matches callers in fish.py
   - `build_tool_embed(tool, dc=None)` used in Task 3 and matches caller in tools.py
   - `build_fishlist_embed(..., tool_filter="All", type_filter="All")` — Task 5 uses correct kwargs
   - `build_search_fish_embed(creatures, page, total_pages, dc, title=...)` — Task 6 uses consistent signature
   - `SearchFishView._refresh()` sets `self.filtered`, `self.total_pages`, `self.page` — matches `DynamicPaginationView` contract

3. **No placeholders:** verified — all steps contain complete code
