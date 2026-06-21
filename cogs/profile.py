from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from utils.embeds import EmbedBuilder, build_profile_embed


class EditSetupModal(discord.ui.Modal, title="Edit Fishing Setup"):
    rod: discord.ui.TextInput = discord.ui.TextInput(
        label="Fishing Rod", placeholder="e.g. Wooden Rod", required=False, max_length=100
    )
    tool: discord.ui.TextInput = discord.ui.TextInput(
        label="Current Tool", placeholder="e.g. Fishing Rod", required=False, max_length=100
    )
    bait: discord.ui.TextInput = discord.ui.TextInput(
        label="Current Bait", placeholder="e.g. Glitter Bait", required=False, max_length=100
    )

    def __init__(self, db, member, message, dank_client):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message
        self.dc = dank_client

    async def on_submit(self, interaction: discord.Interaction) -> None:
        tool_val = self.tool.value.strip() or None
        bait_val = self.bait.value.strip() or None
        if tool_val and not self.dc.get_tool(tool_val):
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid tool", f"No tool named **{tool_val}** found."),
                ephemeral=True,
            )
            return
        if bait_val and not self.dc.get_bait(bait_val):
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid bait", f"No bait named **{bait_val}** found."),
                ephemeral=True,
            )
            return
        updates: dict = {}
        if self.rod.value.strip():
            updates["fishing_rod"] = self.rod.value.strip()
        if tool_val is not None:
            updates["current_tool"] = tool_val
        if bait_val is not None:
            updates["current_bait"] = bait_val
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await self.message.edit(
            embed=build_profile_embed(user_row, self.member),
            view=ProfileView(self.db, self.member, self.dc),
        )
        await interaction.response.defer()


class EditSkillsModal(discord.ui.Modal, title="Edit Skills"):
    fishing_skill: discord.ui.TextInput = discord.ui.TextInput(
        label="Fishing Skill", placeholder="0+", required=False, max_length=6
    )
    luck_skill: discord.ui.TextInput = discord.ui.TextInput(
        label="Luck Skill", placeholder="0+", required=False, max_length=6
    )
    efficiency_skill: discord.ui.TextInput = discord.ui.TextInput(
        label="Efficiency Skill", placeholder="0+", required=False, max_length=6
    )
    prestige: discord.ui.TextInput = discord.ui.TextInput(
        label="Prestige", placeholder="0+", required=False, max_length=6
    )
    coins: discord.ui.TextInput = discord.ui.TextInput(
        label="Coins", placeholder="0+", required=False, max_length=15
    )

    def __init__(self, db, member, message, dank_client=None):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message
        self.dc = dank_client

    async def on_submit(self, interaction: discord.Interaction) -> None:
        fields = {
            "fishing_skill": self.fishing_skill.value,
            "luck_skill": self.luck_skill.value,
            "efficiency_skill": self.efficiency_skill.value,
            "prestige": self.prestige.value,
            "coins": self.coins.value,
        }
        updates: dict = {}
        for key, raw in fields.items():
            if not raw.strip():
                continue
            try:
                val = int(raw.strip())
                if val < 0:
                    raise ValueError
                updates[key] = val
            except ValueError:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error(
                        "Invalid value",
                        f"**{key.replace('_', ' ').title()}** must be a non-negative integer.",
                    ),
                    ephemeral=True,
                )
                return
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await self.message.edit(
            embed=build_profile_embed(user_row, self.member),
            view=ProfileView(self.db, self.member, self.dc),
        )
        await interaction.response.defer()


class EditUnlocksModal(discord.ui.Modal, title="Edit Unlocks"):
    boss_unlock: discord.ui.TextInput = discord.ui.TextInput(
        label="Boss Unlock (yes/no)", placeholder="yes or no", required=False, max_length=3
    )
    mythical_unlock: discord.ui.TextInput = discord.ui.TextInput(
        label="Mythical Unlock (yes/no)", placeholder="yes or no", required=False, max_length=3
    )

    def __init__(self, db, member, message, dank_client=None):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message
        self.dc = dank_client

    async def on_submit(self, interaction: discord.Interaction) -> None:
        updates: dict = {}
        for key, raw in [("boss_unlock", self.boss_unlock.value), ("mythical_unlock", self.mythical_unlock.value)]:
            if not raw.strip():
                continue
            lower = raw.strip().lower()
            if lower not in ("yes", "no"):
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("Invalid value", "Boss/Mythical Unlock must be **yes** or **no**."),
                    ephemeral=True,
                )
                return
            updates[key] = 1 if lower == "yes" else 0
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await self.message.edit(
            embed=build_profile_embed(user_row, self.member),
            view=ProfileView(self.db, self.member, self.dc),
        )
        await interaction.response.defer()


class EditEnvModal(discord.ui.Modal, title="Edit Environment"):
    weather: discord.ui.TextInput = discord.ui.TextInput(
        label="Current Weather", placeholder="e.g. Rainy", required=False, max_length=100
    )
    event: discord.ui.TextInput = discord.ui.TextInput(
        label="Current Event", placeholder="e.g. Fishing Festival", required=False, max_length=100
    )

    def __init__(self, db, member, message, dank_client=None):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message
        self.dc = dank_client

    async def on_submit(self, interaction: discord.Interaction) -> None:
        updates: dict = {}
        if self.weather.value.strip():
            updates["current_weather"] = self.weather.value.strip()
        if self.event.value.strip():
            updates["current_event"] = self.event.value.strip()
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await self.message.edit(
            embed=build_profile_embed(user_row, self.member),
            view=ProfileView(self.db, self.member, self.dc),
        )
        await interaction.response.defer()


