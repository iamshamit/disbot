import pytest
from datetime import time as dt_time
from dankmemer.utils import DotDict
from dankmemer.routes.creatures import Creature
from dankmemer.routes.locations import Location
from dankmemer.routes.tools import Tool
from dankmemer.routes.baits import Bait


def make_creature(
    id="goldfish",
    name="Goldfish",
    imageURL="https://cdn.discordapp.com/emojis/1109186607120130049.png",
    rarity="Common",
    boss=False,
    mythical=False,
    flavor="A shiny fish.",
    locations=None,
    start_h=0,
    end_h=6,
    full_day=False,
    variants=None,
    tools=None,
):
    time_data = {"full_day": full_day}
    if not full_day:
        time_data["start"] = dt_time(hour=start_h)
        time_data["end"] = dt_time(hour=end_h)
    extra = DotDict({
        "boss": boss,
        "mythical": mythical,
        "rarity": rarity,
        "flavor": flavor,
        "locations": locations or ["loc1"],
        "time": time_data,
        "variants": variants or [],
        "tools": tools or {},
    })
    return Creature(id=id, name=name, imageURL=imageURL, extra=extra)


def make_location(
    id="sunken_ship",
    name="Sunken Ship",
    imageURL="https://cdn.discordapp.com/emojis/1157173307263688754.png",
    bannerURL="https://example.com/banner.png",
    thumbnailURL="https://example.com/thumb.png",
    creatures=None,
    disabled=False,
    temporary=False,
    failChance=10,
    mineChance=5,
    npcs=None,
    rarity_fish=None,
    loc_type="saltwater",
):
    extra = DotDict({
        "bannerURL": bannerURL,
        "thumbnailURL": thumbnailURL,
        "creatures": creatures or ["goldfish"],
        "disabled": disabled,
        "temporary": temporary,
        "failChance": failChance,
        "mineChance": mineChance,
        "npcs": npcs or [],
        "days": [],
        "type": loc_type,
    })
    return Location(
        id=id,
        name=name,
        imageURL=imageURL,
        extra=extra,
        rarityFish=rarity_fish or {"Common": ["goldfish"]},
        variantsData={},
    )


def make_tool(
    id="rod",
    name="Fishing Rod",
    imageURL="https://example.com/rod.png",
    flavor="The classic choice.",
    baits=True,
    buffs=None,
    debuffs=None,
    usage=100,
):
    extra = DotDict({
        "flavor": flavor,
        "baits": baits,
        "buffs": buffs or [{"name": "+20% Common catch"}],
        "debuffs": debuffs or [],
        "usage": usage,
    })
    return Tool(id=id, name=name, imageURL=imageURL, extra=extra)


def make_bait(
    id="glitter",
    name="Glitter Bait",
    imageURL="https://example.com/bait.png",
    flavor="Sparkly.",
    explanation="Increases Rare catch by 15%.",
    idle=True,
    usage=50,
):
    extra = DotDict({
        "flavor": flavor,
        "explanation": explanation,
        "idle": idle,
        "usage": usage,
    })
    return Bait(id=id, name=name, imageURL=imageURL, extra=extra)


@pytest.fixture
def creature():
    return make_creature()


@pytest.fixture
def boss_creature():
    return make_creature(id="kraken", name="Kraken", rarity="Absurdly Rare", boss=True)


@pytest.fixture
def fullday_creature():
    return make_creature(id="koi", name="Koi", rarity="Uncommon", full_day=True)


@pytest.fixture
def location():
    return make_location()


@pytest.fixture
def tool():
    return make_tool()


@pytest.fixture
def bait():
    return make_bait()
