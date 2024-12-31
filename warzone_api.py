# https://www.warzone.com/wiki/Category:API
from datetime import datetime, timezone
from typing import Dict, List, Tuple
import requests

from _types import FullWarzoneGame, Game, WarzoneGame, WarzonePlayer
from config import Config
from utils import log_message


class WarzoneAPI:
    CREATE_GAME_ENDPOINT = "https://www.warzone.com/API/CreateGame"
    DELETE_GAME_ENDPOINT = "https://www.warzone.com/API/DeleteLobbyGame"
    QUERY_GAME_ENDPOINT = "https://www.warzone.com/API/GameFeed"
    VALIDATE_INVITE_TOKEN_ENDPOINT = "https://www.warzone.com/API/ValidateInviteToken"
    GAME_URL = "https://www.warzone.com/MultiPlayer?GameID="

    class GameCreationException(Exception):
        pass

    class GameDeletionException(Exception):
        pass

    def __init__(self, config: Config):
        self.config = config
        self.dryrun = False

    def check_game(self, game_id: str) -> WarzoneGame:
        """
        Checks the progress and results of a game using the WZ API.

        Returns the result of the game (in-progress or completed).
        """
        game_json = requests.post(
            f"{WarzoneAPI.QUERY_GAME_ENDPOINT}?GameID={game_id}",
            {"Email": self.config.warzone_email, "APIToken": self.config.warzone_token},
        ).json()

        players = []
        for player in game_json["players"]:
            players.append(
                WarzonePlayer(
                    player["name"], int(player["id"]), player["state"], player["team"]
                )
            )

        game = WarzoneGame(
            players,
            Game.Outcome(game_json["state"]),
            f"{WarzoneAPI.GAME_URL}{game_json['id']}",
            datetime.strptime(game_json["created"], "%m/%d/%Y %H:%M:%S").replace(
                tzinfo=timezone.utc
            ),
            int(game_json["numberOfTurns"]),
        )

        return game

    def get_game_chat(self, game_id: str) -> List[str]:
        """
        Checks the progress and results of a game using the WZ API.

        Returns the result of the game (in-progress or completed).
        """
        game_json = requests.post(
            f"{WarzoneAPI.QUERY_GAME_ENDPOINT}?GameID={game_id}&GetChat=true",
            {"Email": self.config.warzone_email, "APIToken": self.config.warzone_token},
        ).json()

        return game_json["chat"] if "chat" in game_json else []

    def create_game(
        self, players: List[Tuple[str, str]], template: str, name: str, description: str
    ) -> str:
        """
        Creates a game using the WZ API with the specified players, template, and game name/description.

        Returns the game ID if successfully created, else raises a GameCreationException.
        """

        # game_response = {
        #     "gameID": 25876586
        # }

        data = {
            "hostEmail": self.config.warzone_email,
            "hostAPIToken": self.config.warzone_token,
            "templateID": int(template),
            "gameName": name,
            "personalMessage": description,
            "players": list(
                map(
                    lambda e: {"token": e[0], "team": e[1]},
                    players,
                )
            ),
        }
        if self.dryrun:
            print("Running dryrun on game creation")
            game_response = {"gameID": 25876586}
            print(f"{name}\n{description}\n{data['players']}\n\n")
        else:
            game_response = requests.post(
                WarzoneAPI.CREATE_GAME_ENDPOINT,
                json={
                    "hostEmail": self.config.warzone_email,
                    "hostAPIToken": self.config.warzone_token,
                    "templateID": int(template),
                    "gameName": name,
                    "personalMessage": description,
                    "players": list(
                        map(
                            lambda e: {
                                "token": str(e[0]),
                                "team": e[1],
                            },
                            players,
                        )
                    ),
                },
            ).json()

        if "error" in game_response:
            raise WarzoneAPI.GameCreationException(game_response["error"])
        else:
            return game_response["gameID"]

    def delete_game(self, game_id: int):
        """
        Deletes a warzone game if a player did not join in time.

        Returns None if successful, otherwise raises a GameCreationException
        """
        if self.dryrun:
            print("Running dryrun on game deletion")
            game_response = {}
        else:
            game_response = requests.post(
                WarzoneAPI.DELETE_GAME_ENDPOINT,
                json={
                    "Email": self.config.warzone_email,
                    "APIToken": self.config.warzone_token,
                    "gameID": game_id,
                },
            ).json()

        if "error" in game_response:
            raise WarzoneAPI.GameDeletionException(f"Unable to delete game {game_id}")

    def validate_player_template_access(
        self, player_id: str, templates: List[str]
    ) -> Tuple[bool, bool, List[bool]]:
        """
        Checks if the player has access to the list of templates.

        Returns a tuple containing (True if not blacklisted, True if player has access to all templates, List of booleans on access for each template).
        """
        validate_response = requests.post(
            f"{WarzoneAPI.VALIDATE_INVITE_TOKEN_ENDPOINT}?Token={player_id}&TemplateIDs={','.join(templates)}",
            {"Email": self.config["email"], "APIToken": self.config["token"]},
        ).json()

        if "error" in validate_response:
            # Probably blacklisted
            return False, False, []
        has_access_to_all_templates = True
        template_access = []
        for template in templates:
            has_access_to_all_templates = (
                has_access_to_all_templates
                and "CanUseTemplate"
                in validate_response[f"template{template}"]["result"]
            )
            template_access.append(
                "CanUseTemplate" in validate_response[f"template{template}"]["result"]
            )

        return True, has_access_to_all_templates, template_access

    def validate_player(self, player_id: str) -> Dict:
        """
        Checks if the player has access to the list of templates.

        Returns a tuple containing (True if not blacklisted, True if player has access to all templates, List of booleans on access for each template).
        """
        validate_response = requests.post(
            f"{WarzoneAPI.VALIDATE_INVITE_TOKEN_ENDPOINT}?Token={player_id}",
            {"Email": self.config.warzone_email, "APIToken": self.config.warzone_token},
        ).json()

        return validate_response

    def query_game_full(self, game_id: str) -> FullWarzoneGame | None:
        """
        Checks the progress and results of a game using the WZ API.

        Returns the result of the game (in-progress or completed).
        """
        game_json = requests.post(
            f"{WarzoneAPI.QUERY_GAME_ENDPOINT}?GameID={game_id}&getsettings=true",
            {"Email": self.config.warzone_email, "APIToken": self.config.warzone_token},
        ).json()

        if "error" in game_json:
            return None

        players = []
        for player in game_json["players"]:
            players.append(
                WarzonePlayer(
                    player["name"],
                    int(player["id"]),
                    player["state"],
                    player.get("team", ""),
                )
            )

        game = FullWarzoneGame(
            players,
            Game.Outcome(game_json["state"]),
            f"{WarzoneAPI.GAME_URL}{game_json['id']}",
            datetime.strptime(game_json["created"], "%m/%d/%Y %H:%M:%S").replace(
                tzinfo=timezone.utc
            ),
            int(game_json["numberOfTurns"]),
            game_json["name"],
            game_json["settings"]["PersonalMessage"],
        )

        return game
