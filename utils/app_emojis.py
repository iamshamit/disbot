"""Application emoji lookup populated at bot startup from data/app_emojis.json."""
from __future__ import annotations
import json
from pathlib import Path

import discord

_PATH = Path(__file__).parent.parent / "data" / "app_emojis.json"
_emojis: dict[str, discord.PartialEmoji] = {}


def load() -> int:
    """Load from data/app_emojis.json. Returns count loaded (0 if file missing)."""
    global _emojis
    if not _PATH.exists():
        return 0
    with open(_PATH, encoding="utf-8") as f:
        data: dict[str, dict] = json.load(f)
    _emojis = {
        item_id: discord.PartialEmoji(
            name=v["name"],
            id=v["emoji_id"],
            animated=v.get("animated", False),
        )
        for item_id, v in data.items()
    }
    return len(_emojis)


def get(item_id: str) -> discord.PartialEmoji | None:
    return _emojis.get(item_id)
