# Phase 5 — Utility Commands Design Spec
**Date:** 2026-06-23
**Scope:** `/rarity`, `/event`, `/time`, `/today` — read-only utility commands
**Bot:** DankFishingBot · discord.py 2.x · SQLite · dankmemer>=1.0.0rc2

---

## 1. Context

Phases 1–4 delivered the encyclopedia, user profiles, simulator, and local fishing engine.
Phase 5 adds four read-only utility commands that surface time-sensitive game state using
only preloaded data and the local engine — no new DB tables, no live API calls.

**`/weather` is explicitly out of scope for Phase 5.** Weather has no structured data in
`data.json` (it is a free-text profile field). It will be revisited in Phase 9 when the
Dank Memer bot listener is implemented.

---

## 2. Architecture

**New file:** `cogs/utilities.py` — one cog, four commands. No changes to existing cogs.

**Data sources (all preloaded at startup):**
- `dc.fish_by_id` — all 153 creatures
- `dc.location_by_id` — all 14 locations
- `dc.event_by_id` / `dc.event_by_name` — 13 events
- `fishing_engine.creature_eligible(creature, location_id, tool_id, hour, *, bosses, ignore_time)`
- `datetime.utcnow()` for the current UTC hour
- `db.get_or_create_user()` — profile data for `/event` (Set as Current) and `/today`

**No live API calls. No new DB columns or migrations.**

---

## 3. Commands

### 3.1 `/rarity`

**Args:** none

**Output:** Single embed, no interactive controls (Delete button only).

| Field | Content |
|-------|---------|
| Title | "Rarity Tiers" |
| One field per rarity | Name · weight from `RARITY_WEIGHTS` · total fish count · currently catchable count at current UTC hour |

Rarity tiers in order (descending weight):
`Absurdly Common (18.5)`, `Very Common (16.5)`, `Common (14.5)`, `Regular (10.0)`,
`Rare (6.5)`, `Very Rare (1.0)`, `Absurdly Rare (0.075)`.

"Currently catchable": for each fish in `dc.fish_by_id.values()`, iterate over all 14 location IDs and call `creature_eligible(c, location_id, tool_id="fishing-rod", hour=utc_hour, bosses=False, ignore_time=False)`. A fish counts once if it returns `True` for at least one location.

Footer: `UTC hour: {hour}:00`

---

### 3.2 `/event [name]`

**Args:** `name` — optional, autocomplete from `dc.event_by_name`.

#### No-arg mode (overview)
Calls `db.get_or_create_user(str(interaction.user.id))` to read `current_event`.
Paginated embed, 5 events per page. Each entry:
- Thumbnail emoji/image from `event.imageURL`
- Name — prefixed with ⭐ if it matches the invoker's `current_event` in their profile
- Description (first 80 chars, truncated with …)
- Last occurrence: most recent date from `event.extra["last"]` formatted as `YYYY-MM-DD`

Navigation: Prev / Next page buttons + Delete. Page `n/total` in footer.

#### Named mode (detail)
Full embed for a single event:
- Title: event name, thumbnail set to `event.imageURL`
- Description: full `event.extra["description"]`
- Field "Last Seen": up to 3 dates from `event.extra["last"]`, each formatted `YYYY-MM-DD`
- Footer: "Active" if matches profile `current_event`, else empty

Buttons:
- **⭐ Set as Current** — calls `db.update_user(discord_id, current_event=event.name)`, relabels to "✅ Set" and disables itself after click
- **🗑️ Delete**

The "Set as Current" button requires the invoker's Discord ID; it updates only their own profile.

---

### 3.3 `/time`

**Args:** none

**Layout:** Interactive view with one select and two buttons.

**Row 0:** `LocationSelect` — placeholder "Filter by location…", options = all 14 locations
(sorted alphabetically). Default: no selection (shows summary across all locations).

**Row 1:** Delete button.

#### Default state (no location selected)
Embed shows:
- Title: `Current UTC — {hour}:00`
- Description: total catchable fish count across all locations at this hour (using
  `creature_eligible` with `tool_id="fishing-rod", bosses=False, ignore_time=False`)
- Field "Upcoming Windows (next 6 hours)": for hours `h+1` through `h+6`, list any fish
  that become **newly available** (eligible at `h+N` but not at `h`), grouped by hour.
  If no new fish open in a window, omit that hour. If all hours are empty, show "No new
  windows in the next 6 hours."

#### Location-filtered state
After selecting a location:
- Title: `{location_name} — {hour}:00 UTC`
- Field "Catchable Now": list of fish names catchable at this location + hour (rod, no
  bosses). If none, show "No fish catchable at this hour."
- Field "Upcoming Windows (next 6 hours)": same logic as default but scoped to this
  location — fish that open in hours h+1..h+6 that are not open at h.

`_on_select` callback: rebuild embed with filtered data, call `edit_message(embed=..., view=self)`.

---

### 3.4 `/today`

**Args:** none. Reads invoker's profile via `db.get_or_create_user`.

**Output:** Single embed, Delete button only.

| Section | Content |
|---------|---------|
| Title | "Today's Fishing — {YYYY-MM-DD} UTC" |
| Field "Current Time" | `{hour}:00 UTC` |
| Field "Active Event" | Event name from profile `current_event` (looked up via `dc.event_by_id`), or "None set — use `/event` to set one" |
| Field "Catchable Right Now" | Total fish count catchable across all locations at current hour |
| Field "Top Locations" | Top 3 locations by catchable fish count at current hour, format: `{location_name} — {count} fish` |
| Field "Upcoming (next 3h)" | For h+1, h+2, h+3: net change in catchable fish count (e.g. "+2 fish open, 1 fish close"). Omit hours with no change. |

Footer: "Update your setup with /profile"

---

## 4. Error Handling

- All commands: if `dc.fish_by_id` is empty (preload failed), respond with `EmbedBuilder.error(...)` ephemeral.
- `/event` named mode: if name not found, respond with ephemeral error embed.
- `/event` "Set as Current": if DB write fails, respond with ephemeral error embed; do not disable the button.
- `/today`: if `get_or_create_user` fails, still show the time/fish data with "Active Event: unavailable".

---

## 5. Testing

All tests in `tests/test_utilities_cog.py`.

| Test | Covers |
|------|--------|
| `test_rarity_embed_has_7_fields` | All 7 tiers present in embed |
| `test_rarity_currently_catchable_uses_utc_hour` | `creature_eligible` called with `datetime.utcnow().hour` |
| `test_event_overview_paginates` | >5 events → Prev/Next buttons present |
| `test_event_overview_stars_active_event` | Profile `current_event` entry gets ⭐ |
| `test_event_detail_shows_description` | Full description in embed |
| `test_event_set_current_updates_profile` | `db.update_user` called with correct event id |
| `test_time_default_shows_all_locations` | No-location embed shows total count |
| `test_time_select_filters_to_location` | Post-select embed scoped to chosen location |
| `test_time_upcoming_windows_next_6h` | Windows field lists newly-opening fish |
| `test_today_shows_active_event_from_profile` | Event name resolved from profile |
| `test_today_top_3_locations` | Top locations field has ≤3 entries |

---

## 6. Out of Scope

- `/weather` — no structured game data; deferred to Phase 9
- Profit/XP estimates — simulator concern, Phase 6
- Simulator auto-save: persisting simulation inputs (tool, bait, location, event, hour) back to the user's profile after Calculate — Phase 6
- Live API calls of any kind
- New DB tables or migrations
- Notifications, background tasks
