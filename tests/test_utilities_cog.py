from __future__ import annotations
import pytest
import discord
from datetime import time as dt_time
from unittest.mock import AsyncMock, MagicMock, patch
from dankmemer.utils import DotDict


def _make_fish(fid, rarity="Common", locations=None, full_day=True, start_h=0, end_h=6):
    time_data = {"full_day": full_day}
    if not full_day:
        time_data["start"] = dt_time(hour=start_h)
        time_data["end"] = dt_time(hour=end_h)
    extra = DotDict({
        "boss": False, "mythical": False, "rarity": rarity,
        "flavor": "", "locations": locations or ["loc1"],
        "time": time_data, "variants": [],
        "tools": {"fishing-rod": {"max": 1}},
    })
    f = MagicMock()
    f.id = fid
    f.name = fid.capitalize()
    f.extra = extra
    return f


def _make_location(lid, name=None):
    loc = MagicMock()
    loc.id = lid
    loc.name = name or lid.capitalize()
    return loc


def _make_event(eid, name=None, description="Test desc", last=None):
    ev = MagicMock()
    ev.id = eid
    ev.name = name or eid.capitalize()
    ev.imageURL = "https://example.com/img.png"
    ev.extra = {"description": description, "last": last or ["2026-05-15T00:00:00.000Z"]}
    return ev


def _make_dc(fish=None, locations=None, events=None):
    dc = MagicMock()
    fish = fish or [_make_fish("bass")]
    locs = locations or [_make_location("river")]
    evs = events or [_make_event("2xtokens", "Token Cloning")]
    dc.fish_by_id = {f.id: f for f in fish}
    dc.location_by_id = {l.id: l for l in locs}
    dc.event_by_id = {e.id: e for e in evs}
    dc.event_by_name = {e.name.lower(): e for e in evs}
    return dc


def _make_interaction():
    inter = MagicMock()
    inter.response = AsyncMock()
    inter.response.send_message = AsyncMock()
    inter.response.edit_message = AsyncMock()
    inter.response.defer = AsyncMock()
    inter.message = MagicMock()
    inter.message.delete = AsyncMock()
    inter.user = MagicMock()
    inter.user.id = 123
    inter.followup = AsyncMock()
    return inter


# ── /rarity ─────────────────────────────────────────────────────────────────

def test_rarity_embed_has_7_fields():
    import cogs.utilities as u
    dc = _make_dc()
    with patch("cogs.utilities._utc_hour", return_value=12):
        embed = u._build_rarity_embed(dc, hour=12)
    assert len(embed.fields) == 7
    field_names = [f.name for f in embed.fields]
    for tier in ["Absurdly Common", "Very Common", "Common", "Regular",
                 "Rare", "Very Rare", "Absurdly Rare"]:
        assert tier in field_names


def test_rarity_currently_catchable_uses_utc_hour():
    import cogs.utilities as u
    dc = _make_dc(fish=[_make_fish("bass", full_day=True, locations=["river"])])
    embed = u._build_rarity_embed(dc, hour=5)
    # bass is full_day=True so it should be in "Common" now count
    common_field = next(f for f in embed.fields if f.name == "Common")
    assert "Now: **1**" in common_field.value
