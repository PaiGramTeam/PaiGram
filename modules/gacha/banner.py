from enum import Enum
from typing import List, Tuple

from pydantic import BaseModel

from modules.gacha.error import GachaIllegalArgument
from modules.gacha.utils import lerp


class BannerType(Enum):
    STANDARD = 0
    EVENT = 1
    WEAPON = 2


class GachaBanner(BaseModel):
    weight4 = ((1, 510), (8, 510), (10, 10000))
    weight5 = ((1, 60), (73, 60), (90, 10000))
    fallback_items3: List[int] = [
        11301,
        11302,
        11306,
        12301,
        12302,
        12305,
        13303,
        14301,
        14302,
        14304,
        15301,
        15302,
        15304,
    ]
    # 硬编码三星武器
    title: str = ""
    html_title: str = ""
    banner_id: str = ""
    banner_type: BannerType = BannerType.STANDARD
    wish_max_progress: int = 0
    pool_balance_weights4: Tuple[int] = ((1, 255), (17, 255), (21, 10455))
    pool_balance_weights5: Tuple[int] = ((1, 30), (147, 150), (181, 10230))
    event_chance5: int = 50
    event_chance4: int = 50
    event_chance: int = -1
    rate_up_items5: List[int] = []  # UP五星
    fallback_items5_pool1: List[int] = []  # 基础五星角色
    fallback_items5_pool2: List[int] = []  # 基础五星武器
    rate_up_items4: List[int] = []  # UP四星
    fallback_items4_pool1: List[int] = []  # 基础四星角色
    fallback_items4_pool2: List[int] = []  # 基础四星武器
    auto_strip_rate_up_from_fallback: bool = True

    def get_weight(self, rarity: int, pity: int) -> int:
        if rarity == 4:
            return lerp(pity, self.weight4)
        if rarity == 5:
            return lerp(pity, self.weight5)
        raise GachaIllegalArgument

    def has_epitomized(self):
        return self.banner_type == BannerType.WEAPON

    def get_event_chance(self, rarity: int) -> int:
        if rarity == 4:
            return self.event_chance4
        if rarity == 5:
            return self.event_chance5
        if self.event_chance >= -1:
            return self.event_chance
        raise GachaIllegalArgument

    def get_pool_balance_weight(self, rarity: int, pity: int) -> int:
        if rarity == 4:
            return lerp(pity, self.pool_balance_weights4)
        if rarity == 5:
            return lerp(pity, self.pool_balance_weights5)
        raise GachaIllegalArgument
