from __future__ import annotations
from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands

from fishing_engine import creature_eligible, RARITY_WEIGHTS
from utils.optimizer import best_setups, score_setup
from utils.embeds import EmbedBuilder, emoji_from_url

_PRELOAD_MSG = "⏳ Data is still loading, please try again in a moment."

_RARITY_ORDER = [
    "Absurdly Common", "Very Common", "Common", "Regular",
    "Rare", "Very Rare", "Absurdly Rare",
]


def _utc_hour() -> int:
    return datetime.now(timezone.utc).hour


def _catchable_set(dc, hour: int, location_id: str | None = None) -> set[str]:
    """Fish IDs catchable with fishing-rod (no bosses) at hour, across all or one location."""
    loc_ids = [location_id] if location_id else list(dc.location_by_id.keys())
    found: set[str] = set()
    for fish in dc.fish_by_id.values():
        for lid in loc_ids:
            if creature_eligible(fish, lid, "fishing-rod", hour, bosses=False, ignore_time=False):
                found.add(fish.id)
                break
    return found


def _upcoming_windows(dc, hour: int, location_id: str | None = None, ahead: int = 6) -> dict[int, list[str]]:
    """Fish names newly available at each of the next `ahead` hours vs current hour."""
    current = _catchable_set(dc, hour, location_id)
    windows: dict[int, list[str]] = {}
    for delta in range(1, ahead + 1):
        fhour = (hour + delta) % 24
        future = _catchable_set(dc, fhour, location_id)
        newly_open = sorted(dc.fish_by_id[fid].name for fid in (future - current))
        if newly_open:
            windows[fhour] = newly_open
    return windows


def _build_rarity_embed(dc, hour: int) -> discord.Embed:
    by_rarity: dict[str, list[str]] = {r: [] for r in _RARITY_ORDER}
    for fish in dc.fish_by_id.values():
        r = fish.extra.get("rarity", "")
        if r in by_rarity:
            by_rarity[r].append(fish.id)
    catchable = _catchable_set(dc, hour)
    embed = discord.Embed(title="Rarity Tiers", color=0x5865F2)
    for rarity in _RARITY_ORDER:
        fish_ids = by_rarity[rarity]
        total = len(fish_ids)
        now = sum(1 for fid in fish_ids if fid in catchable)
        weight = RARITY_WEIGHTS[rarity]
        embed.add_field(
            name=rarity,
            value=f"Weight: **{weight}** · Total: **{total}** · Now: **{now}**",
            inline=False,
        )
    embed.set_footer(text=f"UTC hour: {hour:02d}:00")
    return embed


_EVENT_PAGE_SIZE = 5


def _build_event_overview_pages(events: list, active_event: str | None) -> list[discord.Embed]:
    total_pages = max(1, (len(events) + _EVENT_PAGE_SIZE - 1) // _EVENT_PAGE_SIZE)
    pages = []
    for page_idx in range(total_pages):
        chunk = events[page_idx * _EVENT_PAGE_SIZE: (page_idx + 1) * _EVENT_PAGE_SIZE]
        embed = discord.Embed(title="Fishing Events", color=0x5865F2)
        for ev in chunk:
            last_dates = ev.extra.get("last", [])
            last_str = str(last_dates[0])[:10] if last_dates else "Unknown"
            desc = ev.extra.get("description", "")
            desc_short = (desc[:80] + "…") if len(desc) > 80 else desc
            star = "⭐ " if ev.name == active_event else ""
            embed.add_field(
                name=f"{star}{ev.name}",
                value=f"{desc_short}\nLast seen: **{last_str}**",
                inline=False,
            )
        embed.set_footer(text=f"Page {page_idx + 1}/{total_pages}")
        pages.append(embed)
    return pages


def _build_event_detail_embed(event, active_event: str | None) -> discord.Embed:
    embed = discord.Embed(
        title=event.name,
        description=event.extra.get("description", ""),
        color=0x5865F2,
    )
    embed.set_thumbnail(url=event.imageURL)
    last_dates = event.extra.get("last", [])[:3]
    if last_dates:
        embed.add_field(
            name="Last Seen",
            value="\n".join(str(d)[:10] for d in last_dates),
            inline=False,
        )
    if event.name == active_event:
        embed.set_footer(text="Active")
    return embed


class EventOverviewView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed]):
        super().__init__(timeout=300)
        self.pages = pages
        self.page = 0
        self.message: discord.Message | None = None
        self._sync()

    def _sync(self) -> None:
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= len(self.pages) - 1

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._sync()
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._sync()
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=0)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.delete()


