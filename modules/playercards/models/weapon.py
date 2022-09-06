from typing import Optional

from pydantic import BaseModel

from modules.playercards.models.item import GameItem


class WeaponInfo(BaseModel):
    """武器信息"""
    item_id: int = 0  # item_id
    name: str = ""  # 武器名字
    level: int = 0  # 武器等级
    affix: int = 1
    main_item: Optional[GameItem] = None  # 武器主词条
    star: int = 1  # 武器星级
    sub_item: Optional[GameItem] = None  # 武器副词条
    icon: str = ""  # 图标
