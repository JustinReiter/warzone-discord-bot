from datetime import datetime
import os
from typing import List, Tuple
from _types import FullWarzoneGame, WarzonePlayer
from config import Config
from utils import log_exception, log_message, read_pickled_file, write_pickled_file
from warzone_api import WarzoneAPI
import sys
import re


config = Config()
api = WarzoneAPI(config)


class ClotGame:

    def __init__(
        self,
        cl: str,
        division: str,
        template: str,
        link: str,
        players: List[WarzonePlayer],
        winner: List[int],
        start_time: datetime,
        turn: int,
    ):
        self.cl: str = cl
        self.division: str = division
        self.template: str = template
        self.link: str = link
        self.players: List[WarzonePlayer] = players
        self.winner: List[int] = winner
        self.start_time: datetime = start_time
        self.turn: int = turn

    def __repr__(self) -> str:
        output_str = " vs ".join([str(player) for player in sorted(self.players)])
        output_str += f"\n\tCL: {self.cl}"
        output_str += f"\n\tDivision: {self.division}"
        output_str += f"\n\tTemplate: {self.template}"
        output_str += f"\n\tWinner: {self.winner}"
        output_str += f"\n\tStart time: {self.start_time}"
        output_str += f"\n\tRound: {self.turn}"
        output_str += f"\n\tLink: {self.link}"
        return output_str


def overwrite_index_seen(cl: str, index: int):
    with open(f"data/ccs_index_{cl}", "w") as f:
        f.write(f"{index}")


def game_matcher_CL9(game: FullWarzoneGame):
    return re.search(r"^CL9 ", game.title) and re.match(
        "This game has been created by the Clan League bot. If you fail to join it within 3 days, vote to end or decline, it will count as a loss",
        game.description,
    )


def title_parser_CL9(game: FullWarzoneGame) -> Tuple[str, str, str]:
    m = re.match(r"(CL\d*) \| (Group \w) - (.*)", game.title)
    return m.group(1), m.group(2), m.group(3)


def game_matcher_CL10(game: FullWarzoneGame):
    return re.search(r"^CL9 ", game.title) and re.match(
        "This game has been created by the Clan League bot. If you fail to join it within 3 days, vote to end or decline, it will count as a loss",
        game.description,
    )


WARZONE_GAME_INDEXES = {
    "CL9": {
        "start": 12820000,
        "end": 14500000,
        "matcher": game_matcher_CL9,
        "parser": title_parser_CL9,
    },
    "CL10": {
        "start": 12820000,
        "end": 14500000,
        "matcher": game_matcher_CL10,
        "parser": title_parser_CL9,
    },
}

print("\n".join(sys.argv))
if len(sys.argv) < 2:
    raise "Invalid arguments provided. Expected `python3 cowboy_cl_scraper.py <CL9 | CL10>`"

cl_info = WARZONE_GAME_INDEXES[sys.argv[1]]
if os.path.exists(f"data/ccs_index_{sys.argv[1]}"):
    with open(f"data/ccs_index_{sys.argv[1]}", "r") as f:
        last_seen_index = int(f.readlines()[0])
    warzone_data: List[ClotGame] = read_pickled_file(f"data/ccs_data_{sys.argv[1]}")
    print(f"here {last_seen_index=}")
else:
    last_seen_index = cl_info["start"]
    warzone_data: List[ClotGame] = []

try:
    for i in range(last_seen_index, cl_info["end"]):
        if i % 1000 == 0:
            # Save entries every 1000 lines
            overwrite_index_seen(sys.argv[1], i)
            write_pickled_file(f"data/ccs_data_{sys.argv[1]}", warzone_data)
            time_str = "[" + datetime.now().isoformat() + "]".format(type)
            log_message(
                f'Finished parsing {i=} and found {len(warzone_data)} matches. Progress: {(i-cl_info["start"])/(cl_info["end"]-cl_info["start"])*100}',
                "CCS",
            )

        game_data = api.query_game_full(i)
        if game_data and cl_info["matcher"](game_data):
            groups = cl_info["parser"](game_data)
            warzone_data.append(
                ClotGame(
                    *groups,
                    game_data.link,
                    game_data.players,
                    game_data.winner,
                    game_data.start_time,
                    game_data.round,
                )
            )
except Exception as e:
    overwrite_index_seen(sys.argv[1], i)
    write_pickled_file(f"data/ccs_data_{sys.argv[1]}", warzone_data)
    log_message(
        f'Finished parsing {i=}. Progress: {(i-cl_info["start"])/(cl_info["end"]-cl_info["start"])*100}',
        "CCS",
    )
    log_exception(e)