class EventDetailView(discord.ui.View):
    def __init__(self, db, event, user_id: str):
        super().__init__(timeout=300)
        self.db = db
        self.event = event
        self.user_id = user_id
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="⭐ Set as Current", style=discord.ButtonStyle.primary, row=0)
    async def set_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.db.update_user(self.user_id, current_event=self.event.name)
        except Exception:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Failed to save", "Could not update your profile."),
                ephemeral=True,
            )
            return
        button.label = "✅ Set"
        button.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=0)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.delete()


def _build_time_embed(dc, hour: int, location_id: str | None) -> discord.Embed:
    if location_id:
        loc = dc.location_by_id.get(location_id)
        loc_name = loc.name if loc else location_id
        catchable_names = sorted(
            dc.fish_by_id[fid].name for fid in _catchable_set(dc, hour, location_id)
        )
        embed = discord.Embed(title=f"{loc_name} — {hour:02d}:00 UTC", color=0x5865F2)
        embed.add_field(
            name="Catchable Now",
            value="\n".join(catchable_names) if catchable_names else "No fish catchable at this hour.",
            inline=False,
        )
    else:
        total = len(_catchable_set(dc, hour))
        embed = discord.Embed(
            title=f"Current UTC — {hour:02d}:00",
            description=f"**{total}** fish catchable across all locations right now.",
            color=0x5865F2,
        )
    windows = _upcoming_windows(dc, hour, location_id)
    if windows:
        lines = [f"**{fh:02d}:00** — {', '.join(names)}" for fh, names in sorted(windows.items())]
        embed.add_field(name="Upcoming Windows (next 6h)", value="\n".join(lines), inline=False)
    else:
        embed.add_field(
            name="Upcoming Windows (next 6h)",
            value="No new windows in the next 6 hours.",
            inline=False,
        )
    return embed


def _build_today_embed(dc, db_row, hour: int) -> discord.Embed:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    embed = discord.Embed(title=f"Today's Fishing — {date_str} UTC", color=0x5865F2)
    embed.add_field(name="Current Time", value=f"{hour:02d}:00 UTC", inline=True)
    if db_row is None:
        active_value = "unavailable"
    else:
        ev = dc.event_by_name.get((db_row["current_event"] or "").lower())
        if ev:
            active_value = ev.name
        else:
            active_value = "None set — use `/event` to set one"
    embed.add_field(name="Active Event", value=active_value, inline=True)
    current_set = _catchable_set(dc, hour)
    embed.add_field(name="Catchable Right Now", value=f"{len(current_set)} fish", inline=True)
    loc_counts = sorted(
        ((loc.name, len(_catchable_set(dc, hour, loc.id))) for loc in dc.location_by_id.values()),
        key=lambda x: x[1],
        reverse=True,
    )
    embed.add_field(
        name="Top Locations",
        value="\n".join(f"{name} — {count} fish" for name, count in loc_counts[:3]),
        inline=False,
    )

    # --- Best Catch Right Now ---
    top_setups = best_setups(dc, hour, limit=1)
    if top_setups:
        top = top_setups[0]
        eligible = [
            f for f in dc.fish_by_id.values()
            if creature_eligible(f, top["location"].id, top["tool"].id, hour, bosses=False, ignore_time=False)
        ]
        best_fish = min(
            eligible,
            key=lambda f: RARITY_WEIGHTS.get(f.extra.get("rarity", ""), float("inf")),
            default=None,
        )
        if best_fish:
            rarity = best_fish.extra.get("rarity", "?")
            best_catch_value = f"**{best_fish.name}** ({rarity})  ·  📍 {top['location'].name}  ·  🎣 {top['tool'].name}"
        else:
            best_catch_value = "Nothing catchable right now."
    else:
        best_catch_value = "Nothing catchable right now."
    embed.add_field(name="🏆 Best Catch Right Now", value=best_catch_value, inline=False)

    # --- Your Setup ---
    current_tool_name = db_row["current_tool"] if db_row else None
    current_bait_id = db_row["current_bait"] if db_row else None
    current_tool_id = None
    if current_tool_name:
        tool_match = dc.tool_by_name.get(current_tool_name.lower())
        if tool_match:
            current_tool_id = tool_match.id
    if current_tool_id:
        best_loc = max(
            dc.location_by_id.values(),
            key=lambda loc: score_setup(dc, current_tool_id, loc.id, hour),
            default=None,
        )
        tool = dc.tool_by_id.get(current_tool_id)
        bait = dc.bait_by_id.get(current_bait_id) if current_bait_id else None
        tool_label = tool.name if tool else current_tool_id
        bait_label = (bait.name if bait else current_bait_id) if current_bait_id else "—"
        loc_label = best_loc.name if best_loc else "—"
        your_setup_value = f"Tool: **{tool_label}**  ·  Bait: **{bait_label}**\nBest location right now: **{loc_label}**"
    else:
        your_setup_value = "Not configured — use `/profile` to set your gear"
    embed.add_field(name="🎣 Your Setup", value=your_setup_value, inline=False)

    upcoming_lines = []
    for delta in range(1, 4):
        fhour = (hour + delta) % 24
        future_set = _catchable_set(dc, fhour)
        opened = len(future_set - current_set)
        closed = len(current_set - future_set)
        if opened == 0 and closed == 0:
            continue
        parts = []
        if opened:
            parts.append(f"+{opened} fish open")
        if closed:
            parts.append(f"{closed} fish close")
        upcoming_lines.append(f"**{fhour:02d}:00** — {', '.join(parts)}")
    if upcoming_lines:
        embed.add_field(name="Upcoming (next 3h)", value="\n".join(upcoming_lines), inline=False)
    embed.set_footer(text="Update your setup with /profile")
    return embed


