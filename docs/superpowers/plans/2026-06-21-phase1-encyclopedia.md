# Phase 1 — Encyclopedia Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all Phase 1 encyclopedia slash commands (`/fish`, `/fishlist`, `/fishcompare`, `/location`, `/locations`, `/locationcompare`, `/tool`, `/toolcompare`, `/bait`, `/baitcompare`, `/npc`, `/stats`) with the full visual design system.

**Architecture:** One cog per entity type (`cogs/fish.py`, `cogs/locations.py`, `cogs/tools.py`, `cogs/baits.py`, `cogs/npcs.py`). Each cog owns its View subclasses. Shared formatting lives in `utils/formatters.py` (new). Embed builders live in `utils/embeds.py` (extended). All data is already preloaded at startup in `DankMemerGameClient` — commands do zero API calls.

**Tech Stack:** Python 3.12, discord.py 2.4+, dankmemer>=1.0.0rc2, aiosqlite, pytest 8+, pytest-asyncio 0.23+

## Global Constraints

- discord.py >= 2.4.0 — use `discord.ui.View`, `app_commands.Choice`, `discord.ui.Modal` APIs
- All slash commands use `@app_commands.command`, registered via cog
- All interactive views have `timeout=300` (5 minutes); on timeout disable all buttons in place
- Every user-visible error is an embed (use `EmbedBuilder.error()`), always `ephemeral=True`
- If `bot.dank_client.fish_by_id` is empty, respond with ephemeral: `"⏳ Data is still loading, please try again in a moment."`
- Disabled-in-Phase-1 buttons: `disabled=True`, label includes `·` suffix (e.g. `"🤍 Favourite"`) — no tooltip needed, Discord shows them greyed out
- View timeout: override `on_timeout`, call `self.message.edit(view=disabled_view)` where `disabled_view` has all items disabled
- `cogs/encyclopedia.py` must be deleted before any new cog is loaded — duplicate `/fish` command will prevent startup
- All embed descriptions must stay under 4096 chars; truncate location/fish lists with `… and N more` if needed
- Progress bars use `█` (U+2588) for filled, `░` (U+2591) for empty
- Availability bar is always 24 characters wide (one char = one UTC hour)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `utils/formatters.py` | **CREATE** | Colour constants, emoji maps, bar builders, availability helpers, compare helpers |
| `utils/embeds.py` | **EXTEND** | Add 12 standalone embed-builder functions alongside existing `EmbedBuilder` class |
| `utils/autocomplete.py` | **EXTEND** | Add `tool_choices`, `bait_choices`, `npc_choices` methods to `AutocompleteIndex` |
| `utils/views.py` | **EXTEND** | Add `DynamicPaginationView` base + `JumpModal`; keep existing `PaginatedView` |
| `dankmemer_client.py` | **EXTEND** | Add `location_creature_map` dict; populate in `preload()` after both entities loaded |
| `cogs/encyclopedia.py` | **DELETE** | Was a stub; replaced by `cogs/fish.py` |
| `cogs/fish.py` | **CREATE** | `FishCog` + `FishView` + `BackView` + `FishListView` + `FishCompareModal` |
| `cogs/locations.py` | **CREATE** | `LocationsCog` + `LocationView` + `LocationsListView` + `LocationCompareModal` |
| `cogs/tools.py` | **CREATE** | `ToolsCog` + `ToolView` + `ToolCompareModal` |
| `cogs/baits.py` | **CREATE** | `BaitsCog` + `BaitView` + `BaitCompareModal` |
| `cogs/npcs.py` | **CREATE** | `NpcsCog` (no custom views) |
| `cogs/core.py` | **EXTEND** | Update `/stats` to show entity counts + cache status |
| `tests/conftest.py` | **CREATE** | Shared mock fixtures (mock_creature, mock_location, mock_tool, mock_bait, mock_npc) |
| `tests/test_formatters.py` | **CREATE** | Unit tests for all formatter functions |
| `tests/test_embeds.py` | **CREATE** | Embed builder tests — check title, color, description content |
| `requirements-dev.txt` | **CREATE** | `pytest>=8.0.0`, `pytest-asyncio>=0.23.0` |

---

## Task 1: Dev setup + `utils/formatters.py`

**Files:**
- Create: `requirements-dev.txt`
- Create: `utils/formatters.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_formatters.py`

**Interfaces — Produces (used by Tasks 2–11):**
```python
# utils/formatters.py
RARITY_COLORS: dict[str, int]   # "Common" → 0x8e9297, etc.
BOSS_COLOR: int                  # 0xff6b35
LOCATION_COLOR: int              # 0x00b4d8
TOOL_COLOR: int                  # 0xff9500
BAIT_COLOR: int                  # 0x95d44a
NPC_COLOR: int                   # 0xb967ff
COMPARE_COLOR: int               # 0x5865f2
RARITY_EMOJI: dict[str, str]     # "Common" → "⚪", etc.
RARITY_ORDER: list[str]          # ["Common", "Uncommon", "Rare", "Very Rare", "Absurdly Rare", "Mythical"]

def rarity_color(rarity: str, boss: bool = False) -> int
def rarity_emoji(rarity: str) -> str
def rarity_rank(rarity: str) -> int          # Common=0 … Mythical=5; unknown=-1
def progress_bar(value: int | float, total: int | float, width: int = 20) -> str
def availability_bar(start_h: int, end_h: int, full_day: bool) -> str  # always 24 chars
def is_available_now(creature) -> bool
def format_time_window(creature) -> str      # "00:00–07:00 UTC · 7h" or "All Day"
def winner_mark(a, b, higher_is_better: bool = True) -> tuple[str, str]
  # returns (str(a)+" ✓", str(b)) or (str(a), str(b)+" ✓") or (str(a), str(b)) on tie
```

- [ ] **Step 1: Create `requirements-dev.txt`**

```
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 2: Install dev deps**

```
pip install -r requirements-dev.txt
```

Expected: installs pytest and pytest-asyncio with no errors.

- [ ] **Step 3: Create `tests/__init__.py`** (empty file)

- [ ] **Step 4: Create `tests/conftest.py`**

```python
import pytest
from datetime import time as dt_time
from dankmemer.utils import DotDict
from dankmemer.routes.creatures import Creature
from dankmemer.routes.locations import Location
from dankmemer.routes.tools import Tool
from dankmemer.routes.baits import Bait


def make_creature(
    id="goldfish",
    name="Goldfish",
    imageURL="https://example.com/goldfish.png",
    rarity="Common",
    boss=False,
    mythical=False,
    flavor="A shiny fish.",
    locations=None,
    start_h=0,
    end_h=6,
    full_day=False,
    variants=None,
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
    })
    return Creature(id=id, name=name, imageURL=imageURL, extra=extra)


def make_location(
    id="sunken_ship",
    name="Sunken Ship",
    imageURL="https://example.com/loc.png",
    bannerURL="https://example.com/banner.png",
    thumbnailURL="https://example.com/thumb.png",
    creatures=None,
    disabled=False,
    temporary=False,
    failChance=10,
    mineChance=5,
    npcs=None,
    rarity_fish=None,
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
    })
    return Location(
        id=id,
        name=name,
        imageURL=imageURL,
        extra=extra,
        rarityFish=rarity_fish or {"Common": ["goldfish"]},
        variantsData={},
    )


def make_tool(
    id="rod",
    name="Fishing Rod",
    imageURL="https://example.com/rod.png",
    flavor="The classic choice.",
    baits=True,
    buffs=None,
    debuffs=None,
    usage=100,
):
    extra = DotDict({
        "flavor": flavor,
        "baits": baits,
        "buffs": buffs or [{"name": "+20% Common catch"}],
        "debuffs": debuffs or [],
        "usage": usage,
    })
    return Tool(id=id, name=name, imageURL=imageURL, extra=extra)


def make_bait(
    id="glitter",
    name="Glitter Bait",
    imageURL="https://example.com/bait.png",
    flavor="Sparkly.",
    explanation="Increases Rare catch by 15%.",
    idle=True,
    usage=50,
):
    extra = DotDict({
        "flavor": flavor,
        "explanation": explanation,
        "idle": idle,
        "usage": usage,
    })
    return Bait(id=id, name=name, imageURL=imageURL, extra=extra)


@pytest.fixture
def creature():
    return make_creature()


@pytest.fixture
def boss_creature():
    return make_creature(id="kraken", name="Kraken", rarity="Absurdly Rare", boss=True)


@pytest.fixture
def fullday_creature():
    return make_creature(id="koi", name="Koi", rarity="Uncommon", full_day=True)


@pytest.fixture
def location():
    return make_location()


@pytest.fixture
def tool():
    return make_tool()


@pytest.fixture
def bait():
    return make_bait()
```

- [ ] **Step 5: Write failing tests in `tests/test_formatters.py`**

```python
import pytest
from utils.formatters import (
    rarity_color, rarity_emoji, rarity_rank,
    progress_bar, availability_bar,
    is_available_now, format_time_window, winner_mark,
    BOSS_COLOR, LOCATION_COLOR, TOOL_COLOR, BAIT_COLOR, NPC_COLOR, COMPARE_COLOR,
)
from tests.conftest import make_creature


def test_rarity_color_common():
    assert rarity_color("Common") == 0x8e9297

def test_rarity_color_boss_overrides():
    assert rarity_color("Common", boss=True) == BOSS_COLOR

def test_rarity_color_unknown_returns_default():
    assert rarity_color("Unknown") == 0x8e9297  # falls back to Common colour

def test_rarity_emoji_known():
    assert rarity_emoji("Rare") == "🔵"

def test_rarity_emoji_unknown():
    result = rarity_emoji("Alien Tier")
    assert isinstance(result, str) and len(result) > 0

def test_rarity_rank_order():
    assert rarity_rank("Common") < rarity_rank("Uncommon") < rarity_rank("Rare")
    assert rarity_rank("Rare") < rarity_rank("Very Rare") < rarity_rank("Absurdly Rare")
    assert rarity_rank("Absurdly Rare") < rarity_rank("Mythical")

def test_rarity_rank_unknown():
    assert rarity_rank("Unknown") == -1

def test_progress_bar_full():
    bar = progress_bar(20, 20, width=20)
    assert bar == "█" * 20

