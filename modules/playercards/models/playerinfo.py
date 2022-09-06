from typing import Union, List

from pydantic import BaseModel

from modules.playercards.error import PlayerInfoDataNotFind


class ShowAvatarInfo(BaseModel):
    avatar_id: int  # 角色ID
    level: int  # 角色ID

    @classmethod
    def de_data(cls, json_data: dict):
        data = cls(avatar_id=json_data.get("avatarId"), level=json_data.get("level"))
        return data


class PlayerInfo(BaseModel):
    uid: Union[str, int]
    nickname: str  # 角色名称
    finish_achievement_num: int  # 完成的成就
    signature: str  # 签名
    tower_floor_index: int  # 深境螺旋到达的层数
    tower_level_index: int  # 深境螺旋到达的次层数
    level: int  # 等级
    world_level: int  # 世界等级
    show_avatar_info: List[ShowAvatarInfo]

    @classmethod
    def de_data(cls, json_data: dict):
        uid = json_data.get("uid")
        player_info = json_data.get("playerInfo")
        if not player_info:
            raise PlayerInfoDataNotFind(uid)
        show_avatar_info_list = player_info.get("showAvatarInfoList")
        return cls(uid=uid, nickname=player_info.get("nickname"),
                   finish_achievement_num=player_info.get("finishAchievementNum"),
                   tower_floor_index=player_info.get("towerFloorIndex"),
                   tower_level_index=player_info.get("towerLevelIndex"), signature=player_info.get("signature"),
                   world_level=player_info.get("worldLevel"), level=player_info.get("level"),
                   show_avatar_info=[ShowAvatarInfo.de_data(show_avatar_info) for show_avatar_info in
                                     show_avatar_info_list])
