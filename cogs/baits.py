from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder, build_bait_embed, build_bait_compare_embed

_PRELOAD_MSG = "⏳ Data is still loading, please try again in a moment."
_NOT_FOUND = "❌ No bait named **{name}** found."


class BaitCompareModal(discord.ui.Modal, title="Compare Bait"):
    second_bait: discord.ui.TextInput = discord.ui.TextInput(
        label="Second bait name",
        placeholder="e.g. Gold Bait",
        min_length=1,
        max_length=60,
    )

    def __init__(self, first_bait, dank_client):
        super().__init__()
        self.first = first_bait
        self.dc = dank_client

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = self.second_bait.value.strip()
        second = self.dc.get_bait(name)
        if second is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=name)), ephemeral=True
            )
            return
        await interaction.response.edit_message(
            embed=build_bait_compare_embed(self.first, second), view=None
        )


class BaitView(discord.ui.View):
    def __init__(self, bait, dank_client, db=None, user_id=None, is_faved=False):
        super().__init__(timeout=300)
        self.bait = bait
        self.dc = dank_client
        self.db = db
        self.user_id = user_id
        self._is_faved = is_faved
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
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="⚔️ Compare", style=discord.ButtonStyle.primary)
    async def compare_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BaitCompareModal(self.bait, self.dc))

    @discord.ui.button(label="⭐ Favourite", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def fav_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._is_faved:
            await self.db.remove_favorite(self.user_id, "bait", self.bait.id)
            self._is_faved = False
            button.label = "⭐ Favourite"
            button.style = discord.ButtonStyle.secondary
        else:
            await self.db.add_favorite(self.user_id, "bait", self.bait.id)
            self._is_faved = True
            button.label = "💛 Unfavourite"
            button.style = discord.ButtonStyle.primary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="🎮 Simulate", style=discord.ButtonStyle.secondary, disabled=True)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class BaitsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _guard(self) -> bool:
        return bool(self.bot.dank_client and self.bot.dank_client.bait_by_id)

    @app_commands.command(name="bait", description="Look up a fishing bait")
    @app_commands.describe(name="Bait name")
    async def bait(self, interaction: discord.Interaction, name: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        b = self.bot.dank_client.get_bait(name)
        if b is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=name)), ephemeral=True
            )
            return
        user_id = str(interaction.user.id)
        is_faved = False
        if self.bot.db:
            try:
                favs = await self.bot.db.get_favorites(user_id, "bait")
                is_faved = any(f["item_id"] == b.id for f in favs)
                await self.bot.db.add_history(user_id, "bait", b.id)
            except Exception:
                pass
        view = BaitView(b, self.bot.dank_client, db=self.bot.db, user_id=user_id, is_faved=is_faved)
        embed = build_bait_embed(b)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @bait.autocomplete("name")
    async def bait_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.bait_choices(current)

    @app_commands.command(name="baitcompare", description="Compare two fishing baits")
    @app_commands.describe(bait1="First bait", bait2="Second bait")
    async def baitcompare(self, interaction: discord.Interaction, bait1: str, bait2: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        b1 = self.bot.dank_client.get_bait(bait1)
        b2 = self.bot.dank_client.get_bait(bait2)
        if b1 is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=bait1)), ephemeral=True
            )
            return
        if b2 is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=bait2)), ephemeral=True
            )
            return
        await interaction.response.send_message(embed=build_bait_compare_embed(b1, b2))

    @baitcompare.autocomplete("bait1")
    @baitcompare.autocomplete("bait2")
    async def baitcompare_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.bait_choices(current)


async def setup(bot: commands.Bot):
    await bot.add_cog(BaitsCog(bot))