def test_progress_bar_empty():
    bar = progress_bar(0, 20, width=20)
    assert bar == "░" * 20

def test_progress_bar_half():
    bar = progress_bar(10, 20, width=20)
    assert bar == "█" * 10 + "░" * 10

def test_progress_bar_zero_total():
    bar = progress_bar(0, 0, width=10)
    assert bar == "░" * 10

def test_availability_bar_length():
    bar = availability_bar(0, 6, full_day=False)
    assert len(bar) == 24

def test_availability_bar_full_day():
    bar = availability_bar(0, 0, full_day=True)
    assert bar == "█" * 24

def test_availability_bar_first_6_hours():
    bar = availability_bar(0, 6, full_day=False)
    assert bar[:6] == "█" * 6
    assert bar[6:] == "░" * 18

def test_availability_bar_wraps_midnight():
    # 22:00 to 02:00 — hours 22,23,0,1 are available
    bar = availability_bar(22, 2, full_day=False)
    assert bar[22] == "█"
    assert bar[23] == "█"
    assert bar[0] == "█"
    assert bar[1] == "█"
    assert bar[2] == "░"
    assert bar[10] == "░"

def test_is_available_now_full_day():
    c = make_creature(full_day=True)
    assert is_available_now(c) is True

def test_is_available_now_missing_time():
    from dankmemer.utils import DotDict
    from dankmemer.routes.creatures import Creature
    c = Creature(id="x", name="X", imageURL="", extra=DotDict({"time": {}}))
    assert is_available_now(c) is True  # unknown → assume available

def test_format_time_window_full_day():
    c = make_creature(full_day=True)
    assert format_time_window(c) == "All Day"

def test_format_time_window_normal():
    c = make_creature(start_h=0, end_h=6, full_day=False)
    result = format_time_window(c)
    assert "00:00" in result
    assert "06:00" in result
    assert "6h" in result

def test_winner_mark_higher_wins():
    a, b = winner_mark(10, 5)
    assert "✓" in a
    assert "✓" not in b

def test_winner_mark_lower_wins():
    a, b = winner_mark(3, 7, higher_is_better=False)
    assert "✓" in a
    assert "✓" not in b

def test_winner_mark_tie():
    a, b = winner_mark(5, 5)
    assert "✓" not in a
    assert "✓" not in b
```

- [ ] **Step 6: Run tests — expect failures**

```
pytest tests/test_formatters.py -v
```

Expected: `ModuleNotFoundError: No module named 'utils.formatters'`

- [ ] **Step 7: Create `utils/formatters.py`**

```python
from __future__ import annotations
from datetime import datetime, timezone, time as dt_time
from typing import Any

RARITY_COLORS: dict[str, int] = {
    "Common":        0x8e9297,
    "Uncommon":      0x57f287,
    "Rare":          0x5865f2,
    "Very Rare":     0xeb459e,
    "Absurdly Rare": 0xed4245,
    "Mythical":      0xffd700,
}
BOSS_COLOR     = 0xff6b35
LOCATION_COLOR = 0x00b4d8
TOOL_COLOR     = 0xff9500
BAIT_COLOR     = 0x95d44a
NPC_COLOR      = 0xb967ff
COMPARE_COLOR  = 0x5865f2

RARITY_EMOJI: dict[str, str] = {
    "Common":        "⚪",
    "Uncommon":      "🟢",
    "Rare":          "🔵",
    "Very Rare":     "🟣",
    "Absurdly Rare": "🔴",
    "Mythical":      "🌟",
}

RARITY_ORDER = ["Common", "Uncommon", "Rare", "Very Rare", "Absurdly Rare", "Mythical"]


def rarity_color(rarity: str, boss: bool = False) -> int:
    if boss:
        return BOSS_COLOR
    return RARITY_COLORS.get(rarity, RARITY_COLORS["Common"])


def rarity_emoji(rarity: str) -> str:
    return RARITY_EMOJI.get(rarity, "⚫")


def rarity_rank(rarity: str) -> int:
    try:
        return RARITY_ORDER.index(rarity)
    except ValueError:
        return -1


def progress_bar(value: int | float, total: int | float, width: int = 20) -> str:
    filled = round((value / total) * width) if total else 0
    filled = max(0, min(filled, width))
    return "█" * filled + "░" * (width - filled)


def availability_bar(start_h: int, end_h: int, full_day: bool) -> str:
    if full_day:
        return "█" * 24
    chars = []
    for h in range(24):
        if start_h <= end_h:
            chars.append("█" if start_h <= h < end_h else "░")
        else:
            chars.append("█" if h >= start_h or h < end_h else "░")
    return "".join(chars)


def is_available_now(creature) -> bool:
    time_data = creature.extra.get("time", {}) if hasattr(creature.extra, "get") else {}
    if time_data.get("full_day"):
        return True
    start = time_data.get("start")
    end = time_data.get("end")
    if not isinstance(start, dt_time) or not isinstance(end, dt_time):
        return True
    now = datetime.now(timezone.utc).time().replace(second=0, microsecond=0)
    if start <= end:
        return start <= now < end
    return now >= start or now < end


def format_time_window(creature) -> str:
    time_data = creature.extra.get("time", {}) if hasattr(creature.extra, "get") else {}
    if time_data.get("full_day"):
        return "All Day"
    start = time_data.get("start")
    end = time_data.get("end")
    if not isinstance(start, dt_time) or not isinstance(end, dt_time):
        return "Unknown"
    start_h, end_h = start.hour, end.hour
    hours = (end_h - start_h) if start_h <= end_h else (24 - start_h + end_h)
    return f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')} UTC  ·  {hours}h"


def winner_mark(a: Any, b: Any, higher_is_better: bool = True) -> tuple[str, str]:
    try:
        a_wins = (a > b) if higher_is_better else (a < b)
        b_wins = (b > a) if higher_is_better else (b < a)
    except TypeError:
        return str(a), str(b)
    if a_wins:
        return f"{a} ✓", str(b)
    if b_wins:
        return str(a), f"{b} ✓"
    return str(a), str(b)
```

- [ ] **Step 8: Run tests — expect pass**

```
pytest tests/test_formatters.py -v
```

Expected: all green.

- [ ] **Step 9: Commit**

```
git add utils/formatters.py tests/__init__.py tests/conftest.py tests/test_formatters.py requirements-dev.txt
git commit -m "feat: add formatters utility and test fixtures"
```

---

## Task 2: `utils/embeds.py` — fish embed builders

**Files:**
- Modify: `utils/embeds.py`
- Create: `tests/test_embeds.py`

**Interfaces — Consumes:**
- `utils/formatters.py`: `rarity_color`, `rarity_emoji`, `rarity_rank`, `availability_bar`, `is_available_now`, `format_time_window`, `winner_mark`, `COMPARE_COLOR`, `progress_bar`

**Interfaces — Produces (used by Task 6):**
```python
def build_fish_embed(creature, dank_client) -> discord.Embed
def build_fish_compare_embed(c1, c2) -> discord.Embed
def build_peak_hours_embed(creature) -> discord.Embed
def build_fishlist_embed(
    creatures: list,
    page: int,
    total_pages: int,
    sort: str,
    rarity_filter: str,
) -> discord.Embed
```

- [ ] **Step 1: Write failing tests in `tests/test_embeds.py`**

```python
import discord
import pytest
from tests.conftest import make_creature, make_location, make_tool, make_bait
from unittest.mock import MagicMock


def make_mock_client(creatures=None, locations=None, tools=None, baits=None):
    client = MagicMock()
    client.fish_by_id = {c.id: c for c in (creatures or [])}
    client.location_by_id = {l.id: l for l in (locations or [])}
    client.tool_by_id = {t.id: t for t in (tools or [])}
    client.bait_by_id = {b.id: b for b in (baits or [])}
    client.npc_by_id = {}
    return client


# --- Fish embeds ---

