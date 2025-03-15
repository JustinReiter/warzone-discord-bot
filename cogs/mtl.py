# https://warlight-mtl.com/api/v1.0/players/

from datetime import datetime
import random
from typing import Dict, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import discord
from discord import app_commands
from discord.ext import commands
import requests

from _types import WarzoneCog
from config import Config
from database import MTLChannel
from sheet import GoogleSheet
from utils import log_exception, log_message
from warzone_api import WarzoneAPI

MTL_API_LINK = "https://warlight-mtl.com/api/v1.0/players/?topk=10"
MTL_GAME_API_LINK = "https://warlight-mtl.com/api/v1.0/games/?topk=10"


class MTLCommands(WarzoneCog):

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

        log_message("Scheduled MTLCommands.engine", "bot")
        self.scheduler = scheduler
        self.scheduler.add_job(
            self.run_engine,
            CronTrigger(hour="*", minute="40", second="0"),
            name="MTL_engine",
        )

    #######################
    ##### CL commands #####
    #######################

    def get_mtl_player_data(self):
        return requests.get(f"{MTL_API_LINK}", verify=False).json()

    def get_mtl_game_data(self):
        return requests.get(f"{MTL_GAME_API_LINK}", verify=False).json()

    def format_discord_embed(self, player_data, game_data):
        embed = discord.Embed(
            title="[MTL Standings](https://www.warlight-mtl.com/)",
            color=discord.Color.red(),
        )

        player_str = "```    Player               | Rating | Best"
        for player in player_data["players"]:
            player_str += f'\n{player["rank"]:>2}. {player["player_name"]:<20} | {player["displayed_rating"]:>6} | {player["best_displayed_rating"]:>4}'
        embed.add_field(
            name=f"Ranked players",
            value=f"{player_str}```",
            inline=False,
        )

        game_str = "**Recent games:**\n"
        for game in game_data["games"]:
            winner = (
                game["players"][0]
                if game["players"][0]["player_id"] == game["winner_id"]
                else game["players"][1]
            )
            loser = (
                game["players"][0]
                if game["players"][0]["player_id"] != game["winner_id"]
                else game["players"][1]
            )

            game_str += f'**{winner["player_name"]}** defeats **{loser["player_name"]}** ([{game["finish_date"]}](https://www.warzone.com/MultiPlayer?GameID={game["game_id"]}))\n'
        embed.description = game_str

        embed.timestamp = datetime.now()
        embed.set_footer(text="Contact JustinR17 to add this live update")

        return embed

    @app_commands.command(
        name="mtl_create_embeds",
        description="Create embeds for MTL. Only Justin can use this command.",
    )
    @commands.is_owner()
    async def mtl_create_embeds(self, interaction: discord.Interaction):
        # new embed
        does_channel_exist = await MTLChannel.filter(id=interaction.channel.id).exists()
        if does_channel_exist:
            log_message("", "mtl.mtl_create_embeds")
            return await interaction.response.send_message(
                "This channel already has an MTL standings post created"
            )

        player_data = self.get_mtl_player_data()
        game_data = self.get_mtl_game_data()
        embed = self.format_discord_embed(player_data, game_data)
        new_embed = await interaction.response.send_message(embed=embed)
        await MTLChannel.create(
            id=interaction.channel.id,
            channel_name=interaction.channel.name,
            server_id=interaction.guild.id,
            message_id=new_embed.message_id,
        )

    #####################
    ##### CL engine #####
    #####################

    async def update_mtl_standings_embeds(self):
        try:
            player_data = self.get_mtl_player_data()
            game_data = self.get_mtl_game_data()
            embed = self.format_discord_embed(player_data, game_data)

            for channel in await MTLChannel.all():
                discord_channel = await self.bot.fetch_channel(channel.id)
                message = await discord_channel.fetch_message(channel.message_id)
                await message.edit(embed=embed)
        except Exception as e:
            log_exception(e)

    async def run_engine(self):
        # runs every hour to update the discord CL server standings embed with latest sheet info
        await self.update_mtl_standings_embeds()