class EditFavsModal(discord.ui.Modal, title="Edit Favourites"):
    fav_fish: discord.ui.TextInput = discord.ui.TextInput(
        label="Favourite Fish", placeholder="e.g. Goldfish", required=False, max_length=100
    )
    fav_location: discord.ui.TextInput = discord.ui.TextInput(
        label="Favourite Location", placeholder="e.g. Sunken Ship", required=False, max_length=100
    )
    fav_tool: discord.ui.TextInput = discord.ui.TextInput(
        label="Favourite Tool", placeholder="e.g. Fishing Rod", required=False, max_length=100
    )
    fav_bait: discord.ui.TextInput = discord.ui.TextInput(
        label="Favourite Bait", placeholder="e.g. Glitter Bait", required=False, max_length=100
    )

    def __init__(self, db, member, message, dank_client=None):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message
        self.dc = dank_client

    async def on_submit(self, interaction: discord.Interaction) -> None:
        updates: dict = {}
        if self.fav_fish.value.strip():
            updates["favorite_fish"] = self.fav_fish.value.strip()
        if self.fav_location.value.strip():
            updates["favorite_location"] = self.fav_location.value.strip()
        if self.fav_tool.value.strip():
            updates["favorite_tool"] = self.fav_tool.value.strip()
        if self.fav_bait.value.strip():
            updates["favorite_bait"] = self.fav_bait.value.strip()
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await self.message.edit(
            embed=build_profile_embed(user_row, self.member),
            view=ProfileView(self.db, self.member, self.dc),
        )
        await interaction.response.defer()


class ResetConfirmView(discord.ui.View):
    def __init__(self, db, member, dank_client):
        super().__init__(timeout=60)
        self.db = db
        self.member = member
        self.dc = dank_client
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="✅ Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(self.member.id)
        await self.db.update_user(
            user_id,
            fishing_rod="Wooden Rod",
            current_tool=None,
            current_bait=None,
            fishing_skill=0,
            luck_skill=0,
            efficiency_skill=0,
            prestige=0,
            coins=0,
            boss_unlock=0,
            mythical_unlock=0,
            favorite_fish=None,
            favorite_location=None,
            favorite_tool=None,
            favorite_bait=None,
            current_weather=None,
            current_event=None,
        )
        user_row = await self.db.get_user(user_id)
        await interaction.response.edit_message(
            embed=build_profile_embed(user_row, self.member),
            view=ProfileView(self.db, self.member, self.dc),
        )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_user(str(self.member.id))
        await interaction.response.edit_message(
            embed=build_profile_embed(user_row, self.member),
            view=ProfileView(self.db, self.member, self.dc),
        )


class ProfileView(discord.ui.View):
    def __init__(self, db, member, dank_client):
        super().__init__(timeout=300)
        self.db = db
        self.member = member
        self.dc = dank_client
        self.message: discord.Message | None = None
        # Disable stub buttons
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.label in ("📤 Export", "📥 Import"):
                item.disabled = True

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="✏️ Edit Setup", style=discord.ButtonStyle.secondary, row=0)
    async def edit_setup_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            EditSetupModal(self.db, self.member, interaction.message, self.dc)
        )

    @discord.ui.button(label="📊 Edit Skills", style=discord.ButtonStyle.secondary, row=0)
    async def edit_skills_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            EditSkillsModal(self.db, self.member, interaction.message, self.dc)
        )

    @discord.ui.button(label="🔓 Edit Unlocks", style=discord.ButtonStyle.secondary, row=0)
    async def edit_unlocks_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            EditUnlocksModal(self.db, self.member, interaction.message, self.dc)
        )

    @discord.ui.button(label="🌤️ Edit Env", style=discord.ButtonStyle.secondary, row=0)
    async def edit_env_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            EditEnvModal(self.db, self.member, interaction.message, self.dc)
        )

    @discord.ui.button(label="⭐ Edit Favs", style=discord.ButtonStyle.secondary, row=0)
    async def edit_favs_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            EditFavsModal(self.db, self.member, interaction.message, self.dc)
        )

    @discord.ui.button(label="🔄 Reset", style=discord.ButtonStyle.danger, row=1)
    async def reset_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        confirm_view = ResetConfirmView(self.db, self.member, self.dc)
        await interaction.response.edit_message(
            embed=EmbedBuilder.warning("Reset Profile", "This will clear all your data. Are you sure?"),
            view=confirm_view,
        )
        confirm_view.message = await interaction.original_response()

    @discord.ui.button(label="📤 Export", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def export_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="📥 Import", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def import_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View and edit your fishing profile")
    async def profile(self, interaction: discord.Interaction):
        user_row = await self.bot.db.get_or_create_user(str(interaction.user.id))
        embed = build_profile_embed(user_row, interaction.user)
        view = ProfileView(self.bot.db, interaction.user, self.bot.dank_client)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
