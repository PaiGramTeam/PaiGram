from typing import Optional

from pydantic import BaseModel

from modules.wish.banner import GenshinBannerType, GachaBanner
from modules.wish.player.banner import PlayerGachaBannerInfo


class PlayerGachaInfo(BaseModel):
    """玩家抽卡全部信息"""

    standard_banner: Optional[PlayerGachaBannerInfo] = None
    event_weapon_banner: Optional[PlayerGachaBannerInfo] = None
    event_character_banner: Optional[PlayerGachaBannerInfo] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.standard_banner is None:
            self.standard_banner = PlayerGachaBannerInfo()
        if self.event_weapon_banner is None:
            self.event_weapon_banner = PlayerGachaBannerInfo()
        if self.event_character_banner is None:
            self.event_character_banner = PlayerGachaBannerInfo()

    def get_banner_info(self, banner: GachaBanner) -> PlayerGachaBannerInfo:
        if banner.banner_type == GenshinBannerType.EVENT:
            return self.event_character_banner
        if banner.banner_type == GenshinBannerType.WEAPON:
            return self.event_weapon_banner
        return self.standard_banner
