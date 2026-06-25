from __future__ import annotations
import io
import json as _json
import discord
from discord import app_commands
from discord.ext import commands
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from utils.embeds import EmbedBuilder, build_profile_embed, emoji_from_url

_UNSET = object()


def _picker_embed(title: str) -> discord.Embed:
    return discord.Embed(
        title=title,
        description="Make your selections below, then click **✅ Save**.",
        color=0x5865F2,
    )


# ---------------------------------------------------------------------------
# Small modals for non-enumerable fields (rod / weather / fav fish)
# ---------------------------------------------------------------------------

class RodModal(discord.ui.Modal, title="Set Fishing Rod"):
    rod: discord.ui.TextInput = discord.ui.TextInput(
        label="Fishing Rod", placeholder="e.g. Wooden Rod", required=False, max_length=100
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        val = self.rod.value.strip()
        if val:
            self.parent_view._pending_rod = val
        await interaction.response.defer()


class WeatherModal(discord.ui.Modal, title="Set Current Weather"):
    weather: discord.ui.TextInput = discord.ui.TextInput(
        label="Current Weather", placeholder="e.g. Rainy", required=False, max_length=100
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.parent_view._pending_weather = self.weather.value.strip() or None
        await interaction.response.defer()


class FavFishModal(discord.ui.Modal, title="Set Favourite Fish"):
    fish: discord.ui.TextInput = discord.ui.TextInput(
        label="Favourite Fish", placeholder="e.g. Goldfish", required=False, max_length=100
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.parent_view._pending_fav_fish = self.fish.value.strip() or None
        await interaction.response.defer()


class EditStatsModal(discord.ui.Modal, title="Edit Stats"):
    prestige: discord.ui.TextInput = discord.ui.TextInput(
        label="Prestige", placeholder="0+", required=False, max_length=6
    )
    coins: discord.ui.TextInput = discord.ui.TextInput(
        label="Coins", placeholder="0+", required=False, max_length=15
    )

    def __init__(self, db, member, message, dc=None):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message
        self.dc = dc

    async def on_submit(self, interaction: discord.Interaction) -> None:
        fields = {"prestige": self.prestige.value, "coins": self.coins.value}
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
                        f"**{key.title()}** must be a non-negative integer.",
                    ),
                    ephemeral=True,
                )
                return
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await interaction.response.defer()
        await self.message.edit(
            embed=build_profile_embed(user_row, self.member, self.dc),
            view=ProfileView(self.db, self.member, self.dc),
        )


# ---------------------------------------------------------------------------
# Picker views — shown inline (edit_message) instead of modal popups
# ---------------------------------------------------------------------------

class EditSetupView(discord.ui.View):
    def __init__(self, db, member, dc):
        super().__init__(timeout=120)
        self.db = db
        self.member = member
        self.dc = dc
        self._pending_rod: str | None = None

        tool_opts = [discord.SelectOption(label="— No Tool —", value="__clear__")] + [
            discord.SelectOption(label=t.name, value=t.id,
                                 emoji=emoji_from_url(getattr(t, "imageURL", None)))
            for t in sorted(dc.tool_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._tool_sel = discord.ui.Select(
            placeholder="🔧 Select tool…", options=tool_opts, min_values=0, max_values=1, row=0
        )
        self._tool_sel.callback = self._defer
        self.add_item(self._tool_sel)

        bait_opts = [discord.SelectOption(label="— No Bait —", value="__clear__")] + [
            discord.SelectOption(label=b.name, value=b.id,
                                 emoji=emoji_from_url(getattr(b, "imageURL", None)))
            for b in sorted(dc.bait_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._bait_sel = discord.ui.Select(
            placeholder="🪱 Select bait…", options=bait_opts, min_values=0, max_values=1, row=1
        )
        self._bait_sel.callback = self._defer
        self.add_item(self._bait_sel)

    async def _defer(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="🖊️ Set Rod", style=discord.ButtonStyle.secondary, row=2)
    async def set_rod_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RodModal(self))

    @discord.ui.button(label="✅ Save", style=discord.ButtonStyle.success, row=3)
    async def save_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        updates: dict = {}
        if self._pending_rod:
            updates["fishing_rod"] = self._pending_rod
        if self._tool_sel.values:
            v = self._tool_sel.values[0]
            if v == "__clear__":
                updates["current_tool"] = None
            else:
                t = self.dc.tool_by_id.get(v)
                if t:
                    updates["current_tool"] = t.name
        if self._bait_sel.values:
            v = self._bait_sel.values[0]
            if v == "__clear__":
                updates["current_bait"] = None
            else:
                b = self.dc.bait_by_id.get(v)
                if b:
                    updates["current_bait"] = b.name
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await interaction.response.edit_message(
            embed=build_profile_embed(user_row, self.member, self.dc),
            view=ProfileView(self.db, self.member, self.dc),
        )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary, row=3)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_user(str(self.member.id))
        await interaction.response.edit_message(
            embed=build_profile_embed(user_row, self.member, self.dc),
            view=ProfileView(self.db, self.member, self.dc),
        )


class EditUnlocksView(discord.ui.View):
    def __init__(self, db, member, dc):
        super().__init__(timeout=120)
        self.db = db
        self.member = member
        self.dc = dc

        self._boss_sel = discord.ui.Select(
            placeholder="👑 Boss Unlock…",
            options=[
                discord.SelectOption(label="✅ Yes", value="1"),
                discord.SelectOption(label="❌ No", value="0"),
            ],
            min_values=0, max_values=1, row=0,
        )
        self._boss_sel.callback = self._defer
        self.add_item(self._boss_sel)

        self._myth_sel = discord.ui.Select(
            placeholder="✨ Mythical Unlock…",
            options=[
                discord.SelectOption(label="✅ Yes", value="1"),
                discord.SelectOption(label="❌ No", value="0"),
            ],
            min_values=0, max_values=1, row=1,
        )
        self._myth_sel.callback = self._defer
        self.add_item(self._myth_sel)

    async def _defer(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="✅ Save", style=discord.ButtonStyle.success, row=2)
    async def save_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        updates: dict = {}
        if self._boss_sel.values:
            updates["boss_unlock"] = int(self._boss_sel.values[0])
        if self._myth_sel.values:
            updates["mythical_unlock"] = int(self._myth_sel.values[0])
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await interaction.response.edit_message(
            embed=build_profile_embed(user_row, self.member, self.dc),
            view=ProfileView(self.db, self.member, self.dc),
        )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary, row=2)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_user(str(self.member.id))
        await interaction.response.edit_message(
            embed=build_profile_embed(user_row, self.member, self.dc),
            view=ProfileView(self.db, self.member, self.dc),
        )


class EditEnvView(discord.ui.View):
    def __init__(self, db, member, dc):
        super().__init__(timeout=120)
        self.db = db
        self.member = member
        self.dc = dc
        self._pending_weather = _UNSET

        event_opts = [discord.SelectOption(label="— No Event —", value="__clear__")] + [
            discord.SelectOption(label=e.name, value=e.id,
                                 emoji=emoji_from_url(getattr(e, "imageURL", None)))
            for e in sorted(dc.event_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._event_sel = discord.ui.Select(
            placeholder="🎉 Select event…", options=event_opts, min_values=0, max_values=1, row=0
        )
        self._event_sel.callback = self._defer
        self.add_item(self._event_sel)

    async def _defer(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="🌤️ Set Weather", style=discord.ButtonStyle.secondary, row=1)
    async def set_weather_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WeatherModal(self))

    @discord.ui.button(label="✅ Save", style=discord.ButtonStyle.success, row=2)
    async def save_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        updates: dict = {}
        if self._pending_weather is not _UNSET:
            updates["current_weather"] = self._pending_weather
        if self._event_sel.values:
            v = self._event_sel.values[0]
            if v == "__clear__":
                updates["current_event"] = None
            else:
                e = self.dc.event_by_id.get(v)
                if e:
                    updates["current_event"] = e.name
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await interaction.response.edit_message(
            embed=build_profile_embed(user_row, self.member, self.dc),
            view=ProfileView(self.db, self.member, self.dc),
        )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary, row=2)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_user(str(self.member.id))
        await interaction.response.edit_message(
            embed=build_profile_embed(user_row, self.member, self.dc),
            view=ProfileView(self.db, self.member, self.dc),
        )


class EditFavsView(discord.ui.View):
    def __init__(self, db, member, dc):
        super().__init__(timeout=120)
        self.db = db
        self.member = member
        self.dc = dc
        self._pending_fav_fish = _UNSET

        NONE_OPT = discord.SelectOption(label="— None —", value="__clear__")

        loc_opts = [NONE_OPT] + [
            discord.SelectOption(label=l.name, value=l.id,
                                 emoji=emoji_from_url(getattr(l, "imageURL", None)))
            for l in sorted(dc.location_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._loc_sel = discord.ui.Select(
            placeholder="📍 Fav Location…", options=loc_opts, min_values=0, max_values=1, row=0
        )
        self._loc_sel.callback = self._defer
        self.add_item(self._loc_sel)

        tool_opts = [NONE_OPT] + [
            discord.SelectOption(label=t.name, value=t.id,
                                 emoji=emoji_from_url(getattr(t, "imageURL", None)))
            for t in sorted(dc.tool_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._tool_sel = discord.ui.Select(
            placeholder="🔧 Fav Tool…", options=tool_opts, min_values=0, max_values=1, row=1
        )
        self._tool_sel.callback = self._defer
        self.add_item(self._tool_sel)

        bait_opts = [NONE_OPT] + [
            discord.SelectOption(label=b.name, value=b.id,
                                 emoji=emoji_from_url(getattr(b, "imageURL", None)))
            for b in sorted(dc.bait_by_id.values(), key=lambda x: x.name)[:24]
        ]
        self._bait_sel = discord.ui.Select(
            placeholder="🪱 Fav Bait…", options=bait_opts, min_values=0, max_values=1, row=2
        )
        self._bait_sel.callback = self._defer
        self.add_item(self._bait_sel)

    async def _defer(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="🐟 Set Fav Fish", style=discord.ButtonStyle.secondary, row=3)
    async def set_fav_fish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FavFishModal(self))

    @discord.ui.button(label="✅ Save", style=discord.ButtonStyle.success, row=4)
    async def save_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        updates: dict = {}
        if self._pending_fav_fish is not _UNSET:
            updates["favorite_fish"] = self._pending_fav_fish
        if self._loc_sel.values:
            v = self._loc_sel.values[0]
            if v == "__clear__":
                updates["favorite_location"] = None
            else:
                loc = self.dc.location_by_id.get(v)
                if loc:
                    updates["favorite_location"] = loc.name
        if self._tool_sel.values:
            v = self._tool_sel.values[0]
            if v == "__clear__":
                updates["favorite_tool"] = None
            else:
                t = self.dc.tool_by_id.get(v)
                if t:
                    updates["favorite_tool"] = t.name
        if self._bait_sel.values:
            v = self._bait_sel.values[0]
            if v == "__clear__":
                updates["favorite_bait"] = None
            else:
                b = self.dc.bait_by_id.get(v)
                if b:
                    updates["favorite_bait"] = b.name
        if updates:
            await self.db.update_user(str(self.member.id), **updates)
        user_row = await self.db.get_user(str(self.member.id))
        await interaction.response.edit_message(
            embed=build_profile_embed(user_row, self.member, self.dc),
            view=ProfileView(self.db, self.member, self.dc),
        )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary, row=4)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_user(str(self.member.id))
        await interaction.response.edit_message(
            embed=build_profile_embed(user_row, self.member, self.dc),
            view=ProfileView(self.db, self.member, self.dc),
        )


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
            skills=None,
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
            embed=build_profile_embed(user_row, self.member, self.dc),
            view=ProfileView(self.db, self.member, self.dc),
        )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_user(str(self.member.id))
        await interaction.response.edit_message(
            embed=build_profile_embed(user_row, self.member, self.dc),
            view=ProfileView(self.db, self.member, self.dc),
        )


_IMPORT_PROFILE_KEYS = (
    "current_tool", "current_bait", "favorite_location", "current_event",
    "fishing_skill", "luck_skill", "efficiency_skill", "prestige", "coins",
    "boss_unlock", "mythical_unlock", "skills", "timezone", "theme", "compact_mode",
)


class ImportModal(discord.ui.Modal, title="Import Profile"):
    json_input: discord.ui.TextInput = discord.ui.TextInput(
        label="Paste your profile JSON",
        style=discord.TextStyle.paragraph,
        max_length=4000,
    )

    def __init__(self, db, member, message):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.json_input.value
        try:
            payload = _json.loads(raw)
        except Exception:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Invalid JSON", "Could not parse the pasted data."),
                ephemeral=True,
            )
            return
        if payload.get("version") != 1:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Incompatible format", "This export was made with an unsupported version."),
                ephemeral=True,
            )
            return
        profile = payload.get("profile", {})
        update_fields = {k: profile[k] for k in _IMPORT_PROFILE_KEYS if k in profile}
        try:
            await self.db.update_user(str(self.member.id), **update_fields)
            for fav in payload.get("favorites", []):
                await self.db.add_favorite(str(self.member.id), fav["type"], fav["item_id"])
        except Exception as exc:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Import failed", f"Could not restore profile: {exc}"),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=EmbedBuilder.info("Profile Imported", "Your profile has been restored."),
            ephemeral=True,
        )