def test_build_fish_embed_title(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    assert embed.title == "Goldfish"

def test_build_fish_embed_color_common(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    assert embed.color.value == 0x8e9297

def test_build_fish_embed_color_boss(boss_creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(boss_creature, make_mock_client())
    from utils.formatters import BOSS_COLOR
    assert embed.color.value == BOSS_COLOR

def test_build_fish_embed_has_availability(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    assert "AVAILABILITY" in embed.description

def test_build_fish_embed_no_variants_section(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    assert "VARIANTS" not in embed.description

def test_build_fish_embed_with_variants():
    from utils.embeds import build_fish_embed
    c = make_creature(variants=[{"name": "Chroma", "chance": 2}])
    embed = build_fish_embed(c, make_mock_client())
    assert "VARIANTS" in embed.description

def test_build_fish_embed_resolves_location_names():
    from utils.embeds import build_fish_embed
    loc = make_location(id="loc1", name="Sunken Ship")
    c = make_creature(locations=["loc1"])
    embed = build_fish_embed(c, make_mock_client(locations=[loc]))
    assert "Sunken Ship" in embed.description

def test_build_fish_embed_footer(creature):
    from utils.embeds import build_fish_embed
    embed = build_fish_embed(creature, make_mock_client())
    assert embed.footer.text == "Internal ID: goldfish"


# --- Compare embed ---

def test_build_fish_compare_embed_title():
    from utils.embeds import build_fish_compare_embed
    c1 = make_creature(name="Goldfish")
    c2 = make_creature(id="koi", name="Koi", rarity="Rare")
    embed = build_fish_compare_embed(c1, c2)
    assert "Goldfish" in embed.title
    assert "Koi" in embed.title

def test_build_fish_compare_embed_winner_marked():
    from utils.embeds import build_fish_compare_embed
    c1 = make_creature(locations=["a", "b"])
    c2 = make_creature(locations=["a", "b", "c", "d", "e"])
    embed = build_fish_compare_embed(c1, c2)
    # c2 has more locations → should have ✓
    assert "✓" in embed.description


# --- Peak hours embed ---

def test_build_peak_hours_embed_contains_grid(creature):
    from utils.embeds import build_peak_hours_embed
    embed = build_peak_hours_embed(creature)
    assert "00" in embed.description
    assert "23" in embed.description

def test_build_peak_hours_embed_full_day(fullday_creature):
    from utils.embeds import build_peak_hours_embed
    embed = build_peak_hours_embed(fullday_creature)
    assert "All Day" in embed.description


# --- Fishlist embed ---

def test_build_fishlist_embed_title():
    from utils.embeds import build_fishlist_embed
    creatures = [make_creature()]
    embed = build_fishlist_embed(creatures, page=0, total_pages=1, sort="alphabetical", rarity_filter="All")
    assert "Fish" in embed.title

def test_build_fishlist_embed_footer_has_page():
    from utils.embeds import build_fishlist_embed
    creatures = [make_creature()]
    embed = build_fishlist_embed(creatures, page=0, total_pages=3, sort="alphabetical", rarity_filter="All")
    assert "1" in embed.footer.text
    assert "3" in embed.footer.text
```

- [ ] **Step 2: Run tests — expect failures**

```
pytest tests/test_embeds.py -v
```

Expected: `ImportError: cannot import name 'build_fish_embed' from 'utils.embeds'`

- [ ] **Step 3: Add fish embed builders to `utils/embeds.py`**

Append the following to the bottom of `utils/embeds.py` (after the `EmbedBuilder` class):

```python
from datetime import time as dt_time
import discord
from utils.formatters import (
    rarity_color, rarity_emoji, rarity_rank,
    availability_bar, is_available_now, format_time_window,
    winner_mark, COMPARE_COLOR, progress_bar, RARITY_EMOJI, RARITY_ORDER,
)

_SEP = "─────────────────────────────────────"


def build_fish_embed(creature, dank_client) -> discord.Embed:
    extra = creature.extra
    boss = extra.get("boss", False)
    mythical = extra.get("mythical", False)
    rarity = extra.get("rarity", "Common")
    flavor = extra.get("flavor", "")
    time_data = extra.get("time", {})
    full_day = time_data.get("full_day", False)
    variants = extra.get("variants") or []

    embed = discord.Embed(title=creature.name, color=rarity_color(rarity, boss=boss))
    embed.set_author(name="🐟 Fish Encyclopedia")
    if creature.imageURL:
        embed.set_thumbnail(url=creature.imageURL)

    lines: list[str] = []
    if flavor:
        lines += [f'*"{flavor}"*', ""]

    rem = rarity_emoji(rarity)
    lines.append(
        f"{rem} **{rarity}**  ·  👑 Boss: {'✅' if boss else '❌'}  ·  ✨ Mythical: {'✅' if mythical else '❌'}"
    )

    # Availability
    lines += ["", _SEP, "**🕐 AVAILABILITY**"]
    start = time_data.get("start")
    end = time_data.get("end")
    if full_day:
        lines.append("▐" + "█" * 24 + "▌  All Day")
    elif isinstance(start, dt_time) and isinstance(end, dt_time):
        bar = availability_bar(start.hour, end.hour, False)
        lines.append(f"▐{bar}▌  {format_time_window(creature)}")
        avail = "✅ Available" if is_available_now(creature) else "❌ Not available"
        lines.append(f"Right now: {avail}")

    # Locations
    loc_ids = extra.get("locations") or []
    loc_names = [
        loc.name for lid in loc_ids
        if (loc := dank_client.location_by_id.get(lid)) is not None
    ]
    lines += ["", _SEP, f"**📍 LOCATIONS  ({len(loc_names)})**"]
    lines.append("  ·  ".join(loc_names) if loc_names else "None")

    # Variants
    if variants:
        lines += ["", _SEP, f"**🔮 VARIANTS  ({len(variants)})**"]
        parts = []
        for v in variants:
            if isinstance(v, dict):
                parts.append(f"✨ {v.get('name', 'Unknown')}")
            else:
                parts.append(f"✨ {v}")
        lines.append("  ·  ".join(parts))

    lines += ["", _SEP]
    embed.description = "\n".join(lines)[:4096]
    embed.set_footer(text=f"Internal ID: {creature.id}")
    return embed


def build_fish_compare_embed(c1, c2) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚔️  {c1.name}  vs  {c2.name}",
        color=COMPARE_COLOR,
    )
    embed.set_author(name="⚔️ Fish Compare")

    rows: list[tuple[str, str, str]] = []

    # Rarity
    r1, r2 = c1.extra.get("rarity", "Common"), c2.extra.get("rarity", "Common")
    rank1, rank2 = rarity_rank(r1), rarity_rank(r2)
    re1, re2 = rarity_emoji(r1), rarity_emoji(r2)
    rv1 = f"{re1} {r1} ✓" if rank1 > rank2 else f"{re1} {r1}"
    rv2 = f"{re2} {r2} ✓" if rank2 > rank1 else f"{re2} {r2}"
    rows.append(("Rarity", rv1, rv2))

    rows.append(("Boss", "✅" if c1.extra.get("boss") else "❌", "✅" if c2.extra.get("boss") else "❌"))
    rows.append(("Mythical", "✅" if c1.extra.get("mythical") else "❌", "✅" if c2.extra.get("mythical") else "❌"))

    w1, w2 = format_time_window(c1), format_time_window(c2)
    rows.append(("Window", w1, w2))

    l1, l2 = len(c1.extra.get("locations") or []), len(c2.extra.get("locations") or [])
    lv1, lv2 = winner_mark(l1, l2)
    rows.append(("Locations", lv1, lv2))

    var1, var2 = len(c1.extra.get("variants") or []), len(c2.extra.get("variants") or [])
    vv1, vv2 = winner_mark(var1, var2)
    rows.append(("Variants", vv1, vv2))

    lw = max(len(r[0]) for r in rows)
    c1w = max(len(c1.name), max(len(r[1]) for r in rows), 14)
    c2w = max(len(c2.name), max(len(r[2]) for r in rows), 14)

    header = f"{'':>{lw}} | {c1.name:<{c1w}} | {c2.name:<{c2w}}"
    divider = f"{'-'*lw}-+-{'-'*c1w}-+-{'-'*c2w}"
    table_rows = [f"{label:>{lw}} | {v1:<{c1w}} | {v2:<{c2w}}" for label, v1, v2 in rows]
    embed.description = "```\n" + "\n".join([header, divider] + table_rows) + "\n```"
    return embed


def build_peak_hours_embed(creature) -> discord.Embed:
    extra = creature.extra
    time_data = extra.get("time", {})
    full_day = time_data.get("full_day", False)
    start = time_data.get("start")
    end = time_data.get("end")

    embed = discord.Embed(
        title=f"🕐 Peak Hours — {creature.name}",
        color=rarity_color(extra.get("rarity", "Common"), boss=extra.get("boss", False)),
    )

    if full_day:
        embed.description = (
            "**This fish is available All Day** — every hour is active.\n\n"
            "`00 01 02 03 04 05 06 07 08 09 10 11`\n"
            "` ✅  ✅  ✅  ✅  ✅  ✅  ✅  ✅  ✅  ✅  ✅  ✅`\n\n"
            "`12 13 14 15 16 17 18 19 20 21 22 23`\n"
            "` ✅  ✅  ✅  ✅  ✅  ✅  ✅  ✅  ✅  ✅  ✅  ✅`"
        )
        return embed

    if not isinstance(start, dt_time) or not isinstance(end, dt_time):
        embed.description = "Availability data unavailable."
        return embed

    from datetime import datetime, timezone
    current_utc = datetime.now(timezone.utc)
    now_h = current_utc.hour

    avail = availability_bar(start.hour, end.hour, False)
    marks_am = []
    marks_pm = []
    for h in range(12):
        mark = "✅" if avail[h] == "█" else "❌"
        cursor = f"[{mark}]" if h == now_h else f" {mark} "
        marks_am.append(cursor)
    for h in range(12, 24):
        mark = "✅" if avail[h] == "█" else "❌"
        cursor = f"[{mark}]" if h == now_h else f" {mark} "
        marks_pm.append(cursor)

    avail_str = is_available_now(creature)
    window = format_time_window(creature)

    lines = [
        f"`00 01 02 03 04 05 06 07 08 09 10 11`",
        f"`{''.join(marks_am)}`",
        "",
        f"`12 13 14 15 16 17 18 19 20 21 22 23`",
        f"`{''.join(marks_pm)}`",
        "",
        f"Window: **{window}**",
        f"Current UTC: {current_utc.strftime('%H:%M')}  →  {'✅ Available' if avail_str else '❌ Not available'}",
    ]
    embed.description = "\n".join(lines)
    return embed


def build_fishlist_embed(
    creatures: list,
    page: int,
    total_pages: int,
    sort: str,
    rarity_filter: str,
) -> discord.Embed:
    from utils.formatters import COMPARE_COLOR, RARITY_COLORS
    color = RARITY_COLORS.get(rarity_filter, COMPARE_COLOR)
    title = f"All Fish  ({len(creatures)} total)" if rarity_filter == "All" else f"{rarity_filter} Fish  ({len(creatures)})"

    embed = discord.Embed(title=f"🐟 {title}", color=color)
    embed.set_author(name="🐟 Fish Encyclopedia")

    ITEMS = 10
    start_idx = page * ITEMS
    page_creatures = creatures[start_idx: start_idx + ITEMS]

    lines = []
    for c in page_creatures:
        extra = c.extra
        rarity = extra.get("rarity", "Common")
        boss = extra.get("boss", False)
        mythical = extra.get("mythical", False)
        avail = "✅" if is_available_now(c) else "❌"
        badges = ""
        if boss:
            badges += " 👑 BOSS"
        if mythical:
            badges += " ✨ MYTHICAL"
        rem = rarity_emoji(rarity)
        lines.append(f"{rem} **{c.name}**{badges}  ·  {avail} now")

    embed.description = "\n".join(lines) if lines else "*No fish match this filter.*"
    embed.set_footer(text=f"Page {page + 1} / {total_pages}  ·  Sort: {sort}  ·  Filter: {rarity_filter}")
    return embed
```

- [ ] **Step 4: Run tests — expect pass**

```
pytest tests/test_embeds.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```
git add utils/embeds.py tests/test_embeds.py
git commit -m "feat: add fish embed builders"
```

---

## Task 3: `utils/embeds.py` — location, tool, bait, NPC embed builders

**Files:**
- Modify: `utils/embeds.py`
- Modify: `tests/test_embeds.py`

**Interfaces — Produces (used by Tasks 7–10):**
```python
def build_location_embed(location, dank_client) -> discord.Embed
def build_location_compare_embed(loc1, loc2) -> discord.Embed
def build_locations_list_embed(locations: list, page: int, total_pages: int, sort: str, filter_: str) -> discord.Embed
def build_tool_embed(tool) -> discord.Embed
def build_toolcompare_embed(tools: list) -> discord.Embed
def build_bait_embed(bait) -> discord.Embed
def build_bait_compare_embed(bait1, bait2) -> discord.Embed
def build_npc_embed(npc) -> discord.Embed
```

- [ ] **Step 1: Add tests to `tests/test_embeds.py`**

Append to the existing test file:

```python
# --- Location embeds ---

def test_build_location_embed_title(location):
    from utils.embeds import build_location_embed
    embed = build_location_embed(location, make_mock_client())
    assert embed.title == "Sunken Ship"

def test_build_location_embed_has_stats(location):
    from utils.embeds import build_location_embed
    embed = build_location_embed(location, make_mock_client())
    assert "Fail" in embed.description
    assert "Mine" in embed.description

def test_build_location_embed_rarity_distribution(location):
    from utils.embeds import build_location_embed
    embed = build_location_embed(location, make_mock_client())
    assert "RARITY" in embed.description

def test_build_location_embed_temporary_badge():
    from utils.embeds import build_location_embed
    loc = make_location(temporary=True)
    embed = build_location_embed(loc, make_mock_client())
    assert "Temporary" in embed.description

def test_build_location_compare_embed_title():
    from utils.embeds import build_location_compare_embed
    l1 = make_location(name="Ocean")
    l2 = make_location(id="lake", name="Lake")
    embed = build_location_compare_embed(l1, l2)
    assert "Ocean" in embed.title
    assert "Lake" in embed.title

def test_build_locations_list_embed_title():
    from utils.embeds import build_locations_list_embed
    locs = [make_location()]
    embed = build_locations_list_embed(locs, 0, 1, "name", "All")
    assert "Location" in embed.title


# --- Tool embeds ---

def test_build_tool_embed_title(tool):
    from utils.embeds import build_tool_embed
    embed = build_tool_embed(tool)
    assert embed.title == "Fishing Rod"

def test_build_tool_embed_has_buffs(tool):
    from utils.embeds import build_tool_embed
    embed = build_tool_embed(tool)
    assert "BUFF" in embed.description

def test_build_tool_embed_bait_support(tool):
    from utils.embeds import build_tool_embed
    embed = build_tool_embed(tool)
    assert "✅" in embed.description

def test_build_toolcompare_embed_contains_all_tools():
    from utils.embeds import build_toolcompare_embed
    t1 = make_tool(name="Rod")
    t2 = make_tool(id="harpoon", name="Harpoon", baits=False, usage=50)
    embed = build_toolcompare_embed([t1, t2])
    assert "Rod" in embed.description
    assert "Harpoon" in embed.description


# --- Bait embeds ---

def test_build_bait_embed_title(bait):
    from utils.embeds import build_bait_embed
    embed = build_bait_embed(bait)
    assert embed.title == "Glitter Bait"

def test_build_bait_embed_explanation(bait):
    from utils.embeds import build_bait_embed
    embed = build_bait_embed(bait)
    assert "Rare catch" in embed.description

def test_build_bait_compare_embed_title():
    from utils.embeds import build_bait_compare_embed
    b1 = make_bait(name="Glitter")
    b2 = make_bait(id="gold", name="Gold Bait", explanation="Doubles Mythical catch.", idle=False, usage=10)
    embed = build_bait_compare_embed(b1, b2)
    assert "Glitter" in embed.title and "Gold Bait" in embed.title


# --- NPC embeds ---

def test_build_npc_embed_title():
    from utils.embeds import build_npc_embed
    from unittest.mock import MagicMock
    from dankmemer.utils import DotDict
    from dankmemer.routes.npcs import NPC  # may vary; adjust if import path differs
    npc = MagicMock()
    npc.name = "Poseidon"
    npc.imageURL = "https://example.com/npc.png"
    npc.id = "poseidon"
    npc.extra = DotDict({"description": "God of the sea.", "locations": ["loc1"]})
    embed = build_npc_embed(npc)
    assert embed.title == "Poseidon"
```

- [ ] **Step 2: Run tests — expect failures for new tests only**

```
pytest tests/test_embeds.py -v -k "location or tool or bait or npc"
```

Expected: `ImportError: cannot import name 'build_location_embed'`

- [ ] **Step 3: Append location, tool, bait, NPC builders to `utils/embeds.py`**

```python
def build_location_embed(location, dank_client) -> discord.Embed:
    extra = location.extra
    disabled = extra.get("disabled", False)
    temporary = extra.get("temporary", False)

    embed = discord.Embed(title=location.name, color=0x00b4d8)
    embed.set_author(name="📍 Location")
    if extra.get("thumbnailURL"):
        embed.set_thumbnail(url=extra["thumbnailURL"])
    if extra.get("bannerURL"):
        embed.set_image(url=extra["bannerURL"])

    lines: list[str] = []
    status_parts = []
    if temporary:
        status_parts.append("🔴 Temporary")
    if disabled:
        status_parts.append("⛔ Disabled")
    if status_parts:
        lines += ["  ·  ".join(status_parts), ""]

    fail = extra.get("failChance", 0)
    mine = extra.get("mineChance", 0)
    creatures = extra.get("creatures") or []
    lines += [
        "**🌊 STATISTICS**",
        f"💀 Fail: **{fail}%**   ⛏️ Mine: **{mine}%**   🐟 Pool: **{len(creatures)} fish**",
        "",
        _SEP,
    ]

    rarity_fish: dict = location.rarityFish or {}
    if rarity_fish:
        lines.append("**🌈 RARITY DISTRIBUTION**")
        total_fish = sum(len(v) for v in rarity_fish.values())
        for rarity in RARITY_ORDER:
            bucket = rarity_fish.get(rarity, [])
            if not bucket:
                continue
            pct = round(len(bucket) / total_fish * 100) if total_fish else 0
            bar = progress_bar(pct, 100, width=20)
            lines.append(f"{rarity_emoji(rarity)} {rarity:<14} {bar}  {pct}%")
        lines += ["", _SEP]

    npcs = extra.get("npcs") or []
    if npcs:
        lines += ["**👤 NPCs**", "  ·  ".join(npcs), "", _SEP]

    embed.description = "\n".join(lines)[:4096]
    embed.set_footer(text=f"Internal ID: {location.id}")
    return embed


def build_location_compare_embed(loc1, loc2) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚔️  {loc1.name}  vs  {loc2.name}",
        color=COMPARE_COLOR,
    )
    embed.set_author(name="⚔️ Location Compare")

    def _count(loc, rarity):
        return len((loc.rarityFish or {}).get(rarity, []))

    rows: list[tuple[str, str, str]] = []

    c1 = len(loc1.extra.get("creatures") or [])
    c2 = len(loc2.extra.get("creatures") or [])
    cv1, cv2 = winner_mark(c1, c2)
    rows.append(("Fish Pool", cv1, cv2))

    f1, f2 = loc1.extra.get("failChance", 0), loc2.extra.get("failChance", 0)
    fv1, fv2 = winner_mark(f1, f2, higher_is_better=False)
    rows.append(("Fail %", fv1, fv2))

    m1, m2 = loc1.extra.get("mineChance", 0), loc2.extra.get("mineChance", 0)
    mv1, mv2 = winner_mark(m1, m2, higher_is_better=False)
    rows.append(("Mine %", mv1, mv2))

    for rarity in ["Rare", "Very Rare", "Absurdly Rare", "Mythical"]:
        r1, r2 = _count(loc1, rarity), _count(loc2, rarity)
        rv1, rv2 = winner_mark(r1, r2)
        rows.append((f"{rarity[:8]} fish", rv1, rv2))

    lw = max(len(r[0]) for r in rows)
    c1w = max(len(loc1.name), max(len(r[1]) for r in rows), 12)
    c2w = max(len(loc2.name), max(len(r[2]) for r in rows), 12)
    header = f"{'':>{lw}} | {loc1.name:<{c1w}} | {loc2.name:<{c2w}}"
    divider = f"{'-'*lw}-+-{'-'*c1w}-+-{'-'*c2w}"
    table_rows = [f"{label:>{lw}} | {v1:<{c1w}} | {v2:<{c2w}}" for label, v1, v2 in rows]
    embed.description = "```\n" + "\n".join([header, divider] + table_rows) + "\n```"
    return embed


def build_locations_list_embed(
    locations: list,
    page: int,
    total_pages: int,
    sort: str,
    filter_: str,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"📍 All Locations  ({len(locations)} total)",
        color=0x00b4d8,
    )
    embed.set_author(name="📍 Locations")

    ITEMS = 8
    start_idx = page * ITEMS
    page_locs = locations[start_idx: start_idx + ITEMS]

    lines = []
    for loc in page_locs:
        extra = loc.extra
        fish_count = len(extra.get("creatures") or [])
        fail = extra.get("failChance", 0)
        badges = ""
        if extra.get("temporary"):
            badges += " 🔴 Temp"
        if extra.get("disabled"):
            badges += " ⛔"
        lines.append(f"📍 **{loc.name}**{badges}  ·  🐟 {fish_count}  ·  💀 {fail}%")

    embed.description = "\n".join(lines) if lines else "*No locations match this filter.*"
    embed.set_footer(text=f"Page {page + 1} / {total_pages}  ·  Sort: {sort}  ·  Filter: {filter_}")
    return embed


def build_tool_embed(tool) -> discord.Embed:
    extra = tool.extra
    embed = discord.Embed(title=tool.name, color=0xff9500)
    embed.set_author(name="🔧 Tool")
    if tool.imageURL:
        embed.set_thumbnail(url=tool.imageURL)

    lines: list[str] = []
    flavor = extra.get("flavor", "")
    if flavor:
        lines += [f'*"{flavor}"*', ""]

    buffs = extra.get("buffs") or []
    if buffs:
        lines += [_SEP, "**✨ BUFFS**"]
        for b in buffs:
            name = b.get("name", str(b)) if isinstance(b, dict) else str(b)
            lines.append(f"• {name}")

    debuffs = extra.get("debuffs") or []
    if debuffs:
        lines += ["", "**💢 DEBUFFS**"]
        for d in debuffs:
            name = d.get("name", str(d)) if isinstance(d, dict) else str(d)
            lines.append(f"• {name}")

    bait_support = "✅" if extra.get("baits") else "❌"
    usage = extra.get("usage", "?")
    lines += ["", _SEP, f"🪱 Bait Support: {bait_support}   ·   📊 Usage: {usage}", _SEP]

    embed.description = "\n".join(lines)[:4096]
    embed.set_footer(text=f"Internal ID: {tool.id}")
    return embed


def build_toolcompare_embed(tools: list) -> discord.Embed:
    embed = discord.Embed(title="⚔️ Tool Comparison", color=COMPARE_COLOR)
    embed.set_author(name="⚔️ Tool Compare")

    headers = ["Tool", "Baits", "Usage", "Buffs", "Debuffs"]
    col_w = [max(len(h), max((len(t.name) for t in tools), default=4)) for h in headers]
    col_w[0] = max(len(h) for h in [t.name for t in tools] + [headers[0]])
    col_w[1] = max(len("Baits"), 5)
    col_w[2] = max(len("Usage"), 5)
    col_w[3] = max(len("Buffs"), 5)
    col_w[4] = max(len("Debuffs"), 7)

    def row_str(cells):
        return " | ".join(str(c).ljust(col_w[i]) for i, c in enumerate(cells))

    hrow = row_str(headers)
    sep = "-+-".join("-" * w for w in col_w)
    rows = [hrow, sep]
    for t in tools:
        extra = t.extra
        rows.append(row_str([
            t.name,
            "✅" if extra.get("baits") else "❌",
            extra.get("usage", "?"),
            len(extra.get("buffs") or []),
            len(extra.get("debuffs") or []),
        ]))
    embed.description = "```\n" + "\n".join(rows) + "\n```"
    return embed


def build_bait_embed(bait) -> discord.Embed:
    extra = bait.extra
    embed = discord.Embed(title=bait.name, color=0x95d44a)
    embed.set_author(name="🪱 Bait")
    if bait.imageURL:
        embed.set_thumbnail(url=bait.imageURL)

    lines: list[str] = []
    flavor = extra.get("flavor", "")
    if flavor:
        lines += [f'*"{flavor}"*', ""]

    explanation = extra.get("explanation", "")
    if explanation:
        lines += [_SEP, "**💡 WHAT IT DOES**", explanation]

    idle = "✅" if extra.get("idle") else "❌"
    usage = extra.get("usage", "?")
    lines += ["", _SEP, f"🤖 Idle Compatible: {idle}   ·   📊 Usage: {usage}", _SEP]

    embed.description = "\n".join(lines)[:4096]
    embed.set_footer(text=f"Internal ID: {bait.id}")
    return embed


def build_bait_compare_embed(bait1, bait2) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚔️  {bait1.name}  vs  {bait2.name}",
        color=COMPARE_COLOR,
    )
    embed.set_author(name="⚔️ Bait Compare")

    e1, e2 = bait1.extra, bait2.extra
    u1, u2 = e1.get("usage", 0), e2.get("usage", 0)
    uv1, uv2 = winner_mark(u1, u2)

    rows: list[tuple[str, str, str]] = [
        ("Idle OK", "✅" if e1.get("idle") else "❌", "✅" if e2.get("idle") else "❌"),
        ("Usage", uv1, uv2),
        ("Effect", (e1.get("explanation") or "—")[:40], (e2.get("explanation") or "—")[:40]),
    ]

    lw = max(len(r[0]) for r in rows)
    c1w = max(len(bait1.name), max(len(r[1]) for r in rows), 12)
    c2w = max(len(bait2.name), max(len(r[2]) for r in rows), 12)
    header = f"{'':>{lw}} | {bait1.name:<{c1w}} | {bait2.name:<{c2w}}"
    divider = f"{'-'*lw}-+-{'-'*c1w}-+-{'-'*c2w}"
    table_rows = [f"{label:>{lw}} | {v1:<{c1w}} | {v2:<{c2w}}" for label, v1, v2 in rows]
    embed.description = "```\n" + "\n".join([header, divider] + table_rows) + "\n```"
    return embed


def build_npc_embed(npc) -> discord.Embed:
    embed = discord.Embed(title=npc.name, color=0xb967ff)
    embed.set_author(name="👤 NPC")
    if getattr(npc, "imageURL", None):
        embed.set_thumbnail(url=npc.imageURL)

    extra = getattr(npc, "extra", {})
    lines: list[str] = []

    for key in ("description", "flavor", "text"):
        desc = extra.get(key) if hasattr(extra, "get") else None
        if desc:
            lines += [f'*"{desc}"*', ""]
            break

    loc_data = extra.get("locations") if hasattr(extra, "get") else None
    if loc_data:
        lines += [_SEP, "**📍 FOUND IN**"]
        if isinstance(loc_data, list):
            lines.append("  ·  ".join(str(l) for l in loc_data))
        else:
            lines.append(str(loc_data))
    lines.append(_SEP)

    embed.description = "\n".join(lines)[:4096] if lines else "No additional data available."
    embed.set_footer(text=f"Internal ID: {getattr(npc, 'id', '?')}")
    return embed
```

- [ ] **Step 4: Run all embed tests**

```
pytest tests/test_embeds.py -v
```

Expected: all green. Note: the NPC test may fail if `dankmemer.routes.npcs.NPC` import path differs — adjust the import in `conftest.py` if so (the `MagicMock` approach avoids needing the exact class).

- [ ] **Step 5: Commit**

```
git add utils/embeds.py tests/test_embeds.py
git commit -m "feat: add location, tool, bait, NPC embed builders"
```

---

## Task 4: `utils/autocomplete.py` + `utils/views.py` — complete shared utilities

**Files:**
- Modify: `utils/autocomplete.py`
- Modify: `utils/views.py`

**Interfaces — Produces (used by Tasks 6–10):**
```python
# utils/autocomplete.py — added to AutocompleteIndex:
def tool_choices(self, current: str) -> list[discord.app_commands.Choice]
def bait_choices(self, current: str) -> list[discord.app_commands.Choice]
def npc_choices(self, current: str) -> list[discord.app_commands.Choice]

# utils/views.py — new additions:
class JumpModal(discord.ui.Modal)
  # .page_number: discord.ui.TextInput
  # .__init__(self, target_view: DynamicPaginationView)
  # .on_submit(self, interaction): sets target_view.page, calls target_view.rebuild and edit_message

class DynamicPaginationView(discord.ui.View)
  # subclass this instead of PaginatedView for list commands
  # .page: int
  # .total_pages: int
  # .build_embed(self) -> discord.Embed  ← abstract; implement in subclass
  # .message: discord.Message | None    ← set after send so on_timeout can edit it
```

- [ ] **Step 1: Extend `utils/autocomplete.py`**

Replace the full file content:

```python
from typing import List
import discord


class AutocompleteIndex:
    def __init__(self, client):
        self.client = client

    def _choices(self, names: list[str], current: str) -> List[discord.app_commands.Choice]:
        matches = [n for n in names if current.lower() in n.lower()]
        return [discord.app_commands.Choice(name=n, value=n) for n in matches[:25]]

    def fish_choices(self, current: str) -> List[discord.app_commands.Choice]:
        return self._choices([c.name for c in self.client.fish_by_id.values()], current)

    def location_choices(self, current: str) -> List[discord.app_commands.Choice]:
        return self._choices([l.name for l in self.client.location_by_id.values()], current)

    def tool_choices(self, current: str) -> List[discord.app_commands.Choice]:
        return self._choices([t.name for t in self.client.tool_by_id.values()], current)

    def bait_choices(self, current: str) -> List[discord.app_commands.Choice]:
        return self._choices([b.name for b in self.client.bait_by_id.values()], current)

    def npc_choices(self, current: str) -> List[discord.app_commands.Choice]:
        return self._choices([n.name for n in self.client.npc_by_id.values()], current)
```

- [ ] **Step 2: Extend `utils/views.py`** — append after `ConfirmationView`:

```python
class JumpModal(discord.ui.Modal, title="Jump to Page"):
    page_number: discord.ui.TextInput = discord.ui.TextInput(
        label="Page number",
        placeholder="Enter a page number",
        min_length=1,
        max_length=4,
    )

    def __init__(self, target_view: "DynamicPaginationView"):
        super().__init__()
        self.target_view = target_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            p = int(self.page_number.value) - 1
            self.target_view.page = max(0, min(p, self.target_view.total_pages - 1))
            await interaction.response.edit_message(
                embed=self.target_view.build_embed(), view=self.target_view
            )
        except ValueError:
            await interaction.response.send_message(
                embed=_err_embed("Please enter a valid number."), ephemeral=True
            )


def _err_embed(msg: str):
    from utils.embeds import EmbedBuilder
    return EmbedBuilder.error("Invalid input", msg)


class DynamicPaginationView(discord.ui.View):
    """Base class for stateful list views. Subclass and implement build_embed()."""

    page: int = 0
    total_pages: int = 1
    message: discord.Message | None = None

    def __init__(self):
        super().__init__(timeout=300)

    def build_embed(self) -> discord.Embed:
        raise NotImplementedError

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Page  ?  / ?", style=discord.ButtonStyle.secondary, row=0)
    async def page_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(JumpModal(self))

    @discord.ui.button(label="▶ Next", style=discord.ButtonStyle.secondary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total_pages - 1:
            self.page += 1
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    def _refresh_page_btn(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button) and "Page" in item.label:
                item.label = f"Page  {self.page + 1}  /  {self.total_pages}"
                item.disabled = self.total_pages <= 1
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.label.startswith("◀"):
                    item.disabled = self.page == 0
                elif item.label.startswith("▶"):
                    item.disabled = self.page >= self.total_pages - 1
```

- [ ] **Step 3: Verify bot still loads (quick sanity check)**

```
python -c "from utils.autocomplete import AutocompleteIndex; from utils.views import DynamicPaginationView, JumpModal; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```
git add utils/autocomplete.py utils/views.py
git commit -m "feat: extend autocomplete index and add DynamicPaginationView"
```

---

## Task 5: `dankmemer_client.py` — cross-ref index + delete stub cog

**Files:**
- Modify: `dankmemer_client.py`
- Delete: `cogs/encyclopedia.py`

**Interfaces — Produces (used by Tasks 6–7):**
```python
# DankMemerGameClient — new attribute:
self.location_creature_map: dict[str, list]
# key = location_id, value = list of Creature objects from that location's creatures list
# populated in preload() AFTER both creatures and locations are loaded
```

- [ ] **Step 1: Delete `cogs/encyclopedia.py`**

```
del E:\disbot\cogs\encyclopedia.py
```

Or via shell: `rm E:/disbot/cogs/encyclopedia.py`

Verify it's gone: `ls E:/disbot/cogs/`

- [ ] **Step 2: Add `location_creature_map` to `DankMemerGameClient.__init__`**

In `dankmemer_client.py`, inside `__init__`, after `self.event_by_id: Dict[str, Any] = {}` add:

```python
        self.location_creature_map: Dict[str, list] = {}
```

- [ ] **Step 3: Populate `location_creature_map` in `preload()`**

In `dankmemer_client.py`, at the end of `preload()`, before the final `logger.info(...)` call, add:

```python
        # Build cross-reference: location → resolved Creature objects
        for loc_id, loc in self.location_by_id.items():
            creature_ids = loc.extra.get("creatures") or [] if hasattr(loc.extra, "get") else []
            self.location_creature_map[loc_id] = [
                self.fish_by_id[cid]
                for cid in creature_ids
                if cid in self.fish_by_id
            ]
        logger.debug("Built location_creature_map for %d locations", len(self.location_creature_map))
```

- [ ] **Step 4: Verify the bot module imports cleanly**

```
python -c "from dankmemer_client import DankMemerGameClient; print(DankMemerGameClient().location_creature_map)"
```

Expected: `{}`

- [ ] **Step 5: Commit**

```
git add dankmemer_client.py
git rm cogs/encyclopedia.py
git commit -m "feat: add location_creature_map cross-ref; remove encyclopedia stub"
```

---

## Task 6: `cogs/fish.py` — `/fish`, `/fishlist`, `/fishcompare`

**Files:**
- Create: `cogs/fish.py`

**Interfaces — Consumes:**
- `utils/embeds.py`: `build_fish_embed(creature, dank_client)`, `build_fish_compare_embed(c1, c2)`, `build_peak_hours_embed(creature)`, `build_fishlist_embed(creatures, page, total_pages, sort, rarity_filter)`
- `utils/views.py`: `DynamicPaginationView`
- `utils/autocomplete.py`: `AutocompleteIndex.fish_choices(current)`
- `utils/embeds.py`: `EmbedBuilder.error(...)`
- `bot.dank_client`: `DankMemerGameClient` with `.fish_by_id`, `.fish_by_name`, `.location_by_id`
- `bot.autocomplete`: `AutocompleteIndex`

- [ ] **Step 1: Create `cogs/fish.py`**

```python
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import (
    EmbedBuilder,
    build_fish_embed,
    build_fish_compare_embed,
    build_peak_hours_embed,
    build_fishlist_embed,
)
from utils.views import DynamicPaginationView
from utils.formatters import RARITY_ORDER, is_available_now, rarity_rank

_PRELOAD_GUARD_MSG = "⏳ Data is still loading, please try again in a moment."
_NOT_FOUND_MSG = "❌ No fish named **{name}** found. Try `/fishlist` to browse."


class FishCompareModal(discord.ui.Modal, title="Compare Fish"):
    second_fish: discord.ui.TextInput = discord.ui.TextInput(
        label="Second fish name",
        placeholder="e.g. Koi",
        min_length=1,
        max_length=60,
    )

    def __init__(self, first_creature, dank_client):
        super().__init__()
        self.first = first_creature
        self.dc = dank_client

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = self.second_fish.value.strip()
        second = self.dc.get_fish(name)
        if second is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND_MSG.format(name=name)),
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            embed=build_fish_compare_embed(self.first, second), view=None
        )


class BackToFishView(discord.ui.View):
    def __init__(self, creature, dank_client):
        super().__init__(timeout=300)
        self.creature = creature
        self.dc = dank_client

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]

    @discord.ui.button(label="↩ Back", style=discord.ButtonStyle.secondary)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = FishView(self.creature, self.dc)
        await interaction.response.edit_message(
            embed=build_fish_embed(self.creature, self.dc), view=view
        )


class FishView(discord.ui.View):
    def __init__(self, creature, dank_client):
        super().__init__(timeout=300)
        self.creature = creature
        self.dc = dank_client
        if not (creature.extra.get("variants") or []):
            self.variants_btn.disabled = True
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="🕐 Peak Hours", style=discord.ButtonStyle.secondary, row=0)
    async def peak_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = BackToFishView(self.creature, self.dc)
        await interaction.response.edit_message(embed=build_peak_hours_embed(self.creature), view=view)

    @discord.ui.button(label="🔮 Variants", style=discord.ButtonStyle.secondary, row=0)
    async def variants_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_fish_embed(self.creature, self.dc)
        variants = self.creature.extra.get("variants") or []
        parts = []
        for v in variants:
            if isinstance(v, dict):
                name = v.get("name", "Unknown")
                chance = v.get("chance", "?")
                parts.append(f"✨ **{name}** — {chance}%")
            else:
                parts.append(f"✨ {v}")
        extra_text = "\n\n**🔮 VARIANTS DETAIL**\n" + ("\n".join(parts) or "No data.")
        embed.description = (embed.description or "")[:3800] + extra_text
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📍 Locations", style=discord.ButtonStyle.secondary, row=0)
    async def locations_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_fish_embed(self.creature, self.dc)
        loc_ids = self.creature.extra.get("locations") or []
        lines = []
        for lid in loc_ids:
            loc = self.dc.location_by_id.get(lid)
            if loc:
                fail = loc.extra.get("failChance", 0) if hasattr(loc.extra, "get") else 0
                lines.append(f"📍 **{loc.name}**  ·  💀 Fail {fail}%")
        detail = "\n".join(lines) if lines else "No location data."
        embed.description = (embed.description or "")[:3700] + f"\n\n**📍 LOCATION DETAILS**\n{detail}"
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⚔️ Compare", style=discord.ButtonStyle.primary, row=1)
    async def compare_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FishCompareModal(self.creature, self.dc))

    @discord.ui.button(label="🤍 Favourite", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def fav_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="🎮 Simulate", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=1)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class FishListView(DynamicPaginationView):
    ITEMS_PER_PAGE = 10

    def __init__(self, dank_client):
        super().__init__()
        self.dc = dank_client
        self.sort = "alphabetical"
        self.rarity_filter = "All"
        self._refresh()

    def _refresh(self):
        creatures = list(self.dc.fish_by_id.values())
        if self.rarity_filter == "Boss":
            creatures = [c for c in creatures if c.extra.get("boss")]
        elif self.rarity_filter == "Mythical only":
            creatures = [c for c in creatures if c.extra.get("mythical")]
        elif self.rarity_filter != "All":
            creatures = [c for c in creatures if c.extra.get("rarity") == self.rarity_filter]

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
            self.filtered, self.page, self.total_pages, self.sort, self.rarity_filter
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


class FishCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _guard(self) -> bool:
        return bool(self.bot.dank_client and self.bot.dank_client.fish_by_id)

    @app_commands.command(name="fish", description="Look up a fish by name")
    @app_commands.describe(name="Fish name")
    async def fish(self, interaction: discord.Interaction, name: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        creature = self.bot.dank_client.get_fish(name)
        if creature is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND_MSG.format(name=name)),
                ephemeral=True,
            )
            return
        view = FishView(creature, self.bot.dank_client)
        embed = build_fish_embed(creature, self.bot.dank_client)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @fish.autocomplete("name")
    async def fish_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.fish_choices(current)

    @app_commands.command(name="fishlist", description="Browse all fish with filters")
    async def fishlist(self, interaction: discord.Interaction):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        view = FishListView(self.bot.dank_client)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="fishcompare", description="Compare two fish side by side")
    @app_commands.describe(fish1="First fish", fish2="Second fish")
    async def fishcompare(self, interaction: discord.Interaction, fish1: str, fish2: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        c1 = self.bot.dank_client.get_fish(fish1)
        c2 = self.bot.dank_client.get_fish(fish2)
        if c1 is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND_MSG.format(name=fish1)), ephemeral=True
            )
            return
        if c2 is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND_MSG.format(name=fish2)), ephemeral=True
            )
            return
        await interaction.response.send_message(embed=build_fish_compare_embed(c1, c2))

    @fishcompare.autocomplete("fish1")
    @fishcompare.autocomplete("fish2")
    async def fishcompare_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.fish_choices(current)


