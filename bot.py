import asyncio
import logging
import signal
import sys
import time
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

import config
import utils.app_emojis as _ae
from dankmemer_client import DankMemerGameClient
from utils.db import Database
from utils.logging_config import setup_logging
from utils.autocomplete import AutocompleteIndex

logger = logging.getLogger(__name__)


class DankFishingBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.dank_client: DankMemerGameClient | None = None
        self.db: Database | None = None
        self.autocomplete: AutocompleteIndex | None = None
        self._shutdown_event = asyncio.Event()
        self._command_start_times: dict[int, float] = {}
        self._preload_task: asyncio.Task | None = None

    async def setup_hook(self) -> None:
        if sys.platform != 'win32':
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.close()))
        self.db = Database(config.DB_PATH)
        await self.db.connect()
        self.dank_client = DankMemerGameClient(
            cache_ttl_hours=config.DANKMEMER_CACHE_TTL_HOURS
        )
        await self.dank_client.connect()
        n = _ae.load()
        if n:
            logger.info("Loaded %d application emojis", n)
        self.autocomplete = AutocompleteIndex(self.dank_client)
        await self._load_cogs()
        self.tree.on_error = self._tree_error_handler
        if config.COMMAND_GUILD_IDS:
            for guild_id in config.COMMAND_GUILD_IDS:
                guild = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def _load_cogs(self) -> None:
        cogs_dir = Path(__file__).parent / "cogs"
        for cog_file in cogs_dir.glob("*.py"):
            if cog_file.name.startswith("_"):
                continue
            cog_name = f"cogs.{cog_file.stem}"
            try:
                await self.load_extension(cog_name)
                logger.info("Loaded cog: %s", cog_name)
            except Exception as e:
                logger.error("Failed to load cog %s: %s", cog_name, e)

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (%s)", self.user, self.user.id)
        logger.info("Guilds: %d", len(self.guilds))
        if self.dank_client and not self.dank_client.fish_by_id:
            if self._preload_task is None or self._preload_task.done():
                self._preload_task = self.loop.create_task(self._preload_data())

    async def _preload_data(self) -> None:
        try:
            await self.dank_client.preload()
            logger.info("Background preload complete")
        except Exception:
            logger.exception("Background preload failed")

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type == discord.InteractionType.application_command:
            now = time.monotonic()
            self._command_start_times = {
                k: v for k, v in self._command_start_times.items() if now - v < 60
            }
            self._command_start_times[interaction.id] = now

    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command) -> None:
        start = self._command_start_times.pop(interaction.id, None)
        duration_ms = int((time.monotonic() - start) * 1000) if start else 0
        logger.info("Command /%s executed by %s in %dms", command.name, interaction.user.id, duration_ms)

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        logger.error("Unhandled error in %s", event_method, exc_info=True)

    async def _tree_error_handler(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        from utils.embeds import EmbedBuilder
        if isinstance(error, app_commands.CommandInvokeError):
            original = error.original
            logger.error("Command error in %s: %s", interaction.command.name if interaction.command else "unknown", original, exc_info=True)
            embed = EmbedBuilder.error("Command failed", "An unexpected error occurred.")
        elif isinstance(error, app_commands.CheckFailure):
            embed = EmbedBuilder.error("Access denied", "You don't have permission to use this command.")
        else:
            logger.error("App command error: %s", error, exc_info=True)
            embed = EmbedBuilder.error("Error", str(error))
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            logger.warning("Failed to send error response to expired interaction", exc_info=True)

    async def close(self) -> None:
        logger.info("Shutting down gracefully...")
        if self.dank_client:
            try:
                await self.dank_client.close()
            except Exception:
                logger.warning("Error closing DankMemerClient", exc_info=True)
        if self.db:
            try:
                await self.db.close()
            except Exception:
                logger.warning("Error closing database", exc_info=True)
        await super().close()
        self._shutdown_event.set()

    def run_bot(self) -> None:
        try:
            super().run(config.DISCORD_BOT_TOKEN, log_handler=None)
        except Exception:
            logger.error("Bot crashed", exc_info=True)
            raise


def main():
    setup_logging(config.LOG_LEVEL)
    bot = DankFishingBot()
    bot.run_bot()


if __name__ == "__main__":
    main()
