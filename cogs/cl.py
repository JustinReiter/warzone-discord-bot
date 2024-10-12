from datetime import datetime
import random
from typing import Dict, List, Tuple
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import discord
from discord import app_commands
from discord.ext import commands

from _types import WarzoneCog
from config import Config
from sheet import GoogleSheet
from utils import log_exception, log_message
from warzone_api import WarzoneAPI


def pop_random(l: List):
    return l.pop(random.randrange(0, len(l)))


class CLSheetInfo:

    def __init__(self, embed_id: int, sheet_id: str, name: str, end_index: str):
        self.embed_id = embed_id
        self.sheet_id = sheet_id
        self.name = name
        self.end_index = end_index


RTL_TEMPLATES: List[Tuple[int, str]] = [
    (1540231, "Strategic MME"),
    (1540232, "Battle Islands V"),
    (1540234, "French Brawl"),
    (1540235, "Volcano Island"),
]

CLAN_LEAGUE_SHEET = CLSheetInfo(
    None, "1ZG0CoSA9RDswzvmYpc3Qtq-NPCtRRiQaXa8_l_jgS1k", "Clan League 17", "108"
)

SHORT_NAMES = {
    "Union of Soviet Socialist Republics": "USSR",
    "[V.I.W] Very Important Weirdos": "VIW",
}


class CLCommands(WarzoneCog):

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
        self.sheet = GoogleSheet(CLAN_LEAGUE_SHEET.sheet_id, False)

        log_message("Scheduled CLCommands.engine", "bot")
        self.scheduler = scheduler
        self.scheduler.add_job(
            self.run_engine, CronTrigger(hour="*", minute="0", second="0"), name="RTL"
        )

    #######################
    ##### CL commands #####
    #######################

    @app_commands.command(
        name="cl_create_embeds",
        description="Create embeds for CL. Only Justin can use this command.",
    )
    @commands.is_owner()
    async def cl_create_embeds(self, interaction: discord.Interaction):
        # new embed
        embed = discord.Embed(
            title=f"{CLAN_LEAGUE_SHEET.name} standings",
        )

        standings = self.sheet.get_rows(f"Summary!B4:O{CLAN_LEAGUE_SHEET.end_index}")
        division = None
        standings_output: Dict[str, List[CLCommands.ClanStandings]] = {}
        for row in standings:
            row.extend("" for _ in range(14 - len(row)))
            if not row[0]:
                division = None
            elif "Division" in row[0] and "Tournament Winners" not in row[0]:
                # parse division
                division = row[0].strip()
                standings_output[division] = []
            elif division and row[0] != "Clan":
                # parse team
                standings_output[division].append(
                    CLCommands.ClanStandings(row[0], *row[2:13])
                )

        for division, clans in standings_output.items():
            embed.add_field(
                name=division,
                value=f"```{'Clan':20} | {'TP':3} | {'MP':3} | {'%PC':4} | GR{chr(10)}{f'{chr(10)}'.join([clan.create_embed_string() for clan in clans])}```"[
                    0:1024
                ],
                inline=False,
            )

        embed.timestamp = datetime.now()
        discord_channel = await self.bot.fetch_channel(self.config.cl_standings_channel)
        await discord_channel.send(embed=embed)
        await interaction.response.send_message(None)

    #####################
    ##### CL engine #####
    #####################

    class ClanStandings:

        def __init__(
            self,
            name: str,
            pts_1v1: str,
            pts_2v2: str,
            pts_3v3: str,
            tp: str,
            mp: str,
            pc: str,
            gp: str,
            gr: str,
            tw: str,
            tl: str,
            wr: str,
        ):
            self.name = name
            self.pts_1v1 = int(pts_1v1)
            self.pts_2v2 = int(pts_2v2)
            self.pts_3v3 = int(pts_3v3)
            self.tp = int(tp)
            self.mp = int(mp)
            self.pc = float(pc)
            self.gp = int(gp)
            self.gr = int(gr)
            self.tw = int(tw)
            self.tl = int(tl)
            self.wr = float(wr)

        def create_embed_string(self):
            name = (
                SHORT_NAMES[self.name]
                if self.name.strip() in SHORT_NAMES
                else self.name.strip()
            )
            return (
                f"{name:20} | {self.tp:3g} | {self.mp:3g} | {self.pc:4} | {self.gr:2g}"
            )

    async def update_cl_standings_embeds(self):
        if CLAN_LEAGUE_SHEET.embed_id is None:
            # no embed exists yet
            return
        discord_channel = self.bot.get_channel(self.config.cl_standings_channel)
        message = await discord_channel.fetch_message(CLAN_LEAGUE_SHEET.embed_id)
        embed = message.embeds[0]
        # embed.description = "Scores are shown as:\n```Team | Pts | MP```"
        embed.clear_fields()

        standings = self.sheet.get_rows(f"Summary!B4:O{CLAN_LEAGUE_SHEET.end_index}")
        division = None
        standings_output: Dict[str, List[CLCommands.ClanStandings]] = {}
        for row in standings:
            row.extend("" for _ in range(14 - len(row)))
            if not row[0]:
                division = None
            elif "Division" in row[0] and "Tournament Winners" not in row[0]:
                # parse division
                division = row[0].strip()
                standings_output[division] = []
            elif division and row[0] != "Clan":
                # parse team
                standings_output[division].append(
                    CLCommands.ClanStandings(row[0], *row[2:13])
                )

        for division, clans in standings_output.items():
            embed.add_field(
                name=division,
                value=f"```{'Clan':20} | {'TP':3} | {'MP':3} | {'%PC':4} | GR{chr(10)}{f'{chr(10)}'.join([clan.create_embed_string() for clan in clans])}```"[
                    0:1024
                ],
                inline=False,
            )
        embed.timestamp = datetime.now()
        await message.edit(embed=embed)
        log_message(f"Successfully updated the embed for {division}")

    async def run_engine(self):
        # runs every minute to check in-progress games, then create new games if possible
        await self.update_cl_standings_embeds()
