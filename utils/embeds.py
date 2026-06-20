import discord


class EmbedBuilder:
    DEFAULT_COLOR = 0x2F3136
    ERROR_COLOR = 0xED4245
    SUCCESS_COLOR = 0x57F287
    WARNING_COLOR = 0xFEE75C
    INFO_COLOR = 0x5865F2

    @staticmethod
    def _base(title: str = None, description: str = None, color: int = DEFAULT_COLOR):
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text="DankFishingBot")
        return embed

    @classmethod
    def info(cls, title: str, description: str = None):
        return cls._base(title=title, description=description, color=cls.INFO_COLOR)

    @classmethod
    def error(cls, title: str = "Something went wrong", description: str = None):
        embed = cls._base(title=f"\u274c {title}", description=description, color=cls.ERROR_COLOR)
        return embed

    @classmethod
    def success(cls, title: str, description: str = None):
        return cls._base(title=f"\u2705 {title}", description=description, color=cls.SUCCESS_COLOR)

    @classmethod
    def warning(cls, title: str, description: str = None):
        return cls._base(title=f"\u26a0\ufe0f {title}", description=description, color=cls.WARNING_COLOR)


from datetime import time as dt_time
import discord
from utils.formatters import (
    rarity_color, rarity_emoji, rarity_rank,
    availability_bar, is_available_now, format_time_window,
    winner_mark, COMPARE_COLOR, progress_bar, RARITY_EMOJI, RARITY_ORDER,
)

_SEP = "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"


def build_fish_embed(creature, dank_client) -> discord.Embed:
    extra = creature.extra
    boss = extra.get("boss", False)
    mythical = extra.get("mythical", False)
    rarity = extra.get("rarity", "Common")
    flavor = extra.get("flavor", "")
    time_data = extra.get("time", {})
    full_day = time_data.get("full_day", False)
    variants = extra.get("variants") or []

    embed = discord.Embed(title=creature.name, color=rarity_color(rarity, boss=boss))
    embed.set_author(name="\ud83d\udc1f Fish Encyclopedia")
    if creature.imageURL:
        embed.set_thumbnail(url=creature.imageURL)

    lines: list[str] = []
    if flavor:
        lines += [f'*"{flavor}"*', ""]

    rem = rarity_emoji(rarity)
    lines.append(
        f"{rem} **{rarity}**  \u00b7  \ud83d\udc51 Boss: {'\u2705' if boss else '\u274c'}  \u00b7  \u2728 Mythical: {'\u2705' if mythical else '\u274c'}"
    )

    # Availability
    lines += ["", _SEP, "**\ud83d\udd50 AVAILABILITY**"]
    start = time_data.get("start")
    end = time_data.get("end")
    if full_day:
        lines.append("\u2590" + "\u2588" * 24 + "\u258c  All Day")
    elif isinstance(start, dt_time) and isinstance(end, dt_time):
        bar = availability_bar(start.hour, end.hour, False)
        lines.append(f"\u2590{bar}\u258c  {format_time_window(creature)}")
        avail = "\u2705 Available" if is_available_now(creature) else "\u274c Not available"
        lines.append(f"Right now: {avail}")

    # Locations
    loc_ids = extra.get("locations") or []
    loc_names = [
        loc.name for lid in loc_ids
        if (loc := dank_client.location_by_id.get(lid)) is not None
    ]
    lines += ["", _SEP, f"**\ud83d\udccd LOCATIONS  ({len(loc_names)})**"]
    lines.append("  \u00b7  ".join(loc_names) if loc_names else "None")

    # Variants
    if variants:
        lines += ["", _SEP, f"**\ud83d\udd2e VARIANTS  ({len(variants)})**"]
        parts = []
        for v in variants:
            if isinstance(v, dict):
                parts.append(f"\u2728 {v.get('name', 'Unknown')}")
            else:
                parts.append(f"\u2728 {v}")
        lines.append("  \u00b7  ".join(parts))

    lines += ["", _SEP]
    embed.description = "\n".join(lines)[:4096]
    embed.set_footer(text=f"Internal ID: {creature.id}")
    return embed