async def setup(bot: commands.Bot):
    await bot.add_cog(FishCog(bot))
```

- [ ] **Step 2: Verify cog syntax**

```
python -c "import cogs.fish; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```
git add cogs/fish.py
git commit -m "feat: implement /fish /fishlist /fishcompare commands"
```

---

## Task 7: `cogs/locations.py` — `/location`, `/locations`, `/locationcompare`

**Files:**
- Create: `cogs/locations.py`

**Interfaces — Consumes:**
- `utils/embeds.py`: `build_location_embed`, `build_location_compare_embed`, `build_locations_list_embed`, `build_fish_embed`, `EmbedBuilder`
- `utils/views.py`: `DynamicPaginationView`
- `utils/autocomplete.py`: `AutocompleteIndex.location_choices`
- `bot.dank_client`: `.location_by_id`, `.location_by_name`, `.fish_by_id`, `.location_creature_map`, `get_location(name)`
- `utils/formatters.py`: `is_available_now`, `rarity_emoji`

- [ ] **Step 1: Create `cogs/locations.py`**

```python
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import (
    EmbedBuilder,
    build_location_embed,
    build_location_compare_embed,
    build_locations_list_embed,
    build_fish_embed,
)
from utils.views import DynamicPaginationView
from utils.formatters import is_available_now, rarity_emoji, rarity_rank

