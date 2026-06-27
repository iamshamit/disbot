from __future__ import annotations
import asyncio
import json as _json
from datetime import datetime, timezone
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder, _ROMAN, loading_embed
from utils.fish_data import creature_eligible
import utils.app_emojis as _ae

SKILL_CATEGORIES_ORDER = ["Economy", "Nature", "Science", "Social"]

# Tools that cannot use any bait at all
_NO_BAIT_TOOLS = {"bare-hand", "dynamite", "magnet-fishing-rope"}
# Idle Fishing Machine can only use this subset of baits
_IFM_BAITS = {"time-bait", "weighted-bait", "golden-bait", "lucky-bait",
               "eyeball-bait", "turkey-bait", "jerky-bait", "omega-bait"}

_SIM_URL = "https://dankmemer.lol/api/bot/fish/simulator"
_SIM_HEADERS = {
    "Origin": "https://dankmemer.lol",
    "Referer": "https://dankmemer.lol/fishing/simulator",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
}


def _picker_embed(title: str) -> discord.Embed:
    return discord.Embed(
        title=title,
        description="Make your selections below, then click **✅ Save**.",
        color=0x5865F2,
    )


async def call_simulator_api(payload: dict) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.post(_SIM_URL, json=payload, headers=_SIM_HEADERS) as resp:
            resp.raise_for_status()
            return await resp.json()


def build_sim_results_embed(data: dict, state: dict, dc) -> discord.Embed:
    fail = data.get("failChance", 0)
    npc = data.get("npcChance", 0)

    loc_id = state.get("location_id")
    loc_name = dc.location_by_id[loc_id].name if loc_id and loc_id in dc.location_by_id else "No Location"
    hour = state.get("hour", 0)

    embed = discord.Embed(title=f"🎣 {loc_name}", color=0x5865F2)
    embed.set_author(name="🎣 Simulator")
    embed.description = f"Hour: **{hour:02d}:00 UTC**"
    embed.add_field(name="❌ Fail", value=f"{fail:.1f}%", inline=True)
    embed.add_field(name="👤 NPC", value=f"{npc:.1f}%", inline=True)

    table = sorted(data.get("table", []), key=lambda x: x.get("chance", 0), reverse=True)
    lines = []
    for entry in table[:20]:
        chance = entry.get("chance", 0)
        val = entry.get("value", {})
        if val.get("type") == "fish-creature":
            cid = val.get("creatureID", "")
            fish_name = dc.fish_by_id[cid].name if cid in dc.fish_by_id else cid
            icon = _ae.get(cid)
            name = (str(icon) + " " if icon else "") + fish_name
        elif val.get("type") == "fish-bait":
            bid = val.get("baitID", "")
            bait_name = dc.bait_by_id[bid].name if bid in dc.bait_by_id else bid
            icon = _ae.get(bid)
            name = (str(icon) + " " if icon else "") + bait_name
        elif val.get("type") == "loot":
            reward = val.get("reward") or {}
            item_id = reward.get("item")
            qty = reward.get("quantity", 1)
            item_name = (dc.item_by_id or {}).get(item_id) if item_id else None
            name = f"{qty}× {item_name}" if item_name else "Misc Loot"
        else:
            name = "Misc Loot"
        lines.append(f"`{chance:5.1f}%` {name}")
    if lines:
        embed.add_field(name="📊 Catch Table", value="\n".join(lines), inline=False)

    return embed


def _utc_hour_ts(hour: int) -> int:
    now = datetime.now(timezone.utc)
    return int(now.replace(hour=hour, minute=0, second=0, microsecond=0).timestamp())


def build_fish_peak_embed(fish_id: str, results: list, dc) -> discord.Embed:
    """Render a per-fish 24-hour catch% sweep, flagging the peak hour(s)."""
    fish_name = dc.fish_by_id[fish_id].name if fish_id in dc.fish_by_id else fish_id
    _fish_icon = _ae.get(fish_id)
    _fish_label = (str(_fish_icon) + "  " if _fish_icon else "") + fish_name

    hourly = []
    for hour, data in results:
        entry = next(
            (e for e in data.get("table", [])
             if e.get("value", {}).get("type") == "fish-creature"
             and e["value"].get("creatureID") == fish_id),
            None,
        )
        hourly.append((hour, entry["chance"] if entry else 0.0))

    if not hourly or all(c == 0 for _, c in hourly):
        embed = discord.Embed(title=f"📈 {_fish_label}", color=0x5865F2)
        embed.set_author(name="🎣 Peak Hours")
        embed.description = "This fish isn't catchable with the selected setup."
        return embed

    best_chance = max(c for _, c in hourly)
    worst_chance = min(c for _, c in hourly)
    best_hour = next(h for h, c in hourly if c == best_chance)
    varies = best_chance != worst_chance

    lines = [
        f"<t:{_utc_hour_ts(h)}:t> `{c:5.1f}%`{' ⭐' if c == best_chance else ''}"
        for h, c in hourly
    ]
    embed = discord.Embed(title=f"📈 {_fish_label}", color=0x5865F2)
    embed.set_author(name="🎣 Peak Hours")
    embed.description = (
        f"Peak: **<t:{_utc_hour_ts(best_hour)}:t>** — **{best_chance:.1f}%**\n"
        f"Low: **{worst_chance:.1f}%**"
        if varies else
        f"Catch chance is constant at **{best_chance:.1f}%** (no time variation)."
    )
    half = (len(lines) + 1) // 2
    embed.add_field(name="Hours 00–11", value="\n".join(lines[:half]) or "—", inline=True)
    embed.add_field(name="Hours 12–23", value="\n".join(lines[half:]) or "—", inline=True)
    return embed


