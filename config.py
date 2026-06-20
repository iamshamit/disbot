import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
if not _DISCORD_BOT_TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is required")

OWNER_ID = os.getenv("OWNER_ID", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DANKMEMER_CACHE_TTL_HOURS = int(os.getenv("DANKMEMER_CACHE_TTL_HOURS", "1"))
DB_PATH = Path(os.getenv("DB_PATH", "data/dankbot.db")).resolve()
DEBUG = os.getenv("DEBUG", "0") == "1"
COMMAND_GUILD_ID = os.getenv("COMMAND_GUILD_ID", "") or None
