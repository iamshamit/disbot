from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import (
    EmbedBuilder,
    build_fish_embed,
    build_fish_compare_embed,
    build_peak_hours_embed,
    build_fishlist_embed,
)
from utils.views import DynamicPaginationView
from utils.formatters import rarity_rank

_PRELOAD_GUARD_MSG = "⏳ Data is still loading, please try again in a moment."
_NOT_FOUND_MSG = "❌ No fish named **{name}** found. Try `/fishlist` to browse."


class FishCompareModal(discord.ui.Modal, title="Compare Fish"):
    second_fish: discord.ui.TextInput = discord.ui.TextInput(
        label="Second fish name",
        placeholder="e.g. Koi",
        min_length=1,
        max_length=60,
    )

    def __init__(self, first_creature, dank_client, db=None, user_id=None):
        super().__init__()
        self.first = first_creature
        self.dc = dank_client
        self.db = db
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = self.second_fish.value.strip()
        second = self.dc.get_fish(name)
        if second is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND_MSG.format(name=name)),
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            embed=build_fish_compare_embed(self.first, second, self.dc),
            view=BackToFishView(creature=self.first, dank_client=self.dc, db=self.db, user_id=self.user_id),
        )


class BackToFishView(discord.ui.View):
    def __init__(self, creature, dank_client, db=None, user_id=None):
        super().__init__(timeout=300)
        self.creature = creature
        self.dc = dank_client
        self.db = db
        self.user_id = user_id

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]

    @discord.ui.button(label="↩ Back", style=discord.ButtonStyle.secondary)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = FishView(self.creature, self.dc, db=self.db, user_id=self.user_id)
        await interaction.response.edit_message(
            embed=build_fish_embed(self.creature, self.dc), view=view
        )


