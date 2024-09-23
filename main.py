from typing import Any, List

from _types import WarzoneCog
from cogs.rtl import RTLCommands
import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands
from config import Config
from database import Database
from utils import log_exception, log_message
from warzone_api import WarzoneAPI

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True


ROUND_TO_EMBED = {
    "Qualifiers": 1264965867419074611,
    "Main": 1271678678048444578,
    "Finals": 0,
}


COGS_TO_INITIATLIZE: List[type[WarzoneCog]] = [RTLCommands]


class WarzoneBot(commands.Bot):

    def __init__(self, **options: Any) -> None:
        super().__init__(command_prefix="jr!", intents=intents, **options)
        self.config = Config()
        self.scheduler = AsyncIOScheduler()
        self.warzone_api = WarzoneAPI(self.config)
        self.database = Database(self.config)
        self.run(self.config.discord_token)

    async def on_ready(self):
        # Add each individual cog to the bot
        # The __init__ should add jobs if scheduler required
        for cog in COGS_TO_INITIATLIZE:
            await self.add_cog(
                cog(self, self.config, self.scheduler, self.api, self.database)
            )
        self.scheduler.start()
        synced = await self.tree.sync()
        print(f"Synced {len(synced)} command(s).")


WarzoneBot()
