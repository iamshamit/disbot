import discord
import json as _skills_json


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


from datetime import time as dt_time, datetime, timezone
from utils.formatters import (
    rarity_color, rarity_emoji, rarity_rank,
    availability_bar, is_available_now, format_time_window,
    COMPARE_COLOR, progress_bar, RARITY_ORDER,
    RARITY_COLORS,
)

_SEP = "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"

import re as _re


def emoji_from_url(url: str | None) -> discord.PartialEmoji | None:
    if not url or not isinstance(url, str):
        return None
    m = _re.search(r'/emojis/(\d+)\.(png|gif)$', url)
    if not m:
        return None
    return discord.PartialEmoji(name='_', id=int(m.group(1)), animated=m.group(2) == 'gif')


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
    badge_parts = [f"{rem} **{rarity}**"]
    if boss:
        badge_parts.append("\ud83d\udc51 Boss")
    if mythical:
        badge_parts.append("\u2728 Mythical")
    lines.append("  \u00b7  ".join(badge_parts))

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

    # Tools section
    tools_data = extra.get("tools") or {}
    if tools_data and dank_client.tool_by_id:
        best_max = max((v.get("max", 0) for v in tools_data.values()), default=0)
        tool_lines = []
        for tid, catch in tools_data.items():
            t = dank_client.tool_by_id.get(tid)
            if t is None:
                continue
            lo, hi = catch.get("min", 0), catch.get("max", 0)
            star = "  \u2b50 Best" if hi == best_max and best_max > 0 else ""
            tool_lines.append(f"**{t.name}** \u2014 {lo}\u2013{hi}{star}")
        if tool_lines:
            lines += ["", _SEP, f"**\U0001f527 TOOLS  ({len(tool_lines)})**"]
            lines.extend(tool_lines)

    # Best Location
    loc_ids = extra.get("locations") or []
    best_loc = None
    best_fail = None
    for lid in loc_ids:
        loc = dank_client.location_by_id.get(lid)
        if loc is None:
            continue
        fail = loc.extra.get("failChance", 100) if hasattr(loc.extra, "get") else 100
        if best_fail is None or fail < best_fail or (fail == best_fail and loc.name < best_loc.name):
            best_fail = fail
            best_loc = loc
    if best_loc is not None:
        lines += ["", f"\U0001f4cd **Best Location:** {best_loc.name}  (fail: {best_fail}%)"]

    lines += ["", _SEP]
    embed.description = "\n".join(lines)[:4096]
    embed.set_footer(text=f"Internal ID: {creature.id}")
    return embed


def build_fish_compare_embed(c1, c2, dc=None) -> discord.Embed:
    embed = discord.Embed(
        title=f"\u2694\ufe0f  {c1.name}  vs  {c2.name}",
        color=COMPARE_COLOR,
    )
    embed.set_author(name="\u2694\ufe0f Fish Compare")

    r1, r2 = c1.extra.get("rarity", "Common"), c2.extra.get("rarity", "Common")
    rank1, rank2 = rarity_rank(r1), rarity_rank(r2)

    def _best_tool_info(c):
        tools_data = c.extra.get("tools") or {}
        if not tools_data:
            return "\u2014", 0
        best_max = max(v.get("max", 0) for v in tools_data.values())
        best_ids = [tid for tid, v in tools_data.items() if v.get("max", 0) == best_max]
        if dc and best_ids and best_ids[0] in dc.tool_by_id:
            name = dc.tool_by_id[best_ids[0]].name
        else:
            name = best_ids[0] if best_ids else "\u2014"
        return name, best_max

    bt1_name, bt1_max = _best_tool_info(c1)
    bt2_name, bt2_max = _best_tool_info(c2)

    def _col(c, other):
        ex, ox = c.extra, other.extra
        rarity = ex.get("rarity", "Common")
        rr = rarity_rank(rarity)
        orr = rarity_rank(ox.get("rarity", "Common"))
        locs = len(ex.get("locations") or [])
        olocs = len(ox.get("locations") or [])
        varis = len(ex.get("variants") or [])
        ovaris = len(ox.get("variants") or [])
        bt_name, bt_max = _best_tool_info(c)
        _, o_max = _best_tool_info(other)
        bt_mark = " \u2713" if bt_max > o_max or (bt_max == o_max and bt_max > 0) else ""
        mc_mark = " \u2713" if bt_max > o_max else ""
        return "\n".join([
            f"{rarity_emoji(rarity)} {rarity}" + (" \u2713" if rr > orr else ""),
            "\u2705" if ex.get("boss") else "\u274c",
            "\u2705" if ex.get("mythical") else "\u274c",
            format_time_window(c),
            str(locs) + (" \u2713" if locs > olocs else ""),
            str(varis) + (" \u2713" if varis > ovaris else ""),
            bt_name + bt_mark,
            str(bt_max) + mc_mark,
        ])

    embed.add_field(name="\u200b", value="**Rarity**\n**Boss**\n**Mythical**\n**Window**\n**Locations**\n**Variants**\n**Best Tool**\n**Max Catch**", inline=True)
    embed.add_field(name=c1.name, value=_col(c1, c2), inline=True)
    embed.add_field(name=c2.name, value=_col(c2, c1), inline=True)
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
    embed.set_footer(text=f"Page {page + 1} / {total_pages}  \u00b7  Sort: {sort}  \u00b7  Rarity: {rarity_filter}")
    return embed


