from datetime import datetime
from enum import Enum
from typing import Dict, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from warzone_api import WarzoneAPI


from config import Config


class WarzoneCog(commands.Cog):

    def __init__(
        self,
        bot: commands.Bot,
        config: Config,
        scheduler: AsyncIOScheduler,
        warzone_api: "WarzoneAPI",
    ):
        pass


class Player:

    def __init__(self, name: str, id: str, team: "Team"):
        self.name = name
        self.id = str(id)
        self.team = team

    def __lt__(self, other: "Player"):
        return (
            self.id < other.id
            if self.team.name == other.team.name
            else self.team.name > other.team.name
        )

    def __repr__(self) -> str:
        return f"{self.name} ({self.id})"


class Team:

    def __init__(self, name: str):
        self.name = name
        self.players: List[Player] = []

    def __lt__(self, other: "Team"):
        return self.name > other.name


class Game:

    class Outcome(Enum):
        WAITING_FOR_PLAYERS = "WaitingForPlayers"
        DISTRIBUTING_TERRITORIES = "DistributingTerritories"
        IN_PROGRESS = "Playing"
        FINISHED = "Finished"
        UNDEFINED = "undefined"

    def __init__(self, players, outcome=Outcome.UNDEFINED, link="") -> None:
        self.outcome: Game.Outcome = outcome
        self.winner: str = ""
        self.players: List[Player] = sorted(
            players
        )  # sort the players for the case of 2v2s (to match team games in sheet properly)
        self.link: str = link

    def __repr__(self) -> str:
        players_by_team: Dict[str, List[str]] = {}
        for player in self.players:
            players_by_team.setdefault(player.team.name, []).append(player.name)

        team_strings: List[str] = []
        for team, players in players_by_team.items():
            team_strings.append(f"({team}) " + ", ".join(players))

        return " vs. ".join(team_strings)

    def get_player_names_by_team(self):
        players_by_team: Dict[str, List[str]] = {}
        for player in self.players:
            players_by_team.setdefault(player.team.name, []).append(player.name)
        return players_by_team

    def get_players_by_team(self):
        players_by_team: Dict[str, List[Player]] = {}
        for player in self.players:
            players_by_team.get(player.team.name, []).append(player)

        # Sanity check to ensure proper ordering of players. Should not be needed since order is preserved
        for team_name, players in players_by_team.items():
            players_by_team[team_name] = sorted(players)
        return players_by_team


class WarzoneGame:

    def __init__(
        self,
        players,
        outcome=Game.Outcome.UNDEFINED,
        link="",
        start_time=datetime.now(),
        round=0,
    ) -> None:
        self.outcome: Game.Outcome = outcome
        self.winner: List[int] = []
        self.players: List[WarzonePlayer] = players
        self.link: str = link
        self.start_time: datetime = start_time
        self.round: int = round

    def __repr__(self) -> str:
        output_str = " vs ".join([str(player) for player in sorted(self.players)])
        output_str += f"\n\tWinner: {self.winner}"
        output_str += f"\n\tStart time: {self.start_time}"
        output_str += f"\n\tOutcome: {self.outcome}"
        output_str += f"\n\tRound: {self.round}"
        output_str += f"\n\tLink: {self.link}"
        return output_str


class FullWarzoneGame:

    def __init__(
        self,
        players,
        outcome=Game.Outcome.UNDEFINED,
        link="",
        start_time=datetime.now(),
        round=0,
        title="",
        description="",
    ) -> None:
        self.outcome: Game.Outcome = outcome
        self.winner: List[int] = []
        self.players: List[WarzonePlayer] = players
        self.link: str = link
        self.start_time: datetime = start_time
        self.round: int = round
        self.title: str = title
        self.description: str = description

    def __repr__(self) -> str:
        output_str = " vs ".join([str(player) for player in sorted(self.players)])
        output_str += f"\n\tWinner: {self.winner}"
        output_str += f"\n\tStart time: {self.start_time}"
        output_str += f"\n\tOutcome: {self.outcome}"
        output_str += f"\n\tRound: {self.round}"
        output_str += f"\n\tLink: {self.link}"
        return output_str


class WarzonePlayer:

    class Outcome(Enum):
        WON = "Won"
        PLAYING = "Playing"
        INVITED = "Invited"
        SURRENDER_ACCEPTED = "SurrenderAccepted"
        ELIMINATED = "Eliminated"
        BOOTED = "Booted"
        ENDED_BY_VOTE = "EndedByVote"
        DECLINED = "Declined"
        REMOVED_BY_HOST = "RemovedByHost"
        UNDEFINED = "undefined"

    def __init__(self, name, id, outcome="", team=""):
        self.name: str = name
        self.id: int = id
        self.team: str = team
        self.score: float = 0.0

        if outcome == "":
            self.outcome = WarzonePlayer.Outcome.UNDEFINED
        else:
            self.outcome = WarzonePlayer.Outcome(outcome)

    def __repr__(self) -> str:
        return f"**{self.team}** {self.name} ({self.id})"

    def get_player_state_str(self) -> str:
        return f"{self.name.encode()} {self.outcome}"

    def __lt__(self, other: "WarzonePlayer"):
        return self.id < other.id if self.team == other.team else self.team > other.team
