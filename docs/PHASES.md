# DankFishingBot — Feature Phases

Phase 1 is complete. This document maps the remaining spec to phases ordered by dependency.

---

## ✅ Phase 1 — Encyclopedia (DONE)

Read-only lookup commands using preloaded DankMemer game data.

| Command | Status |
|---------|--------|
| `/fish <name>` | ✅ Done |
| `/fishlist` | ✅ Done |
| `/fishcompare <f1> <f2>` | ✅ Done |
| `/location <name>` | ✅ Done |
| `/locations` | ✅ Done |
| `/locationcompare <l1> <l2>` | ✅ Done |
| `/tool <name>` | ✅ Done |
| `/toolcompare` | ✅ Done |
| `/bait <name>` | ✅ Done |
| `/baitcompare <b1> <b2>` | ✅ Done |
| `/npc <name>` | ✅ Done |
| `/stats` | ✅ Done |

---

## Phase 2 — User Data (Profile, Favorites, History, Settings)

**Goal:** Persistent user data layer. Enables Favorite buttons, History tracking, and stored setups for the Simulator in Phase 3.

**DB schema:** Already in `migrations/001_initial.sql` — `users`, `favorites`, `history` tables all exist.

### Commands

#### `/profile`
View and edit your fishing profile.

**Displayed fields:**
- Fishing Rod, Current Tool, Current Bait
- Fishing Skill, Luck Skill, Efficiency Skill
- Prestige, Coins
- Boss Unlock, Mythical Unlock
- Favorite Fish / Location / Tool / Bait
- Current Weather, Current Event
- Last Updated

**Buttons (open modals or sub-views):**
- Edit Rod · Edit Tool · Edit Bait · Edit Skills
- Edit Weather · Edit Event · Edit Favorites
- Reset Profile · Export Profile · Import Profile

Auto-creates user row on first use.

---

#### `/favorites`
View and manage your saved favourites in one embed.

**Sections:** Favourite Fish · Favourite Locations · Favourite Tools · Favourite Baits

**Per-item buttons:** Open (posts the detail embed ephemeral) · Remove · Simulate (Phase 3, disabled for now)

Reads from `favorites` table.

---

#### `/history`
View recently accessed items.

**Sections:**
- Last 20 Fish viewed
- Last 20 Locations viewed
- Last Simulations run (Phase 3, shows empty until then)
- Recently Used Commands

Reads from `history` table (capped at 20 per type with `LIMIT`).

---

#### `/settings`
User-level preferences.

**Options:**
- Timezone (default UTC) — affects time displays across all commands
- Theme (dark / light) — affects embed colour palette
- Compact Mode (on/off) — shorter embed descriptions
- Default Simulator Values — pre-fills `/simulate` params (Phase 3)
- Notification Preferences — toggles per event type (Phase 6)

Stored in `users` table columns.

---

### Also in Phase 2
- **Enable Favourite button** in `/fish`, `/location`, `/tool`, `/bait` embeds (was disabled in Phase 1)
- **Write history row** on every `/fish`, `/location`, `/tool`, `/bait` command invocation

---

## Phase 3 — Simulator

**Goal:** Full interactive catch simulator. Enables the Simulate buttons disabled in Phases 1 & 2.

**Dependency:** Phase 2 (reads profile for default values).

### Commands

#### `/simulate`
Interactive embed that calculates catch probabilities.

**Inputs (all have defaults from `/profile`):**
- Location · Tool · Bait · UTC Time · Weather · Event
- Fishing Skill · Luck Skill · Efficiency Skill
- Prestige · Boss Unlock · Mythical Unlock

**Outputs:**
- Fail Chance · Mine Chance · NPC Chance
- Boss Chance · Mythical Chance · High Quality Chance · Unique Chance · Chroma Chance
- Catch Distribution (progress bars per rarity)
- Expected Rarity Distribution
- Expected Catch Count
- Estimated Profit · Estimated XP

**Interactive Controls (edit message in place, no new messages):**

Dropdowns: Location · Tool · Bait · Weather · Event · Time

Buttons: Calculate · Peak Hours · Statistics · Export · Settings · Delete

**Sub-views:**

_Peak Hours_ — 24-hour grid per fish at this location/tool combo. Shows probability bars per hour.

_Statistics_ — expanded breakdown with progress bars for every metric.

