from typing import Any, List
from tortoise import run_async

from _types import WarzoneCog
from cogs.cl import CLCommands
from cogs.rtl import RTLCommands
import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands
from cogs.util import UtilCommands
from config import Config
from database import init
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


COGS_TO_INITIATLIZE: List[type[WarzoneCog]] = [
    CLCommands,
    # RTLCommands, # temp disable while WIP
    UtilCommands,
]


class WarzoneBot(commands.Bot):

    def __init__(self, **options: Any) -> None:
        super().__init__(command_prefix="jr!", intents=intents, **options)
        self.config = Config()
        self.has_loaded_cogs = False
        self.scheduler = AsyncIOScheduler()
        self.warzone_api = WarzoneAPI(self.config)
        self.run(self.config.discord_token)

    @commands.command(name="sync")
    async def sync(self, ctx):
        synced = await self.tree.sync()
        print(f"Synced {len(synced)} command(s).")
        await ctx.send(f"Synced {len(synced)} command(s).")

    async def on_ready(self):
        # Add each individual cog to the bot
        # The __init__ should add jobs if scheduler required
        if not self.has_loaded_cogs:
            # only add cogs once
            for cog in COGS_TO_INITIATLIZE:
                await self.add_cog(
                    cog(self, self.config, self.scheduler, self.warzone_api)
                )
            self.scheduler.start()
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s).")
            self.has_loaded_cogs = True


run_async(init())
WarzoneBot()