_STATS_RARITY_ORDER = [
    "Absurdly Common", "Very Common", "Common", "Regular",
    "Rare", "Very Rare", "Absurdly Rare",
]


def build_statistics_embed(sim_data: dict, state: dict, dc) -> discord.Embed:
    fail = sim_data.get("failChance", 0.0)
    npc = sim_data.get("npcChance", 0.0)
    net = max(0.0, 100.0 - fail - npc)

    loc_id = state.get("location_id")
    mine_str = "—"
    if loc_id and loc_id in dc.location_by_id:
        mine_val = dc.location_by_id[loc_id].extra.get("mineChance", None)
        if mine_val is not None:
            mine_str = f"{mine_val}%"

    rarity_totals: dict[str, float] = {}
    boss_total = 0.0
    for entry in sim_data.get("table", []):
        chance = entry.get("chance", 0.0)
        val = entry.get("value", {})
        if val.get("type") == "fish-creature":
            cid = val.get("creatureID", "")
            fish = dc.fish_by_id.get(cid)
            if fish:
                rarity = fish.extra.get("rarity", "Unknown") if hasattr(fish.extra, "get") else "Unknown"
                rarity_totals[rarity] = rarity_totals.get(rarity, 0.0) + chance
                if (fish.extra.get("boss") if hasattr(fish.extra, "get") else False):
                    boss_total += chance

    variant_lines = []
    for cid, var_list in sim_data.get("variants", {}).items():
        name = dc.fish_by_id[cid].name if cid in dc.fish_by_id else cid
        total_var = sum(v.get("chance", 0.0) for v in var_list if v.get("chance", 0.0) > 0)
        if total_var > 0:
            variant_lines.append(f"✨ **{name}** — {total_var:.1f}%")

    embed = discord.Embed(title="📊 Statistics", color=0x5865F2)
    embed.set_author(name="🎣 Simulator")
    embed.add_field(name="❌ Fail", value=f"{fail:.1f}%", inline=True)
    embed.add_field(name="👤 NPC", value=f"{npc:.1f}%", inline=True)
    embed.add_field(name="🎣 Net Catch", value=f"{net:.1f}%", inline=True)
    embed.add_field(name="⛏️ Mine Chance", value=mine_str, inline=True)
    if boss_total > 0:
        embed.add_field(name="👾 Boss", value=f"{boss_total:.1f}%", inline=True)

    rarity_lines = [
        f"**{r}**: {rarity_totals[r]:.1f}%"
        for r in _STATS_RARITY_ORDER
        if r in rarity_totals
    ]
    if rarity_lines:
        embed.add_field(name="📊 Rarity Breakdown", value="\n".join(rarity_lines), inline=False)
    if variant_lines:
        embed.add_field(name="✨ Variants", value="\n".join(variant_lines[:10]), inline=False)

    loc_name = dc.location_by_id[loc_id].name if loc_id and loc_id in dc.location_by_id else "No location"
    hour = state.get("hour", 0)
    embed.set_footer(text=f"{loc_name} · {hour:02d}:00 UTC")
    return embed


# SkillsPickerView  (defined here; imported by cogs/profile.py)

_ROMAN = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX")


def _skill_bar(current: int, max_tier: int, width: int = 10) -> str:
    filled = round(width * current / max_tier) if max_tier else 0
    filled = max(0, min(filled, width))
    return "\u2588" * filled + "\u2591" * (width - filled)


