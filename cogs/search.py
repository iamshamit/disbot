from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder, emoji_from_url
from utils.views import DynamicPaginationView
from utils.formatters import is_available_now, rarity_emoji

_PRELOAD_GUARD_MSG = "⏳ Data is still loading, please try again in a moment."


def build_search_fish_embed(
    creatures: list,
    page: int,
    total_pages: int,
    dc,
    title: str = "🔍 Fish Search",
) -> discord.Embed:
    embed = discord.Embed(title=title, color=0x5865f2)
    embed.set_author(name="🔍 Search")
    if not creatures:
        embed.description = "No fish match these filters."
        embed.set_footer(text="0 results")
        return embed
    ITEMS = 10
    page_slice = creatures[page * ITEMS: page * ITEMS + ITEMS]
    lines = []
    for c in page_slice:
        rarity = c.extra.get("rarity", "Common")
        rem = rarity_emoji(rarity)
        locs = len(c.extra.get("locations") or [])
        lines.append(f"{rem} **{c.name}**  ·  {rarity}  ·  {locs} loc{'s' if locs != 1 else ''}")
    embed.description = "\n".join(lines)
    embed.set_footer(text=f"Page {page + 1} / {total_pages}  ·  {len(creatures)} results")
    return embed


class SearchFishView(DynamicPaginationView):
    ITEMS_PER_PAGE = 10

    def __init__(self, dank_client, title: str = "🔍 Fish Search"):
        super().__init__()
        self.dc = dank_client
        self.title = title
        self.rarity_filter = "All"
        self.tool_filter = "All"
        self.type_filter = "All"
        # Override tool select options with actual data
        for item in self.children:
            if isinstance(item, discord.ui.Select) and "Tool" in (item.placeholder or ""):
                item.options = [
                    discord.SelectOption(label="All tools", value="All", default=True)
                ] + [
                    discord.SelectOption(
                        label=t.name,
                        value=t.id,
                        emoji=emoji_from_url(t.imageURL),
                    )
                    for t in sorted(self.dc.tool_by_id.values(), key=lambda x: x.name)
                ]
        self._refresh()

    def _refresh(self):
        creatures = list(self.dc.fish_by_id.values())
        if self.rarity_filter == "Boss":
            creatures = [c for c in creatures if c.extra.get("boss")]
        elif self.rarity_filter == "Mythical":
            creatures = [c for c in creatures if c.extra.get("mythical")]
        elif self.rarity_filter != "All":
            creatures = [c for c in creatures if c.extra.get("rarity") == self.rarity_filter]
        if self.tool_filter != "All":
            creatures = [c for c in creatures if self.tool_filter in c.extra.get("tools", {})]
        if self.type_filter == "Has Variants":
            creatures = [c for c in creatures if c.extra.get("variants")]
        elif self.type_filter == "Available Now":
            creatures = [c for c in creatures if is_available_now(c)]
        creatures.sort(key=lambda c: c.name.lower())
        self.filtered = creatures
        self.total_pages = max(1, (len(creatures) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        self.page = min(self.page, self.total_pages - 1)
        self._refresh_page_btn()

    def build_embed(self) -> discord.Embed:
        return build_search_fish_embed(
            self.filtered, self.page, self.total_pages, self.dc, title=self.title
        )

    @discord.ui.select(
        placeholder="🔍 Filter Rarity ▾",
        row=1,
        options=[
            discord.SelectOption(label="All", value="All", default=True),
            discord.SelectOption(label="⚪ Common", value="Common"),
            discord.SelectOption(label="🟢 Uncommon", value="Uncommon"),
            discord.SelectOption(label="🔵 Rare", value="Rare"),
            discord.SelectOption(label="🟣 Very Rare", value="Very Rare"),
            discord.SelectOption(label="🔴 Absurdly Rare", value="Absurdly Rare"),
            discord.SelectOption(label="🌟 Mythical", value="Mythical"),
            discord.SelectOption(label="👑 Boss", value="Boss"),
        ],
    )
    async def rarity_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.rarity_filter = select.values[0]
        self.page = 0
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.select(
        placeholder="🔧 Filter Tool ▾",
        row=2,
        options=[discord.SelectOption(label="All tools", value="All", default=True)],
    )
    async def tool_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.tool_filter = select.values[0]
        self.page = 0
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.select(
        placeholder="🏷️ Filter Type ▾",
        row=3,
        options=[
            discord.SelectOption(label="All", value="All", default=True),
            discord.SelectOption(label="✨ Has Variants", value="Has Variants"),
            discord.SelectOption(label="✅ Available Now", value="Available Now"),
        ],
    )
    async def type_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.type_filter = select.values[0]
        self.page = 0
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=4)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        self.stop()


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

    def _guard(self) -> bool:
        return bool(self.bot.dank_client and self.bot.dank_client.fish_by_id)

    @app_commands.command(name="searchfish", description="Search fish with multiple filters")
    async def searchfish(self, interaction: discord.Interaction):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        view = SearchFishView(self.bot.dank_client)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="creatures", description="Browse all creatures")
    async def creatures(self, interaction: discord.Interaction):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        view = SearchFishView(self.bot.dank_client, title="🦎 Creatures")
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()

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