class FishView(discord.ui.View):
    def __init__(self, creature, dank_client, db=None, user_id=None, is_faved=False):
        super().__init__(timeout=300)
        self.creature = creature
        self.dc = dank_client
        self.db = db
        self.user_id = user_id
        self._is_faved = is_faved
        if not (creature.extra.get("variants") or []):
            self.variants_btn.disabled = True
        # Configure fav button
        fav_btn = next(
            item for item in self.children
            if isinstance(item, discord.ui.Button) and "Favour" in item.label
        )
        if db is None:
            fav_btn.disabled = True
        else:
            fav_btn.disabled = False
            if is_faved:
                fav_btn.label = "💛 Unfavourite"
                fav_btn.style = discord.ButtonStyle.primary
        sim_btn_item = next(
            (item for item in self.children if isinstance(item, discord.ui.Button) and "Simulate" in item.label),
            None,
        )
        if sim_btn_item:
            sim_btn_item.disabled = db is None
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="🕐 Peak Hours", style=discord.ButtonStyle.secondary, row=0)
    async def peak_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = BackToFishView(self.creature, self.dc, db=self.db, user_id=self.user_id)
        await interaction.response.edit_message(embed=build_peak_hours_embed(self.creature), view=view)

    @discord.ui.button(label="🔮 Variants", style=discord.ButtonStyle.secondary, row=0)
    async def variants_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_fish_embed(self.creature, self.dc)
        variants = self.creature.extra.get("variants") or []
        parts = []
        for v in variants:
            if isinstance(v, dict):
                name = v.get("name", "Unknown")
                chance = v.get("chance", "?")
                parts.append(f"✨ **{name}** — {chance}%")
            else:
                parts.append(f"✨ {v}")
        extra_text = "\n\n**🔮 VARIANTS DETAIL**\n" + ("\n".join(parts) or "No data.")
        max_body = 4096 - len(extra_text)
        embed.description = (embed.description or "")[:max_body] + extra_text
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📍 Locations", style=discord.ButtonStyle.secondary, row=0)
    async def locations_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_fish_embed(self.creature, self.dc)
        loc_ids = self.creature.extra.get("locations") or []
        lines = []
        for lid in loc_ids:
            loc = self.dc.location_by_id.get(lid)
            if loc:
                fail = loc.extra.get("failChance", 0) if hasattr(loc.extra, "get") else 0
                lines.append(f"📍 **{loc.name}**  ·  💀 Fail {fail}%")
        detail = "\n".join(lines) if lines else "No location data."
        detail_text = f"\n\n**📍 LOCATION DETAILS**\n{detail}"
        max_body = 4096 - len(detail_text)
        embed.description = (embed.description or "")[:max_body] + detail_text
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⚔️ Compare", style=discord.ButtonStyle.primary, row=1)
    async def compare_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            FishCompareModal(self.creature, self.dc, db=self.db, user_id=self.user_id)
        )

    @discord.ui.button(label="⭐ Favourite", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def fav_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if self._is_faved:
                await self.db.remove_favorite(self.user_id, "fish", self.creature.id)
                self._is_faved = False
                button.label = "⭐ Favourite"
                button.style = discord.ButtonStyle.secondary
            else:
                await self.db.add_favorite(self.user_id, "fish", self.creature.id)
                self._is_faved = True
                button.label = "💛 Unfavourite"
                button.style = discord.ButtonStyle.primary
            await interaction.response.edit_message(view=self)
        except Exception:
            try:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("Error", "Could not update favourite. Please try again."),
                    ephemeral=True,
                )
            except Exception:
                pass

    @discord.ui.button(label="🎮 Simulate", style=discord.ButtonStyle.secondary, row=1)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.db:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not available", "Simulator requires database connection."),
                ephemeral=True,
            )
            return
        from cogs.simulator import SimulatorView
        from utils.embeds import EmbedBuilder as _EB
        view = SimulatorView(self.db, interaction.user, self.dc)
        embed = _EB.info("🎣 Simulator", "Select your options and click **🔄 Calculate**.")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=1)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class FishListView(DynamicPaginationView):
    ITEMS_PER_PAGE = 10

    def __init__(self, dank_client):
        super().__init__()
        self.dc = dank_client
        self.sort = "alphabetical"
        self.rarity_filter = "All"
        self._refresh()

    def _refresh(self):
        creatures = list(self.dc.fish_by_id.values())
        if self.rarity_filter == "Boss":
            creatures = [c for c in creatures if c.extra.get("boss")]
        elif self.rarity_filter == "Mythical only":
            creatures = [c for c in creatures if c.extra.get("mythical")]
        elif self.rarity_filter != "All":
            creatures = [c for c in creatures if c.extra.get("rarity") == self.rarity_filter]

        if self.sort == "alphabetical":
            creatures.sort(key=lambda c: c.name.lower())
        elif self.sort == "rarity_asc":
            creatures.sort(key=lambda c: rarity_rank(c.extra.get("rarity", "Common")))
        elif self.sort == "rarity_desc":
            creatures.sort(key=lambda c: -rarity_rank(c.extra.get("rarity", "Common")))

        self.filtered = creatures
        self.total_pages = max(1, (len(creatures) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        self.page = min(self.page, self.total_pages - 1)
        self._refresh_page_btn()

    def build_embed(self) -> discord.Embed:
        return build_fishlist_embed(
            self.filtered, self.page, self.total_pages, self.sort, self.rarity_filter
        )

    @discord.ui.select(
        placeholder="📊 Sort ▾",
        row=1,
        options=[
            discord.SelectOption(label="Alphabetical", value="alphabetical", default=True),
            discord.SelectOption(label="Rarity (Common → Mythical)", value="rarity_asc"),
            discord.SelectOption(label="Rarity (Mythical → Common)", value="rarity_desc"),
        ],
    )
    async def sort_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.sort = select.values[0]
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.select(
        placeholder="🔍 Filter Rarity ▾",
        row=2,
        options=[
            discord.SelectOption(label="All", value="All", default=True),
            discord.SelectOption(label="⚪ Common", value="Common"),
            discord.SelectOption(label="🟢 Uncommon", value="Uncommon"),
            discord.SelectOption(label="🔵 Rare", value="Rare"),
            discord.SelectOption(label="🟣 Very Rare", value="Very Rare"),
            discord.SelectOption(label="🔴 Absurdly Rare", value="Absurdly Rare"),
            discord.SelectOption(label="🌟 Mythical", value="Mythical"),
            discord.SelectOption(label="👑 Boss only", value="Boss"),
            discord.SelectOption(label="✨ Mythical flag only", value="Mythical only"),
        ],
    )
    async def rarity_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.rarity_filter = select.values[0]
        self.page = 0
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class FishCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _guard(self) -> bool:
        return bool(self.bot.dank_client and self.bot.dank_client.fish_by_id)

    @app_commands.command(name="fish", description="Look up a fish by name")
    @app_commands.describe(name="Fish name")
    async def fish(self, interaction: discord.Interaction, name: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        creature = self.bot.dank_client.get_fish(name)
        if creature is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND_MSG.format(name=name)),
                ephemeral=True,
            )
            return
        user_id = str(interaction.user.id)
        is_faved = False
        if self.bot.db:
            try:
                favs = await self.bot.db.get_favorites(user_id, "fish")
                is_faved = any(f["item_id"] == creature.id for f in favs)
                await self.bot.db.add_history(user_id, "fish", creature.id)
            except Exception:
                pass
        view = FishView(creature, self.bot.dank_client, db=self.bot.db, user_id=user_id, is_faved=is_faved)
        embed = build_fish_embed(creature, self.bot.dank_client)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @fish.autocomplete("name")
    async def fish_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.fish_choices(current)

    @app_commands.command(name="fishlist", description="Browse all fish with filters")
    async def fishlist(self, interaction: discord.Interaction):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        view = FishListView(self.bot.dank_client)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="fishcompare", description="Compare two fish side by side")
    @app_commands.describe(fish1="First fish", fish2="Second fish")
    async def fishcompare(self, interaction: discord.Interaction, fish1: str, fish2: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_GUARD_MSG), ephemeral=True
            )
            return
        c1 = self.bot.dank_client.get_fish(fish1)
        c2 = self.bot.dank_client.get_fish(fish2)
        if c1 is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND_MSG.format(name=fish1)), ephemeral=True
            )
            return
        if c2 is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND_MSG.format(name=fish2)), ephemeral=True
            )
            return
        await interaction.response.send_message(embed=build_fish_compare_embed(c1, c2, self.bot.dank_client))

    @fishcompare.autocomplete("fish1")
    @fishcompare.autocomplete("fish2")
    async def fishcompare_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.fish_choices(current)


async def setup(bot: commands.Bot):
    await bot.add_cog(FishCog(bot))
