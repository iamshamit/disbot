from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Any
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder, loading_embed, emoji_from_url
from utils.optimizer import best_setups, score_setup, session_windows
from utils.fish_data import creature_eligible

_PRELOAD_GUARD_MSG = "⏳ Data is still loading, please try again in a moment."

# Tools that cannot use any bait
_NO_BAIT_TOOLS = {"bare-hand", "dynamite", "magnet-fishing-rope"}
# IFM only accepts these baits
_IFM_BAITS = {"time-bait", "weighted-bait", "golden-bait", "lucky-bait",
               "eyeball-bait", "turkey-bait", "jerky-bait", "omega-bait"}

# (fish_id, utc_hour) → list of result dicts
_opt_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}


def _utc_hour() -> int:
    return datetime.now(timezone.utc).hour


def _ts_for_hour(hour: int) -> int:
    """Millisecond timestamp for today at the given UTC hour."""
    now = datetime.now(timezone.utc)
    t = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    return int(t.timestamp() * 1000)


def _valid_baits_for_tool(tool_id: str, all_baits: list) -> list:
    """Return valid baits for a given tool (empty list = no bait)."""
    if tool_id in _NO_BAIT_TOOLS:
        return []
    if tool_id == "idle-fishing-machine":
        return [b for b in all_baits if b.id in _IFM_BAITS]
    return list(all_baits)


async def _run_fish_optimizer(dc, fish, hour: int) -> list[dict[str, Any]]:
    """Try all valid (tool, bait, location) combos for a fish at `hour`.

    Returns results sorted by catch% for the target fish, descending.
    Timely Bait combos are run separately when fish isn't available at `hour`.
    """
    from cogs.simulator import call_simulator_api

    fish_locs = list(fish.extra.get("locations") or [])
    all_baits = list(dc.bait_by_id.values())
    timely_bait = dc.bait_by_id.get("time-bait")

    # Build combo list — only (tool, location) pairs where fish is eligible
    combos: list[dict] = []
    timely_combos: list[dict] = []
    fish_is_available_now = False

    for loc_id in fish_locs:
        for tool in dc.tool_by_id.values():
            eligible_now = creature_eligible(
                fish, loc_id, tool.id, hour, bosses=False, ignore_time=False
            )
            eligible_timely = creature_eligible(
                fish, loc_id, tool.id, hour, bosses=False, ignore_time=True
            )
            if eligible_now:
                fish_is_available_now = True
                for bait in _valid_baits_for_tool(tool.id, all_baits):
                    combos.append({"tool": tool, "bait": bait, "loc_id": loc_id, "timely": False})
                if not _valid_baits_for_tool(tool.id, all_baits) or tool.id in _NO_BAIT_TOOLS:
                    combos.append({"tool": tool, "bait": None, "loc_id": loc_id, "timely": False})
            elif eligible_timely and timely_bait and tool.id not in _NO_BAIT_TOOLS:
                # Only Timely Bait unlocks this fish at this hour
                timely_combos.append({"tool": tool, "bait": timely_bait, "loc_id": loc_id, "timely": True})

    ts = _ts_for_hour(hour)
    sem = asyncio.Semaphore(30)

    async def call_one(combo: dict) -> dict | None:
        bait_ids = [combo["bait"].id] if combo.get("bait") else []
        payload = {
            "locationID": combo["loc_id"],
            "toolID": combo["tool"].id,
            "baitsIDs": bait_ids,
            "time": ts,
            "events": [],
            "bosses": False,
            "skills": {},
            "bonusBossMultiplier": 1,
            "bonusMythicalMultiplier": 1,
            "forceTrash": False,
            "mythicalFishID": None,
            "discoveredCreatures": None,
            "anglerTuesday": False,
            "invasion": False,
            "locationWinner": None,
        }
        async with sem:
            try:
                data = await call_simulator_api(payload)
            except Exception:
                return None
        for entry in data.get("table", []):
            val = entry.get("value", {})
            if val.get("type") == "fish-creature" and val.get("creatureID") == fish.id:
                return {**combo, "chance": round(entry.get("chance", 0), 2)}
        return {**combo, "chance": 0.0}

    all_combos = combos + timely_combos
    if not all_combos:
        return []

    raw = await asyncio.gather(*[call_one(c) for c in all_combos])
    results = [r for r in raw if r and r["chance"] > 0]
    results.sort(key=lambda r: (-r["chance"], r["timely"]))
    return results


