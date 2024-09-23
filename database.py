from typing import List
from _types import RTLPlayerModel, WarzoneGame
from config import Config


class Database:

    def __init__(self, config: Config) -> None:
        self.config = config

    def get_active_games() -> List[WarzoneGame]:
        pass

    def get_active_players():
        pass

    def join_player(player_id) -> bool:
        pass

    def leave_player(player_id) -> bool:
        pass

    def add_game() -> bool:
        pass

    def update_game() -> bool:
        pass

    def update_player(player: RTLPlayerModel) -> bool:
        pass