class SkillsPickerView(discord.ui.View):
    def __init__(self, db, member, dc, current_skills: dict, return_fn):
        super().__init__(timeout=300)
        self.db = db
        self.member = member
        self.dc = dc
        self._skills = dict(current_skills)   # live state, auto-saved on every change
        self._mode = "summary"                # "summary" | "skill"
        self._skill_idx = 0                   # linear index across all skills
        self._return_fn = return_fn
        self._rebuild()

    def _all_skills(self) -> list[tuple[str, dict]]:
        result = []
        for cat in SKILL_CATEGORIES_ORDER:
            for s in self.dc.skill_categories.get(cat, []):
                result.append((cat, s))
        return result

    def _get_level(self, base: str) -> int:
        return self._skills.get(base, 0)

    def _build_summary_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Fish Skills", color=0x5865F2)
        total_sp = sum(self._skills.values())
        embed.set_author(name=f"Skill Points used: {total_sp}")
        cat_emoji = {"Economy": "\U0001f4b0", "Nature": "\U0001f33f", "Social": "\U0001f465", "Science": "\U0001f52c"}
        for cat in SKILL_CATEGORIES_ORDER:
            skills = self.dc.skill_categories.get(cat, [])
            if not skills:
                continue
            lines = []
            for s in skills:
                level = self._get_level(s["base"])
                max_t = s["max_tier"]
                bar = _skill_bar(level, max_t)
                label = f"{s['name']} {_ROMAN[min(level, 9)]}" if level > 0 else s["name"]
                lines.append(f"`{bar}` {label}")
            embed.add_field(name=f"{cat_emoji.get(cat, '')} {cat}", value="\n".join(lines), inline=False)
        embed.set_footer(text="Select a category above to edit skills")
        return embed

    def _build_skill_embed(self) -> discord.Embed:
        all_skills = self._all_skills()
        cat, s = all_skills[self._skill_idx]
        level = self._get_level(s["base"])
        max_t = s["max_tier"]
        bar = _skill_bar(level, max_t, width=15)
        tier_text = (
            f"Tier {_ROMAN[min(level, 9)]}  /  {_ROMAN[max_t]}" if level > 0
            else f"Not unlocked  ·  max {_ROMAN[max_t]}"
        )
        cat_skills = [i for i, (c, _) in enumerate(all_skills) if c == cat]
        pos = cat_skills.index(self._skill_idx) + 1
        cat_colors = {"Economy": 0xF1C40F, "Nature": 0x2ECC71, "Social": 0xE74C3C, "Science": 0x3498DB}
        embed = discord.Embed(title=s["name"], color=cat_colors.get(cat, 0x5865F2))
        embed.set_author(name=f"Fish Skills  ·  {cat}  ·  {pos} of {len(cat_skills)}")
        embed.add_field(name="Current Level", value=f"`{bar}`\n{tier_text}", inline=False)
        return embed

    def _rebuild(self) -> None:
        self.clear_items()
        all_skills = self._all_skills()
        cur_cat = all_skills[self._skill_idx][0] if self._mode == "skill" and all_skills else None
        cat_emoji = {"Economy": "\U0001f4b0", "Nature": "\U0001f33f", "Social": "\U0001f465", "Science": "\U0001f52c"}

        # Row 0: summary / category selector
        mode_opts = [
            discord.SelectOption(label="\U0001f4cb Summary", value="summary", default=self._mode == "summary"),
        ]
        for cat in SKILL_CATEGORIES_ORDER:
            if cat in self.dc.skill_categories:
                mode_opts.append(discord.SelectOption(
                    label=f"{cat_emoji.get(cat, '')} {cat}",
                    value=f"cat:{cat}",
                    default=self._mode == "skill" and cur_cat == cat,
                ))
        mode_sel = discord.ui.Select(
            placeholder="Select view…", options=mode_opts, min_values=0, max_values=1, row=0
        )
        mode_sel.callback = self._on_mode_select
        self.add_item(mode_sel)

        if self._mode == "summary":
            done_btn = discord.ui.Button(label="✅ Done", style=discord.ButtonStyle.success, row=4)
            done_btn.callback = self._done
            self.add_item(done_btn)
        else:
            # Row 1: tier dropdown — auto-saves on selection
            if 0 <= self._skill_idx < len(all_skills):
                _, s = all_skills[self._skill_idx]
                level = self._get_level(s["base"])
                max_t = s["max_tier"]
                placeholder = f"Tier {_ROMAN[min(level, 9)]}" if level > 0 else "Not Unlocked"
                opts = [discord.SelectOption(label="— Not Unlocked —", value="0", default=level == 0)] + [
                    discord.SelectOption(label=f"Tier {_ROMAN[t]}", value=str(t), default=level == t)
                    for t in range(1, min(max_t, 9) + 1)
                ]
                tier_sel = discord.ui.Select(
                    placeholder=placeholder, options=opts[:25], min_values=1, max_values=1, row=1
                )
                tier_sel.callback = self._make_tier_cb(s["base"])
                self.add_item(tier_sel)

            # Row 4: prev / next / back to summary
            total = len(all_skills)
            prev_btn = discord.ui.Button(
                label="◀", style=discord.ButtonStyle.secondary,
                disabled=self._skill_idx <= 0, row=4,
            )
            prev_btn.callback = self._prev_skill
            self.add_item(prev_btn)
            next_btn = discord.ui.Button(
                label="▶", style=discord.ButtonStyle.secondary,
                disabled=self._skill_idx >= total - 1, row=4,
            )
            next_btn.callback = self._next_skill
            self.add_item(next_btn)
            summary_btn = discord.ui.Button(label="\U0001f4cb Summary", style=discord.ButtonStyle.secondary, row=4)
            summary_btn.callback = self._to_summary
            self.add_item(summary_btn)

    def _make_tier_cb(self, base: str):
        async def callback(interaction: discord.Interaction) -> None:
            tier = int(interaction.data["values"][0])
            if tier == 0:
                self._skills.pop(base, None)
            else:
                self._skills[base] = tier
            await self.db.update_user(
                str(self.member.id),
                skills=_json.dumps(self._skills) if self._skills else None,
            )
            self._rebuild()
            await interaction.response.edit_message(embed=self._build_skill_embed(), view=self)
        return callback

    async def _prev_skill(self, interaction: discord.Interaction) -> None:
        self._skill_idx = max(0, self._skill_idx - 1)
        self._rebuild()
        await interaction.response.edit_message(embed=self._build_skill_embed(), view=self)

    async def _next_skill(self, interaction: discord.Interaction) -> None:
        self._skill_idx = min(len(self._all_skills()) - 1, self._skill_idx + 1)
        self._rebuild()
        await interaction.response.edit_message(embed=self._build_skill_embed(), view=self)

    async def _on_mode_select(self, interaction: discord.Interaction) -> None:
        sel = next(c for c in self.children if isinstance(c, discord.ui.Select))
        if not sel.values:
            await interaction.response.defer()
            return
        v = sel.values[0]
        if v == "summary":
            self._mode = "summary"
            self._rebuild()
            await interaction.response.edit_message(embed=self._build_summary_embed(), view=self)
        elif v.startswith("cat:"):
            cat = v[4:]
            self._mode = "skill"
            for i, (c, _) in enumerate(self._all_skills()):
                if c == cat:
                    self._skill_idx = i
                    break
            self._rebuild()
            await interaction.response.edit_message(embed=self._build_skill_embed(), view=self)

    async def _to_summary(self, interaction: discord.Interaction) -> None:
        self._mode = "summary"
        self._rebuild()
        await interaction.response.edit_message(embed=self._build_summary_embed(), view=self)

    async def _done(self, interaction: discord.Interaction) -> None:
        await self._return_fn(interaction)

