from __future__ import annotations
from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder
from utils.optimizer import best_setups, score_setup, session_windows

_PRELOAD_GUARD_MSG = "⏳ Data is still loading, please try again in a moment."


def _utc_hour() -> int:
    return datetime.now(timezone.utc).hour


def _build_optimizer_embed(
    setups: list[dict], dc, user_bait_id: str | None, target_fish=None
) -> discord.Embed:
    title = f"🎯 Best Setup for {target_fish.name}" if target_fish else "🏆 Best Setup Right Now"
    embed = discord.Embed(title=title, color=0x5865F2)
    if not setups:
        embed.description = "No fish catchable right now."
        return embed
    lines = [
        f"**{i}.** {s['tool'].name}  ·  📍 {s['location'].name}  — score {s['score']:.1f}"
        for i, s in enumerate(setups, 1)
    ]
    embed.description = "\n".join(lines)
    if user_bait_id:
        bait = dc.bait_by_id.get(user_bait_id)
        bait_label = bait.name if bait else user_bait_id
        embed.set_footer(text=f"🪱 Bait: {bait_label} (your current) · bait doesn't change which fish appear")
    else:
        embed.set_footer(text="🪱 Bait: any — bait doesn't change which fish appear")
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

    tool_scores = {
        tid: sum(score_setup(dc, tid, location.id, w["hour"]) for w in windows)
        for tid in dc.tool_by_id
    }
    best_tool_id = max(tool_scores, key=lambda t: tool_scores[t]) if tool_scores else user_tool_id
    best_tool = dc.tool_by_id.get(best_tool_id) if best_tool_id else None
    if user_bait_id:
        bait = dc.bait_by_id.get(user_bait_id)
        bait_label = f"{bait.name if bait else user_bait_id} (your current)"
    else:
        bait_label = "any — bait doesn't change which fish appear"
    embed.add_field(
        name="🎣 Recommended setup",
        value=f"Tool: **{best_tool.name if best_tool else '—'}**  (best across all windows)\nBait: {bait_label}",
        inline=False,
    )
    return embed


class IntelligenceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="optimizer", description="Find the best tool and location combo right now")
    @app_commands.describe(target="Optional: fish you want to catch — blank for best overall setup")
    async def optimizer(self, interaction: discord.Interaction, target: str | None = None):
        dc = self.bot.dank_client
        if not dc or not dc.fish_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        target_fish = None
        if target:
            target_fish = dc.get_fish(target)
            if target_fish is None:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error(
                        "Not found",
                        f"No fish named **{target}** found. Try `/fishlist` to browse.",
                    ),
                    ephemeral=True,
                )
                return
        hour = _utc_hour()
        setups = best_setups(dc, hour, target_fish_id=(target_fish.id if target_fish else None))
        if target_fish and not setups:
            next_hour = None
            for delta in range(1, 24):
                if best_setups(dc, (hour + delta) % 24, target_fish_id=target_fish.id):
                    next_hour = (hour + delta) % 24
                    break
            embed = discord.Embed(title=f"🎯 Best Setup for {target_fish.name}", color=0x5865F2)
            if next_hour is not None:
                embed.description = (
                    f"❌ **{target_fish.name}** is not catchable at this UTC hour.\n"
                    f"Next window: **{next_hour:02d}:00 UTC**"
                )
            else:
                embed.description = f"❌ **{target_fish.name}** cannot be caught with any current tool or location."
            await interaction.response.send_message(embed=embed)
            return
        user_bait_id = None
        if self.bot.db:
            try:
                row = await self.bot.db.get_or_create_user(str(interaction.user.id))
                user_bait_id = row["current_bait"]
            except Exception:
                pass
        await interaction.response.send_message(
            embed=_build_optimizer_embed(setups, dc, user_bait_id, target_fish)
        )

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
