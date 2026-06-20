import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder


class CoreCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = EmbedBuilder.success("Pong!", f"Latency: **{latency}ms**")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="stats", description="Show bot statistics")
    async def stats(self, interaction: discord.Interaction):
        embed = EmbedBuilder.info("Bot Statistics")
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        if self.bot.dank_client:
            embed.add_field(name="Fish", value=str(len(self.bot.dank_client.fish_by_id)), inline=True)
            embed.add_field(name="Locations", value=str(len(self.bot.dank_client.location_by_id)), inline=True)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(CoreCog(bot))
