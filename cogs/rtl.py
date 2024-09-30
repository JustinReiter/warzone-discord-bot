import asyncio
from datetime import datetime, timedelta, timezone
import random
from typing import List, Tuple
from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import discord
from discord import app_commands
from discord.ext import commands
from tortoise.expressions import Q
import requests

from _types import Game, WarzoneCog, WarzonePlayer
from config import Config
from database import RTLGameModel, RTLPlayerModel
from utils import log_exception, log_message
from warzone_api import WarzoneAPI


def pop_random(l: List):
    return l.pop(random.randrange(0, len(l)))


RTL_TEMPLATES: List[Tuple[int, str]] = [
    (1540231, "Strategic MME"),
    (1540232, "Battle Islands V"),
    (1540234, "French Brawl"),
    (1540235, "Volcano Island"),
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

    ########################
    ##### RTL commands #####
    ########################

    @app_commands.command(
        name="rtl_link",
        description="Link your warzone account to your discord account.",
    )
    async def rtl_link(self, interaction: discord.Interaction, token: str):
        try:
            if not token:
                return await interaction.response.send_message(
                    "You need to provide a token from site"
                )
            players = requests.get(
                "http://127.0.0.1:8000/admin_get_users?auth=97FKog0F0tjVAsjT2Fvgem09d3xnnU9vjV8x1LydrHhZYvqD",
            ).json()
            for player in players:
                if player["token"] == token:
                    # create new player
                    await RTLPlayerModel.create(
                        warzone_id=player["id"],
                        name=player["name"],
                        discord_id=interaction.user.id,
                    )
                    log_message(
                        f"{interaction.user.name} ({interaction.user.id}) linked their discord to warzone: {player['name']} ({player['id']})",
                        "RTL.link",
                    )
                    return await interaction.response.send_message(
                        f"Successfully created new player linking {interaction.user.name} to {player['name']} on warzone"
                    )
            return await interaction.response.send_message(
                f"Unable to find player with the associated token"
            )
        except Exception as e:
            log_exception(e)

    @app_commands.command(
        name="rtl_join",
        description="Joins the RTL ladder. Specify second value as False to stay after one game.",
    )
    async def rtl_join(
        self, interaction: discord.Interaction, join_single_game: bool = True
    ):
        try:
            player = await RTLPlayerModel.filter(discord_id=interaction.user.id).first()
            if player and (
                not player.active or player.join_single_game != join_single_game
            ):
                # if player exists AND player is not active or switching b/w single vs multiple games
                player.active = True
                player.join_single_game = join_single_game
                await player.save()
                log_message(
                    f"{interaction.user.name} ({interaction.user.id}) joined the RTL ladder with {join_single_game=}.",
                    "RTL.join",
                )
                await interaction.response.send_message(
                    f"[{player.name}](<https://www.warzone.com/Profile?p={player.warzone_id}>) successfully joined the RTL ladder."
                )
                await self.notify_active_players()
            elif player:
                # if player is already joined and has same game preference
                await interaction.response.send_message(
                    f"[{player.name}](<https://www.warzone.com/Profile?p={player.warzone_id}>) is already joined to the RTL ladder."
                )
            else:
                # player is not found
                await interaction.response.send_message(
                    f"No warzone player found linked to you. Use `/rtl_link` to get instructions"
                )
        except Exception as e:
            log_exception(e)

    @app_commands.command(name="rtl_leave", description="Leave the RTL ladder.")
    async def rtl_leave(self, interaction: discord.Interaction):
        try:
            player = await RTLPlayerModel.filter(discord_id=interaction.user.id).first()
            if player and player.active:
                player.active = False
                player.join_single_game = False
                await player.save()
                log_message(
                    f"{interaction.user.name} ({interaction.user.id}) left the RTL ladder.",
                    "RTL.leave",
                )
                await interaction.response.send_message(
                    f"[{player.name}](<https://www.warzone.com/Profile?p={player.warzone_id}>) successfully left the RTL ladder."
                )
                await self.notify_active_players()
            elif player:
                await interaction.response.send_message(
                    f"[{player.name}](<https://www.warzone.com/Profile?p={player.warzone_id}>) is not joined to the RTL ladder."
                )
            else:
                await interaction.response.send_message(
                    f"No warzone player found linked to you. Use `/rtl_link` to link your warzone account"
                )
        except Exception as e:
            log_exception(e)

    @app_commands.command(
        name="rtl_standings", description="Show the top 10 players on the RTL."
    )
    async def rtl_standings(self, interaction: discord.Interaction):
        try:
            # Called whenever there is a change to active players on the RTL (added/removed)
            players = await RTLPlayerModel.filter().order_by("-elo").limit(10).all()

            embed = discord.Embed(
                title=f"JR17's real-time ladder - standings",
            )
            # players are joined to the ladder
            active_players_list = []
            for i, player in enumerate(players):
                active_players_list.append(
                    f"{i+1:2}. {player.elo:.0f} - [{player.name}](<https://www.warzone.com/Profile?p={player.warzone_id}>)  ({player.wins}W - {player.losses}L)"
                )
            embed.description = "\n".join(active_players_list)
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            log_exception(e)

    @app_commands.command(name="rtl_profile", description="Show a players RTL profile.")
    async def rtl_profile(self, interaction: discord.Interaction, discord_id: str):
        try:
            discord_id: int = int(discord_id)
            # Called whenever there is a change to active players on the RTL (added/removed)
            player = await RTLPlayerModel.filter(discord_id=discord_id).first()
            if not player:
                # no player found
                pass

            player_games = (
                await RTLGameModel.filter(
                    Q(player_a=player) | Q(player_b=player), ended__not_isnull=True
                )
                .order_by("-ended")
                .limit(10)
                .prefetch_related("player_a", "player_b", "winner")
                .all()
            )
            embed = discord.Embed(
                title=f"JR17's real-time ladder - profile",
            )
            # players are joined to the ladder
            games_list = []
            for game in player_games:
                other_player: RTLPlayerModel = (
                    game.player_b
                    if game.player_a_id == player.warzone_id
                    else game.player_a
                )
                games_list.append(
                    f"{'WON ' if game.winner_id == player.warzone_id else 'LOST' } vs [{other_player.name}](<https://www.warzone.com/Profile?p={other_player.warzone_id}>) - [link](https://www.warzone.com/MultiPlayer?GameID={game.id}) - {other_player.elo:.0f} ({other_player.wins}W - {other_player.losses}L)"
                )
            embed.description = (
                f"[{player.name}](<https://www.warzone.com/Profile?p={player.warzone_id}>) - {player.elo:.0f} ({player.wins}W - {player.losses}L)\n\n"
                + "\n".join(games_list)
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            log_exception(e)

    @app_commands.command(
        name="rtl_add_channel",
        description="Add the current channel to receive updates from the RTL ladder.",
    )
    @commands.check_any(
        commands.is_owner(), commands.has_permissions(administrator=True)
    )
    async def rtl_add_channel(self, interaction: discord.Interaction):
        try:
            if interaction.channel.id not in self.config.rtl_channels:
                self.config.rtl_channels.append(interaction.channel.id)
                self.config.save_rtl_channels()
                log_message(
                    f"{interaction.user.name} ({interaction.user.id}) added {interaction.channel.name} ({interaction.channel.id} - {interaction.guild.name}) to RTL updates.",
                    "RTL.add_channel",
                )
                await interaction.response.send_message(
                    f"Successfully added '{interaction.channel.name}' to the RTL live updates"
                )
            else:
                await interaction.response.send_message(
                    f"The channel, '{interaction.channel.name}', is already registered for RTL live updates"
                )
        except Exception as e:
            log_exception(e)

    @app_commands.command(
        name="rtl_remove_channel",
        description="Remove the current ladder from receiving updates from the RTL ladder.",
    )
    @commands.check_any(
        commands.is_owner(), commands.has_permissions(administrator=True)
    )
    async def rtl_remove_channel(self, interaction: discord.Interaction):
        try:
            if interaction.channel.id in self.config.rtl_channels:
                self.config.rtl_channels.remove(interaction.channel.id)
                self.config.save_rtl_channels()
                log_message(
                    f"{interaction.user.name} ({interaction.user.id}) removed {interaction.channel.name} ({interaction.channel.id} - {interaction.guild.name}) from RTL updates.",
                    "RTL.remove_channel",
                )
                await interaction.response.send_message(
                    f"Successfully removed '{interaction.channel.name}' from the RTL live updates"
                )
            else:
                await interaction.response.send_message(
                    f"The channel, '{interaction.channel.name}', is not currently registered for RTL live updates"
                )
        except Exception as e:
            log_exception(e)

    @app_commands.command(name="rtl_kill", description="Nothing to see here.")
    @commands.is_owner()
    async def rtl_kill(self, interaction: discord.Interaction):
        job: Job = self.scheduler.get_job("RTL")
        job.pause()
        log_message(
            f"{interaction.user.name} ({interaction.user.id}) killed the RTL engine process.",
            "RTL.kill",
        )
        await interaction.response.send_message(
            f"Successfully shut off the RTL engine scheduler"
        )

    ######################
    ##### RTL engine #####
    ######################

    async def notify_active_players(self):
        # Called whenever there is a change to active players on the RTL (added/removed)
        players = await RTLPlayerModel.filter(active=True).order_by("-elo").all()

        embed = discord.Embed(
            title=f"JR17's real-time ladder - active players",
        )
        if len(players) == 0:
            # no players
            embed.description = "No active players on the RTL"
        else:
            # players are joined to the ladder
            active_players_list = []
            for player in players:
                in_game_str = "\*" if player.in_game else " "
                single_game_str = "†" if player.join_single_game else " "
                active_players_list.append(
                    f"{in_game_str}{single_game_str} {player.name}: {player.elo:.0f} ({player.wins}W - {player.losses}L)"
                )
            embed.description = (
                "\n".join(active_players_list)
                + "\n\n\* denotes player is currently in a game\n† denotes player is joined for a single game"
            )

        for channel_id in self.config.rtl_channels:
            try:
                channel = self.bot.get_channel(channel_id)
                await channel.send(embed=embed)
            except Exception as e:
                log_message(
                    f"Failed sending message to {channel.name} in {channel.guild.name}",
                    "notify_active_players",
                )
                log_exception(e)

    async def notify_new_game(self, game: RTLGameModel, template_name: str):
        player_a: RTLPlayerModel = game.player_a
        player_b: RTLPlayerModel = game.player_b
        link = f"https://www.warzone.com/MultiPlayer?GameID={game.id}"
        embed = discord.Embed(
            title=f"JR17's real-time ladder - new game",
            description=f"{player_a.name} vs {player_b.name}\n[game link](<{link}>)",
        )
        embed.add_field(
            name=f"{template_name}"[0:256],
            value=f"**{player_a.name}** {player_a.elo:.0f}; **{player_b.name}** {player_b.elo:.0f}"[
                0:1024
            ],
        )

        discord_user_a = self.bot.get_user(player_a.discord_id)
        await discord_user_a.send(embed=embed)
        discord_user_b = self.bot.get_user(player_b.discord_id)
        await discord_user_b.send(embed=embed)

        for channel_id in self.config.rtl_channels:
            channel = self.bot.get_channel(channel_id)
            try:
                await channel.send(embed=embed)
            except Exception as e:
                log_message(
                    f"Failed sending message to {channel.name} in {channel.guild.name}",
                    "notify_new_game",
                )
                log_exception(e)

    async def notify_finished_game(self, game: RTLGameModel):
        winner: RTLPlayerModel = (
            game.player_a if game.winner_id == game.player_a_id else game.player_b
        )
        loser: RTLPlayerModel = (
            game.player_b if game.winner_id == game.player_a_id else game.player_a
        )
        link = f"https://www.warzone.com/MultiPlayer?GameID={game.id}"
        embed = discord.Embed(
            title=f"{winner.name} defeats {loser.name}",
            description=f"[Game link]({link})",
        )
        embed.add_field(
            name=f"Elo rating"[0:256],
            value=f"**{game.player_a.name}** {game.player_a.elo:.0f}; **{game.player_b.name}** {game.player_b.elo:.0f}"[
                0:1024
            ],
        )

        for channel_id in self.config.rtl_channels:
            try:
                channel = self.bot.get_channel(channel_id)
                await channel.send(embed=embed)
            except Exception as e:
                log_message(
                    f"Failed sending message to {channel.name} in {channel.guild.name}",
                    "notify_finished_game",
                )
                log_exception(e)

    async def update_player_ratings(
        self, winner: RTLPlayerModel, loser: RTLPlayerModel
    ):
        expected_score_winner = 1 / (1 + 10 ** ((loser.elo - winner.elo) / 400))
        expected_score_loser = 1 / (1 + 10 ** ((winner.elo - loser.elo) / 400))
        winner.elo += 32 * (1 - expected_score_winner)
        loser.elo += 32 * (0 - expected_score_loser)
        winner.wins += 1
        loser.losses += 1
        winner.active = not winner.join_single_game
        loser.active = not loser.join_single_game
        winner.in_game = False
        winner.in_game = False
        await asyncio.gather(winner.save(), loser.save())
        if winner.join_single_game or loser.join_single_game:
            return True
        return False

    async def update_games(self):
        active_games = (
            await RTLGameModel.filter(ended=None)
            .all()
            .prefetch_related("player_a")
            .prefetch_related("player_b")
        )
        for game in active_games:
            warzone_game = self.warzone_api.check_game(game.id)
            await game.fetch_related("player_a", "player_b")
            if warzone_game.outcome == Game.Outcome.FINISHED:
                # Game newly finished
                winner = next(
                    (
                        player
                        for player in warzone_game.players
                        if player.outcome == WarzonePlayer.Outcome.WON
                    ),
                    None,
                )
                if winner:
                    winner_player: RTLPlayerModel = (
                        game.player_a
                        if game.player_a.warzone_id == winner.id
                        else game.player_b
                    )
                else:
                    # Why VTE... randomly assign this
                    winner_player = (
                        game.player_a if bool(random.getrandbits(1)) else game.player_b
                    )
                    log_message(
                        f"No winner found, defaulting to random winner: {winner_player.name.encode()} {winner_player.warzone_id}",
                        "update_new_games",
                    )

                loser_player: RTLPlayerModel = (
                    game.player_a
                    if game.player_a.warzone_id != winner_player.warzone_id
                    else game.player_b
                )
                has_changed_player_status = await self.update_player_ratings(
                    winner_player, loser_player
                )
                game.winner_id = winner_player.warzone_id
                game.ended = datetime.now()
                log_message(
                    f"New game finished: {warzone_game.players[0].name.encode()} {warzone_game.players[0].outcome} v {warzone_game.players[1].name.encode()} {warzone_game.players[1].outcome} ({warzone_game.link})",
                    "update_new_games",
                )
                await game.save()
                await self.notify_finished_game(game)
                if has_changed_player_status:
                    await self.notify_active_players()
            elif (
                warzone_game.outcome == Game.Outcome.WAITING_FOR_PLAYERS
                and datetime.now(timezone.utc) - warzone_game.start_time
                > timedelta(minutes=5)
            ):
                # Game has been in the join lobby for too long. Game will be deleted and appropriate winner selected according to algorithm:
                # 1. Assign win to left player if they have joined, or are invited and the right player declined
                # 2. Assign win to the right player if they have joined, or are invited and the left player declined
                # 3. Randomly assign win if both players are invited, or declined
                log_message(
                    f"New game passed join time: {warzone_game.players[0].name.encode()} {warzone_game.players[0].outcome} v {warzone_game.players[1].name.encode()} {warzone_game.players[1].outcome} ({warzone_game.link})",
                    "update_new_games",
                )
                log_message(f"Storing end response: {warzone_game}")

                if warzone_game.players[0].outcome == WarzonePlayer.Outcome.PLAYING or (
                    warzone_game.players[0].outcome == WarzonePlayer.Outcome.INVITED
                    and warzone_game.players[1].outcome
                    == WarzonePlayer.Outcome.DECLINED
                ):
                    # first player won
                    winner_id = warzone_game.players[0].id

                elif warzone_game.players[
                    1
                ].outcome == WarzonePlayer.Outcome.PLAYING or (
                    warzone_game.players[1].outcome == WarzonePlayer.Outcome.INVITED
                    and warzone_game.players[0].outcome
                    == WarzonePlayer.Outcome.DECLINED
                ):
                    # second player won
                    winner_id = warzone_game.players[1].id
                else:
                    # Some weird combo where neither player accepted
                    # Randomly assign winner
                    winner_id = warzone_game.players[random.getrandbits(1)].id
                    log_message(
                        f"No winner found, defaulting to random winner: {winner_id}",
                        "update_new_games",
                    )

                winner_player: RTLPlayerModel = (
                    game.player_a
                    if winner_id == game.player_a.warzone_id
                    else game.player_b
                )
                loser_player: RTLPlayerModel = (
                    game.player_a
                    if winner_id != game.player_a.warzone_id
                    else game.player_b
                )

                # save game as completed and announce to servers
                has_changed_player_status = await self.update_player_ratings(
                    winner_player, loser_player
                )
                game.winner_id = winner_player.warzone_id
                game.ended = datetime.now()
                await game.save()
                await game.fetch_related("winner")
                await self.notify_finished_game(game)

                # delete the game
                self.warzone_api.delete_game(game.id)
                if has_changed_player_status:
                    await self.notify_active_players()

    async def create_games(self):
        active_players = await RTLPlayerModel.filter(active=True, in_game=False).all()

        pairs: List[Tuple[RTLPlayerModel, RTLPlayerModel]] = []
        while len(active_players) > 1:
            pairs.append([pop_random(active_players), pop_random(active_players)])

        # create games
        for pair in pairs:
            template_id, template_name = random.choice(RTL_TEMPLATES)

            try:
                game_id = self.warzone_api.create_game(
                    [(pair[0].warzone_id, "1"), (pair[1].warzone_id, "2")],
                    template_id,
                    "JR17's real-time ladder",
                    f"This game is a part of JustinR17's real-time ladder. Players have 5 minutes to join the game. \n\n{template_name}",
                )

                log_message(
                    f"Created new game between {pair[0].name} ({pair[0].warzone_id}) and {pair[1].name} ({pair[1].warzone_id}) on {template_name}. game link: {game_id}",
                    "RTL.create_games",
                )
                new_game = await RTLGameModel.create(
                    id=int(game_id),
                    created=datetime.now(),
                    template=template_id,
                    player_a_id=pair[0].warzone_id,
                    player_b_id=pair[1].warzone_id,
                )
                await new_game.fetch_related("player_a", "player_b")
                pair[0].in_game = True
                pair[1].in_game = True
                await asyncio.gather(pair[0].save(), pair[1].save())
                await self.notify_new_game(new_game, template_name)
            except Exception as e:
                log_message(
                    f"Failed creating a game between {pair[0].name} ({pair[0].warzone_id}) and {pair[1].name} ({pair[1].warzone_id})",
                    "RTL.create_games",
                )
                log_exception(e)

    async def run_engine(self):
        # runs every minute to check in-progress games, then create new games if possible
        await self.update_games()
        await self.create_games()
