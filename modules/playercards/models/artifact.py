from typing import Optional, List

from pydantic import BaseModel

from modules.playercards.models.item import GameItem


class ArtifactInfo(BaseModel):
    """圣遗物信息"""
    item_id: int = 0  # item_id
    name: str = ""  # 圣遗物名字
    level: int = 0  # 圣遗物等级
    main_item: Optional[GameItem] = None  # 主词条
    star: int = 1  # 圣遗物星级
    sub_item: List[GameItem] = []  # 副词条
    icon: str = ""  # 图标
