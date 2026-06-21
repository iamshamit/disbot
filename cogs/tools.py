from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder, build_tool_embed, build_toolcompare_embed

_PRELOAD_MSG = "⏳ Data is still loading, please try again in a moment."
_NOT_FOUND = "❌ No tool named **{name}** found."


class ToolCompareModal(discord.ui.Modal, title="Compare Tool"):
    second_tool: discord.ui.TextInput = discord.ui.TextInput(
        label="Second tool name",
        placeholder="e.g. Harpoon",
        min_length=1,
        max_length=60,
    )

    def __init__(self, first_tool, dank_client):
        super().__init__()
        self.first = first_tool
        self.dc = dank_client

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = self.second_tool.value.strip()
        second = self.dc.get_tool(name)
        if second is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=name)), ephemeral=True
            )
            return
        await interaction.response.edit_message(
            embed=build_toolcompare_embed([self.first, second]), view=None
        )


class ToolView(discord.ui.View):
    def __init__(self, tool, dank_client, db=None, user_id=None, is_faved=False):
        super().__init__(timeout=300)
        self.tool = tool
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
        await interaction.response.send_modal(ToolCompareModal(self.tool, self.dc))

    @discord.ui.button(label="⭐ Favourite", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def fav_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if self._is_faved:
                await self.db.remove_favorite(self.user_id, "tool", self.tool.id)
                self._is_faved = False
                button.label = "⭐ Favourite"
                button.style = discord.ButtonStyle.secondary
            else:
                await self.db.add_favorite(self.user_id, "tool", self.tool.id)
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

    @discord.ui.button(label="🎮 Simulate", style=discord.ButtonStyle.secondary, disabled=True)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class ToolsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _guard(self) -> bool:
        return bool(self.bot.dank_client and self.bot.dank_client.tool_by_id)

    @app_commands.command(name="tool", description="Look up a fishing tool")
    @app_commands.describe(name="Tool name")
    async def tool(self, interaction: discord.Interaction, name: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        t = self.bot.dank_client.get_tool(name)
        if t is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=name)), ephemeral=True
            )
            return
        user_id = str(interaction.user.id)
        is_faved = False
        if self.bot.db:
            try:
                favs = await self.bot.db.get_favorites(user_id, "tool")
                is_faved = any(f["item_id"] == t.id for f in favs)
                await self.bot.db.add_history(user_id, "tool", t.id)
            except Exception:
                pass
        view = ToolView(t, self.bot.dank_client, db=self.bot.db, user_id=user_id, is_faved=is_faved)
        embed = build_tool_embed(t)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @tool.autocomplete("name")
    async def tool_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.tool_choices(current)

    @app_commands.command(name="toolcompare", description="Compare all fishing tools side by side")
    async def toolcompare(self, interaction: discord.Interaction):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        tools = list(self.bot.dank_client.tool_by_id.values())
        await interaction.response.send_message(embed=build_toolcompare_embed(tools))


async def setup(bot: commands.Bot):
    await bot.add_cog(ToolsCog(bot))