class TimeView(discord.ui.View):
    def __init__(self, dc):
        super().__init__(timeout=300)
        self.dc = dc
        self._loc_id: str | None = None
        self.message: discord.Message | None = None
        loc_opts = [
            discord.SelectOption(label=loc.name, value=loc.id,
                                 emoji=emoji_from_url(getattr(loc, "imageURL", None)))
            for loc in sorted(dc.location_by_id.values(), key=lambda l: l.name)
        ]
        self._loc_sel = discord.ui.Select(
            placeholder="Filter by location…",
            options=loc_opts,
            min_values=0,
            max_values=1,
            row=0,
        )
        self._loc_sel.callback = self._on_select
        self.add_item(self._loc_sel)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    async def _on_select(self, interaction: discord.Interaction) -> None:
        self._loc_id = self._loc_sel.values[0] if self._loc_sel.values else None
        embed = _build_time_embed(self.dc, _utc_hour(), self._loc_id)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=1)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.delete()


class UtilitiesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def dc(self):
        return self.bot.dank_client

    @property
    def db(self):
        return self.bot.db

    @app_commands.command(name="rarity", description="Show rarity tiers and how many fish are catchable right now.")
    async def rarity(self, interaction: discord.Interaction):
        if not self.dc.fish_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not ready", _PRELOAD_MSG), ephemeral=True
            )
            return
        hour = _utc_hour()
        embed = _build_rarity_embed(self.dc, hour)
        view = _DeleteView()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="event", description="Browse fishing events or view a specific event.")
    @app_commands.describe(name="Event name — leave blank for an overview of all events")
    async def event(self, interaction: discord.Interaction, name: str | None = None):
        if not self.dc.event_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not ready", _PRELOAD_MSG), ephemeral=True
            )
            return
        if not self.db:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not available", "Database unavailable."), ephemeral=True
            )
            return
        if name:
            event_obj = self.dc.event_by_name.get(name.lower())
            if event_obj is None:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("Not found", f"No event named **{name}** found."),
                    ephemeral=True,
                )
                return
            user_row = await self.db.get_or_create_user(str(interaction.user.id))
            embed = _build_event_detail_embed(event_obj, user_row["current_event"])
            view = EventDetailView(self.db, event_obj, str(interaction.user.id))
            await interaction.response.send_message(
                embed=embed,
                view=view,
            )
            view.message = await interaction.original_response()
        else:
            user_row = await self.db.get_or_create_user(str(interaction.user.id))
            events = sorted(self.dc.event_by_id.values(), key=lambda e: e.name)
            pages = _build_event_overview_pages(events, user_row["current_event"])
            view = EventOverviewView(pages)
            await interaction.response.send_message(embed=pages[0], view=view)
            view.message = await interaction.original_response()

    @event.autocomplete("name")
    async def event_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=e.name, value=e.name)
            for e in self.dc.event_by_id.values()
            if current.lower() in e.name.lower()
        ][:25]

    @app_commands.command(name="time", description="Show which fish are catchable right now and upcoming windows.")
    async def time(self, interaction: discord.Interaction):
        if not self.dc.fish_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not ready", _PRELOAD_MSG), ephemeral=True
            )
            return
        hour = _utc_hour()
        embed = _build_time_embed(self.dc, hour, None)
        view = TimeView(self.dc)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="today", description="Daily summary: current fish, top locations, and active event.")
    async def today(self, interaction: discord.Interaction):
        if not self.dc.fish_by_id:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Not ready", _PRELOAD_MSG), ephemeral=True
            )
            return
        hour = _utc_hour()
        try:
            db_row = await self.db.get_or_create_user(str(interaction.user.id))
        except Exception:
            db_row = None
        embed = _build_today_embed(self.dc, db_row, hour)
        view = _DeleteView()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


class _DeleteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.delete()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilitiesCog(bot))
