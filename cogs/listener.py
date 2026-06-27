"""Listens for Dank Memer bot messages and auto-syncs fishing data to user profiles."""
from __future__ import annotations
import json as _json
import logging
import re

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

DANK_MEMER_ID = 270904126974590976

# Fishing embed: `N / M` <progress emotes> <item emote> Item Name
_EQUIP_RE = re.compile(r'`[^`]+`\s*(?:<:[^>]+>)+\s+<:[^>]+>\s+(.+)')
# Fishing embed: location line after **Current Location:**
_LOC_RE = re.compile(r'\*\*Current Location:\*\*\n<:[^>]+>\s+(.+)')

# Skills embed: lines that start with one or more custom emotes followed by the skill name
_SKILL_LINE_RE = re.compile(r'^(?:<:[^>]+>)+\s+(.+?)\s*$', re.MULTILINE)

# Heading in embed description: ### Title or ## Title
_HEADING_RE = re.compile(r'^#{1,3}\s+(.+?)(?:\n|$)')

_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
          "VI": 6, "VII": 7, "VIII": 8, "IX": 9}


def _embed_heading(embed: discord.Embed) -> str:
    """Return the effective title — embed.title or first heading in description."""
    if embed.title:
        return embed.title.strip()
    if embed.description:
        m = _HEADING_RE.match(embed.description)
        if m:
            return m.group(1).strip()
    return ""


def _parse_fishing_embed(description: str) -> dict[str, str | None]:
    equip = _EQUIP_RE.findall(description)
    loc_m = _LOC_RE.search(description)
    return {
        "tool": equip[0].strip() if len(equip) >= 1 else None,
        "bait": equip[1].strip() if len(equip) >= 2 else None,
        "location": loc_m.group(1).strip() if loc_m else None,
    }


def _parse_skills_embed(description: str, dc) -> dict[str, int]:
    """Parse Fish Skills embed into {base_id: tier}. Tier 0 entries are omitted."""
    name_to_base: dict[str, str] = {}
    for skills in dc.skill_categories.values():
        for s in skills:
            name_to_base[s["name"].lower()] = s["base"]

    result: dict[str, int] = {}
    for m in _SKILL_LINE_RE.finditer(description):
        raw = m.group(1).strip()
        parts = raw.rsplit(" ", 1)
        if len(parts) == 2 and parts[1] in _ROMAN:
            name, tier = parts[0], _ROMAN[parts[1]]
        else:
            name, tier = raw, 0

        base = name_to_base.get(name.lower())
        if base and tier > 0:
            result[base] = tier

    return result


async def _get_user_id(message: discord.Message) -> str | None:
    # Slash command: interaction carries the user directly
    if getattr(message, "interaction", None) and message.interaction.user:
        return str(message.interaction.user.id)
    # Prefix command: DM bot replies to the user's message
    if message.reference:
        ref = message.reference.resolved
        if isinstance(ref, discord.Message) and not ref.author.bot:
            return str(ref.author.id)
        # resolved is None when message isn't cached — fetch it
        if message.reference.message_id:
            try:
                ref_msg = await message.channel.fetch_message(message.reference.message_id)
                if not ref_msg.author.bot:
                    return str(ref_msg.author.id)
            except Exception:
                pass
    return None


class ListenerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.id != DANK_MEMER_ID:
            return

        if not message.embeds:
            await message.channel.send(f"[dbg] DM msg seen, no embeds", delete_after=15)
            return

        embed = message.embeds[0]
        heading = _embed_heading(embed)
        desc_preview = (embed.description or "")[:100].replace("\n", "\\n")
        await message.channel.send(
            f"[dbg] title=`{embed.title!r}` heading=`{heading!r}`\ndesc=`{desc_preview}`",
            delete_after=15,
        )

        db = self.bot.db
        dc = self.bot.dank_client
        if not db or not dc or not dc.fish_by_id:
            await message.channel.send("[dbg] db/dc not ready", delete_after=15)
            return

        description = embed.description or ""

        if heading == "Fishing" and description:
            await self._sync_fishing(message, description, db, dc)
        elif heading == "Fish Skills" and description:
            await self._sync_skills(message, description, db, dc)
        else:
            await message.channel.send(f"[dbg] heading `{heading!r}` no match — skipping", delete_after=15)

    async def _sync_fishing(self, message, description: str, db, dc) -> None:
        user_id = await _get_user_id(message)
        if not user_id:
            return

        parsed = _parse_fishing_embed(description)
        updates: dict[str, str] = {}
        if parsed["tool"]:
            t = dc.tool_by_name.get(parsed["tool"].lower())
            if t:
                updates["current_tool"] = t.name
        if parsed["bait"]:
            b = dc.bait_by_name.get(parsed["bait"].lower())
            if b:
                updates["current_bait"] = b.name
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
            parts = [f"**Tool:** {updates['current_tool']}" if "current_tool" in updates else None,
                     f"**Bait:** {updates['current_bait']}" if "current_bait" in updates else None,
                     f"**Location:** {updates['favorite_location']}" if "favorite_location" in updates else None]
            summary = "  ·  ".join(p for p in parts if p)
            await message.channel.send(f"✅ Synced your fishing setup — {summary}", delete_after=6)
        except Exception:
            logger.exception("Failed to auto-sync fishing data for user %s", user_id)

    async def _sync_skills(self, message, description: str, db, dc) -> None:
        user_id = await _get_user_id(message)
        if not user_id:
            return
        if not dc.skill_categories:
            return

        skills = _parse_skills_embed(description, dc)
        if not skills:
            return
        try:
            await db.get_or_create_user(user_id)
            await db.update_user(user_id, skills=_json.dumps(skills))
            logger.info("Auto-synced %d skills for user %s", len(skills), user_id)
            await message.channel.send(f"✅ Synced {len(skills)} skills to your profile", delete_after=6)
        except Exception:
            logger.exception("Failed to auto-sync skills for user %s", user_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ListenerCog(bot))