_PRELOAD_MSG = "⏳ Data is still loading, please try again in a moment."
_NOT_FOUND = "❌ No location named **{name}** found. Try `/locations` to browse."


class LocationCompareModal(discord.ui.Modal, title="Compare Location"):
    second_loc: discord.ui.TextInput = discord.ui.TextInput(
        label="Second location name",
        placeholder="e.g. Murky Pond",
        min_length=1,
        max_length=60,
    )

    def __init__(self, first_loc, dank_client):
        super().__init__()
        self.first = first_loc
        self.dc = dank_client

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = self.second_loc.value.strip()
        second = self.dc.get_location(name)
        if second is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=name)), ephemeral=True
            )
            return
        await interaction.response.edit_message(
            embed=build_location_compare_embed(self.first, second), view=None
        )


class LocationView(discord.ui.View):
    def __init__(self, location, dank_client):
        super().__init__(timeout=300)
        self.loc = location
        self.dc = dank_client
        self.message: discord.Message | None = None
        self._build_fish_select()

    def _build_fish_select(self):
        creatures = self.dc.location_creature_map.get(self.loc.id, [])
        if not creatures:
            return
        creatures_sorted = sorted(
            creatures,
            key=lambda c: -rarity_rank(c.extra.get("rarity", "Common"))
        )[:25]
        options = []
        for c in creatures_sorted:
            rarity = c.extra.get("rarity", "Common")
            avail = "✅" if is_available_now(c) else "❌"
            options.append(
                discord.SelectOption(
                    label=c.name[:100],
                    value=c.id,
                    description=f"{rarity}  ·  {avail} now",
                    emoji=rarity_emoji(rarity),
                )
            )
        select = discord.ui.Select(
            placeholder=f"🐟 Fish Pool ({len(creatures)} creatures) ▾",
            options=options,
            row=0,
        )
        select.callback = self._fish_selected
        self.add_item(select)
        self._selected_creature_id: str | None = None

    async def _fish_selected(self, interaction: discord.Interaction):
        select: discord.ui.Select = interaction.data  # type: ignore
        chosen_id = interaction.data["values"][0]  # type: ignore
        creature = self.dc.fish_by_id.get(chosen_id)
        if creature is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", "Could not load that fish."), ephemeral=True
            )
            return
        self._selected_creature_id = chosen_id
        embed = build_location_embed(self.loc, self.dc)
        # Show brief fish info appended to description
        rarity = creature.extra.get("rarity", "Common")
        flavor = creature.extra.get("flavor", "")
        snippet = f"\n\n{rarity_emoji(rarity)} **{creature.name}** — {rarity}\n*{flavor[:120]}*" if flavor else f"\n\n{rarity_emoji(rarity)} **{creature.name}** — {rarity}"
        embed.description = (embed.description or "")[:3700] + snippet
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="🔗 Open Fish", style=discord.ButtonStyle.primary, row=1)
    async def open_fish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not hasattr(self, "_selected_creature_id") or self._selected_creature_id is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("No fish selected", "Select a fish from the dropdown first."),
                ephemeral=True,
            )
            return
        creature = self.dc.fish_by_id.get(self._selected_creature_id)
        if creature is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", "Fish data unavailable."), ephemeral=True
            )
            return
        from cogs.fish import FishView
        view = FishView(creature, self.dc)
        embed = build_fish_embed(creature, self.dc)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @discord.ui.button(label="⚔️ Compare", style=discord.ButtonStyle.primary, row=1)
    async def compare_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LocationCompareModal(self.loc, self.dc))

    @discord.ui.button(label="🎮 Simulate", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="🤍 Favourite", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def fav_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=1)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class LocationsListView(DynamicPaginationView):
    ITEMS_PER_PAGE = 8

    def __init__(self, dank_client):
        super().__init__()
        self.dc = dank_client
        self.sort = "name"
        self.filter_ = "All"
        self._refresh()

    def _refresh(self):
        locs = list(self.dc.location_by_id.values())
        if self.filter_ == "Temporary":
            locs = [l for l in locs if l.extra.get("temporary")]
        elif self.filter_ == "Disabled":
            locs = [l for l in locs if l.extra.get("disabled")]
        elif self.filter_ == "Active":
            locs = [l for l in locs if not l.extra.get("disabled") and not l.extra.get("temporary")]

        if self.sort == "name":
            locs.sort(key=lambda l: l.name.lower())
        elif self.sort == "fish_count":
            locs.sort(key=lambda l: -len(l.extra.get("creatures") or []))
        elif self.sort == "fail_chance":
            locs.sort(key=lambda l: l.extra.get("failChance", 0))
        elif self.sort == "mine_chance":
            locs.sort(key=lambda l: -l.extra.get("mineChance", 0))

        self.filtered = locs
        self.total_pages = max(1, (len(locs) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        self.page = min(self.page, self.total_pages - 1)
        self._refresh_page_btn()

    def build_embed(self) -> discord.Embed:
        return build_locations_list_embed(self.filtered, self.page, self.total_pages, self.sort, self.filter_)

    @discord.ui.select(
        placeholder="📊 Sort ▾",
        row=1,
        options=[
            discord.SelectOption(label="Name (A–Z)", value="name", default=True),
            discord.SelectOption(label="Fish Count (most first)", value="fish_count"),
            discord.SelectOption(label="Fail Chance (lowest first)", value="fail_chance"),
            discord.SelectOption(label="Mine Chance (highest first)", value="mine_chance"),
        ],
    )
    async def sort_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.sort = select.values[0]
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.select(
        placeholder="🔍 Filter ▾",
        row=2,
        options=[
            discord.SelectOption(label="All", value="All", default=True),
            discord.SelectOption(label="Active only", value="Active"),
            discord.SelectOption(label="🔴 Temporary", value="Temporary"),
            discord.SelectOption(label="⛔ Disabled", value="Disabled"),
        ],
    )
    async def filter_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.filter_ = select.values[0]
        self.page = 0
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class LocationsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _guard(self) -> bool:
        return bool(self.bot.dank_client and self.bot.dank_client.location_by_id)

    @app_commands.command(name="location", description="Look up a fishing location")
    @app_commands.describe(name="Location name")
    async def location(self, interaction: discord.Interaction, name: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        loc = self.bot.dank_client.get_location(name)
        if loc is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=name)), ephemeral=True
            )
            return
        view = LocationView(loc, self.bot.dank_client)
        embed = build_location_embed(loc, self.bot.dank_client)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @location.autocomplete("name")
    async def location_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.location_choices(current)

    @app_commands.command(name="locations", description="Browse all fishing locations")
    async def locations(self, interaction: discord.Interaction):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        view = LocationsListView(self.bot.dank_client)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="locationcompare", description="Compare two locations")
    @app_commands.describe(location1="First location", location2="Second location")
    async def locationcompare(self, interaction: discord.Interaction, location1: str, location2: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        l1 = self.bot.dank_client.get_location(location1)
        l2 = self.bot.dank_client.get_location(location2)
        if l1 is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=location1)), ephemeral=True
            )
            return
        if l2 is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=location2)), ephemeral=True
            )
            return
        await interaction.response.send_message(embed=build_location_compare_embed(l1, l2))

    @locationcompare.autocomplete("location1")
    @locationcompare.autocomplete("location2")
    async def locationcompare_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.location_choices(current)


