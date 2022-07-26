from enum import Enum
from typing import Union, Optional

from model.base import GameItem
from model.baseobject import BaseObject


class WeaponInfo(BaseObject):
    """武器信息
    """

    def __init__(self, item_id: int = 0, name: str = "", level: int = 0, main_item: Optional[GameItem] = None,
                 affix: int = 0, pos: Union[Enum, str] = "", star: int = 1, sub_item: Optional[GameItem] = None,
                 icon: str = ""):
        """
        :param item_id: item_id
        :param name: 武器名字
        :param level: 武器等级
        :param main_item: 主词条
        :param affix: 精炼等级
        :param pos: 武器类型
        :param star: 星级
        :param sub_item: 副词条
        :param icon: 图片
        """
        self.affix = affix
        self.icon = icon
        self.item_id = item_id
        self.level = level
        self.main_item = main_item
        self.name = name
        self.pos = pos
        self.star = star
        self.sub_item = sub_item

    __slots__ = ("name", "type", "value", "pos", "star", "sub_item", "main_item", "level", "item_id", "icon", "affix")
