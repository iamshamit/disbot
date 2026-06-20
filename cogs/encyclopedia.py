import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder


class EncyclopediaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="fish", description="Look up a fish (skeleton)")
    async def fish(self, interaction: discord.Interaction):
        embed = EmbedBuilder.info("Fish Encyclopedia", "Coming in P4.")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(EncyclopediaCog(bot))
