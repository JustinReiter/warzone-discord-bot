import requests
from config import Config


config = Config()


data = {
    "hostEmail": config.warzone_email,
    "hostAPIToken": config.warzone_token,
    "templateID": 1524819,
    "gameName": "[TEST] justinr17",
    "players": [
        {"token": "1277277659", "team": "1"},
        {"token": "7616995446", "team": "2"},
    ],
}

game_response = requests.post(
    "https://www.warzone.com/API/CreateGame",
    json=data,
).json()

print(game_response)