def _build_optimizer_embed(results: list[dict], fish, dc, hour: int) -> discord.Embed:
    fish_emoji = emoji_from_url(getattr(fish, "imageURL", None))
    fish_label = (str(fish_emoji) + "  " if fish_emoji else "") + fish.name

    embed = discord.Embed(title=f"🎯 Best Setup for {fish_label}", color=0x5865F2)
    embed.set_author(name="🧠 Optimizer")
    embed.timestamp = discord.utils.utcnow()

    if not results:
        embed.description = (
            f"❌ **{fish.name}** cannot be caught with any known setup."
        )
        return embed

    regular = [r for r in results if not r.get("timely")]
    timely = [r for r in results if r.get("timely")]

    def _result_line(r: dict, rank: int) -> str:
        loc = dc.location_by_id.get(r["loc_id"])
        loc_name = loc.name if loc else r["loc_id"]
        loc_emoji = emoji_from_url(getattr(loc, "imageURL", None)) if loc else None
        loc_label = (str(loc_emoji) + " " if loc_emoji else "📍 ") + loc_name
        tool_name = r["tool"].name
        bait_name = r["bait"].name if r.get("bait") else "No bait"
        return f"**{rank}.** `{r['chance']:.1f}%`  {tool_name}  ·  🪱 {bait_name}  ·  {loc_label}"

    if regular:
        lines = [_result_line(r, i + 1) for i, r in enumerate(regular[:5])]
        embed.add_field(
            name=f"✅ Available at {hour:02d}:00 UTC",
            value="\n".join(lines),
            inline=False,
        )
    else:
        embed.add_field(
            name=f"❌ Not available at {hour:02d}:00 UTC",
            value=f"**{fish.name}** is outside its time window right now.",
            inline=False,
        )

    if timely:
        lines = [_result_line(r, i + 1) for i, r in enumerate(timely[:3])]
        embed.add_field(
            name="⏰ With Timely Bait (any hour)",
            value="\n".join(lines),
            inline=False,
        )

    embed.set_footer(text=f"Cached for UTC hour {hour:02d}  ·  No skills/events applied")
    return embed


def _build_planner_embed(
    location, windows: list[dict], dc, user_tool_id: str | None, user_bait_id: str | None
) -> discord.Embed:
    start_h = windows[0]["hour"]
    end_h = (windows[-1]["hour"] + 1) % 24
    embed = discord.Embed(
        title=f"🗓️ Session Plan — {location.name}  ({start_h:02d}:00–{end_h:02d}:00 UTC)",
        color=0x5865F2,
    )

    whole_session = set.intersection(*(w["fish_ids"] for w in windows)) if windows else set()
    if whole_session:
        names = sorted(dc.fish_by_id[fid].name for fid in whole_session if fid in dc.fish_by_id)
        embed.add_field(
            name=f"🐟 Catchable the whole session ({len(whole_session)} fish)",
            value=" · ".join(names) or "—",
            inline=False,
        )
    else:
        embed.add_field(
            name="🐟 Catchable the whole session",
            value="No fish are available the entire session — availability varies by hour, see below.",
            inline=False,
        )

    opens_lines, closes_lines = [], []
    for w in windows[1:]:
        h = w["hour"]
        if w["opens"]:
            ns = sorted(dc.fish_by_id[fid].name for fid in w["opens"] if fid in dc.fish_by_id)
            opens_lines.append(f"**{h:02d}:00** → {', '.join(ns)}")
        if w["closes"]:
            ns = sorted(dc.fish_by_id[fid].name for fid in w["closes"] if fid in dc.fish_by_id)
            closes_lines.append(f"**{h:02d}:00** → {', '.join(ns)}")
    if opens_lines:
        embed.add_field(name="🔓 Opens during session", value="\n".join(opens_lines), inline=False)
    if closes_lines:
        embed.add_field(name="🔒 Closes during session", value="\n".join(closes_lines), inline=False)

    # Best tool across all windows (score_setup no longer counts qty)
    tool_scores = {
        tid: sum(score_setup(dc, tid, location.id, w["hour"]) for w in windows)
        for tid in dc.tool_by_id
    }
    best_tool_id = max(tool_scores, key=lambda t: tool_scores[t]) if tool_scores else user_tool_id
    best_tool = dc.tool_by_id.get(best_tool_id) if best_tool_id else None

    # Best bait: score each bait by summing rarity weights of fish it doesn't block
    # Baits don't affect availability so we pick based on utility hints from explanation
    # Recommended: Lucky Bait (rarity boost) unless user has a specific bait set
    if user_bait_id and user_bait_id in dc.bait_by_id:
        user_bait = dc.bait_by_id[user_bait_id]
        bait_label = f"{user_bait.name} (your current)"
    else:
        # Suggest Lucky Bait as a safe default for rarity improvement
        lucky = dc.bait_by_id.get("lucky-bait")
        bait_label = f"{lucky.name} — increases rarity luck" if lucky else "Lucky Bait"

    tool_emoji = emoji_from_url(getattr(best_tool, "imageURL", None)) if best_tool else None
    tool_display = (str(tool_emoji) + " " if tool_emoji else "") + (best_tool.name if best_tool else "—")

    # Timely Bait hint: count fish not available the whole session but accessible with time-bait
    timely_locked = set()
    for fid in dc.fish_by_id:
        fish = dc.fish_by_id[fid]
        locs = fish.extra.get("locations") or []
        if location.id not in locs:
            continue
        available_any = any(
            creature_eligible(fish, location.id, "fishing-rod", w["hour"], bosses=False, ignore_time=False)
            for w in windows
        )
        if not available_any:
            # Check if Timely Bait would unlock it (eligible ignore_time=True)
            if creature_eligible(fish, location.id, "fishing-rod", windows[0]["hour"], bosses=False, ignore_time=True):
                timely_locked.add(fid)

    timely_hint = ""
    if timely_locked:
        timely_hint = f"\n⏰ Timely Bait unlocks {len(timely_locked)} fish outside time windows"

    embed.add_field(
        name="🎣 Recommended setup",
        value=f"Tool: {tool_display}\nBait: **{bait_label}**{timely_hint}",
        inline=False,
    )
    return embed


class IntelligenceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="optimizer", description="Find the best setup to catch a specific fish right now")
    @app_commands.describe(target="Fish you want to catch")
    async def optimizer(self, interaction: discord.Interaction, target: str):
        dc = self.bot.dank_client
        if not dc or not dc.fish_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        fish = dc.get_fish(target)
        if fish is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "Not found",
                    f"No fish named **{target}** found. Try `/fishlist` to browse.",
                ),
                ephemeral=True,
            )
            return

        hour = _utc_hour()
        cache_key = (fish.id, hour)

        if cache_key in _opt_cache:
            embed = _build_optimizer_embed(_opt_cache[cache_key], fish, dc, hour)
            embed.set_footer(text=f"⚡ Cached result for UTC hour {hour:02d}  ·  No skills/events applied")
            await interaction.response.send_message(embed=embed)
            return

        await interaction.response.defer()
        fish_emoji = emoji_from_url(getattr(fish, "imageURL", None))
        fish_label = (str(fish_emoji) + " " if fish_emoji else "") + fish.name
        await interaction.followup.send(
            embed=loading_embed(f"Scanning all setups for {fish_label}…")
        )

        results = await _run_fish_optimizer(dc, fish, hour)
        _opt_cache[cache_key] = results
        embed = _build_optimizer_embed(results, fish, dc, hour)
        await interaction.edit_original_response(embed=embed)

    @optimizer.autocomplete("target")
    async def optimizer_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.fish_choices(current)

    @app_commands.command(name="planner", description="Plan a fishing session at a location")
    @app_commands.describe(
        location="Location name — blank for the best location right now",
        hours="Session length in hours (1–6, default 3)",
    )
    async def planner(
        self,
        interaction: discord.Interaction,
        location: str | None = None,
        hours: app_commands.Range[int, 1, 6] = 3,
    ):
        dc = self.bot.dank_client
        if not dc or not dc.fish_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        hour = _utc_hour()
        if location:
            loc_obj = dc.location_by_id.get(location) or next(
                (l for l in dc.location_by_id.values() if l.name.lower() == location.lower()),
                None,
            )
            if loc_obj is None:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("Not found", f"No location named **{location}** found."),
                    ephemeral=True,
                )
                return
        else:
            top = best_setups(dc, hour, limit=1)
            if not top:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("No data", "No fish catchable right now."), ephemeral=True
                )
                return
            loc_obj = top[0]["location"]
        windows = session_windows(dc, loc_obj.id, hour, hours)
        if not any(w["fish_ids"] for w in windows):
            embed = discord.Embed(
                title=f"🗓️ Session Plan — {loc_obj.name}",
                description=f"No fish available at **{loc_obj.name}** during this window.",
                color=0x5865F2,
            )
            await interaction.response.send_message(embed=embed)
            return
        user_tool_id = None
        user_bait_id = None
        if self.bot.db:
            try:
                row = await self.bot.db.get_or_create_user(str(interaction.user.id))
                user_tool_id = row["current_tool"]
                user_bait_id = row["current_bait"]
            except Exception:
                pass
        await interaction.response.send_message(
            embed=_build_planner_embed(loc_obj, windows, dc, user_tool_id, user_bait_id)
        )

    @planner.autocomplete("location")
    async def planner_location_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.dank_client:
            return []
        return [
            app_commands.Choice(name=loc.name, value=loc.name)
            for loc in self.bot.dank_client.location_by_id.values()
            if current.lower() in loc.name.lower()
        ][:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(IntelligenceCog(bot))
