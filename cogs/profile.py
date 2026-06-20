import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View your fishing profile")
    async def profile(self, interaction: discord.Interaction):
        embed = EmbedBuilder.info("Profile", "Profile system coming in P3.")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
