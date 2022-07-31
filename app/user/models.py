from model.base import RegionEnum
from model.baseobject import BaseObject


class User(BaseObject):
    def __init__(self, user_id: int = 0, yuanshen_game_uid: int = 0, genshin_game_uid: int = 0,
                 region: RegionEnum = RegionEnum.NULL):
        self.user_id = user_id
        self.yuanshen_game_uid = yuanshen_game_uid
        self.genshin_game_uid = genshin_game_uid
        self.region = region
