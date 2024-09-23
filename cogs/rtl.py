import random
from typing import List
from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord import app_commands
from discord.ext import commands

from _types import RTLPlayerModel, WarzoneCog
from config import Config
from database import Database
from utils import log_message
from warzone_api import WarzoneAPI


def pop_random(l: List):
    return l.pop(random.randrange(0, len(l)))


class RTLCommands(WarzoneCog):

    def __init__(
        self,
        bot: commands.Bot,
        config: Config,
        scheduler: AsyncIOScheduler,
        warzone_api: WarzoneAPI,
        database: Database,
    ) -> None:
        self.bot = bot
        self.config = config
        self.warzone_api = warzone_api
        self.database = database

        log_message("Scheduled RTLCommands.engine", "bot")
        self.scheduler = scheduler
        self.scheduler.add_job(
            self.run_engine, CronTrigger(hour="*", minute="*", second="0"), name="RTL"
        )
        self.scheduler.start()

    ########################
    ##### RTL commands #####
    ########################

    @commands.command(name="rtl_link")
    async def rtl_link(self, ctx: commands.Context):
        pass

    @commands.command(name="rtl_join")
    async def rtl_join(self, ctx: commands.Context, single_game: bool):
        pass

    @commands.command(name="rtl_leave")
    async def rtl_leave(self, ctx: commands.Context):
        pass

    @commands.command(name="rtl_add_channel")
    @commands.check_any(
        commands.is_owner(), commands.has_permissions(administrator=True)
    )
    async def rtl_add_channel(self, ctx: commands.Context):
        if ctx.channel.id not in self.config.rtl_channels:
            self.config.rtl_channels.append(ctx.channel.id)
            self.config.save_rtl_channels()
            await ctx.send(
                f"Successfully added '{ctx.channel.name}' to the RTL live updates"
            )
        else:
            await ctx.send(
                f"The channel, '{ctx.channel.name}', is already registered for RTL live updates"
            )

    @commands.command(name="rtl_remove_channel")
    @commands.check_any(
        commands.is_owner(), commands.has_permissions(administrator=True)
    )
    async def rtl_remove_channel(self, ctx: commands.Context):
        if ctx.channel.id in self.config.rtl_channels:
            self.config.rtl_channels.remove(ctx.channel.id)
            self.config.save_rtl_channels()
            await ctx.send(
                f"Successfully removed '{ctx.channel.name}' from the RTL live updates"
            )
        else:
            await ctx.send(
                f"The channel, '{ctx.channel.name}', is not currently registered for RTL live updates"
            )

    @commands.command(name="rtl_kill")
    @commands.is_owner()
    async def rtl_kill(self, ctx: commands.Context):
        job: Job = self.scheduler.get_job("RTL")
        job.pause()
        await ctx.send(f"Successfully shut off the RTL engine scheduler")

    ######################
    ##### RTL engine #####
    ######################

    async def update_player_ratings(
        self, winner: RTLPlayerModel, loser: RTLPlayerModel
    ):
        expected_score_winner = 1 / (1 + 10 ** ((loser.elo - winner.elo) / 400))
        expected_score_loser = 1 / (1 + 10 ** ((winner.elo - loser.elo) / 400))
        winner.elo += 32 * (1 - expected_score_winner)
        loser.elo += 32 * (1 - expected_score_loser)
        winner.wins += 1
        loser.losses += 1
        self.database.update_player(winner)
        self.database.update_player(loser)

    async def update_games(self):
        active_games = self.database.get_active_games()
        for game in active_games:
            pass

    async def create_games(self):
        active_players = self.database.get_active_players()

        pairs = []
        while len(active_players) > 1:
            pairs.append([pop_random(active_players), pop_random(active_players)])

        # create games

        # remove players that were given games

    async def run_engine(self):
        # runs every minute to check in-progress games, then create new games if possible
        await self.update_games()
        await self.create_games()