class ProfileView(discord.ui.View):
    def __init__(self, db, member, dank_client):
        super().__init__(timeout=300)
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

    @discord.ui.button(label="✏️ Edit Setup", style=discord.ButtonStyle.secondary, row=0)
    async def edit_setup_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=_picker_embed("✏️ Edit Setup"),
            view=EditSetupView(self.db, self.member, self.dc),
        )

    @discord.ui.button(label="📊 Edit Skills", style=discord.ButtonStyle.secondary, row=0)
    async def edit_skills_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.simulator import SkillsPickerView
        user_row = await self.db.get_user(str(self.member.id))
        try:
            current_skills = _json.loads(user_row["skills"]) if user_row["skills"] else {}
        except (ValueError, TypeError, KeyError, IndexError):
            current_skills = {}

        async def return_fn(inter: discord.Interaction) -> None:
            fresh_row = await self.db.get_user(str(self.member.id))
            await inter.response.edit_message(
                embed=build_profile_embed(fresh_row, self.member, self.dc),
                view=ProfileView(self.db, self.member, self.dc),
            )

        await interaction.response.edit_message(
            embed=_picker_embed("📊 Edit Skills"),
            view=SkillsPickerView(self.db, self.member, self.dc, current_skills, return_fn),
        )

    @discord.ui.button(label="🔓 Edit Unlocks", style=discord.ButtonStyle.secondary, row=0)
    async def edit_unlocks_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=_picker_embed("🔓 Edit Unlocks"),
            view=EditUnlocksView(self.db, self.member, self.dc),
        )

    @discord.ui.button(label="🌤️ Edit Env", style=discord.ButtonStyle.secondary, row=0)
    async def edit_env_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=_picker_embed("🌤️ Edit Environment"),
            view=EditEnvView(self.db, self.member, self.dc),
        )

    @discord.ui.button(label="⭐ Edit Favs", style=discord.ButtonStyle.secondary, row=0)
    async def edit_favs_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=_picker_embed("⭐ Edit Favourites"),
            view=EditFavsView(self.db, self.member, self.dc),
        )

    @discord.ui.button(label="🔄 Reset", style=discord.ButtonStyle.danger, row=1)
    async def reset_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        confirm_view = ResetConfirmView(self.db, self.member, self.dc)
        await interaction.response.edit_message(
            embed=EmbedBuilder.warning("Reset Profile", "This will clear all your data. Are you sure?"),
            view=confirm_view,
        )
        confirm_view.message = await interaction.original_response()

    @discord.ui.button(label="📈 Edit Stats", style=discord.ButtonStyle.secondary, row=1)
    async def edit_stats_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            EditStatsModal(self.db, self.member, interaction.message, self.dc)
        )

    @discord.ui.button(label="📤 Export", style=discord.ButtonStyle.secondary, row=1)
    async def export_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(self.member.id)
        try:
            user_row = await self.db.get_or_create_user(user_id)
            fav_rows = await self.db.get_favorites(user_id)
        except Exception as exc:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Export failed", f"Could not read profile: {exc}"),
                ephemeral=True,
            )
            return
        payload = {
            "version": 1,
            "profile": {k: user_row[k] for k in _IMPORT_PROFILE_KEYS},
            "favorites": [{"type": r["type"], "item_id": r["item_id"]} for r in fav_rows],
        }
        raw = _json.dumps(payload, indent=2).encode()
        await interaction.response.send_message(
            embed=EmbedBuilder.info("Profile Exported", "Your profile data is attached."),
            file=discord.File(io.BytesIO(raw), filename="profile.json"),
            ephemeral=True,
        )

    @discord.ui.button(label="📥 Import", style=discord.ButtonStyle.secondary, row=1)
    async def import_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            ImportModal(self.db, self.member, interaction.message)
        )


