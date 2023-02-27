from pydantic import BaseModel

from modules.gacha.error import GachaIllegalArgument


class PlayerGachaBannerInfo(BaseModel):
    """玩家当前抽卡统计信息"""

    pity5: int = 0
    pity4: int = 0
    pity4_pool1: int = 0
    pity4_pool2: int = 0
    pity5_pool1: int = 0
    pity5_pool2: int = 0
    wish_item_id: int = 0
    failed_chosen_item_pulls: int = 0
    failed_featured4_item_pulls: int = 0
    failed_featured_item_pulls: int = 0
    total_pulls: int = 0

    def inc_pity_all(self):
        self.pity5 += 1
        self.pity4 += 1
        self.pity4_pool1 += 1
        self.pity4_pool2 += 1
        self.pity5_pool1 += 1
        self.pity5_pool2 += 1

    def get_failed_featured_item_pulls(self, rarity: int) -> int:
        if rarity == 4:
            return self.failed_featured4_item_pulls
        if rarity == 5:
            return self.failed_featured_item_pulls
        raise GachaIllegalArgument

    def set_failed_featured_item_pulls(self, rarity: int, amount: int):
        if rarity == 4:
            self.failed_featured4_item_pulls = amount
        elif rarity == 5:
            self.failed_featured_item_pulls = amount
        else:
            raise GachaIllegalArgument

    def add_failed_featured_item_pulls(self, rarity: int, amount: int):
        if rarity == 4:
            self.failed_featured4_item_pulls += amount
        elif rarity == 5:
            self.failed_featured_item_pulls += amount
        else:
            raise GachaIllegalArgument

    def get_pity_pool(self, rarity: int, param: int) -> int:
        if rarity == 4:
            return self.pity4_pool1 if param == 1 else self.pity4_pool2
        if rarity == 5:
            return self.pity5_pool1 if param == 1 else self.pity5_pool2
        raise GachaIllegalArgument

    def set_pity_pool(self, rarity: int, pool: int, amount: int):
        if rarity == 4:
            if pool == 1:
                self.pity4_pool1 = amount
            else:
                self.pity4_pool2 = amount
        elif rarity == 5:
            if pool == 1:
                self.pity5_pool1 = amount
            else:
                self.pity5_pool2 = amount
        else:
            raise GachaIllegalArgument

    def add_failed_chosen_item_pulls(self, amount: int):
        self.failed_chosen_item_pulls += amount

    def add_total_pulls(self, times: int):
        self.total_pulls += times
