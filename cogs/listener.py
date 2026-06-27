"""Listens for Dank Memer bot messages and auto-syncs fishing equipment to user profiles."""
from __future__ import annotations
import logging
import re

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

DANK_MEMER_ID = 270904126974590976

# Matches equipment lines: `N / M` <progress emotes...> <item emote> Item Name
_EQUIP_RE = re.compile(r'`[^`]+`\s*(?:<:[^>]+>)+\s+<:[^>]+>\s+(.+)')
# Matches the location line that follows **Current Location:**
_LOC_RE = re.compile(r'\*\*Current Location:\*\*\n<:[^>]+>\s+(.+)')


def _parse_fishing_embed(description: str) -> dict[str, str | None]:
    equip = _EQUIP_RE.findall(description)
    loc_m = _LOC_RE.search(description)
    return {
        "tool": equip[0].strip() if len(equip) >= 1 else None,
        "bait": equip[1].strip() if len(equip) >= 2 else None,
        "location": loc_m.group(1).strip() if loc_m else None,
    }


class ListenerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.id != DANK_MEMER_ID:
            return
        if not message.embeds:
            return
        embed = message.embeds[0]
        if embed.title != "Fishing":
            return
        if not embed.description:
            return

        # Identify the user who triggered the command
        user_id: str | None = None
        if getattr(message, "interaction", None) and message.interaction.user:
            user_id = str(message.interaction.user.id)
        elif message.reference and message.reference.resolved:
            ref = message.reference.resolved
            if isinstance(ref, discord.Message) and not ref.author.bot:
                user_id = str(ref.author.id)

        if not user_id:
            return

        db = self.bot.db
        dc = self.bot.dank_client
        if not db or not dc or not dc.fish_by_id:
            return

        parsed = _parse_fishing_embed(embed.description)

        updates: dict[str, str] = {}
        if parsed["tool"]:
            tool = dc.tool_by_name.get(parsed["tool"].lower())
            if tool:
                updates["current_tool"] = tool.name
        if parsed["bait"]:
            bait = dc.bait_by_name.get(parsed["bait"].lower())
            if bait:
                updates["current_bait"] = bait.name
        if parsed["location"]:
            loc = dc.location_by_name.get(parsed["location"].lower())
            if loc:
                updates["favorite_location"] = loc.name

        if not updates:
            return

        try:
            await db.get_or_create_user(user_id)
            await db.update_user(user_id, **updates)
            logger.info("Auto-synced fishing setup for user %s: %s", user_id, updates)
        except Exception:
            logger.exception("Failed to auto-sync fishing data for user %s", user_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ListenerCog(bot))
