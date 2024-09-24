import asyncio
from datetime import datetime, timedelta, timezone
import random
from typing import Dict, List, Tuple
from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord.ext import commands

from _types import Game, Player, WarzoneCog, WarzonePlayer
from config import Config
from database import RTLGameModel, RTLPlayerModel
from utils import log_message
from warzone_api import WarzoneAPI


def pop_random(l: List):
    return l.pop(random.randrange(0, len(l)))


RTL_TEMPLATES: List[Tuple[int, str]] = [
    [0, "name"],
]


class RTLCommands(WarzoneCog):

    def __init__(
        self,
        bot: commands.Bot,
        config: Config,
        scheduler: AsyncIOScheduler,
        warzone_api: WarzoneAPI,
    ) -> None:
        self.bot = bot
        self.config = config
        self.warzone_api = warzone_api

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
    async def rtl_join(self, ctx: commands.Context, join_single_game=True):
        player = await RTLPlayerModel.filter(discord_id=ctx.author.id).first()
        if player:
            player.active = True
            player.join_single_game = join_single_game
            await player.save()
            await ctx.send(
                f"{player.name} (ID: {player.warzone_id}) successfully joined the RTL ladder."
            )
        else:
            await ctx.send(
                f"No warzone player found linked to you. Use `\\rtl_link` to get instructions"
            )

    @commands.command(name="rtl_leave")
    async def rtl_leave(self, ctx: commands.Context):
        player = await RTLPlayerModel.filter(discord_id=ctx.author.id).first()
        if player:
            player.active = False
            player.join_single_game = False
            await player.save()
            await ctx.send(
                f"{player.name} (ID: {player.warzone_id}) successfully left the RTL ladder."
            )
        else:
            await ctx.send(
                f"No warzone player found linked to you. Use `\\rtl_link` to get instructions"
            )

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
        winner.active = not winner.join_single_game
        loser.active = not loser.join_single_game
        await asyncio.gather(winner.save(), loser.save())

    async def update_games(self):
        active_games = (
            await RTLGameModel.filter(ended=None)
            .all()
            .prefetch_related("player_a")
            .prefetch_related("player_b")
        )
        for game in active_games:
            warzone_game = self.warzone_api.check_game(game.id)
            if warzone_game.outcome == Game.Outcome.FINISHED:
                # Game newly finished
                winner = next(
                    player.id
                    for player in warzone_game.players
                    if player.outcome == WarzonePlayer.Outcome.WON
                )
                winner_player: RTLPlayerModel = (
                    game.player_a if game.player_a.id == winner else game.player_b
                )
                loser_player: RTLPlayerModel = (
                    game.player_a if game.player_a.id != winner else game.player_b
                )
                await self.update_player_ratings(winner_player, loser_player)
                game.ended = datetime.now()
                await game.save()
            elif game.outcome == Game.Outcome.WAITING_FOR_PLAYERS and datetime.now(
                timezone.utc
            ) - game.start_time > timedelta(minutes=5):
                # Game has expired lobby join time
                pass

    async def create_games(self):
        active_players = await RTLPlayerModel.filter(active=True).all()

        pairs: List[Tuple[RTLPlayerModel, RTLPlayerModel]] = []
        while len(active_players) > 1:
            pairs.append([pop_random(active_players), pop_random(active_players)])

        # create games
        for pair in pairs:
            template_id, template_name = random.choice(RTL_TEMPLATES)
            game_id = self.warzone_api.create_game(
                [pair[0].warzone_id, pair[1].warzone_id],
                template_id,
                "Title",
                "Description",
            )

            await RTLGameModel.create(
                id=game_id,
                created=datetime.now(),
                template=template_id,
                player_a=pair[0].warzone_id,
                player_b=pair[1].warzone_id,
            )

        # remove players that were given games
        for pair in pairs:
            pair[0].active = False
            pair[1].active = False
            await asyncio.gather(pair[0].save(), pair[1].save())

    async def run_engine(self):
        # runs every minute to check in-progress games, then create new games if possible
        await self.update_games()
        await self.create_games()
