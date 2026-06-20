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
    winner_mark, COMPARE_COLOR, progress_bar, RARITY_EMOJI, RARITY_ORDER,
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

    rows: list[tuple[str, str, str]] = []

    c1 = len(loc1.extra.get("creatures") or [])
    c2 = len(loc2.extra.get("creatures") or [])
    cv1, cv2 = winner_mark(c1, c2)
    rows.append(("Fish Pool", cv1, cv2))

    f1, f2 = loc1.extra.get("failChance", 0), loc2.extra.get("failChance", 0)
    fv1, fv2 = winner_mark(f1, f2, higher_is_better=False)
    rows.append(("Fail %", fv1, fv2))

    m1, m2 = loc1.extra.get("mineChance", 0), loc2.extra.get("mineChance", 0)
    mv1, mv2 = winner_mark(m1, m2, higher_is_better=False)
    rows.append(("Mine %", mv1, mv2))

    for rarity in ["Rare", "Very Rare", "Absurdly Rare", "Mythical"]:
        r1, r2 = _count(loc1, rarity), _count(loc2, rarity)
        rv1, rv2 = winner_mark(r1, r2)
        rows.append((f"{rarity[:8]} fish", rv1, rv2))

    lw = max(len(r[0]) for r in rows)
    c1w = max(len(loc1.name), max(len(r[1]) for r in rows), 12)
    c2w = max(len(loc2.name), max(len(r[2]) for r in rows), 12)
    header = f"{'':>{lw}} | {loc1.name:<{c1w}} | {loc2.name:<{c2w}}"
    divider = f"{'-'*lw}-+-{'-'*c1w}-+-{'-'*c2w}"
    table_rows = [f"{label:>{lw}} | {v1:<{c1w}} | {v2:<{c2w}}" for label, v1, v2 in rows]
    embed.description = "```\n" + "\n".join([header, divider] + table_rows) + "\n```"
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
    uv1, uv2 = winner_mark(u1, u2)

    rows: list[tuple[str, str, str]] = [
        ("Idle OK", "\u2705" if e1.get("idle") else "\u274c", "\u2705" if e2.get("idle") else "\u274c"),
        ("Usage", uv1, uv2),
        ("Effect", (e1.get("explanation") or "\u2014")[:40], (e2.get("explanation") or "\u2014")[:40]),
    ]

    lw = max(len(r[0]) for r in rows)
    c1w = max(len(bait1.name), max(len(r[1]) for r in rows), 12)
    c2w = max(len(bait2.name), max(len(r[2]) for r in rows), 12)
    header = f"{'':>{lw}} | {bait1.name:<{c1w}} | {bait2.name:<{c2w}}"
    divider = f"{'-'*lw}-+-{'-'*c1w}-+-{'-'*c2w}"
    table_rows = [f"{label:>{lw}} | {v1:<{c1w}} | {v2:<{c2w}}" for label, v1, v2 in rows]
    embed.description = "```\n" + "\n".join([header, divider] + table_rows) + "\n```"
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