def _group_favs(rows) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {"fish": [], "location": [], "tool": [], "bait": []}
    for row in rows:
        t = row["type"]
        if t in result:
            result[t].append(row["item_id"])
    return result


class FavoritesView(discord.ui.View):
    def __init__(self, db, user, dank_client, fav_rows):
        super().__init__(timeout=300)
        self.db = db
        self.user = user
        self.dc = dank_client
        self.selected_type: str | None = None
        self.selected_id: str | None = None
        self.message: discord.Message | None = None
        self._build_select(fav_rows)
        self._update_action_buttons()

    def _build_select(self, fav_rows):
        for item in list(self.children):
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)
        TYPE_EMOJI = {"fish": "\U0001f420", "location": "\U0001f4cd", "tool": "\U0001f527", "bait": "\U0001fab1"}
        options = []
        for row in fav_rows[:25]:
            emoji = TYPE_EMOJI.get(row["type"], "⭐")
            label = f"{emoji} {row['item_id']}"
            value = f"{row['type']}:{row['item_id']}"
            options.append(discord.SelectOption(label=label[:100], value=value))
        if not options:
            return
        select = discord.ui.Select(placeholder="Choose a favourite to view…", options=options, row=0)
        select.callback = self._on_select
        self.add_item(select)

    def _update_action_buttons(self):
        has = self.selected_id is not None
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.label in (
                "\U0001f517 Open", "\U0001f5d1️ Remove", "\U0001f3ae Simulate"
            ):
                item.disabled = not has

    async def _on_select(self, interaction: discord.Interaction) -> None:
        select = next(c for c in self.children if isinstance(c, discord.ui.Select))
        value = select.values[0]
        self.selected_type, self.selected_id = value.split(":", 1)
        self._update_action_buttons()
        favs = await self.db.get_favorites(str(self.user.id))
        by_type = _group_favs(favs)
        from utils.embeds import build_favorites_embed
        embed = build_favorites_embed(by_type, self.user)
        embed.set_footer(text=f"Selected: {self.selected_id} — click Open to view or Remove to delete")
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="\U0001f517 Open", style=discord.ButtonStyle.primary, disabled=True, row=1)
    async def open_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        from utils.embeds import build_fish_embed, build_location_embed, build_tool_embed, build_bait_embed
        embed = None
        if self.selected_type == "fish":
            item = self.dc.fish_by_id.get(self.selected_id)
            if item:
                embed = build_fish_embed(item, self.dc)
        elif self.selected_type == "location":
            item = self.dc.location_by_id.get(self.selected_id)
            if item:
                embed = build_location_embed(item, self.dc)
        elif self.selected_type == "tool":
            item = self.dc.tool_by_id.get(self.selected_id)
            if item:
                embed = build_tool_embed(item)
        elif self.selected_type == "bait":
            item = self.dc.bait_by_id.get(self.selected_id)
            if item:
                embed = build_bait_embed(item)
        if embed is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", "This item no longer exists in the game data."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="\U0001f5d1️ Remove", style=discord.ButtonStyle.danger, disabled=True, row=1)
    async def remove_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.db.remove_favorite(str(self.user.id), self.selected_type, self.selected_id)
        self.selected_type = None
        self.selected_id = None
        favs = await self.db.get_favorites(str(self.user.id))
        by_type = _group_favs(favs)
        self._build_select(favs)
        self._update_action_buttons()
        from utils.embeds import build_favorites_embed
        embed = build_favorites_embed(by_type, self.user)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="\U0001f3ae Simulate", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.simulator import SimulatorView
        initial_state: dict = {}
        if self.selected_type == "location":
            initial_state["location_id"] = self.selected_id
        elif self.selected_type == "tool":
            initial_state["tool_id"] = self.selected_id
        view = SimulatorView(self.db, self.user, self.dc, initial_state=initial_state)
        embed = EmbedBuilder.info("🎣 Simulator", "Select your options and click **🔄 Calculate**.")
        await interaction.response.send_message(embed=embed, view=view)


