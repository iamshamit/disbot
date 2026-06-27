from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import (
    EmbedBuilder,
    build_location_embed,
    build_locations_list_embed,
    build_fish_embed,
    emoji_from_url,
)
from utils.views import DynamicPaginationView
from utils.formatters import is_available_now, rarity_emoji, rarity_rank

_PRELOAD_MSG = "⏳ Data is still loading, please try again in a moment."
_NOT_FOUND = "❌ No location named **{name}** found. Try `/locations` to browse."



class BackToLocationView(discord.ui.View):
    def __init__(self, location, dank_client, db=None, user_id=None):
        super().__init__(timeout=300)
        self.location = location
        self.dc = dank_client
        self.db = db
        self.user_id = user_id

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]

    @discord.ui.button(label="📍 Back to Location", style=discord.ButtonStyle.secondary)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=build_location_embed(self.location, self.dc),
            view=LocationView(self.location, self.dc, db=self.db, user_id=self.user_id),
        )


class LocationView(discord.ui.View):
    def __init__(self, location, dank_client, db=None, user_id=None, is_faved=False):
        super().__init__(timeout=300)
        self.loc = location
        self.dc = dank_client
        self.db = db
        self.user_id = user_id
        self._is_faved = is_faved
        self.message: discord.Message | None = None
        self._build_fish_select()
        # Configure fav button
        fav_btn = next(
            item for item in self.children
            if isinstance(item, discord.ui.Button) and "Favour" in item.label
        )
        if db is None:
            fav_btn.disabled = True
        else:
            fav_btn.disabled = False
            if is_faved:
                fav_btn.label = "💛 Unfavourite"
                fav_btn.style = discord.ButtonStyle.primary
        sim_btn_item = next(
            (item for item in self.children if isinstance(item, discord.ui.Button) and "Simulate" in item.label),
            None,
        )
        if sim_btn_item:
            sim_btn_item.disabled = db is None

    def _build_fish_select(self):
        creatures = self.dc.location_creature_map.get(self.loc.id, [])
        if not creatures:
            return
        creatures_sorted = sorted(
            creatures,
            key=lambda c: -rarity_rank(c.extra.get("rarity", "Common"))
        )
        total = len(creatures_sorted)
        if total > 25:
            placeholder = f"🐟 Fish Pool — Showing 25 of {total} ▾"
            creatures_sorted = creatures_sorted[:25]
        else:
            placeholder = f"🐟 Fish Pool ({total} fish) ▾"
        options = []
        for c in creatures_sorted:
            rarity = c.extra.get("rarity", "Common")
            avail = "✅" if is_available_now(c) else "❌"
            fish_emoji = emoji_from_url(getattr(c, "imageURL", None))
            options.append(
                discord.SelectOption(
                    label=c.name[:100],
                    value=c.id,
                    description=f"{rarity}  ·  {avail} now",
                    emoji=fish_emoji or rarity_emoji(rarity),
                )
            )
        select = discord.ui.Select(
            placeholder=placeholder,
            options=options,
            row=0,
        )
        select.callback = self._fish_selected
        self.add_item(select)
        self._selected_creature_id: str | None = None

    async def _fish_selected(self, interaction: discord.Interaction):
        chosen_id = interaction.data["values"][0]  # type: ignore
        creature = self.dc.fish_by_id.get(chosen_id)
        if creature is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", "Could not load that fish."), ephemeral=True
            )
            return
        self._selected_creature_id = chosen_id
        embed = build_location_embed(self.loc, self.dc)
        # Show brief fish info appended to description
        rarity = creature.extra.get("rarity", "Common")
        flavor = creature.extra.get("flavor", "")
        snippet = f"\n\n{rarity_emoji(rarity)} **{creature.name}** — {rarity}\n*{flavor[:120]}*" if flavor else f"\n\n{rarity_emoji(rarity)} **{creature.name}** — {rarity}"
        max_body = 4096 - len(snippet)
        embed.description = (embed.description or "")[:max_body] + snippet
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="🔗 Open Fish", style=discord.ButtonStyle.primary, row=1)
    async def open_fish_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not hasattr(self, "_selected_creature_id") or self._selected_creature_id is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("No fish selected", "Select a fish from the dropdown first."),
                ephemeral=True,
            )
            return
        creature = self.dc.fish_by_id.get(self._selected_creature_id)
        if creature is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", "Fish data unavailable."), ephemeral=True
            )
            return
        from cogs.fish import FishView
        view = FishView(creature, self.dc, db=self.db, user_id=self.user_id)
        embed = build_fish_embed(creature, self.dc)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @discord.ui.button(label="🎮 Simulate", style=discord.ButtonStyle.secondary, row=1)
    async def sim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.db:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not available", "Simulator requires database connection."),
                ephemeral=True,
            )
            return
        from cogs.simulator import SimulatorView, call_simulator_api, build_sim_results_embed
        import json as _json
        from datetime import datetime, timezone
        from utils.embeds import EmbedBuilder as _EB

        dc = self.dc
        db = self.db
        user_row = await db.get_or_create_user(self.user_id)
        if not user_row:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not available", "Could not load your profile."),
                ephemeral=True,
            )
            return
        tool_id = None
        if user_row["current_tool"]:
            t = dc.tool_by_name.get(user_row["current_tool"].lower())
            if t:
                tool_id = t.id
        bait_id = None
        if user_row["current_bait"]:
            b = dc.bait_by_name.get(user_row["current_bait"].lower())
            if b:
                bait_id = b.id

        initial_state = {
            "location_id": self.loc.id,
            "tool_id": tool_id,
            "bait_id": bait_id,
            "event_id": None,
            "hour": datetime.now(timezone.utc).hour,
        }
        view = SimulatorView(db, interaction.user, dc, initial_state=initial_state)
        embed = _EB.info("🎣 Simulator", "Select your options and click **🔄 Calculate**.")
        await interaction.response.defer(ephemeral=True)
        try:
            payload = view._build_payload(user_row)
            data = await call_simulator_api(payload)
            embed = build_sim_results_embed(data, view._current_state(), dc)
            view._last_embed = embed
            await db.add_history(str(interaction.user.id), "simulation", self.loc.id, data=_json.dumps(data))
        except Exception as exc:
            embed = _EB.error("Simulator error", f"Could not calculate: {exc}")
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="⭐ Favourite", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def fav_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if self._is_faved:
                await self.db.remove_favorite(self.user_id, "location", self.loc.id)
                self._is_faved = False
                button.label = "⭐ Favourite"
                button.style = discord.ButtonStyle.secondary
            else:
                await self.db.add_favorite(self.user_id, "location", self.loc.id)
                self._is_faved = True
                button.label = "💛 Unfavourite"
                button.style = discord.ButtonStyle.primary
            await interaction.response.edit_message(view=self)
        except Exception:
            try:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("Error", "Could not update favourite. Please try again."),
                    ephemeral=True,
                )
            except Exception:
                pass

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=1)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.delete()


