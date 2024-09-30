from tortoise import Tortoise, fields, Model


class RTLPlayerModel(Model):
    warzone_id = fields.IntField(primary_key=True)
    name = fields.TextField()
    discord_id = fields.IntField()
    active = fields.BooleanField(default=False)
    join_single_game = fields.BooleanField(default=False)
    in_game = fields.BooleanField(default=False)
    wins = fields.IntField(default=0)
    losses = fields.IntField(default=0)
    elo = fields.FloatField(default=1500)


class RTLGameModel(Model):
    id = fields.IntField(primary_key=True)
    created = fields.DatetimeField()
    ended = fields.DatetimeField(null=True)
    template = fields.IntField()
    player_a = fields.ForeignKeyField("models.RTLPlayerModel", related_name=False)
    player_b = fields.ForeignKeyField("models.RTLPlayerModel", related_name=False)
    winner = fields.ForeignKeyField(
        "models.RTLPlayerModel", related_name=False, null=True
    )


class ClotPlayer(Model):
    warzone_id = fields.IntField(primary_key=True)
    name = fields.TextField()
    created = fields.DatetimeField()
    clan = fields.TextField(null=True)
    discord_token = fields.TextField()


async def init():
    await Tortoise.init(db_url="sqlite://db.sqlite3", modules={"models": ["database"]})
    # Generate the schema
    await Tortoise.generate_schemas()