class HistoryView(discord.ui.View):
    def __init__(self, db, user):
        super().__init__(timeout=300)
        self.db = db
        self.user = user
        self.current_tab = "fish"
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    async def _switch_tab(self, interaction: discord.Interaction, tab: str) -> None:
        self.current_tab = tab
        rows = await self.db.get_history(str(self.user.id), tab)
        from utils.embeds import build_history_embed
        embed = build_history_embed(rows, self.user, tab)
        # Update button styles: active tab → primary, others → secondary (skip disabled)
        tab_map = {
            "fish": "fish_tab",
            "location": "location_tab",
            "simulation": "sim_tab",
            "command": "command_tab",
        }
        for item in self.children:
            if isinstance(item, discord.ui.Button) and not item.disabled:
                for tab_key, attr_name in tab_map.items():
                    btn = getattr(self, attr_name, None)
                    if btn is item:
                        item.style = discord.ButtonStyle.primary if tab_key == tab else discord.ButtonStyle.secondary
                        break
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="\U0001f420 Fish", style=discord.ButtonStyle.primary, row=0)
    async def fish_tab(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "fish")

    @discord.ui.button(label="\U0001f4cd Locations", style=discord.ButtonStyle.secondary, row=0)
    async def location_tab(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "location")

    @discord.ui.button(label="\U0001f3ae Simulations", style=discord.ButtonStyle.secondary, row=0)
    async def sim_tab(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "simulation")

    @discord.ui.button(label="\U0001f4ac Commands", style=discord.ButtonStyle.secondary, row=0)
    async def command_tab(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_tab(interaction, "command")


class TimezoneModal(discord.ui.Modal, title="Set Timezone"):
    timezone: discord.ui.TextInput = discord.ui.TextInput(
        label="IANA Timezone",
        placeholder="e.g. UTC, Asia/Kolkata, America/New_York",
        min_length=2,
        max_length=50,
    )

    def __init__(self, db, member, message, current_tz: str):
        super().__init__()
        self.db = db
        self.member = member
        self.message = message
        self.timezone.default = current_tz

    async def on_submit(self, interaction: discord.Interaction) -> None:
        tz_str = self.timezone.value.strip()
        try:
            ZoneInfo(tz_str)
        except (ZoneInfoNotFoundError, KeyError):
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    "Invalid timezone",
                    f"Unknown timezone **{tz_str}**. Use an IANA name like `UTC` or `Asia/Kolkata`.",
                ),
                ephemeral=True,
            )
            return
        await self.db.update_user(str(self.member.id), timezone=tz_str)
        user_row = await self.db.get_or_create_user(str(self.member.id))
        from utils.embeds import build_settings_embed
        new_settings_view = SettingsView(self.db, self.member)
        new_settings_view.message = self.message
        await self.message.edit(embed=build_settings_embed(user_row), view=new_settings_view)
        await interaction.response.defer()


