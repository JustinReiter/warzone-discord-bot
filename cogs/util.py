from datetime import datetime
import random
from typing import Dict, List, Tuple
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import discord
from discord import app_commands
from discord.ext import commands

from _types import FullWarzoneGame, WarzoneCog
from config import Config
from sheet import GoogleSheet
from utils import log_exception, log_message
from warzone_api import WarzoneAPI


class UtilCommands(WarzoneCog):

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

        log_message("Scheduled UtilCommands.engine", "bot")
        # self.scheduler = scheduler
        # self.scheduler.add_job(
        #     self.run_engine,
        #     CronTrigger(hour="*", minute="25", second="0"),
        #     name="CL_engine",
        # )

    #########################
    ##### Util functions ####
    #########################

    def create_custom_scenario_settings(
        self, game: FullWarzoneGame, turn_number: int
    ) -> Dict:
        custom_scenario = []
        for territory in game.standings[turn_number]:
            custom_scenario.append(
                {
                    "terr": territory["terrID"],
                    "armies": territory["armies"],
                }
            )
            if territory["ownedBy"] != "Neutral":
                for i, p in enumerate(game.players):
                    if territory["ownedBy"] == str(p.id)[2:-2]:
                        custom_scenario[-1]["slot"] = f"{i}"
                        break
        game.settings["CustomScenario"] = custom_scenario
        return game.settings

    def create_game_at_picks(self, game: FullWarzoneGame) -> Tuple[Dict, Dict]:
        return game.settings, game.distribution_standing

    #########################
    ##### Util commands #####
    #########################

    @app_commands.command(
        name="util_custom_game",
        description="Creates custom scenario of game. Only Justin can use this command.",
    )
    @app_commands.describe(
        game_id="Game ID to clone found in the URL of the game page.",
        turn_number="Turn number to clone from between 0 and max turn length. The number should be the same as viewing the turn in history.",
        players="Comma-separated list of player IDs to invite to the game.",
    )
    async def util_custom_game(
        self,
        interaction: discord.Interaction,
        game_id: int,
        turn_number: int,
        players: str,
        without_fog: bool = True,
    ):
        log_message(
            f"User: {interaction.user.name} ({interaction.user.id}) in {interaction.guild.name}. Creating custom game from {game_id} at turn {turn_number} with players {players}",
            "util.util_custom_game",
        )
        game = self.warzone_api.query_game_full(game_id)
        if not (0 <= turn_number <= game.round):
            await interaction.response.send_message(
                "Invalid turn number. Must be between 0 and max turn length in game."
            )
            return

        if turn_number >= 0:
            settings = self.create_custom_scenario_settings(game, turn_number)

        if without_fog:
            game.settings["Fog"] = "NoFog"

        new_game_id = self.warzone_api.create_custom_scenario_game(
            [[player, f"{i}"] for i, player in enumerate(players.split(","))],
            "JR17 - Custom Scenario Game",
            f"This game was created by cloning {game_id} at turn {turn_number}.",
            settings,
        )

        await interaction.response.send_message(
            f"Game created: <https://www.warzone.com/MultiPlayer?GameID={new_game_id}>"
        )
