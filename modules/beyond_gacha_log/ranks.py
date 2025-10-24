from abc import ABC
from pathlib import Path

from simnet.models.genshin.wish import GenshinBeyondBannerType

from core.services.gacha_log_rank.models import GachaLogTypeEnum, GachaLogQueryTypeEnum
from gram_core.services.gacha_log_rank.models import GachaLogRank
from modules.beyond_gacha_log.models import BeyondGachaLogInfo
from modules.gacha_log.error import GachaLogNotFound
from modules.gacha_log.models import ImportType
from modules.gacha_log.ranks import GachaLogRanks, GachaLogError


class BeyondGachaLogRanks(GachaLogRanks, ABC):
    """抽卡记录排行榜"""

    ITEM_LIST_MAP = {
        "活动颂愿": GachaLogTypeEnum.PET,
    }
    ITEM_LIST_MAP_REV = {
        GachaLogTypeEnum.PET: "活动颂愿",
    }
    BANNER_TYPE_MAP = {
        "活动颂愿": GenshinBeyondBannerType.EVENT,
    }
    SCORE_TYPE_MAP = {
        "五星平均": GachaLogQueryTypeEnum.FIVE_STAR_AVG,
    }

    async def recount_one_data(self, file_path: Path) -> list[GachaLogRank]:
        """重新计算一个文件的数据"""
        try:
            gacha_log = BeyondGachaLogInfo.parse_obj(await self.load_json(file_path))
            if gacha_log.get_import_type != ImportType.UIGF:
                raise GachaLogError("不支持的抽卡记录类型")
        except ValueError as e:
            raise GachaLogError from e
        player_id = int(gacha_log.uid)
        data = []
        for k, v in self.BANNER_TYPE_MAP.items():
            rank_type = self.ITEM_LIST_MAP[k]
            try:
                gacha_log_data = await self.get_analysis_data(gacha_log, v, None)
            except GachaLogNotFound:
                continue
            rank = self.parse_analysis_data(player_id, rank_type, gacha_log_data)
            data.append(rank)
        return data
