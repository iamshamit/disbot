from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder, build_npc_embed

_PRELOAD_MSG = "⏳ Data is still loading, please try again in a moment."
_NOT_FOUND = "❌ No NPC named **{name}** found."


class NpcsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _guard(self) -> bool:
        return bool(self.bot.dank_client and self.bot.dank_client.npc_by_id)

    @app_commands.command(name="npc", description="Look up a fishing NPC")
    @app_commands.describe(name="NPC name")
    async def npc(self, interaction: discord.Interaction, name: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        n = self.bot.dank_client.get_npc(name)
        if n is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=name)), ephemeral=True
            )
            return
        await interaction.response.send_message(embed=build_npc_embed(n))

    @npc.autocomplete("name")
    async def npc_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.npc_choices(current)


async def setup(bot: commands.Bot):
    await bot.add_cog(NpcsCog(bot))