def build_fish_compare_embed(c1, c2) -> discord.Embed:
    embed = discord.Embed(
        title=f"\u2694\ufe0f  {c1.name}  vs  {c2.name}",
        color=COMPARE_COLOR,
    )
    embed.set_author(name="\u2694\ufe0f Fish Compare")

    rows: list[tuple[str, str, str]] = []

    # Rarity
    r1, r2 = c1.extra.get("rarity", "Common"), c2.extra.get("rarity", "Common")
    rank1, rank2 = rarity_rank(r1), rarity_rank(r2)
    re1, re2 = rarity_emoji(r1), rarity_emoji(r2)
    rv1 = f"{re1} {r1} \u2713" if rank1 > rank2 else f"{re1} {r1}"
    rv2 = f"{re2} {r2} \u2713" if rank2 > rank1 else f"{re2} {r2}"
    rows.append(("Rarity", rv1, rv2))

    rows.append(("Boss", "\u2705" if c1.extra.get("boss") else "\u274c", "\u2705" if c2.extra.get("boss") else "\u274c"))
    rows.append(("Mythical", "\u2705" if c1.extra.get("mythical") else "\u274c", "\u2705" if c2.extra.get("mythical") else "\u274c"))

    w1, w2 = format_time_window(c1), format_time_window(c2)
    rows.append(("Window", w1, w2))

    l1, l2 = len(c1.extra.get("locations") or []), len(c2.extra.get("locations") or [])
    lv1, lv2 = winner_mark(l1, l2)
    rows.append(("Locations", lv1, lv2))

    var1, var2 = len(c1.extra.get("variants") or []), len(c2.extra.get("variants") or [])
    vv1, vv2 = winner_mark(var1, var2)
    rows.append(("Variants", vv1, vv2))

    lw = max(len(r[0]) for r in rows)
    c1w = max(len(c1.name), max(len(r[1]) for r in rows), 14)
    c2w = max(len(c2.name), max(len(r[2]) for r in rows), 14)

    header = f"{'':>{lw}} | {c1.name:<{c1w}} | {c2.name:<{c2w}}"
    divider = f"{'-'*lw}-+-{'-'*c1w}-+-{'-'*c2w}"
    table_rows = [f"{label:>{lw}} | {v1:<{c1w}} | {v2:<{c2w}}" for label, v1, v2 in rows]
    embed.description = "```\n" + "\n".join([header, divider] + table_rows) + "\n```"
    return embed


def build_peak_hours_embed(creature) -> discord.Embed:
    extra = creature.extra
    time_data = extra.get("time", {})
    full_day = time_data.get("full_day", False)
    start = time_data.get("start")
    end = time_data.get("end")

    embed = discord.Embed(
        title=f"\ud83d\udd50 Peak Hours \u2014 {creature.name}",
        color=rarity_color(extra.get("rarity", "Common"), boss=extra.get("boss", False)),
    )

    if full_day:
        embed.description = (
            "**This fish is available All Day** \u2014 every hour is active.\n\n"
            "`00 01 02 03 04 05 06 07 08 09 10 11`\n"
            "` \u2705  \u2705  \u2705  \u2705  \u2705  \u2705  \u2705  \u2705  \u2705  \u2705  \u2705  \u2705`\n\n"
            "`12 13 14 15 16 17 18 19 20 21 22 23`\n"
            "` \u2705  \u2705  \u2705  \u2705  \u2705  \u2705  \u2705  \u2705  \u2705  \u2705  \u2705  \u2705`"
        )
        return embed

    if not isinstance(start, dt_time) or not isinstance(end, dt_time):
        embed.description = "Availability data unavailable."
        return embed

    from datetime import datetime, timezone
    current_utc = datetime.now(timezone.utc)
    now_h = current_utc.hour

    avail = availability_bar(start.hour, end.hour, False)
    marks_am = []
    marks_pm = []
    for h in range(12):
        mark = "\u2705" if avail[h] == "\u2588" else "\u274c"
        cursor = f"[{mark}]" if h == now_h else f" {mark} "
        marks_am.append(cursor)
    for h in range(12, 24):
        mark = "\u2705" if avail[h] == "\u2588" else "\u274c"
        cursor = f"[{mark}]" if h == now_h else f" {mark} "
        marks_pm.append(cursor)

    avail_str = is_available_now(creature)
    window = format_time_window(creature)

    lines = [
        f"`00 01 02 03 04 05 06 07 08 09 10 11`",
        f"`{''.join(marks_am)}`",
        "",
        f"`12 13 14 15 16 17 18 19 20 21 22 23`",
        f"`{''.join(marks_pm)}`",
        "",
        f"Window: **{window}**",
        f"Current UTC: {current_utc.strftime('%H:%M')}  \u2192  {'\u2705 Available' if avail_str else '\u274c Not available'}",
    ]
    embed.description = "\n".join(lines)
    return embed


def build_fishlist_embed(
    creatures: list,
    page: int,
    total_pages: int,
    sort: str,
    rarity_filter: str,
) -> discord.Embed:
    from utils.formatters import COMPARE_COLOR, RARITY_COLORS
    color = RARITY_COLORS.get(rarity_filter, COMPARE_COLOR)
    title = f"All Fish  ({len(creatures)} total)" if rarity_filter == "All" else f"{rarity_filter} Fish  ({len(creatures)})"

    embed = discord.Embed(title=f"\ud83d\udc1f {title}", color=color)
    embed.set_author(name="\ud83d\udc1f Fish Encyclopedia")

    ITEMS = 10
    start_idx = page * ITEMS
    page_creatures = creatures[start_idx: start_idx + ITEMS]

    lines = []
    for c in page_creatures:
        extra = c.extra
        rarity = extra.get("rarity", "Common")
        boss = extra.get("boss", False)
        mythical = extra.get("mythical", False)
        avail = "\u2705" if is_available_now(c) else "\u274c"
        badges = ""
        if boss:
            badges += " \ud83d\udc51 BOSS"
        if mythical:
            badges += " \u2728 MYTHICAL"
        rem = rarity_emoji(rarity)
        lines.append(f"{rem} **{c.name}**{badges}  \u00b7  {avail} now")

    embed.description = "\n".join(lines) if lines else "*No fish match this filter.*"
    embed.set_footer(text=f"Page {page + 1} / {total_pages}  \u00b7  Sort: {sort}  \u00b7  Filter: {rarity_filter}")
    return embed
