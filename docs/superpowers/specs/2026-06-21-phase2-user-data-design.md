# Phase 2 — User Data Design Spec

**Date:** 2026-06-21
**Phase:** 2 of 6
**Depends on:** Phase 1 (encyclopedia commands, embed helpers)
**Unlocks:** Phase 3 (Simulator reads profile defaults), Phase 6 (notifications read prefs)

---

## Goal

Persistent user data layer: profile editing, favourites, history, and settings. Also enables the Favourite button disabled in Phase 1.

---

## Database

Schema already fully in place (`migrations/001_initial.sql`). No migrations needed.

**Tables used:**

| Table | Key columns |
|-------|-------------|
| `users` | discord_id (PK), fishing_rod, current_tool, current_bait, fishing_skill, luck_skill, efficiency_skill, prestige, coins, boss_unlock, mythical_unlock, favorite_fish, favorite_location, favorite_tool, favorite_bait, current_weather, current_event, timezone, theme, compact_mode, simulator_presets, notification_prefs, updated_at |
| `favorites` | discord_id, type (fish/location/tool/bait), item_id — UNIQUE(discord_id, type, item_id) |
| `history` | discord_id, type (fish/location/tool/bait/simulation/command), item_id, data, created_at |

**New DB helper methods needed in `utils/db.py`:**

```python
add_favorite(discord_id, type, item_id)         # INSERT OR IGNORE
remove_favorite(discord_id, type, item_id)       # DELETE
get_favorites(discord_id, type=None)             # SELECT, optionally filtered by type
add_history(discord_id, type, item_id, data=None) # INSERT, prune to last 20 per type
get_history(discord_id, type, limit=20)          # SELECT ORDER BY created_at DESC
```

Row auto-created on first `/profile` call via `get_or_create_user(discord_id)`.

---

## Commands

### `/profile`

**Embed layout:**

```
Author: 👤 Profile
Title:  @username (display name)
Color:  0x5865f2 (blurple — user-themed, not rarity)
Thumbnail: user avatar URL

🎣 SETUP
Rod: Wooden Rod  ·  Tool: Fishing Rod  ·  Bait: None

📊 SKILLS
Fishing: 0  ·  Luck: 0  ·  Efficiency: 0
Prestige: 0  ·  Coins: 0

🔓 UNLOCKS
👑 Boss: ❌  ·  ✨ Mythical: ❌

🌤️ ENVIRONMENT
Weather: None  ·  Event: None

⭐ FAVOURITES
Fish: None  ·  Location: None  ·  Tool: None  ·  Bait: None

Footer: "Last updated: {timestamp in user's timezone}"
```

**Buttons (2 rows):**

Row 1: `✏️ Edit Setup` | `📊 Edit Skills` | `🔓 Edit Unlocks` | `🌤️ Edit Env` | `⭐ Edit Favs`
Row 2: `🔄 Reset` | `📤 Export` [disabled] | `📥 Import` [disabled]

**Modals (one per Edit button, opened via `discord.ui.Modal`):**

| Button | Modal title | Inputs |
|--------|-------------|--------|
| Edit Setup | Edit Fishing Setup | Rod (text) · Tool (text) · Bait (text) |
| Edit Skills | Edit Skills | Fishing Skill (int) · Luck Skill (int) · Efficiency Skill (int) · Prestige (int) · Coins (int) |
| Edit Unlocks | Edit Unlocks | Boss Unlock (yes/no) · Mythical Unlock (yes/no) |
| Edit Env | Edit Environment | Current Weather (text) · Current Event (text) |
| Edit Favs | Edit Favourites | Fav Fish (text) · Fav Location (text) · Fav Tool (text) · Fav Bait (text) |