def build_location_embed(location, dank_client) -> discord.Embed:
    extra = location.extra
    disabled = extra.get("disabled", False)
    temporary = extra.get("temporary", False)

    embed = discord.Embed(title=location.name, color=0x00b4d8)
    embed.set_author(name="\U0001f4cd Location")
    if extra.get("thumbnailURL"):
        embed.set_thumbnail(url=extra["thumbnailURL"])
    if extra.get("bannerURL"):
        embed.set_image(url=extra["bannerURL"])

    lines: list[str] = []
    status_parts = []
    if temporary:
        status_parts.append("\U0001f534 Temporary")
    if disabled:
        status_parts.append("\u26d4 Disabled")
    if status_parts:
        lines += ["  \u00b7  ".join(status_parts), ""]

    fail = extra.get("failChance", 0)
    mine = extra.get("mineChance", 0)
    creatures = extra.get("creatures") or []
    lines += [
        "**\U0001f30a STATISTICS**",
        f"\U0001f480 Fail: **{fail}%**   \u26cf\ufe0f Mine: **{mine}%**   \U0001f41f Pool: **{len(creatures)} fish**",
        "",
        _SEP,
    ]

    rarity_fish: dict = location.rarityFish or {}
    if rarity_fish:
        lines.append("**\U0001f308 RARITY DISTRIBUTION**")
        total_fish = sum(len(v) for v in rarity_fish.values())
        for rarity in RARITY_ORDER:
            bucket = rarity_fish.get(rarity, [])
            if not bucket:
                continue
            pct = round(len(bucket) / total_fish * 100) if total_fish else 0
            bar = progress_bar(pct, 100, width=20)
            lines.append(f"{rarity_emoji(rarity)} {rarity:<14} {bar}  {pct}%")
        lines += ["", _SEP]

    npcs = extra.get("npcs") or []
    if npcs:
        lines += ["**\U0001f464 NPCs**", "  \u00b7  ".join(npcs), "", _SEP]

    embed.description = "\n".join(lines)[:4096]
    embed.set_footer(text=f"Internal ID: {location.id}")
    return embed