---

### Also in Phase 3
- Enable **Simulate** button in `/fish`, `/location`, `/tool`, `/bait` embeds
- Store simulation runs in `history` table

---

## Phase 4 — Intelligence Layer

**Goal:** Recommendation and planning commands. Depend on the simulation engine from Phase 3.

**Dependency:** Phase 3 (runs simulations internally).

### Commands

#### `/optimizer`
Find the best fishing setup for a goal.

**Modes:** Highest Profit · Highest XP · Highest Boss Chance · Highest Mythical Chance · Highest Variant Chance · Catch Specific Fish

**Outputs:** Recommended Tool · Bait · Location · Time · Weather · Event, plus confidence score.

---

#### `/planner`
Generate a personalised fishing plan using your `/profile` values.

Recommends: Tool · Bait · Location · Time · Weather · Event

Explains reasoning and shows confidence percentage.

---

#### `/today`
Daily summary embed.

**Displays:** Current Weather · Current Event · Recommended Setup · Best Fish right now · Best Location right now · Current Peak Hours

---

#### `/time`
Current UTC clock + what's catchable right now.

**Displays:** Current UTC · Fish available now · Upcoming peak windows

---

## Phase 5 — Discovery, Search & Encyclopedia Enhancements

**Goal:** Advanced search commands, weather/event info, and backfilling the encyclopedia fields that require game-data cross-referencing (best tool, catch amounts, etc.).

**Dependency:** Phase 3 (some fields need simulation data to compute).

### New Commands

#### `/searchfish`
Multi-filter fish search. Filters: Name · Rarity · Tool · Boss · Mythical · Location · Availability · Variant

#### `/searchlocation`
Multi-filter location search. Filters: Saltwater · Freshwater · Temporary · Disabled · Fail Chance · Mine Chance · Fish Count

#### `/creatures`
Browse all creatures (alias/superset of `/fishlist` with richer filters: Boss · Mythical · Variant · Rarity).

#### `/rarity`
Rarity statistics embed. Shows each rarity, fish count, average spawn rate, available fish right now.

#### `/weather`
Current weather, upcoming weather, effects, and simulator impact.

#### `/event`
Current event, upcoming events, effects, and simulator impact.

### Encyclopedia Enhancements

**`/fish` additions:**
- Best Tool · Best Location (computed via simulator)
- Supported Tools · Catch Amount Per Tool
- Variant Chances (percentage per variant)
- Related Fish

**`/fishlist` new filters:**
- Filter By Tool · Filter By Location · Filter Boss · Filter Mythical · Filter Availability

**`/location` additions:**
- Saltwater / Freshwater type label

**`/locations` new filters:**
- Saltwater · Freshwater filter

**`/npc` enhancements:**
- Spawn Chance · Effects (if available in API)

---

## Phase 6 — Notifications & Import/Export

**Goal:** Async background features for power users.

**Dependency:** Phase 2 (notification_prefs stored in user settings).

### Notifications
DM users for:
- Peak hour windows for favourite fish
- Weather changes
- Event starts/ends
- Boss availability
- Mythical availability

Toggles stored in `users.notification_prefs` (JSON).

Implemented as a background task that checks on a schedule.

### Import / Export

**Export:** Profile · Simulator Presets · Favorites · Settings → JSON file (attached to DM)

**Import:** Upload JSON → validates schema → applies to user row

Both as buttons on `/profile` and as standalone commands.

---

## Dependency Graph

```
Phase 1  ──────────────────────────────────────────── Encyclopedia (done)
Phase 2  ─── Phase 1 (uses embed patterns)         ── User Data
Phase 3  ─── Phase 2 (reads profile defaults)      ── Simulator
Phase 4  ─── Phase 3 (runs simulations)            ── Intelligence
Phase 5  ─── Phase 3 (best-tool needs sim data)    ── Search & Enhancements
Phase 6  ─── Phase 2 (reads notification_prefs)    ── Notifications & I/E
```

---

## Out of Scope (Future Expansion)

From the spec's "Future Expansion" section — not in any current phase:

- Real-time live simulator updates
- Setup sharing / QR export
- Fishing analytics / profit history / XP history
- Guild leaderboards
- Personal statistics dashboard
- Advanced multi-preset optimizer
- Custom embed themes
- Mobile-friendly layouts
- Plugin architecture
