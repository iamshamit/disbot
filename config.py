import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
if not _DISCORD_BOT_TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is required")
DISCORD_BOT_TOKEN = _DISCORD_BOT_TOKEN

OWNER_ID = os.getenv("OWNER_ID", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
try:
    DANKMEMER_CACHE_TTL_HOURS = int(os.getenv("DANKMEMER_CACHE_TTL_HOURS", "1"))
except ValueError:
    raise RuntimeError("DANKMEMER_CACHE_TTL_HOURS must be a valid integer")
DB_PATH = Path(os.getenv("DB_PATH", "data/dankbot.db")).resolve()
DEBUG = os.getenv("DEBUG", "0") == "1"
_COMMAND_GUILD_IDS_RAW = os.getenv("COMMAND_GUILD_ID", "") or None
COMMAND_GUILD_IDS: list[int] = []
if _COMMAND_GUILD_IDS_RAW:
    for part in _COMMAND_GUILD_IDS_RAW.split(","):
        part = part.strip()
        if part:
            try:
                COMMAND_GUILD_IDS.append(int(part))
            except ValueError:
                raise RuntimeError(f"COMMAND_GUILD_ID contains invalid guild ID: {part!r}")