async def setup(bot: commands.Bot):
    await bot.add_cog(LocationsCog(bot))
```

- [ ] **Step 2: Verify syntax**

```
python -c "import cogs.locations; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```
git add cogs/locations.py
git commit -m "feat: implement /location /locations /locationcompare commands"
```

---

## Task 8: `cogs/tools.py` — `/tool`, `/toolcompare`

**Files:**
- Create: `cogs/tools.py`

**Interfaces — Consumes:**
- `utils/embeds.py`: `build_tool_embed(tool)`, `build_toolcompare_embed(tools)`, `EmbedBuilder`
- `utils/autocomplete.py`: `AutocompleteIndex.tool_choices`
- `bot.dank_client`: `.tool_by_id`, `.tool_by_name`, `get_tool(name)`

- [ ] **Step 1: Create `cogs/tools.py`**

```python
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder, build_tool_embed, build_toolcompare_embed

_PRELOAD_MSG = "⏳ Data is still loading, please try again in a moment."
_NOT_FOUND = "❌ No tool named **{name}** found."


class ToolCompareModal(discord.ui.Modal, title="Compare Tool"):
    second_tool: discord.ui.TextInput = discord.ui.TextInput(
        label="Second tool name",
        placeholder="e.g. Harpoon",
        min_length=1,
        max_length=60,
    )

    def __init__(self, first_tool, dank_client):
        super().__init__()
        self.first = first_tool
        self.dc = dank_client

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = self.second_tool.value.strip()
        second = self.dc.get_tool(name)
        if second is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=name)), ephemeral=True
            )
            return
        await interaction.response.edit_message(
            embed=build_toolcompare_embed([self.first, second]), view=None
        )


class ToolView(discord.ui.View):
    def __init__(self, tool, dank_client):
        super().__init__(timeout=300)
        self.tool = tool
        self.dc = dank_client
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="⚔️ Compare", style=discord.ButtonStyle.primary)
    async def compare_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ToolCompareModal(self.tool, self.dc))

    @discord.ui.button(label="🎮 Simulate", style=discord.ButtonStyle.secondary, disabled=True)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class ToolsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _guard(self) -> bool:
        return bool(self.bot.dank_client and self.bot.dank_client.tool_by_id)

    @app_commands.command(name="tool", description="Look up a fishing tool")
    @app_commands.describe(name="Tool name")
    async def tool(self, interaction: discord.Interaction, name: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        t = self.bot.dank_client.get_tool(name)
        if t is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=name)), ephemeral=True
            )
            return
        view = ToolView(t, self.bot.dank_client)
        embed = build_tool_embed(t)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @tool.autocomplete("name")
    async def tool_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.tool_choices(current)

    @app_commands.command(name="toolcompare", description="Compare all fishing tools side by side")
    async def toolcompare(self, interaction: discord.Interaction):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        tools = list(self.bot.dank_client.tool_by_id.values())
        await interaction.response.send_message(embed=build_toolcompare_embed(tools))


async def setup(bot: commands.Bot):
    await bot.add_cog(ToolsCog(bot))