def build_location_compare_embed(loc1, loc2) -> discord.Embed:
    embed = discord.Embed(
        title=f"\u2694\ufe0f  {loc1.name}  vs  {loc2.name}",
        color=COMPARE_COLOR,
    )
    embed.set_author(name="\u2694\ufe0f Location Compare")

    def _count(loc, rarity):
        return len((loc.rarityFish or {}).get(rarity, []))

    _RARITIES = ["Rare", "Very Rare", "Absurdly Rare", "Mythical"]
    labels = ["**Fish Pool**", "**Fail %**", "**Mine %**"] + [f"**{r[:8]} fish**" for r in _RARITIES]

    def _col(loc, other):
        ex, ox = loc.extra, other.extra
        lc = len(ex.get("creatures") or [])
        oc = len(ox.get("creatures") or [])
        fc, ofc = ex.get("failChance", 0), ox.get("failChance", 0)
        mc, omc = ex.get("mineChance", 0), ox.get("mineChance", 0)
        vals = [
            str(lc) + (" \u2713" if lc > oc else ""),
            str(fc) + (" \u2713" if fc < ofc else ""),
            str(mc) + (" \u2713" if mc < omc else ""),
        ]
        for rarity in _RARITIES:
            r, o = _count(loc, rarity), _count(other, rarity)
            vals.append(str(r) + (" \u2713" if r > o else ""))
        return "\n".join(vals)

    embed.add_field(name="\u200b", value="\n".join(labels), inline=True)
    embed.add_field(name=loc1.name, value=_col(loc1, loc2), inline=True)
    embed.add_field(name=loc2.name, value=_col(loc2, loc1), inline=True)
    return embed


def build_locations_list_embed(
    locations: list,
    page: int,
    total_pages: int,
    sort: str,
    filter_: str,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"\U0001f4cd All Locations  ({len(locations)} total)",
        color=0x00b4d8,
    )
    embed.set_author(name="\U0001f4cd Locations")

    ITEMS = 8
    start_idx = page * ITEMS
    page_locs = locations[start_idx: start_idx + ITEMS]

    lines = []
    for loc in page_locs:
        extra = loc.extra
        fish_count = len(extra.get("creatures") or [])
        fail = extra.get("failChance", 0)
        badges = ""
        if extra.get("temporary"):
            badges += " \U0001f534 Temp"
        if extra.get("disabled"):
            badges += " \u26d4"
        lines.append(f"\U0001f4cd **{loc.name}**{badges}  \u00b7  \U0001f41f {fish_count}  \u00b7  \U0001f480 {fail}%")

    embed.description = "\n".join(lines) if lines else "*No locations match this filter.*"
    embed.set_footer(text=f"Page {page + 1} / {total_pages}  \u00b7  Sort: {sort}  \u00b7  Filter: {filter_}")
    return embed


def build_tool_embed(tool, dc=None) -> discord.Embed:
    extra = tool.extra
    embed = discord.Embed(title=tool.name, color=0xff9500)
    embed.set_author(name="\U0001f527 Tool")
    if tool.imageURL:
        embed.set_thumbnail(url=tool.imageURL)

    lines: list[str] = []
    flavor = extra.get("flavor", "")
    if flavor:
        lines += [f'*"{flavor}"*', ""]

    buffs = extra.get("buffs") or []
    if buffs:
        lines += [_SEP, "**\u2728 BUFFS**"]
        for b in buffs:
            name = b.get("name", str(b)) if isinstance(b, dict) else str(b)
            lines.append(f"\u2022 {name}")

    debuffs = extra.get("debuffs") or []
    if debuffs:
        lines += ["", "**\U0001f4a2 DEBUFFS**"]
        for d in debuffs:
            name = d.get("name", str(d)) if isinstance(d, dict) else str(d)
            lines.append(f"\u2022 {name}")

    bait_support = "\u2705" if extra.get("baits") else "\u274c"
    usage = extra.get("usage", "?")
    lines += ["", _SEP, f"\U0001fab1 Bait Support: {bait_support}   \u00b7   \U0001f4ca Usage: {usage}", _SEP]

    # Supported Fish section (only when dc provided)
    if dc is not None:
        supported = [
            (f, (f.extra.get("tools") or {}).get(tool.id, {}))
            for f in dc.fish_by_id.values()
            if tool.id in (f.extra.get("tools") or {})
        ]
        if supported:
            supported.sort(key=lambda fc: fc[0].name.lower())
            best_tuple = max(supported, key=lambda fc: rarity_rank(fc[0].extra.get("rarity", "Common")))
            best_fish = best_tuple[0]
            best_catch = best_tuple[1]
            best_rarity = best_fish.extra.get("rarity", "Common")
            bc_lo, bc_hi = best_catch.get("min", 0), best_catch.get("max", 0)
            lines += ["", _SEP, f"**\ud83d\udc1f SUPPORTED FISH  ({len(supported)})**"]
            lines.append(
                f"Best: **{best_fish.name}** ({best_rarity}) \u2014 catches {bc_lo}\u2013{bc_hi}"
            )
            for fish, catch in supported[:12]:
                lo, hi = catch.get("min", 0), catch.get("max", 0)
                lines.append(f"**{fish.name}** \u2014 {lo}\u2013{hi}")
            if len(supported) > 12:
                lines.append(f"\u2026 and {len(supported) - 12} more")

    embed.description = "\n".join(lines)[:4096]
    embed.set_footer(text=f"Internal ID: {tool.id}")
    return embed


