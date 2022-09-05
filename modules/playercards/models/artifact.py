from enum import Enum
from typing import Union, Optional, List

from utils.baseobject import BaseObject
from utils.models.base import GameItem
from utils.models.types import JSONDict


class ArtifactInfo(BaseObject):
    """圣遗物信息"""

    def __init__(self, item_id: int = 0, name: str = "", level: int = 0, main_item: Optional[GameItem] = None,
                 pos: Union[Enum, str] = "", star: int = 1, sub_item: Optional[List[GameItem]] = None, icon: str = ""):
        """
        :param item_id: item_id
        :param name: 圣遗物名字
        :param level: 圣遗物等级
        :param main_item: 主词条
        :param pos: 圣遗物类型
        :param star: 星级
        :param sub_item: 副词条
        :param icon: 图片
        """
        self.icon = icon
        self.item_id = item_id
        self.level = level
        self.main_item = main_item
        self.name = name
        self.pos = pos
        self.star = star
        self.sub_item: List[GameItem] = []
        if sub_item is not None:
            self.sub_item = sub_item

    def to_dict(self) -> JSONDict:
        data = super().to_dict()
        if self.sub_item:
            data["sub_item"] = [e.to_dict() for e in self.sub_item]
        return data

    @classmethod
    def de_json(cls, data: Optional[JSONDict]) -> Optional["ArtifactInfo"]:
        data = cls._parse_data(data)
        if not data:
            return None
        data["sub_item"] = GameItem.de_list(data.get("sub_item"))
        return cls(**data)

    __slots__ = ("name", "type", "value", "pos", "star", "sub_item", "main_item", "level", "item_id", "icon")
