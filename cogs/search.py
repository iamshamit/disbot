from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder

_PRELOAD_GUARD_MSG = "⏳ Data is still loading, please try again in a moment."


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
        self.stop()


class SearchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SearchCog(bot))
