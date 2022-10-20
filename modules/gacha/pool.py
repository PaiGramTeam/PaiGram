from typing import List

from modules.gacha.banner import GachaBanner
from modules.gacha.utils import set_subtract


class BannerPool:
    rate_up_items5: List[int] = []
    fallback_items5_pool1: List[int] = []
    fallback_items5_pool2: List[int] = []
    rate_up_items4: List[int] = []
    fallback_items4_pool1: List[int] = []
    fallback_items4_pool2: List[int] = []

    def __init__(self, banner: GachaBanner):
        self.rate_up_items4 = banner.rate_up_items4
        self.rate_up_items5 = banner.rate_up_items5
        self.fallback_items5_pool1 = banner.fallback_items5_pool1
        self.fallback_items5_pool2 = banner.fallback_items5_pool2
        self.fallback_items4_pool1 = banner.fallback_items4_pool1
        self.fallback_items4_pool2 = banner.fallback_items4_pool2

        if banner.auto_strip_rate_up_from_fallback:  # 把UP四星从非UP四星排除
            self.fallback_items5_pool1 = set_subtract(banner.fallback_items5_pool1, banner.rate_up_items5)
            self.fallback_items5_pool2 = set_subtract(banner.fallback_items5_pool2, banner.rate_up_items5)
            self.fallback_items4_pool1 = set_subtract(banner.fallback_items4_pool1, banner.rate_up_items4)
            self.fallback_items4_pool2 = set_subtract(banner.fallback_items4_pool2, banner.rate_up_items4)
