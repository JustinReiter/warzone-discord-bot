from typing import List
from dotenv import dotenv_values

from utils import read_pickled_file, write_pickled_file


class Config:

    def __init__(self) -> None:
        config = dotenv_values(".env")

        self.warzone_email: str = config["warzone_email"]
        self.warzone_token: str = config["warzone_token"]
        self.discord_token: str = config["discord_token"]
        self.flask_secret_key: str = config["FLASK_SECRET_KEY"]
        self.flask_auth_key: str = config["FLASK_AUTH_KEY"]

        self.rtl_channels: List[int] = read_pickled_file("data/rtl_channels.json")
        self.rtl_templates: List[int] = read_pickled_file("data/rtl_templates.json")

    def save_rtl_channels(self):
        write_pickled_file("data/rtl_channels.json", self.rtl_channels)