class TimeModal(discord.ui.Modal, title="Set UTC Hour"):
    hour: discord.ui.TextInput = discord.ui.TextInput(
        label="UTC Hour (0–23)", placeholder="e.g. 14", required=True, max_length=2
    )

    def __init__(self, parent: "SimulatorView"):
        super().__init__()
        self.parent = parent

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            h = int(self.hour.value.strip())
            if not (0 <= h <= 23):
                raise ValueError
            self.parent._hour = h
            await interaction.response.defer()
        except ValueError:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid hour", "Enter a whole number between 0 and 23."),
                ephemeral=True,
            )


def _build_variants_embed(sim_data: dict, dc) -> discord.Embed:
    embed = discord.Embed(title="✨ Variants", color=0x5865F2)
    embed.set_author(name="🎣 Simulator")
    for cid, var_list in sim_data.get("variants", {}).items():
        fish = dc.fish_by_id.get(cid)
        name = fish.name if fish else cid
        icon = _ae.get(cid)
        label = (str(icon) + "  " if icon else "") + name
        parts = [f"{v['type'].capitalize()}: {v['chance']:.1f}%" for v in var_list if v.get("chance", 0) > 0]
        if parts:
            embed.add_field(name=label, value="  ·  ".join(parts), inline=False)
    if not embed.fields:
        embed.description = "No variant data for this setup."
    return embed


class VariantsView(discord.ui.View):
    def __init__(self, sim_view: "SimulatorView"):
        super().__init__(timeout=120)
        self.sim_view = sim_view

    @discord.ui.button(label="← Back", style=discord.ButtonStyle.primary)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.sim_view._last_embed, view=self.sim_view)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.delete()


class ExtrasView(discord.ui.View):
    def __init__(self, parent: "SimulatorView", current_embed: discord.Embed):
        super().__init__(timeout=120)
        self.parent = parent
        self.current_embed = current_embed

        yn = [
            discord.SelectOption(label="✅ Yes", value="1"),
            discord.SelectOption(label="❌ No", value="0"),
        ]
        self._tuesday_sel = discord.ui.Select(placeholder="📅 Angler Tuesday…", options=yn, min_values=0, max_values=1, row=0)
        self._tuesday_sel.callback = self._defer
        self.add_item(self._tuesday_sel)

        self._invasion_sel = discord.ui.Select(placeholder="⚔️ Active Invasion…", options=yn, min_values=0, max_values=1, row=1)
        self._invasion_sel.callback = self._defer
        self.add_item(self._invasion_sel)

        self._winner_sel = discord.ui.Select(placeholder="🏆 Location Winner…", options=yn, min_values=0, max_values=1, row=2)
        self._winner_sel.callback = self._defer
        self.add_item(self._winner_sel)

        # Enable variants button if sim data has variant entries
        has_variants = bool(
            parent._last_sim_data and any(
                v.get("chance", 0) > 0
                for var_list in parent._last_sim_data.get("variants", {}).values()
                for v in var_list
            )
        )
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.label == "✨ Variants":
                item.disabled = not has_variants
                break

    async def _defer(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="🕐 Set Time", style=discord.ButtonStyle.secondary, row=3)
    async def set_time_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TimeModal(self.parent))

    @discord.ui.button(label="✅ Save", style=discord.ButtonStyle.success, row=3)
    async def save_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._tuesday_sel.values:
            self.parent._angler_tuesday = self._tuesday_sel.values[0] == "1"
        if self._invasion_sel.values:
            self.parent._invasion = self._invasion_sel.values[0] == "1"
        if self._winner_sel.values:
            self.parent._loc_winner = self._winner_sel.values[0] == "1"
        await interaction.response.edit_message(embed=self.current_embed, view=self.parent)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary, row=3)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.current_embed, view=self.parent)

    @discord.ui.button(label="🪣 Live Loot", style=discord.ButtonStyle.secondary, row=3)
    async def live_loot_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            user_row = await self.parent.db.get_or_create_user(str(self.parent.member.id))
            data = await call_simulator_api(self.parent._build_payload(user_row))
        except Exception as exc:
            await interaction.followup.send(
                embed=EmbedBuilder.error("API error", f"Could not fetch loot: {exc}"),
                ephemeral=True,
            )
            return
        embed = build_sim_results_embed(data, self.parent._current_state(), self.parent.dc)
        self.parent._last_embed = embed
        self.parent._last_sim_data = data
        await interaction.edit_original_response(embed=embed, view=self.parent)

    @discord.ui.button(label="✨ Variants", style=discord.ButtonStyle.secondary, row=3, disabled=True)
    async def variants_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        sim_data = self.parent._last_sim_data
        if not sim_data:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("No data", "Run Calculate first."), ephemeral=True
            )
            return
        embed = _build_variants_embed(sim_data, self.parent.dc)
        await interaction.response.edit_message(embed=embed, view=VariantsView(self.parent))