def build_toolcompare_embed(tools: list) -> discord.Embed:
    embed = discord.Embed(title="\u2694\ufe0f Tool Comparison", color=COMPARE_COLOR)
    embed.set_author(name="\u2694\ufe0f Tool Compare")

    headers = ["Tool", "Baits", "Usage", "Buffs", "Debuffs"]
    col_w = [max(len(h), max((len(t.name) for t in tools), default=4)) for h in headers]
    col_w[0] = max(len(h) for h in [t.name for t in tools] + [headers[0]])
    col_w[1] = max(len("Baits"), 5)
    col_w[2] = max(len("Usage"), 5)
    col_w[3] = max(len("Buffs"), 5)
    col_w[4] = max(len("Debuffs"), 7)

    def row_str(cells):
        return " | ".join(str(c).ljust(col_w[i]) for i, c in enumerate(cells))

    hrow = row_str(headers)
    sep = "-+-".join("-" * w for w in col_w)
    rows = [hrow, sep]
    for t in tools:
        extra = t.extra
        rows.append(row_str([
            t.name,
            "\u2705" if extra.get("baits") else "\u274c",
            extra.get("usage", "?"),
            len(extra.get("buffs") or []),
            len(extra.get("debuffs") or []),
        ]))
    embed.description = "```\n" + "\n".join(rows) + "\n```"
    embed.description = embed.description[:4096]
    return embed


def build_bait_embed(bait) -> discord.Embed:
    extra = bait.extra
    embed = discord.Embed(title=bait.name, color=0x95d44a)
    embed.set_author(name="\U0001fab1 Bait")
    if bait.imageURL:
        embed.set_thumbnail(url=bait.imageURL)

    lines: list[str] = []
    flavor = extra.get("flavor", "")
    if flavor:
        lines += [f'*"{flavor}"*', ""]

    explanation = extra.get("explanation", "")
    if explanation:
        lines += [_SEP, "**\U0001f4a1 WHAT IT DOES**", explanation]

    idle = "\u2705" if extra.get("idle") else "\u274c"
    usage = extra.get("usage", "?")
    lines += ["", _SEP, f"\U0001f916 Idle Compatible: {idle}   \u00b7   \U0001f4ca Usage: {usage}", _SEP]

    embed.description = "\n".join(lines)[:4096]
    embed.set_footer(text=f"Internal ID: {bait.id}")
    return embed


def build_bait_compare_embed(bait1, bait2) -> discord.Embed:
    embed = discord.Embed(
        title=f"\u2694\ufe0f  {bait1.name}  vs  {bait2.name}",
        color=COMPARE_COLOR,
    )
    embed.set_author(name="\u2694\ufe0f Bait Compare")

    e1, e2 = bait1.extra, bait2.extra

    def _col(ex, ox):
        u, ou = ex.get("usage", 0), ox.get("usage", 0)
        return "\n".join([
            "\u2705" if ex.get("idle") else "\u274c",
            str(u) + (" \u2713" if u > ou else ""),
            (ex.get("explanation") or "\u2014")[:60],
        ])

    embed.add_field(name="\u200b", value="**Idle OK**\n**Usage**\n**Effect**", inline=True)
    embed.add_field(name=bait1.name, value=_col(e1, e2), inline=True)
    embed.add_field(name=bait2.name, value=_col(e2, e1), inline=True)
    return embed


