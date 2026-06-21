from __future__ import annotations
import json as _json
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import EmbedBuilder

SKILL_CATEGORIES_ORDER = ["Economy", "Nature", "Science", "Social"]
_ROMAN = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX")


def _picker_embed(title: str) -> discord.Embed:
    return discord.Embed(
        title=title,
        description="Make your selections below, then click **✅ Save**.",
        color=0x5865F2,
    )


class SkillsPickerView(discord.ui.View):
    """
    4-category paginated skills picker. Shared between profile and simulator.
    return_fn: async callable(interaction) → None — called on both Save and Cancel.
    Save first writes pending skills to DB.
    """

    def __init__(self, db, member, dc, current_skills: dict, return_fn):
        super().__init__(timeout=300)
        self.db = db
        self.member = member
        self.dc = dc
        self._current_skills = dict(current_skills)
        self._pending: dict[str, int] = {}
        self._category = next(
            (c for c in SKILL_CATEGORIES_ORDER if c in dc.skill_categories),
            SKILL_CATEGORIES_ORDER[0],
        )
        self._page = 0
        self._return_fn = return_fn
        self._rebuild()

    def _skills_for_cat(self) -> list[dict]:
        return self.dc.skill_categories.get(self._category, [])

    def _page_count(self) -> int:
        return max(1, (len(self._skills_for_cat()) + 2) // 3)

    def _rebuild(self) -> None:
        self.clear_items()

        # Row 0: category tab buttons
        for cat in SKILL_CATEGORIES_ORDER:
            if cat not in self.dc.skill_categories:
                continue
            btn = discord.ui.Button(
                label=cat,
                style=discord.ButtonStyle.primary if cat == self._category else discord.ButtonStyle.secondary,
                row=0,
            )
            btn.callback = self._make_cat_cb(cat)
            self.add_item(btn)

        # Rows 1-3: up to 3 skill selects for current page
        skills = self._skills_for_cat()
        page_skills = skills[self._page * 3 : self._page * 3 + 3]
        for i, skill in enumerate(page_skills):
            base = skill["base"]
            max_tier = skill["max_tier"]
            effective = self._pending.get(base, self._current_skills.get(base, 0))
            placeholder = (
                f"{skill['name']} — {_ROMAN[min(effective, 9)]}"
                if effective > 0
                else f"{skill['name']} — Not Unlocked"
            )
            opts = [discord.SelectOption(label="— Not Unlocked —", value="0")] + [
                discord.SelectOption(label=f"Tier {_ROMAN[t]}", value=str(t))
                for t in range(1, min(max_tier, 9) + 1)
            ]
            sel = discord.ui.Select(
                placeholder=placeholder, options=opts[:25], min_values=0, max_values=1, row=i + 1
            )
            sel.callback = self._make_skill_cb(base, sel)
            self.add_item(sel)

        # Row 4: nav + save/cancel
        page_count = self._page_count()
        prev_btn = discord.ui.Button(
            label="◀", style=discord.ButtonStyle.secondary,
            disabled=self._page == 0, row=4,
        )
        prev_btn.callback = self._prev_page
        self.add_item(prev_btn)

        next_btn = discord.ui.Button(
            label="▶", style=discord.ButtonStyle.secondary,
            disabled=self._page >= page_count - 1, row=4,
        )
        next_btn.callback = self._next_page
        self.add_item(next_btn)

        save_btn = discord.ui.Button(label="✅ Save", style=discord.ButtonStyle.success, row=4)
        save_btn.callback = self._save
        self.add_item(save_btn)

        cancel_btn = discord.ui.Button(label="❌ Cancel", style=discord.ButtonStyle.secondary, row=4)
        cancel_btn.callback = self._cancel
        self.add_item(cancel_btn)

    def _make_cat_cb(self, cat: str):
        async def callback(interaction: discord.Interaction) -> None:
            self._category = cat
            self._page = 0
            self._rebuild()
            await interaction.response.edit_message(view=self)
        return callback

    def _make_skill_cb(self, base: str, sel: discord.ui.Select):
        async def callback(interaction: discord.Interaction) -> None:
            if sel.values:
                self._pending[base] = int(sel.values[0])
            await interaction.response.defer()
        return callback

    async def _prev_page(self, interaction: discord.Interaction) -> None:
        self._page = max(0, self._page - 1)
        self._rebuild()
        await interaction.response.edit_message(view=self)

    async def _next_page(self, interaction: discord.Interaction) -> None:
        self._page = min(self._page_count() - 1, self._page + 1)
        self._rebuild()
        await interaction.response.edit_message(view=self)

    async def _save(self, interaction: discord.Interaction) -> None:
        merged = dict(self._current_skills)
        for base, tier in self._pending.items():
            if tier == 0:
                merged.pop(base, None)
            else:
                merged[base] = tier
        skills_value = _json.dumps(merged) if merged else None
        await self.db.update_user(str(self.member.id), skills=skills_value)
        await self._return_fn(interaction)

    async def _cancel(self, interaction: discord.Interaction) -> None:
        await self._return_fn(interaction)


class SimulatorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="simulate", description="Simulate fishing (coming in Phase 3 Task 3)")
    async def simulate(self, interaction: discord.Interaction):
        embed = EmbedBuilder.info("Simulator", "Full simulator coming soon.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SimulatorCog(bot))