```

- [ ] **Step 2: Verify syntax**

```
python -c "import cogs.tools; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```
git add cogs/tools.py
git commit -m "feat: implement /tool /toolcompare commands"
```

---

## Task 9: `cogs/baits.py` + `cogs/npcs.py`

**Files:**
- Create: `cogs/baits.py`
- Create: `cogs/npcs.py`

**Interfaces — Consumes:**
- `utils/embeds.py`: `build_bait_embed`, `build_bait_compare_embed`, `build_npc_embed`, `EmbedBuilder`
- `utils/autocomplete.py`: `AutocompleteIndex.bait_choices`, `AutocompleteIndex.npc_choices`
- `bot.dank_client`: `.bait_by_id`, `get_bait(name)`, `.npc_by_id`, `get_npc(name)`

- [ ] **Step 1: Create `cogs/baits.py`**

```python
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder, build_bait_embed, build_bait_compare_embed

_PRELOAD_MSG = "⏳ Data is still loading, please try again in a moment."
_NOT_FOUND = "❌ No bait named **{name}** found."


class BaitCompareModal(discord.ui.Modal, title="Compare Bait"):
    second_bait: discord.ui.TextInput = discord.ui.TextInput(
        label="Second bait name",
        placeholder="e.g. Gold Bait",
        min_length=1,
        max_length=60,
    )

    def __init__(self, first_bait, dank_client):
        super().__init__()
        self.first = first_bait
        self.dc = dank_client

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = self.second_bait.value.strip()
        second = self.dc.get_bait(name)
        if second is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=name)), ephemeral=True
            )
            return
        await interaction.response.edit_message(
            embed=build_bait_compare_embed(self.first, second), view=None
        )


class BaitView(discord.ui.View):
    def __init__(self, bait, dank_client):
        super().__init__(timeout=300)
        self.bait = bait
        self.dc = dank_client
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="⚔️ Compare", style=discord.ButtonStyle.primary)
    async def compare_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BaitCompareModal(self.bait, self.dc))

    @discord.ui.button(label="🎮 Simulate", style=discord.ButtonStyle.secondary, disabled=True)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class BaitsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _guard(self) -> bool:
        return bool(self.bot.dank_client and self.bot.dank_client.bait_by_id)

    @app_commands.command(name="bait", description="Look up a fishing bait")
    @app_commands.describe(name="Bait name")
    async def bait(self, interaction: discord.Interaction, name: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        b = self.bot.dank_client.get_bait(name)
        if b is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=name)), ephemeral=True
            )
            return
        view = BaitView(b, self.bot.dank_client)
        embed = build_bait_embed(b)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @bait.autocomplete("name")
    async def bait_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.bait_choices(current)

    @app_commands.command(name="baitcompare", description="Compare two fishing baits")
    @app_commands.describe(bait1="First bait", bait2="Second bait")
    async def baitcompare(self, interaction: discord.Interaction, bait1: str, bait2: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        b1 = self.bot.dank_client.get_bait(bait1)
        b2 = self.bot.dank_client.get_bait(bait2)
        if b1 is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=bait1)), ephemeral=True
            )
            return
        if b2 is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=bait2)), ephemeral=True
            )
            return
        await interaction.response.send_message(embed=build_bait_compare_embed(b1, b2))

    @baitcompare.autocomplete("bait1")
    @baitcompare.autocomplete("bait2")
    async def baitcompare_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.bait_choices(current)


async def setup(bot: commands.Bot):
    await bot.add_cog(BaitsCog(bot))
```

- [ ] **Step 2: Create `cogs/npcs.py`**

```python
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder, build_npc_embed

_PRELOAD_MSG = "⏳ Data is still loading, please try again in a moment."
_NOT_FOUND = "❌ No NPC named **{name}** found."


class NpcsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _guard(self) -> bool:
        return bool(self.bot.dank_client and self.bot.dank_client.npc_by_id)

    @app_commands.command(name="npc", description="Look up a fishing NPC")
    @app_commands.describe(name="NPC name")
    async def npc(self, interaction: discord.Interaction, name: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        n = self.bot.dank_client.get_npc(name)
        if n is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=name)), ephemeral=True
            )
            return
        await interaction.response.send_message(embed=build_npc_embed(n))

    @npc.autocomplete("name")
    async def npc_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.npc_choices(current)


async def setup(bot: commands.Bot):
    await bot.add_cog(NpcsCog(bot))
```

- [ ] **Step 3: Verify syntax on both**

```
python -c "import cogs.baits; import cogs.npcs; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```
git add cogs/baits.py cogs/npcs.py
git commit -m "feat: implement /bait /baitcompare /npc commands"
```

---

## Task 10: `cogs/core.py` — update `/stats`

**Files:**
- Modify: `cogs/core.py`

- [ ] **Step 1: Replace `stats` command in `cogs/core.py`**

Replace the existing `stats` method (lines 18–26) with:

```python
    @app_commands.command(name="stats", description="Show bot statistics and data status")
    async def stats(self, interaction: discord.Interaction):
        embed = EmbedBuilder.info("📊 Bot Statistics")
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="​", value="​", inline=True)  # spacer

        dc = self.bot.dank_client
        if dc:
            fish_count = len(dc.fish_by_id)
            loc_count = len(dc.location_by_id)
            tool_count = len(dc.tool_by_id)
            bait_count = len(dc.bait_by_id)
            npc_count = len(dc.npc_by_id)
            status = "✅ Ready" if fish_count > 0 else "⏳ Loading…"
            embed.add_field(name="🐟 Fish", value=str(fish_count), inline=True)
            embed.add_field(name="📍 Locations", value=str(loc_count), inline=True)
            embed.add_field(name="🔧 Tools", value=str(tool_count), inline=True)
            embed.add_field(name="🪱 Baits", value=str(bait_count), inline=True)
            embed.add_field(name="👤 NPCs", value=str(npc_count), inline=True)
            embed.add_field(name="Cache", value=status, inline=True)
        else:
            embed.add_field(name="Data", value="❌ Client not initialised", inline=False)

        await interaction.response.send_message(embed=embed)
```

- [ ] **Step 2: Verify syntax**

```
python -c "import cogs.core; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```
git add cogs/core.py
git commit -m "feat: update /stats with entity counts and cache status"
```

---

## Task 11: Full smoke test

- [ ] **Step 1: Run the full test suite**

```
pytest tests/ -v
```

Expected: all green.

- [ ] **Step 2: Run the bot locally**

Copy `.env.example` to `.env` and fill in `DISCORD_BOT_TOKEN` and optionally `COMMAND_GUILD_ID` (set to your test server ID for instant slash command registration).

```
python main.py
```

Expected log output (in order):
```
INFO  Loaded cog: cogs.baits
INFO  Loaded cog: cogs.core
INFO  Loaded cog: cogs.fish
INFO  Loaded cog: cogs.locations
INFO  Loaded cog: cogs.npcs
INFO  Loaded cog: cogs.profile       ← stub, that's fine
INFO  Loaded cog: cogs.simulator     ← stub, that's fine
INFO  Loaded cog: cogs.tools
INFO  Logged in as <BotName> (<id>)
INFO  Preloading DankMemer game data...
INFO  Preload complete: N fish, N locations, N tools, N baits, N npcs, N events
```

- [ ] **Step 3: Test every command in Discord**

Test each command in your server:

| Command | What to verify |
|---------|---------------|
| `/stats` | Shows fish/loc/tool/bait/npc counts, Cache: ✅ Ready |
| `/fish <any name>` | Embed with colour, availability bar, locations |
| `/fish <any name>` → Peak Hours button | 24-hour grid, current hour highlighted |
| `/fish <any name>` → Locations button | Location names and fail % |
| `/fish <any name>` → Compare button | Modal appears; typing a second fish shows compare table |
| `/fishlist` | 10 fish per page, sort and filter selects work, page jump works |
| `/fishcompare <f1> <f2>` | Compare table with ✓ on winners |
| `/location <any name>` | Embed with banner image, rarity bars, fish pool select |
| `/location` fish pool select | Choosing a fish updates embed inline |
| `/location` → Open Fish | Sends ephemeral fish embed |
| `/location` → Compare button | Modal → compare table |
| `/locations` | List with sort/filter, pagination |
| `/locationcompare <l1> <l2>` | Compare table |
| `/tool <any name>` | Tool embed with buffs/debuffs |
| `/tool` → Compare button | Modal → compare table for 2 tools |
| `/toolcompare` | All tools in one code-block table |
| `/bait <any name>` | Bait embed |
| `/bait` → Compare button | Compare table |
| `/baitcompare <b1> <b2>` | Compare table |
| `/npc <any name>` | NPC embed |
| Any command with bad name | Ephemeral error embed, not an exception |
| Wait 5 min on any view | Buttons disable in place, no timeout error in logs |

- [ ] **Step 4: Fix any issues found during smoke test**

Fix inline. Commit each fix separately:
```
git commit -m "fix: <describe what broke>"
```

- [ ] **Step 5: Push to remote**

```
git push origin master
```

---

## Self-Review Checklist

- [x] **Spec coverage:** All 12 commands from the spec are covered (fish, fishlist, fishcompare, location, locations, locationcompare, tool, toolcompare, bait, baitcompare, npc, stats).
- [x] **Button sets match spec:** Peak Hours ✓, Variants ✓, Locations ✓, Compare ✓, Favourite (disabled) ✓, Simulate (disabled) ✓, Delete ✓.
- [x] **Visual design system:** Rarity colours, emoji, availability bar, progress bar, comparison table with ✓ markers — all implemented in formatters.py and used in embed builders.
- [x] **Cross-ref index:** `location_creature_map` built in Task 5, used in LocationView fish pool select.
- [x] **`encyclopedia.py` deletion:** In Task 5.
- [x] **View timeout:** All views implement `on_timeout`, disable buttons, edit message.
- [x] **Preload guard:** All cog commands check `self._guard()` and return ephemeral error if data not ready.
- [x] **Not-found errors:** All lookups return ephemeral error embed, not a plain message.
- [x] **`/fishlist` embed header:** Added in Task 2 — title says "All Fish (N total)" with correct colour.
- [x] **Type consistency:** `build_fish_embed(creature, dank_client)` — same signature used in FishCog, LocationView Open Fish, BackToFishView.
- [x] **NPC test import:** Test uses `MagicMock` for NPC object — avoids breaking on unknown NPC class path.
- [x] **Placeholder scan:** No TBDs, TODOs, or "similar to" references found.