class SettingsView(discord.ui.View):
    def __init__(self, db, member):
        super().__init__(timeout=300)
        self.db = db
        self.member = member
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="\U0001f30d Set Timezone", style=discord.ButtonStyle.secondary, row=0)
    async def timezone_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_or_create_user(str(self.member.id))
        current_tz = (user_row["timezone"] if user_row else None) or "UTC"
        await interaction.response.send_modal(
            TimezoneModal(self.db, self.member, interaction.message, current_tz)
        )

    @discord.ui.button(label="\U0001f319 Theme: Dark", style=discord.ButtonStyle.secondary, row=0)
    async def theme_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_or_create_user(str(self.member.id))
        current = (user_row["theme"] if user_row else None) or "dark"
        new_theme = "light" if current == "dark" else "dark"
        await self.db.update_user(str(self.member.id), theme=new_theme)
        button.label = f"{'🌕' if new_theme == 'light' else '🌑'} Theme: {'Light' if new_theme == 'light' else 'Dark'}"
        user_row = await self.db.get_or_create_user(str(self.member.id))
        from utils.embeds import build_settings_embed
        await interaction.response.edit_message(embed=build_settings_embed(user_row), view=self)

    @discord.ui.button(label="\U0001f4c4 Compact: Off", style=discord.ButtonStyle.secondary, row=0)
    async def compact_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_or_create_user(str(self.member.id))
        current = bool(user_row["compact_mode"] if user_row else False)
        new_val = not current
        await self.db.update_user(str(self.member.id), compact_mode=int(new_val))
        button.label = f"\U0001f4c4 Compact: {'On' if new_val else 'Off'}"
        user_row = await self.db.get_or_create_user(str(self.member.id))
        from utils.embeds import build_settings_embed
        await interaction.response.edit_message(embed=build_settings_embed(user_row), view=self)

    @discord.ui.button(label="\U0001f514 Notifications", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def notif_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="\U0001f3ae Default Sim Values", style=discord.ButtonStyle.secondary, row=1)
    async def sim_defaults_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_row = await self.db.get_or_create_user(str(self.member.id))
        tool = user_row["current_tool"] or "None"
        bait = user_row["current_bait"] or "None"
        location = user_row["favorite_location"] or "None"
        event = user_row["current_event"] or "None"
        embed = discord.Embed(title="\U0001f3ae Default Sim Values", color=0x5865F2)
        embed.add_field(name="Tool", value=tool, inline=True)
        embed.add_field(name="Bait", value=bait, inline=True)
        embed.add_field(name="Location", value=location, inline=True)
        embed.add_field(name="Event", value=event, inline=True)
        embed.set_footer(text="Run /simulate and click \U0001f504 Calculate to auto-update these values.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View and edit your fishing profile")
    async def profile(self, interaction: discord.Interaction):
        user_row = await self.bot.db.get_or_create_user(str(interaction.user.id))
        embed = build_profile_embed(user_row, interaction.user, self.bot.dank_client)
        view = ProfileView(self.bot.db, interaction.user, self.bot.dank_client)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="favorites", description="View and manage your favourited fish, locations, tools, and baits")
    async def favorites(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        fav_rows = await self.bot.db.get_favorites(user_id)
        by_type = _group_favs(fav_rows)
        from utils.embeds import build_favorites_embed
        embed = build_favorites_embed(by_type, interaction.user)
        view = FavoritesView(self.bot.db, interaction.user, self.bot.dank_client, fav_rows)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="history", description="View recently viewed fish, locations, and simulations")
    async def history(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        rows = await self.bot.db.get_history(user_id, "fish")
        from utils.embeds import build_history_embed
        embed = build_history_embed(rows, interaction.user, "fish")
        view = HistoryView(self.bot.db, interaction.user)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="settings", description="Configure your personal preferences")
    async def settings(self, interaction: discord.Interaction):
        user_row = await self.bot.db.get_or_create_user(str(interaction.user.id))
        from utils.embeds import build_settings_embed
        embed = build_settings_embed(user_row)
        view = SettingsView(self.bot.db, interaction.user)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
