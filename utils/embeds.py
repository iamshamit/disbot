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


from datetime import time as dt_time, datetime, timezone
from utils.formatters import (
    rarity_color, rarity_emoji, rarity_rank,
    availability_bar, is_available_now, format_time_window,
    COMPARE_COLOR, progress_bar, RARITY_ORDER,
    RARITY_COLORS,
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

    r1, r2 = c1.extra.get("rarity", "Common"), c2.extra.get("rarity", "Common")
    rank1, rank2 = rarity_rank(r1), rarity_rank(r2)
    l1 = len(c1.extra.get("locations") or [])
    l2 = len(c2.extra.get("locations") or [])
    var1 = len(c1.extra.get("variants") or [])
    var2 = len(c2.extra.get("variants") or [])

    def _col(c, other):
        ex, ox = c.extra, other.extra
        rarity = ex.get("rarity", "Common")
        rr = rarity_rank(rarity)
        orr = rarity_rank(ox.get("rarity", "Common"))
        locs = len(ex.get("locations") or [])
        olocs = len(ox.get("locations") or [])
        varis = len(ex.get("variants") or [])
        ovaris = len(ox.get("variants") or [])
        return "\n".join([
            f"{rarity_emoji(rarity)} {rarity}" + (" \u2713" if rr > orr else ""),
            "\u2705" if ex.get("boss") else "\u274c",
            "\u2705" if ex.get("mythical") else "\u274c",
            format_time_window(c),
            str(locs) + (" \u2713" if locs > olocs else ""),
            str(varis) + (" \u2713" if varis > ovaris else ""),
        ])

    embed.add_field(name="\u200b", value="**Rarity**\n**Boss**\n**Mythical**\n**Window**\n**Locations**\n**Variants**", inline=True)
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
    embed.set_footer(text=f"Page {page + 1} / {total_pages}  \u00b7  Sort: {sort}  \u00b7  Filter: {rarity_filter}")
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


def build_tool_embed(tool) -> discord.Embed:
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
    u1, u2 = e1.get("usage", 0), e2.get("usage", 0)

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