**Validation:**
- Tool / Bait: validated against `dank_client.tool_by_name` / `bait_by_name`. Invalid → ephemeral error, no save.
- Skill/Prestige/Coins: must be non-negative integers. Invalid → ephemeral error.
- Boss Unlock / Mythical Unlock: accept `yes`/`no` (case-insensitive). Invalid → ephemeral error.
- Rod / Weather / Event / Fav Fish / Fav Location / Fav Tool / Fav Bait: free text, no validation (game data doesn't enumerate rods/weather/events reliably in all versions).

**Reset button:** sends a confirmation embed with ✅ Confirm and ❌ Cancel buttons. On confirm, sets all fields to their DB defaults (NULL / 0) and re-renders profile embed.

**Export / Import buttons:** disabled (greyed out) — Phase 6.

---

### `/favorites`

**Embed layout:**

One embed with four inline sections, each listing up to 10 items:

```
Title: ⭐ Your Favourites
Color: 0x5865f2

Field "🐟 Fish" (value: comma-separated names, or "None")
Field "📍 Locations" (value: ...)
Field "🔧 Tools" (value: ...)
Field "🪱 Baits" (value: ...)
```

**Select menu:** "Choose a favourite to view…" — options show all saved favourites, prefixed by type emoji (🐟 Bass, 📍 Mystic Pond, etc.). On select, posts the item's detail embed as an ephemeral response.

**Buttons (shown after a selection):**
- `🔗 Open` — posts the detail embed as ephemeral
- `🗑️ Remove` — removes from favourites table, re-renders list embed
- `🎮 Simulate` [disabled] — Phase 3

**Empty state:** friendly embed explaining how to add favourites (via ⭐ button on `/fish`, `/location`, etc.).

---

### `/history`

**Embed layout:**

```
Title: 📜 Recent Activity
Color: 0x5865f2
```

Four tabs as buttons: `🐟 Fish` | `📍 Locations` | `🎮 Simulations` | `💬 Commands`

Default tab: Fish. Each tab re-renders the embed description as a numbered list:

```
1. Goldfish — 2 min ago
2. Koi — 5 min ago
...
```

- Simulations tab shows "No simulations yet" until Phase 3.
- Max 20 rows per tab.
- Timestamps formatted relative to current time (e.g., "5 min ago", "2 hours ago").

---

### `/settings`

**Embed layout:**

```
Title: ⚙️ Settings
Color: 0x5865f2

Description:
Timezone: UTC
Theme: 🌑 Dark
Compact Mode: Off
Notification Preferences: Coming in Phase 6
Default Simulator Values: Coming in Phase 3
```

**Controls:**

| Setting | Control |
|---------|---------|
| Timezone | Button → modal (1 input: IANA timezone string, e.g. `Asia/Kolkata`) |
| Theme | Button → cycles Dark ↔ Light, re-renders embed inline |
| Compact Mode | Button → toggles, re-renders embed inline |
| Notification Prefs | Button [disabled] |
| Default Sim Values | Button [disabled] |

Timezone validation: use `zoneinfo.ZoneInfo(tz)` — catch `ZoneInfoNotFoundError`, respond with ephemeral error.

---

## Favourite Button Integration (Phase 1 Embeds)

Enable the currently-disabled ⭐ Favourite button in `FishView`, `LocationView`, `ToolView`, `BaitView`.

**Initial render:** At view creation, query `get_favorites(discord_id, type)` to check if this item is already favourited. Set initial button label accordingly:
- Not favourited → `⭐ Favourite` (style: secondary)
- Already favourited → `💛 Unfavourite` (style: primary)

**On click:**
1. Check current state (toggle):
   - If currently favourited → **remove** from `favorites`, update button to `⭐ Favourite` (secondary).
   - If not favourited → **add** to `favorites`, update button to `💛 Unfavourite` (primary).
2. Edit the original message in place (no new message).

Views created from autocomplete (no prior user context) start with ⭐ Favourite and query asynchronously on first click.

---

## History Row Writing (Phase 1 Cogs)

After a successful lookup in each cog, write a history row:

```python
await db.add_history(interaction.user.id, "fish", creature.id)
await db.add_history(interaction.user.id, "location", location.id)
await db.add_history(interaction.user.id, "tool", tool.id)
await db.add_history(interaction.user.id, "bait", bait.id)
```

Prune to last 20 per type (delete oldest rows beyond limit). Fire-and-forget — never block the response on it.

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `utils/db.py` | Modify | Add `add_favorite`, `remove_favorite`, `get_favorites`, `add_history`, `get_history`, `get_or_create_user` |
| `cogs/profile.py` | Rewrite | `/profile`, `/favorites`, `/history`, `/settings` |
| `cogs/fish.py` | Modify | Write history row, enable Favourite toggle button |
| `cogs/locations.py` | Modify | Write history row, enable Favourite toggle button |
| `cogs/tools.py` | Modify | Write history row, enable Favourite toggle button |
| `cogs/baits.py` | Modify | Write history row, enable Favourite toggle button |
| `tests/test_db.py` | Create | Tests for new DB helpers |
| `tests/test_profile_cog.py` | Create | Tests for profile/favorites/history/settings commands |

---

## Error Handling

All errors displayed as ephemeral embeds (consistent with Phase 1):
- Invalid tool/bait name in Edit Setup → "No tool named '{name}' found."
- Invalid timezone → "Unknown timezone '{tz}'. Use an IANA name like `UTC` or `Asia/Kolkata`."
- Invalid skill value (not an integer or negative) → "Skills must be non-negative integers."
- Invalid unlock value → "Boss/Mythical unlock must be `yes` or `no`."
- No favourites to view → "You haven't favourited anything yet. Use ⭐ on any fish, location, tool, or bait."

---

## Out of Scope for Phase 2

- Export / Import (Phase 6)
- Notification Preferences (Phase 6)
- Default Simulator Values (Phase 3)
- Simulate button in /favorites (Phase 3)
- Simulations tab in /history (Phase 3)
