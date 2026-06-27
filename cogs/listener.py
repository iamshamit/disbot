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

logger = logging.getLogger(__name__)

DANK_MEMER_ID = 270904126974590976

# Equipment lines: `N / M` :progress_emotes: :item_emote: Item Name
_EQUIP_RE = re.compile(r'`[^`]+`\s+(?::[^:]+:)+\s+:[^:]+:\s+([^:\n]+)')
# Location line after **Current Location:**
_LOC_RE = re.compile(r'\*\*Current Location:\*\*\n:[^:]+:\s+(.+)')
# Skill lines: one or more :emote: followed by skill name (+ optional Roman numeral)
_SKILL_LINE_RE = re.compile(r'^(?::[^:]+:)+\s+(.+?)\s*$', re.MULTILINE)
# Heading: ### Title
_HEADING_RE = re.compile(r'^#{1,3}\s+(.+?)(?:\n|$)')

_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
          "VI": 6, "VII": 7, "VIII": 8, "IX": 9}


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
    equip = _EQUIP_RE.findall(text)
    loc_m = _LOC_RE.search(text)
    return {
        "tool": equip[0].strip() if len(equip) >= 1 else None,
        "bait": equip[1].strip() if len(equip) >= 2 else None,
        "location": loc_m.group(1).strip() if loc_m else None,
    }


def _parse_skills_text(text: str, dc) -> dict[str, int]:
    name_to_base: dict[str, str] = {}
    for skills in dc.skill_categories.values():
        for s in skills:
            name_to_base[s["name"].lower()] = s["base"]

    result: dict[str, int] = {}
    for m in _SKILL_LINE_RE.finditer(text):
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
            await message.channel.send(f"[dbg] matched Fishing", delete_after=10)
            await self._sync_fishing(message, text, db, dc)
        elif h == "Fish Skills":
            await message.channel.send(f"[dbg] matched Fish Skills", delete_after=10)
            await self._sync_skills(message, text, db, dc)
        else:
            await message.channel.send(f"[dbg] heading=`{h!r}` no match", delete_after=10)

    async def _sync_fishing(self, message, text: str, db, dc) -> None:
        user_id = await _get_user_id(message)
        await message.channel.send(f"[dbg] user_id={user_id!r}", delete_after=10)
        if not user_id:
            return

        await message.channel.send(f"[dbg] text={text[50:250]!r}", delete_after=30)
        parsed = _parse_fishing_text(text)
        await message.channel.send(f"[dbg] parsed={parsed}", delete_after=10)
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

        await message.channel.send(f"[dbg] updates={updates}", delete_after=10)
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

    async def _sync_skills(self, message, text: str, db, dc) -> None:
        user_id = await _get_user_id(message)
        await message.channel.send(f"[dbg skills] user_id={user_id!r}", delete_after=15)
        if not user_id:
            return
        if not dc.skill_categories:
            await message.channel.send("[dbg skills] no skill_categories", delete_after=15)
            return

        await message.channel.send(f"[dbg skills] text={text[50:300]!r}", delete_after=30)
        skills = _parse_skills_text(text, dc)
        await message.channel.send(f"[dbg skills] found {len(skills)} skills: {list(skills.keys())[:5]}", delete_after=15)
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
