from __future__ import annotations
import discord
import pytest
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


# ── /event ──────────────────────────────────────────────────────────────────

def test_event_overview_paginates():
    import cogs.utilities as u
    events = [_make_event(f"ev{i}", f"Event {i}") for i in range(8)]
    pages = u._build_event_overview_pages(events, active_event=None)
    assert len(pages) == 2  # 8 events, 5 per page → 2 pages
    assert "1/2" in (pages[0].footer.text or "")


def test_event_overview_stars_active_event():
    import cogs.utilities as u
    events = [
        _make_event("ev1", "Alpha Event"),
        _make_event("ev2", "Beta Event"),
    ]
    pages = u._build_event_overview_pages(events, active_event="Alpha Event")
    body = " ".join(f.name for f in pages[0].fields)
    assert "⭐" in body
    # Beta should not have a star
    beta_field = next(f for f in pages[0].fields if "Beta" in f.name)
    assert "⭐" not in beta_field.name


def test_event_detail_shows_description():
    import cogs.utilities as u
    ev = _make_event("ev1", "Great Event", description="Full event description here.")
    embed = u._build_event_detail_embed(ev, active_event=None)
    assert "Full event description here." in (embed.description or "")
    assert embed.title == "Great Event"


@pytest.mark.asyncio
async def test_event_set_current_updates_profile():
    import cogs.utilities as u
    db = MagicMock()
    db.update_user = AsyncMock()
    ev = _make_event("ev1", "Great Event")
    view = u.EventDetailView(db, ev, user_id="999")
    interaction = _make_interaction()
    set_btn = next(b for b in view.children if isinstance(b, discord.ui.Button) and "Set" in b.label)
    await set_btn.callback(interaction)
    db.update_user.assert_called_once_with("999", current_event="Great Event")
    assert set_btn.disabled is True
    assert set_btn.label == "✅ Set"


# ── /time ────────────────────────────────────────────────────────────────────

def test_time_default_shows_all_locations():
    import cogs.utilities as u
    # bass is full_day → always catchable
    dc = _make_dc(fish=[_make_fish("bass", full_day=True, locations=["river"])], locations=[_make_location("river")])
    embed = u._build_time_embed(dc, hour=12, location_id=None)
    assert "1" in (embed.description or "")  # 1 fish catchable


def test_time_select_filters_to_location():
    import cogs.utilities as u
    fish_river = _make_fish("bass", full_day=True, locations=["river"])
    fish_lake = _make_fish("trout", full_day=True, locations=["lake"])
    dc = _make_dc(
        fish=[fish_river, fish_lake],
        locations=[_make_location("river"), _make_location("lake")],
    )
    embed = u._build_time_embed(dc, hour=12, location_id="river")
    field_names = [f.name for f in embed.fields]
    assert "Catchable Now" in field_names
    catchable_field = next(f for f in embed.fields if f.name == "Catchable Now")
    assert "Bass" in catchable_field.value
    assert "Trout" not in catchable_field.value


def test_time_upcoming_windows_next_6h():
    import cogs.utilities as u
    # bass: available only hours 5..10
    bass = _make_fish("bass", full_day=False, start_h=5, end_h=10, locations=["river"])
    dc = _make_dc(fish=[bass], locations=[_make_location("river")])
    # At hour 4, bass is NOT catchable. At hour 5 it becomes available.
    windows = u._upcoming_windows(dc, hour=4, location_id=None, ahead=6)
    assert 5 in windows
    assert "Bass" in windows[5]


# ── /today ───────────────────────────────────────────────────────────────────

def test_today_shows_active_event_from_profile():
    import cogs.utilities as u
    dc = _make_dc(fish=[_make_fish("bass", full_day=True)], locations=[_make_location("river")])
    db_row = {"current_event": "Token Cloning"}
    embed = u._build_today_embed(dc, db_row, hour=10)
    active_field = next((f for f in embed.fields if f.name == "Active Event"), None)
    assert active_field is not None
    assert "Token Cloning" in active_field.value


def test_today_top_3_locations():
    import cogs.utilities as u
    locs = [_make_location(f"loc{i}") for i in range(5)]
    # bass is in loc0, loc1, loc2 only
    bass = _make_fish("bass", full_day=True, locations=["loc0", "loc1", "loc2"])
    dc = _make_dc(fish=[bass], locations=locs)
    embed = u._build_today_embed(dc, db_row=None, hour=10)
    top_field = next((f for f in embed.fields if f.name == "Top Locations"), None)
    assert top_field is not None
    lines = top_field.value.strip().split("\n")
    assert len(lines) <= 3


def test_today_active_event_not_in_dc():
    import cogs.utilities as u
    dc = _make_dc(fish=[_make_fish("bass", full_day=True)], locations=[_make_location("river")])
    db_row = {"current_event": "unknown event"}
    embed = u._build_today_embed(dc, db_row, hour=10)
    active_field = next((f for f in embed.fields if f.name == "Active Event"), None)
    assert active_field is not None
    assert "None set — use `/event` to set one" in active_field.value
