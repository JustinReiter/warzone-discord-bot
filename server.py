### server.py
# Basic webserver for acting as the intermediary between warzone & the clot
# users will login through the webserver and the clot will interface with the webserver via authenticated rest API

# this is built with flask

from datetime import datetime
import secrets
import string
from flask import (
    Flask,
    render_template,
    session,
    redirect,
    request,
    url_for,
)
from tortoise import run_async


from config import Config
from database import ClotPlayer, init
from warzone_api import WarzoneAPI

app = Flask(__name__)
count = 0
config = Config()
api = WarzoneAPI(config)

alphabet = string.ascii_letters + string.digits


def generate_discord_token():
    return "".join(secrets.choice(alphabet) for _ in range(48))


@app.route("/")
async def home():
    if "token" not in session:
        # work on login flow
        return redirect("https://www.warzone.com/CLOT/Auth?p=88157522499&state=join")
    player = await ClotPlayer.filter(warzone_id=session["token"]).first()
    # TODO: return page
    return render_template(
        "home.html",
        warzone_player=player.name,
        discord_token=player.discord_token,
    )


@app.route("/login")
async def login():
    print(generate_discord_token())
    clotpass = request.args.get("clotpass", None)
    token = int(request.args.get("token", 0))
    state = request.args.get("state", None)

    if state != "join" or not clotpass or not token or not token:
        return redirect(url_for("home"))

    player_info = api.validate_player(token)
    print(player_info)
    if player_info["clotpass"] == clotpass:
        session["token"] = token
        player_exists = await ClotPlayer.filter(warzone_id=token).exists()
        if not player_exists:
            await ClotPlayer.create(
                warzone_id=token,
                name=player_info["name"],
                created=datetime.now(),
                clan=player_info.get("clan", None),
                discord_token=generate_discord_token(),
            )

    return redirect(url_for("home"))


@app.route("/delete_player")
async def delete_player():
    player = await ClotPlayer.filter(warzone_id=session["token"]).first()
    await player.delete()

    session.pop("token")

    return redirect(url_for("home"))


@app.route("/logout")
async def logout():
    session.pop("token")

    return redirect(url_for("home"))


@app.route("/reset_token")
async def reset_token():
    if "token" not in session:
        # work on login flow
        return redirect(url_for("home"))
    player = await ClotPlayer.filter(warzone_id=session["token"]).first()
    player.discord_token = generate_discord_token()
    await player.save()
    return redirect(url_for("home"))


@app.route("/admin_get_users")
async def admin_get_users():
    if request.args.get("auth", None) != config.flask_auth_key:
        return {}
    players = await ClotPlayer.all()
    player_response = []
    for player in players:
        player_response.append(
            {
                "name": player.name,
                "id": player.warzone_id,
                "created": player.created,
                "clan": player.clan,
                "token": player.discord_token,
            }
        )
    return player_response


@app.route("/healthz")
def health():
    return "ok"


app.secret_key = config.flask_secret_key
run_async(init())
app.run(port=8000)