def build_npc_embed(npc) -> discord.Embed:
    embed = discord.Embed(title=npc.name, color=0xb967ff)
    embed.set_author(name="\U0001f464 NPC")
    if getattr(npc, "imageURL", None):
        embed.set_thumbnail(url=npc.imageURL)

    extra = getattr(npc, "extra", {})
    lines: list[str] = []

    for key in ("description", "flavor", "text"):
        desc = extra.get(key) if hasattr(extra, "get") else None
        if desc:
            lines += [f'*"{desc}"*', ""]
            break

    loc_data = extra.get("locations") if hasattr(extra, "get") else None
    if loc_data:
        lines += [_SEP, "**\U0001f4cd FOUND IN**"]
        if isinstance(loc_data, list):
            lines.append("  \u00b7  ".join(str(l) for l in loc_data))
        else:
            lines.append(str(loc_data))
    lines.append(_SEP)

    embed.description = "\n".join(lines)[:4096] if lines else "No additional data available."
    embed.set_footer(text=f"Internal ID: {getattr(npc, 'id', '?')}")
    return embed


_ROMAN = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX")


def _format_skills(skills_json: str | None, dc=None) -> str:
    if not skills_json:
        return "No skills unlocked"
    try:
        skills = _skills_json.loads(skills_json)
    except (ValueError, TypeError):
        return "No skills unlocked"
    if not skills:
        return "No skills unlocked"
    if dc and getattr(dc, "skill_categories", None):
        cat_parts = {}
        for cat, skill_list in dc.skill_categories.items():
            entries = []
            for s in skill_list:
                tier = skills.get(s["base"], 0)
                if tier > 0:
                    entries.append(f"{s['name']} {_ROMAN[min(tier, 9)]}")
            if entries:
                cat_parts[cat] = entries
        if not cat_parts:
            return "No skills unlocked"
        return "\n".join(f"{cat}: {', '.join(entries)}" for cat, entries in cat_parts.items())
    parts = []
    for base, tier in skills.items():
        if tier > 0:
            parts.append(f"{base.replace('-', ' ').title()} {_ROMAN[min(tier, 9)]}")
    return ", ".join(parts) if parts else "No skills unlocked"


def build_profile_embed(user_row, member, dc=None) -> discord.Embed:
    embed = discord.Embed(color=0x5865F2)
    embed.set_author(name="\U0001f464 Profile")
    embed.title = getattr(member, "display_name", str(member))
    if hasattr(member, "display_avatar") and member.display_avatar:
        embed.set_thumbnail(url=str(member.display_avatar.url))

    rod = user_row["fishing_rod"] or "Wooden Rod"
    tool = user_row["current_tool"] or "None"
    bait = user_row["current_bait"] or "None"
    embed.add_field(
        name="\U0001f3a3 SETUP",
        value=f"Rod: **{rod}**  ·  Tool: **{tool}**  ·  Bait: **{bait}**",
        inline=False,
    )

    try:
        skills_json = user_row["skills"]
    except (KeyError, IndexError):
        skills_json = None
    prestige = user_row["prestige"] or 0
    coins = user_row["coins"] or 0
    embed.add_field(
        name="\U0001f4ca SKILLS",
        value=(
            f"{_format_skills(skills_json, dc)}\n"
            f"Prestige: **{prestige}**  ·  Coins: **{coins:,}**"
        ),
        inline=False,
    )

    boss = "✅" if user_row["boss_unlock"] else "❌"
    myth = "✅" if user_row["mythical_unlock"] else "❌"
    embed.add_field(
        name="\U0001f513 UNLOCKS",
        value=f"\U0001f451 Boss: {boss}  ·  ✨ Mythical: {myth}",
        inline=False,
    )

    weather = user_row["current_weather"] or "None"
    event = user_row["current_event"] or "None"
    embed.add_field(
        name="\U0001f324️ ENVIRONMENT",
        value=f"Weather: **{weather}**  ·  Event: **{event}**",
        inline=False,
    )

    ff = user_row["favorite_fish"] or "None"
    fl = user_row["favorite_location"] or "None"
    ft = user_row["favorite_tool"] or "None"
    fb = user_row["favorite_bait"] or "None"
    embed.add_field(
        name="⭐ FAVOURITES",
        value=f"Fish: **{ff}**  ·  Location: **{fl}**\nTool: **{ft}**  ·  Bait: **{fb}**",
        inline=False,
    )

    embed.set_footer(text=f"Last updated: {user_row['updated_at'] or 'Never'}")
    return embed


