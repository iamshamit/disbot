"""Listens for Dank Memer bot messages and auto-syncs fishing data to user profiles.

Dank Memer uses Discord components v2 (type 17 Container → TextDisplay children)
instead of traditional embeds. Text uses :EmoteName: shortcodes, not <:name:id>.
"""
from __future__ import annotations
import json as _json
import logging
import re

import discord
from discord.ext import commands

import utils.app_emojis as _ae

logger = logging.getLogger(__name__)

DANK_MEMER_ID = 270904126974590976

# Heading: ### Title
_HEADING_RE = re.compile(r'^#{1,3}\s+(.+?)(?:\n|$)')
# Both <:name:id> and :name: emote formats
_EMOTE_RE = re.compile(r'<:[^:]+:\d+>|:[^:\s<>]+:')

_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
          "VI": 6, "VII": 7, "VIII": 8, "IX": 9}


def _strip_emotes(s: str) -> str:
    return ' '.join(_EMOTE_RE.sub('', s).split())


def _extract_text(message: discord.Message) -> str:
    """Walk the component tree and concatenate all TextDisplay content."""
    parts: list[str] = []

    def _walk(items) -> None:
        for comp in items:
            if hasattr(comp, "content") and isinstance(comp.content, str):
                parts.append(comp.content)
            children = getattr(comp, "children", None) or []
            if children:
                _walk(children)

    _walk(message.components)
    return "\n".join(parts)


def _heading(text: str) -> str:
    m = _HEADING_RE.match(text)
    return m.group(1).strip() if m else ""


def _parse_fishing_text(text: str) -> dict[str, str | None]:
    equip: list[str] = []
    location: str | None = None
    in_equip = in_loc = False

    for line in text.split('\n'):
        s = line.strip()
        if 'Current Equipment:' in s:
            in_equip, in_loc = True, False
        elif 'Bucket Space:' in s:
            in_equip, in_loc = False, False
        elif 'Current Location:' in s:
            in_equip, in_loc = False, True
        elif 'Active Events:' in s:
            in_equip, in_loc = False, False
        elif in_equip and re.search(r'\d+\s*/\s*\d+', s):
            name = _strip_emotes(re.sub(r'`[^`]*`|\d+\s*/\s*\d+', '', s))
            if name:
                equip.append(name)
        elif in_loc and s:
            location = _strip_emotes(s)
            in_loc = False

    return {
        "tool": equip[0] if equip else None,
        "bait": equip[1] if len(equip) > 1 else None,
        "location": location,
    }


def _parse_skills_text(text: str, dc) -> dict[str, int]:
    name_to_base: dict[str, str] = {}
    for skills in dc.skill_categories.values():
        for s in skills:
            name_to_base[s["name"].lower()] = s["base"]

    result: dict[str, int] = {}
    for line in text.split('\n'):
        # lines with emotes followed by skill name
        if not _EMOTE_RE.search(line):
            continue
        clean = _strip_emotes(line)
        if not clean or not clean[0].isupper():
            continue
        parts = clean.rsplit(' ', 1)
        if len(parts) == 2 and parts[1] in _ROMAN:
            name, tier = parts[0], _ROMAN[parts[1]]
        else:
            name, tier = clean, 0
        base = name_to_base.get(name.lower())
        if base and tier > 0:
            result[base] = tier

    return result


async def _get_user_id(message: discord.Message) -> str | None:
    meta = getattr(message, "interaction_metadata", None)
    if meta:
        user = getattr(meta, "user", None)
        if user:
            return str(user.id)
        user_id = getattr(meta, "user_id", None)
        if user_id:
            return str(user_id)
    if message.reference:
        ref = message.reference.resolved
        if isinstance(ref, discord.Message) and not ref.author.bot:
            return str(ref.author.id)
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
        if not message.components:
            return

        text = _extract_text(message)
        if not text:
            return

        h = _heading(text)
        db = self.bot.db
        dc = self.bot.dank_client
        if not db or not dc or not dc.fish_by_id:
            return

        if h == "Fishing":
            await self._sync_fishing(message, text, db, dc)
        elif h == "Fish Skills":
            await self._sync_skills(message, text, db, dc)

    async def _sync_fishing(self, message, text: str, db, dc) -> None:
        user_id = await _get_user_id(message)
        if not user_id:
            return

        parsed = _parse_fishing_text(text)
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
            row = await db.get_or_create_user(user_id)
            updates = {k: v for k, v in updates.items() if row[k] != v}
            if not updates:
                return
            await db.update_user(user_id, **updates)
            logger.info("Auto-synced fishing setup for user %s: %s", user_id, updates)
            embed = discord.Embed(title="Fishing Setup Synced", color=0x57F287)
            if "current_tool" in updates:
                tool_obj = dc.tool_by_name.get(updates["current_tool"].lower())
                emoji = _ae.get(tool_obj.id) if tool_obj else None
                label = f"{emoji} " if emoji else ""
                embed.add_field(name="Tool", value=f"{label}{updates['current_tool']}", inline=True)
            if "current_bait" in updates:
                bait_obj = dc.bait_by_name.get(updates["current_bait"].lower())
                emoji = _ae.get(bait_obj.id) if bait_obj else None
                label = f"{emoji} " if emoji else ""
                embed.add_field(name="Bait", value=f"{label}{updates['current_bait']}", inline=True)
            if "favorite_location" in updates:
                loc_obj = dc.location_by_name.get(updates["favorite_location"].lower())
                emoji = _ae.get(loc_obj.id) if loc_obj else None
                label = f"{emoji} " if emoji else ""
                embed.add_field(name="Location", value=f"{label}{updates['favorite_location']}", inline=True)
            embed.set_footer(text="Auto-synced from pls f catch")
            await message.channel.send(embed=embed, delete_after=8)
        except Exception:
            logger.exception("Failed to auto-sync fishing data for user %s", user_id)

    async def _sync_skills(self, message, text: str, db, dc) -> None:
        user_id = await _get_user_id(message)
        if not user_id:
            return
        if not dc.skill_categories:
            return

        skills = _parse_skills_text(text, dc)
        if not skills:
            return
        try:
            row = await db.get_or_create_user(user_id)
            new_skills_json = _json.dumps(skills)
            if row["skills"] == new_skills_json:
                return
            await db.update_user(user_id, skills=new_skills_json)
            logger.info("Auto-synced %d skills for user %s", len(skills), user_id)

            # build skill name lookup: base -> skill dict
            base_to_skill: dict[str, dict] = {}
            for cat_skills in dc.skill_categories.values():
                for s in cat_skills:
                    base_to_skill[s["base"]] = s

            lines: list[str] = []
            for base, tier in skills.items():
                s = base_to_skill.get(base)
                if not s:
                    continue
                emoji = _ae.get(base)
                prefix = f"{emoji} " if emoji else ""
                roman = next(k for k, v in _ROMAN.items() if v == tier)
                lines.append(f"{prefix}**{s['name']}** {roman}")

            embed = discord.Embed(
                title="Fish Skills Synced",
                description="\n".join(lines) if lines else f"{len(skills)} skills updated",
                color=0x57F287,
            )
            embed.set_footer(text="Auto-synced from pls f skills")
            await message.channel.send(embed=embed, delete_after=10)
        except Exception:
            logger.exception("Failed to auto-sync skills for user %s", user_id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ListenerCog(bot))
