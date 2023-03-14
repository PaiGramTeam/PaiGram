import random
from typing import List, Tuple

from modules.gacha.banner import GachaBanner
from modules.gacha.error import GachaIllegalArgument, GachaInvalidTimes
from modules.gacha.player.info import PlayerGachaBannerInfo, PlayerGachaInfo
from modules.gacha.pool import BannerPool


class BannerSystem:
    fallback_items5_pool2_default: Tuple[int] = (11501, 11502, 12501, 12502, 13502, 13505, 14501, 14502, 15501, 15502)
    fallback_items4_pool2_default: Tuple[int] = (
        11401,
        11402,
        11403,
        11405,
        12401,
        12402,
        12403,
        12405,
        13401,
        13407,
        14401,
        14402,
        14403,
        14409,
        15401,
        15402,
        15403,
        15405,
    )

    def do_pulls(self, player_gacha_info: PlayerGachaInfo, banner: GachaBanner, times: int) -> List[int]:
        item_list: List[int] = []
        if times not in (10, 1):
            raise GachaInvalidTimes

        gacha_info = player_gacha_info.get_banner_info(banner)
        gacha_info.add_total_pulls(times)
        pools = BannerPool(banner)
        for _ in range(times):
            item_id = self.do_pull(banner, gacha_info, pools)
            item_list.append(item_id)
        return item_list

    def do_pull(self, banner: GachaBanner, gacha_info: PlayerGachaBannerInfo, pools: BannerPool) -> int:
        gacha_info.inc_pity_all()
        # 对玩家卡池信息的计数全部加1，方便计算
        # 就这么说吧，如果你加之前比已经四星9发没出，那么这个能让你下次权重必定让你出四星的角色
        # 而不是使用 if gacha_info.pity4 + 1 >= 10 的形式计算
        weights = [banner.get_weight(5, gacha_info.pity5), banner.get_weight(4, gacha_info.pity4), 10000]
        leval_won = 5 - self.draw_roulette(weights, 10000)
        # 根据权重信息获得当前所抽到的星级
        if leval_won == 5:
            # print(f"已经获得五星，当前五星权重为{weights[0]}")
            gacha_info.pity5 = 0
            return self.do_rare_pull(
                pools.rate_up_items5, pools.fallback_items5_pool1, pools.fallback_items5_pool2, 5, banner, gacha_info
            )
        if leval_won == 4:
            gacha_info.pity4 = 0
            return self.do_rare_pull(
                pools.rate_up_items4, pools.fallback_items4_pool1, pools.fallback_items4_pool2, 4, banner, gacha_info
            )
        return self.get_random(banner.fallback_items3)

    @staticmethod
    def draw_roulette(weights, cutoff: int) -> int:
        total = 0
        for weight in weights:
            if weight < 0:
                raise GachaIllegalArgument("Weights must be non-negative!")
            total += weight
        roll = random.randint(0, min(total, cutoff))  # nosec
        sub_total = 0
        for index, value in enumerate(weights):
            sub_total += value
            if roll < sub_total:
                return index
        return 0

    def do_rare_pull(
        self,
        featured: List[int],
        fallback1: List[int],
        fallback2: List[int],
        rarity: int,
        banner: GachaBanner,
        gacha_info: PlayerGachaBannerInfo,
    ) -> int:
        # 以下是防止点炒饭
        epitomized = (banner.has_epitomized()) and (rarity == 5) and (gacha_info.wish_item_id != 0)  # 判断定轨信息是否正确
        pity_epitomized = gacha_info.failed_chosen_item_pulls >= banner.wish_max_progress  # 判断定轨值
        pity_featured = gacha_info.get_failed_featured_item_pulls(rarity) >= 1  # 通过UP值判断当前是否为UP
        roll_featured = self.random_range(1, 100) <= banner.get_event_chance(rarity)  # 随机判断当前是否为UP
        pull_featured = pity_featured or roll_featured  # 获得最终是否为 UP

        if epitomized and pity_epitomized:  # 给武器用的定轨代码
            gacha_info.set_failed_featured_item_pulls(rarity, 0)
            item_id = gacha_info.wish_item_id
        elif pull_featured and featured:  # 是UP角色
            gacha_info.set_failed_featured_item_pulls(rarity, 0)
            item_id = self.get_random(featured)
        else:  # 寄
            gacha_info.add_failed_featured_item_pulls(rarity, 1)
            item_id = self.do_fallback_rare_pull(fallback1, fallback2, rarity, banner, gacha_info)
        if epitomized:
            if item_id == gacha_info.wish_item_id:  # 判断当前UP是否为定轨的UP
                gacha_info.failed_chosen_item_pulls = 0  # 是的话清除定轨
            else:
                gacha_info.add_failed_chosen_item_pulls(1)
        return item_id

    def do_fallback_rare_pull(
        self,
        fallback1: List[int],
        fallback2: List[int],
        rarity: int,
        banner: GachaBanner,
        gacha_info: PlayerGachaBannerInfo,
    ) -> int:
        if len(fallback1) < 1:
            if len(fallback2) < 1:
                return self.get_random(
                    self.fallback_items5_pool2_default if rarity == 5 else self.fallback_items4_pool2_default
                )
            return self.get_random(fallback2)
        if len(fallback2) < 1:
            return self.get_random(fallback1)
        pity_pool1 = banner.get_pool_balance_weight(rarity, gacha_info.get_pity_pool(rarity, 1))
        pity_pool2 = banner.get_pool_balance_weight(rarity, gacha_info.get_pity_pool(rarity, 2))
        if pity_pool1 >= pity_pool2:
            chosen_pool = 1 + self.draw_roulette((pity_pool1, pity_pool2), 10000)
        else:
            chosen_pool = 2 - self.draw_roulette((pity_pool2, pity_pool1), 10000)
        if chosen_pool == 1:
            gacha_info.set_pity_pool(rarity, 1, 0)
            return self.get_random(fallback1)
        gacha_info.set_pity_pool(rarity, 2, 0)
        return self.get_random(fallback2)

    @staticmethod
    def get_random(items) -> int:
        return random.choice(items)  # nosec

    @staticmethod
    def random_range(_mix: int, _max: int) -> int:
        return random.randint(_mix, _max)  # nosec
