from __future__ import annotations
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands

from fishing_engine import creature_eligible, RARITY_WEIGHTS
from utils.embeds import EmbedBuilder

_PRELOAD_MSG = "⏳ Data is still loading, please try again in a moment."

_RARITY_ORDER = [
    "Absurdly Common", "Very Common", "Common", "Regular",
    "Rare", "Very Rare", "Absurdly Rare",
]


def _utc_hour() -> int:
    return datetime.utcnow().hour


def _catchable_set(dc, hour: int, location_id: str | None = None) -> set[str]:
    """Fish IDs catchable with fishing-rod (no bosses) at hour, across all or one location."""
    loc_ids = [location_id] if location_id else list(dc.location_by_id.keys())
    found: set[str] = set()
    for fish in dc.fish_by_id.values():
        for lid in loc_ids:
            if creature_eligible(fish, lid, "fishing-rod", hour, bosses=False, ignore_time=False):
                found.add(fish.id)
                break
    return found


def _upcoming_windows(dc, hour: int, location_id: str | None = None, ahead: int = 6) -> dict[int, list[str]]:
    """Fish names newly available at each of the next `ahead` hours vs current hour."""
    current = _catchable_set(dc, hour, location_id)
    windows: dict[int, list[str]] = {}
    for delta in range(1, ahead + 1):
        fhour = (hour + delta) % 24
        future = _catchable_set(dc, fhour, location_id)
        newly_open = sorted(dc.fish_by_id[fid].name for fid in (future - current))
        if newly_open:
            windows[fhour] = newly_open
    return windows


def _build_rarity_embed(dc, hour: int) -> discord.Embed:
    by_rarity: dict[str, list[str]] = {r: [] for r in _RARITY_ORDER}
    for fish in dc.fish_by_id.values():
        r = fish.extra.get("rarity", "")
        if r in by_rarity:
            by_rarity[r].append(fish.id)
    catchable = _catchable_set(dc, hour)
    embed = discord.Embed(title="Rarity Tiers", color=0x5865F2)
    for rarity in _RARITY_ORDER:
        fish_ids = by_rarity[rarity]
        total = len(fish_ids)
        now = sum(1 for fid in fish_ids if fid in catchable)
        weight = RARITY_WEIGHTS[rarity]
        embed.add_field(
            name=rarity,
            value=f"Weight: **{weight}** · Total: **{total}** · Now: **{now}**",
            inline=False,
        )
    embed.set_footer(text=f"UTC hour: {hour:02d}:00")
    return embed


class UtilitiesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.dc = bot.dank_client

    @app_commands.command(name="rarity", description="Show rarity tiers and how many fish are catchable right now.")
    async def rarity(self, interaction: discord.Interaction):
        if not self.dc.fish_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not ready", _PRELOAD_MSG), ephemeral=True
            )
            return
        hour = _utc_hour()
        embed = _build_rarity_embed(self.dc, hour)
        view = _DeleteView()
        await interaction.response.send_message(embed=embed, view=view)


class _DeleteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilitiesCog(bot))
