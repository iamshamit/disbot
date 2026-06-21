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

    @app_commands.command(name="stats", description="Show bot statistics and data status")
    async def stats(self, interaction: discord.Interaction):
        embed = EmbedBuilder.info("📊 Bot Statistics")
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="​", value="​", inline=True)  # spacer

        dc = self.bot.dank_client
        if dc:
            fish_count = len(dc.fish_by_id)
            loc_count = len(dc.location_by_id)
            tool_count = len(dc.tool_by_id)
            bait_count = len(dc.bait_by_id)
            npc_count = len(dc.npc_by_id)
            status = "✅ Ready" if fish_count > 0 else "⏳ Loading…"
            embed.add_field(name="🐟 Fish", value=str(fish_count), inline=True)
            embed.add_field(name="📍 Locations", value=str(loc_count), inline=True)
            embed.add_field(name="🔧 Tools", value=str(tool_count), inline=True)
            embed.add_field(name="🪱 Baits", value=str(bait_count), inline=True)
            embed.add_field(name="👤 NPCs", value=str(npc_count), inline=True)
            embed.add_field(name="Cache", value=status, inline=True)
        else:
            embed.add_field(name="Data", value="❌ Client not initialised", inline=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(CoreCog(bot))