class StatisticsView(discord.ui.View):
    def __init__(self, sim_view: "SimulatorView", sim_data: dict, dc):
        super().__init__(timeout=300)
        self.sim_view = sim_view
        self.sim_data = sim_data
        self.dc = dc
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="← Back", style=discord.ButtonStyle.primary, row=0)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.sim_view._last_embed, view=self.sim_view)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=0)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.delete()


class SimulatorView(discord.ui.View):
    def __init__(self, db, member, dc, initial_state: dict | None = None):
        super().__init__(timeout=300)
        self.db = db
        self.member = member
        self.dc = dc
        self._loc_id: str | None = None
        self._tool_id: str | None = None
        self._bait_id: str | None = None
        self._bait2_id: str | None = None
        self._event_id: str | None = None
        self._hour: int = datetime.now(timezone.utc).hour
        self._angler_tuesday: bool = False
        self._invasion: bool = False
        self._loc_winner: bool = False
        self._last_embed: discord.Embed | None = None
        self._last_sim_data: dict | None = None
        self._has_dual_bait: bool = False
        if initial_state:
            self._loc_id = initial_state.get("location_id")
            self._tool_id = initial_state.get("tool_id")
            self._bait_id = initial_state.get("bait_id")
            self._bait2_id = initial_state.get("bait2_id")
            self._event_id = initial_state.get("event_id")
            self._hour = initial_state.get("hour", self._hour)
        # Clear bait if incompatible with the pre-filled tool
        allowed = self._allowed_baits()
        if allowed is not None and self._bait_id not in {b.id for b in allowed}:
            self._bait_id = None
        if allowed is not None and self._bait2_id not in {b.id for b in allowed}:
            self._bait2_id = None
        self._build_selects()

    def _allowed_baits(self) -> list | None:
        """Returns filtered bait list, or None meaning all baits are allowed."""
        if self._tool_id in _NO_BAIT_TOOLS:
            return []
        if self._tool_id == "idle-fishing-machine":
            return [b for b in sorted(self.dc.bait_by_id.values(), key=lambda x: x.name)
                    if b.id in _IFM_BAITS]
        return None

    async def _check_dual_bait(self) -> None:
        """Check if user has Theory Crafter IV for dual bait support."""
        if not self.db:
            return
        try:
            user_row = await self.db.get_or_create_user(str(self.member.id))
            skills_json = user_row.get("skills")
            if skills_json:
                skills = _json.loads(skills_json)
                tc_tier = skills.get("theory-crafter", 0)
                self._has_dual_bait = tc_tier >= 4
        except Exception:
            pass

    def _build_selects(self) -> None:
        # Removes and re-adds select items; safe to call again when tool changes. Buttons are class-level and untouched.
        for item in list(self.children):
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)

        loc_opts = [discord.SelectOption(label="— No Location —", value="__none__", default=self._loc_id is None)] + [
            discord.SelectOption(label=l.name, value=l.id, default=l.id == self._loc_id,
                                 emoji=_ae.get(l.id))
            for l in sorted(self.dc.location_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._loc_sel = discord.ui.Select(placeholder="📍 Location…", options=loc_opts, min_values=0, max_values=1, row=0)
        self._loc_sel.callback = self._on_select
        self.add_item(self._loc_sel)

        tool_opts = [discord.SelectOption(label="— No Tool —", value="__none__", default=self._tool_id is None)] + [
            discord.SelectOption(label=t.name, value=t.id, default=t.id == self._tool_id,
                                 emoji=_ae.get(t.id))
            for t in sorted(self.dc.tool_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._tool_sel = discord.ui.Select(placeholder="🔧 Tool…", options=tool_opts, min_values=0, max_values=1, row=1)
        self._tool_sel.callback = self._on_tool_select
        self.add_item(self._tool_sel)

        allowed = self._allowed_baits()
        dual = self._has_dual_bait and allowed is not None
        max_bait = 2 if dual else 1
        bait_label = "🪱 Bait…" if not dual else "🪱 Baits (2x with Theory Crafter IV)…"
        if allowed is not None and len(allowed) == 0:
            bait_opts = [discord.SelectOption(label="— Not available —", value="__none__", default=True)]
            self._bait_sel = discord.ui.Select(
                placeholder="🪱 Bait — N/A for this tool", options=bait_opts,
                min_values=0, max_values=1, row=2, disabled=True,
            )
        else:
            source = allowed if allowed is not None else sorted(self.dc.bait_by_id.values(), key=lambda x: x.name)[:24]
            current_baits = [b for b in [self._bait_id, self._bait2_id] if b]
            bait_opts = [discord.SelectOption(label="— No Bait —", value="__none__", default=not current_baits)] + [
                discord.SelectOption(label=b.name, value=b.id, default=b.id in current_baits,
                                     emoji=_ae.get(b.id))
                for b in source
            ]
            self._bait_sel = discord.ui.Select(placeholder=bait_label, options=bait_opts, min_values=0, max_values=max_bait, row=2)
        self._bait_sel.callback = self._on_bait_select
        self.add_item(self._bait_sel)

        event_opts = [discord.SelectOption(label="— No Event —", value="__none__", default=self._event_id is None)] + [
            discord.SelectOption(label=e.name, value=e.id, default=e.id == self._event_id,
                                 emoji=_ae.get(e.id))
            for e in sorted(self.dc.event_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._event_sel = discord.ui.Select(placeholder="🎉 Event…", options=event_opts, min_values=0, max_values=1, row=3)
        self._event_sel.callback = self._on_select
        self.add_item(self._event_sel)

    async def _on_tool_select(self, interaction: discord.Interaction) -> None:
        if self._tool_sel.values:
            v = self._tool_sel.values[0]
            self._tool_id = None if v == "__none__" else v
        # Clear bait if now incompatible with the new tool
        allowed = self._allowed_baits()
        if allowed is not None and self._bait_id not in {b.id for b in allowed}:
            self._bait_id = None
        self._build_selects()
        await interaction.response.edit_message(view=self)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        if self._loc_sel.values:
            v = self._loc_sel.values[0]
            self._loc_id = None if v == "__none__" else v
        if self._event_sel.values:
            v = self._event_sel.values[0]
            self._event_id = None if v == "__none__" else v
        self._build_selects()
        await interaction.response.edit_message(view=self)

    async def _on_bait_select(self, interaction: discord.Interaction) -> None:
        vals = self._bait_sel.values
        if not vals or (len(vals) == 1 and vals[0] == "__none__"):
            self._bait_id = None
            self._bait2_id = None
        elif len(vals) == 1:
            self._bait_id = vals[0]
            self._bait2_id = None
        else:
            self._bait_id = vals[0]
            self._bait2_id = vals[1]
        self._build_selects()
        await interaction.response.edit_message(view=self)

    def _build_payload(self, user_row) -> dict:
        try:
            skills = _json.loads(user_row["skills"]) if user_row["skills"] else {}
        except (ValueError, TypeError, KeyError, IndexError):
            skills = {}
        now = datetime.now(timezone.utc)
        ts = int(now.replace(hour=self._hour, minute=0, second=0, microsecond=0).timestamp() * 1000)
        baits = [b for b in [self._bait_id, self._bait2_id] if b]
        return {
            "locationID": self._loc_id,
            "toolID": self._tool_id,
            "baitsIDs": baits,
            "time": ts,
            "events": [self._event_id] if self._event_id else [],
            "bosses": bool(user_row["boss_unlock"]),
            "skills": skills,
            "bonusBossMultiplier": 1,
            "bonusMythicalMultiplier": 1,
            "forceTrash": False,
            "mythicalFishID": None,
            "discoveredCreatures": None,
            "anglerTuesday": self._angler_tuesday,
            "invasion": self._invasion,
            "locationWinner": self._loc_winner,
        }

    def _current_state(self) -> dict:
        return {
            "location_id": self._loc_id,
            "tool_id": self._tool_id,
            "bait_id": self._bait_id,
            "bait2_id": self._bait2_id,
            "event_id": self._event_id,
            "hour": self._hour,
        }

    @discord.ui.button(label="🔄 Calculate", style=discord.ButtonStyle.primary, row=4)
    async def calculate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self._check_dual_bait()
        self._build_selects()
        await interaction.edit_original_response(embed=loading_embed("Simulating catch rates..."))
        user_row = await self.db.get_or_create_user(str(self.member.id))
        try:
            data = await call_simulator_api(self._build_payload(user_row))
        except Exception as exc:
            await interaction.followup.send(
                embed=EmbedBuilder.error("Simulator error", f"Could not calculate: {exc}"),
                ephemeral=True,
            )
            return
        embed = build_sim_results_embed(data, self._current_state(), self.dc)
        self._last_embed = embed
        self._last_sim_data = data
        self.statistics_btn.disabled = False
        await interaction.edit_original_response(embed=embed, view=self)
        await self.db.add_history(
            str(self.member.id), "simulation",
            self._loc_id or "unknown",
            data=_json.dumps(data),
        )
        try:
            await self.db.update_user(
                str(self.member.id),
                current_tool=self.dc.tool_by_id[self._tool_id].name if self._tool_id and self._tool_id in self.dc.tool_by_id else None,
                current_bait=self.dc.bait_by_id[self._bait_id].name if self._bait_id and self._bait_id in self.dc.bait_by_id else None,
                favorite_location=self.dc.location_by_id[self._loc_id].name if self._loc_id and self._loc_id in self.dc.location_by_id else None,
                current_event=self.dc.event_by_id[self._event_id].name if self._event_id and self._event_id in self.dc.event_by_id else None,
            )
        except Exception:
            pass

    @discord.ui.button(label="👥 Skills", style=discord.ButtonStyle.secondary, row=4)
    async def skills_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_or_create_user(str(self.member.id))
        try:
            current_skills = _json.loads(user_row["skills"]) if user_row["skills"] else {}
        except (ValueError, TypeError, KeyError, IndexError):
            current_skills = {}
        sim_embed = self._last_embed or EmbedBuilder.info("Simulator", "Click 🔄 Calculate to see results.")
        sim_view = self

        async def return_fn(inter: discord.Interaction) -> None:
            await inter.response.edit_message(embed=sim_embed, view=sim_view)

        skills_view = SkillsPickerView(self.db, self.member, self.dc, current_skills, return_fn)
        await interaction.response.edit_message(
            embed=skills_view._build_summary_embed(),
            view=skills_view,
        )

    @discord.ui.button(label="⚙️ Extras", style=discord.ButtonStyle.secondary, row=4)
    async def extras_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_embed = self._last_embed or EmbedBuilder.info("Simulator", "Click 🔄 Calculate to see results.")
        await interaction.response.edit_message(
            embed=_picker_embed("⚙️ Extras"),
            view=ExtrasView(self, current_embed),
        )

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=4)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.delete()

    @discord.ui.button(label="📊 Statistics", style=discord.ButtonStyle.secondary, disabled=True, row=4)
    async def statistics_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_statistics_embed(self._last_sim_data, self._current_state(), self.dc)
        stats_view = StatisticsView(self, self._last_sim_data, self.dc)
        await interaction.response.edit_message(embed=embed, view=stats_view)
        stats_view.message = await interaction.original_response()


class PeakHoursView(discord.ui.View):
    def __init__(self, db, member, dc, initial_loc_id=None, initial_tool_id=None):
        super().__init__(timeout=300)
        self.db = db
        self.member = member
        self.dc = dc
        self._loc_id = initial_loc_id
        self._tool_id = initial_tool_id
        self._fish_id: str | None = None
        self._build_selects()

    def _eligible_fish(self) -> list:
        if not self._loc_id or not self._tool_id:
            return []
        return sorted(
            [c for c in self.dc.fish_by_id.values()
             if creature_eligible(c, self._loc_id, self._tool_id, 0,
                                  bosses=True, ignore_time=True)],
            key=lambda c: c.name,
        )

    def _build_payload_for_hour(self, user_row, hour: int) -> dict:
        now = datetime.now(timezone.utc)
        ts = int(now.replace(hour=hour, minute=0, second=0, microsecond=0).timestamp() * 1000)
        return {
            "locationID": self._loc_id,
            "toolID": self._tool_id,
            "baitsIDs": [],
            "time": ts,
            "events": [],
            "bosses": bool(user_row["boss_unlock"]),
            "skills": {},
            "bonusBossMultiplier": 1,
            "bonusMythicalMultiplier": 1,
            "forceTrash": False,
            "mythicalFishID": None,
            "discoveredCreatures": None,
            "anglerTuesday": False,
            "invasion": None,
            "locationWinner": False,
        }

    def _build_selects(self) -> None:
        for item in list(self.children):
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)

        loc_opts = [discord.SelectOption(label="— No Location —", value="__none__", default=self._loc_id is None)] + [
            discord.SelectOption(label=l.name, value=l.id, default=l.id == self._loc_id,
                                 emoji=_ae.get(l.id))
            for l in sorted(self.dc.location_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._loc_sel = discord.ui.Select(placeholder="📍 Location…", options=loc_opts, min_values=0, max_values=1, row=0)
        self._loc_sel.callback = self._on_loc_tool_select
        self.add_item(self._loc_sel)

        tool_opts = [discord.SelectOption(label="— No Tool —", value="__none__", default=self._tool_id is None)] + [
            discord.SelectOption(label=t.name, value=t.id, default=t.id == self._tool_id,
                                 emoji=_ae.get(t.id))
            for t in sorted(self.dc.tool_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._tool_sel = discord.ui.Select(placeholder="🔧 Tool…", options=tool_opts, min_values=0, max_values=1, row=1)
        self._tool_sel.callback = self._on_loc_tool_select
        self.add_item(self._tool_sel)

        fish = self._eligible_fish()
        if fish:
            fish_opts = [discord.SelectOption(label="— Select a fish —", value="__none__", default=self._fish_id is None)] + [
                discord.SelectOption(label=f.name, value=f.id, default=f.id == self._fish_id,
                                     emoji=_ae.get(f.id))
                for f in fish[:24]
            ]
            self._fish_sel = discord.ui.Select(placeholder="🐟 Fish…", options=fish_opts, min_values=0, max_values=1, row=2)
        else:
            self._fish_sel = discord.ui.Select(
                placeholder="🐟 Pick location + tool first",
                options=[discord.SelectOption(label="—", value="__none__")],
                min_values=0, max_values=1, row=2, disabled=True,
            )
        self._fish_sel.callback = self._on_fish_select
        self.add_item(self._fish_sel)

    async def _on_loc_tool_select(self, interaction: discord.Interaction) -> None:
        if self._loc_sel.values:
            v = self._loc_sel.values[0]
            self._loc_id = None if v == "__none__" else v
        if self._tool_sel.values:
            v = self._tool_sel.values[0]
            self._tool_id = None if v == "__none__" else v
        if self._fish_id not in {f.id for f in self._eligible_fish()}:
            self._fish_id = None
        self._build_selects()
        await interaction.response.edit_message(view=self)

    async def _on_fish_select(self, interaction: discord.Interaction) -> None:
        if self._fish_sel.values:
            v = self._fish_sel.values[0]
            self._fish_id = None if v == "__none__" else v
        self._build_selects()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="📈 Show Peak Hours", style=discord.ButtonStyle.primary, row=3)
    async def show_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._loc_id or not self._tool_id or not self._fish_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Incomplete", "Select a location, tool, and fish first."),
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        await interaction.edit_original_response(embed=loading_embed("Fetching peak hours..."))
        try:
            user_row = await self.db.get_or_create_user(str(self.member.id))
            results = []
            batch_size = 5
            hours = list(range(24))
            for i in range(0, 24, batch_size):
                batch = hours[i:i + batch_size]
                tasks = [call_simulator_api(self._build_payload_for_hour(user_row, h)) for h in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                for hour, result in zip(batch, batch_results):
                    if isinstance(result, Exception):
                        results.append((hour, {"failChance": 0, "npcChance": 0, "table": [], "variants": {}}))
                    else:
                        results.append((hour, result))
                if i + batch_size < 24:
                    progress_h = min(i + batch_size, 24)
                    await interaction.edit_original_response(
                        embed=loading_embed(f"Fetching peak hours... {progress_h}/24")
                    )
                    await asyncio.sleep(2)
        except Exception as exc:
            await interaction.followup.send(
                embed=EmbedBuilder.error("Error", f"Could not calculate: {exc}"),
                ephemeral=True,
            )
            return
        embed = build_fish_peak_embed(self._fish_id, results, self.dc)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=3)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.delete()


class SimulatorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="simulate", description="Simulate a fishing attempt with your current setup")
    async def simulate(self, interaction: discord.Interaction):
        dc = self.bot.dank_client
        db = self.bot.db
        if not dc or not dc.fish_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not ready", "Game data still loading."), ephemeral=True
            )
            return
        if not db:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not available", "Database unavailable."), ephemeral=True
            )
            return

        user_row = await db.get_or_create_user(str(interaction.user.id))

        loc_id = None
        if user_row["favorite_location"]:
            loc = dc.location_by_name.get(user_row["favorite_location"].lower())
            if loc:
                loc_id = loc.id

        tool_id = None
        if user_row["current_tool"]:
            tool = dc.tool_by_name.get(user_row["current_tool"].lower())
            if tool:
                tool_id = tool.id

        bait_id = None
        if user_row["current_bait"]:
            bait = dc.bait_by_name.get(user_row["current_bait"].lower())
            if bait:
                bait_id = bait.id

        event_id = None
        if user_row["current_event"]:
            ev = dc.event_by_name.get(user_row["current_event"].lower())
            if ev:
                event_id = ev.id

        initial_state = {
            "location_id": loc_id,
            "tool_id": tool_id,
            "bait_id": bait_id,
            "event_id": event_id,
            "hour": datetime.now(timezone.utc).hour,
        }
        view = SimulatorView(db, interaction.user, dc, initial_state=initial_state)
        embed = EmbedBuilder.info("🎣 Simulator", "Select your options and click **🔄 Calculate**.")
        await interaction.response.send_message(embed=embed, view=view)


    @app_commands.command(name="peakhours", description="Find the best fishing hours for a specific fish")
    async def peakhours(self, interaction: discord.Interaction):
        dc = self.bot.dank_client
        db = self.bot.db
        if not dc or not dc.fish_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not ready", "Game data still loading."), ephemeral=True
            )
            return
        if not db:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not available", "Database unavailable."), ephemeral=True
            )
            return

        user_row = await db.get_or_create_user(str(interaction.user.id))

        loc_id = None
        if user_row["favorite_location"]:
            loc = dc.location_by_name.get(user_row["favorite_location"].lower())
            if loc:
                loc_id = loc.id

        tool_id = None
        if user_row["current_tool"]:
            tool = dc.tool_by_name.get(user_row["current_tool"].lower())
            if tool:
                tool_id = tool.id

        view = PeakHoursView(db, interaction.user, dc, initial_loc_id=loc_id, initial_tool_id=tool_id)
        embed = EmbedBuilder.info("🎣 Peak Hours", "Select a location, tool, and fish, then click **📈 Show Peak Hours**.")
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(SimulatorCog(bot))
