import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder


class SimulatorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="simulate", description="Simulate fishing (skeleton)")
    async def simulate(self, interaction: discord.Interaction):
        embed = EmbedBuilder.info("Simulator", "Coming in P5.")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SimulatorCog(bot))