def build_favorites_embed(favs_by_type: dict, member) -> discord.Embed:
    embed = discord.Embed(title="⭐ Your Favourites", color=0x5865F2)
    embed.set_author(name="⭐ Favourites")
    if hasattr(member, "display_avatar") and member.display_avatar:
        embed.set_thumbnail(url=str(member.display_avatar.url))
    type_labels = {
        "fish": ("\U0001f420 Fish", "fish"),
        "location": ("\U0001f4cd Locations", "location"),
        "tool": ("\U0001f527 Tools", "tool"),
        "bait": ("\U0001fab1 Baits", "bait"),
    }
    for key, (label, _) in type_labels.items():
        items = favs_by_type.get(key, [])
        value = ", ".join(items[:10]) if items else "None"
        embed.add_field(name=label, value=value, inline=False)
    if not any(favs_by_type.get(k) for k in favs_by_type):
        embed.description = (
            "You haven't favourited anything yet.\n"
            "Use the ⭐ button on any `/fish`, `/location`, `/tool`, or `/bait` embed."
        )
    return embed


def _relative_time(ts_str: str | None) -> str:
    if not ts_str:
        return "unknown"
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        delta = now - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return "just now"
        mins = secs // 60
        if mins < 60:
            return f"{mins}m ago"
        hours = mins // 60
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except (ValueError, TypeError):
        return str(ts_str)


def build_history_embed(rows: list, member, tab: str) -> discord.Embed:
    import json as _hj
    tab_labels = {
        "fish": "\U0001f420 Fish",
        "location": "\U0001f4cd Locations",
        "simulation": "\U0001f3ae Simulations",
        "command": "\U0001f4ac Commands",
    }
    embed = discord.Embed(
        title=f"\U0001f4dc Recent — {tab_labels.get(tab, tab)}",
        color=0x5865F2,
    )
    embed.set_author(name="\U0001f4dc History")
    if not rows:
        tab_display = tab_labels.get(tab, tab.capitalize())
        embed.description = f"No {tab_display} history yet."
        return embed
    lines = []
    for i, row in enumerate(rows, 1):
        item_id = row["item_id"] or "?"
        ts = _relative_time(row["created_at"])
        if tab == "simulation":
            fail_pct = ""
            try:
                d = _hj.loads(row["data"] or "{}")
                fail_pct = f"  ❌ {d.get('failChance', 0):.1f}%"
            except Exception:
                pass
            lines.append(f"`{i:>2}.` **{item_id}**{fail_pct} — {ts}")
        else:
            lines.append(f"`{i:>2}.` **{item_id}** — {ts}")
    embed.description = "\n".join(lines)
    return embed


def build_settings_embed(user_row) -> discord.Embed:
    tz = user_row["timezone"] or "UTC"
    theme = (user_row["theme"] or "dark").capitalize()
    compact = "On" if user_row["compact_mode"] else "Off"
    embed = discord.Embed(title="⚙️ Settings", color=0x5865F2)
    embed.set_author(name="⚙️ Settings")
    embed.description = (
        f"\U0001f30d **Timezone:** {tz}\n"
        f"\U0001f319 **Theme:** {theme}\n"
        f"\U0001f4c4 **Compact Mode:** {compact}\n"
        f"\U0001f514 **Notification Preferences:** *Coming in Phase 6*\n"
        f"\U0001f3ae **Default Simulator Values:** *Available*"
    )
    return embed
