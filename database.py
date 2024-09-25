from tortoise import fields, Model


class RTLPlayerModel(Model):
    warzone_id = fields.IntField(primary_key=True)
    name = fields.TextField()
    discord_id = fields.IntField()
    active = fields.BooleanField(default=False)
    join_single_game = fields.BooleanField(default=False)
    in_game = fields.BooleanField(default=False)
    wins = fields.IntField()
    losses = fields.IntField()
    elo = fields.FloatField()


class RTLGameModel(Model):
    id = fields.IntField(primary_key=True)
    created = fields.DatetimeField()
    ended = fields.DatetimeField(null=True)
    template = fields.IntField()
    player_a = fields.ForeignKeyField("models.RTLPlayerModel")
    player_b = fields.ForeignKeyField("models.RTLPlayerModel")
    is_winner_a = fields.BooleanField(null=True)