class LocationsListView(DynamicPaginationView):
    ITEMS_PER_PAGE = 8

    def __init__(self, dank_client):
        super().__init__()
        self.dc = dank_client
        self.sort = "name"
        self.filter_ = "All"
        self.type_filter = "All"
        self.page = 0
        self._refresh()

    def _refresh(self):
        locs = list(self.dc.location_by_id.values())
        if self.filter_ == "Temporary":
            locs = [l for l in locs if l.extra.get("temporary")]
        elif self.filter_ == "Disabled":
            locs = [l for l in locs if l.extra.get("disabled")]
        elif self.filter_ == "Active":
            locs = [l for l in locs if not l.extra.get("disabled") and not l.extra.get("temporary")]
        if self.type_filter == "saltwater":
            locs = [l for l in locs if (l.extra.get("type") if hasattr(l.extra, "get") else None) == "saltwater"]
        elif self.type_filter == "freshwater":
            locs = [l for l in locs if (l.extra.get("type") if hasattr(l.extra, "get") else None) == "freshwater"]

        if self.sort == "name":
            locs.sort(key=lambda l: l.name.lower())
        elif self.sort == "fish_count":
            locs.sort(key=lambda l: -len(l.extra.get("creatures") or []))
        elif self.sort == "fail_chance":
            locs.sort(key=lambda l: l.extra.get("failChance", 0))
        elif self.sort == "mine_chance":
            locs.sort(key=lambda l: -l.extra.get("mineChance", 0))

        self.filtered = locs
        self.total_pages = max(1, (len(locs) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        self.page = min(self.page, self.total_pages - 1)
        self._refresh_page_btn()

    def build_embed(self) -> discord.Embed:
        return build_locations_list_embed(self.filtered, self.page, self.total_pages, self.sort, self.filter_)

    @discord.ui.select(
        placeholder="📊 Sort ▾",
        row=1,
        options=[
            discord.SelectOption(label="Name (A–Z)", value="name", default=True),
            discord.SelectOption(label="Fish Count (most first)", value="fish_count"),
            discord.SelectOption(label="Fail Chance (lowest first)", value="fail_chance"),
            discord.SelectOption(label="Mine Chance (highest first)", value="mine_chance"),
        ],
    )
    async def sort_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.sort = select.values[0]
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.select(
        placeholder="🔍 Filter ▾",
        row=2,
        options=[
            discord.SelectOption(label="All", value="All", default=True),
            discord.SelectOption(label="Active only", value="Active"),
            discord.SelectOption(label="🔴 Temporary", value="Temporary"),
            discord.SelectOption(label="⛔ Disabled", value="Disabled"),
        ],
    )
    async def filter_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.filter_ = select.values[0]
        self.page = 0
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.select(
        placeholder="🌊 Water Type ▾",
        row=3,
        options=[
            discord.SelectOption(label="All types", value="All", default=True),
            discord.SelectOption(label="🌊 Saltwater", value="saltwater"),
            discord.SelectOption(label="🏞️ Freshwater", value="freshwater"),
        ],
    )
    async def type_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.type_filter = select.values[0]
        self.page = 0
        self._refresh()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class LocationsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _guard(self) -> bool:
        return bool(self.bot.dank_client and self.bot.dank_client.location_by_id)

    @app_commands.command(name="location", description="Look up a fishing location")
    @app_commands.describe(name="Location name")
    async def location(self, interaction: discord.Interaction, name: str):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        loc = self.bot.dank_client.get_location(name)
        if loc is None:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not found", _NOT_FOUND.format(name=name)), ephemeral=True
            )
            return
        user_id = str(interaction.user.id)
        is_faved = False
        if self.bot.db:
            try:
                favs = await self.bot.db.get_favorites(user_id, "location")
                is_faved = any(f["item_id"] == loc.id for f in favs)
                await self.bot.db.add_history(user_id, "location", loc.id)
            except Exception:
                pass
        view = LocationView(loc, self.bot.dank_client, db=self.bot.db, user_id=user_id, is_faved=is_faved)
        embed = build_location_embed(loc, self.bot.dank_client)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @location.autocomplete("name")
    async def location_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.bot.autocomplete:
            return []
        return self.bot.autocomplete.location_choices(current)

    @app_commands.command(name="locations", description="Browse all fishing locations")
    async def locations(self, interaction: discord.Interaction):
        if not self._guard():
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Loading", _PRELOAD_MSG), ephemeral=True
            )
            return
        view = LocationsListView(self.bot.dank_client)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(LocationsCog(bot))
