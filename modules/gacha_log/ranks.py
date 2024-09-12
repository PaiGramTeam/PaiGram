import asyncio
import contextlib
from abc import abstractmethod
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING, Dict

from simnet.models.genshin.wish import BannerType

from core.services.gacha_log_rank.services import GachaLogRankService
from core.services.gacha_log_rank.models import GachaLogRank, GachaLogTypeEnum, GachaLogQueryTypeEnum
from modules.gacha_log.error import GachaLogNotFound
from modules.gacha_log.models import GachaLogInfo, ImportType
from utils.log import logger

if TYPE_CHECKING:
    from core.dependence.assets import AssetsService
    from telegram import Message


class GachaLogError(Exception):
    """抽卡记录异常"""


class GachaLogRanks:
    """抽卡记录排行榜"""

    gacha_log_path: Path
    ITEM_LIST_MAP = {
        "角色祈愿": GachaLogTypeEnum.CHARACTER,
        "武器祈愿": GachaLogTypeEnum.WEAPON,
        "常驻祈愿": GachaLogTypeEnum.DEFAULT,
        "集录祈愿": GachaLogTypeEnum.HUN,
    }
    ITEM_LIST_MAP_REV = {
        GachaLogTypeEnum.CHARACTER: "角色祈愿",
        GachaLogTypeEnum.WEAPON: "武器祈愿",
        GachaLogTypeEnum.DEFAULT: "常驻祈愿",
        GachaLogTypeEnum.HUN: "集录祈愿",
    }
    BANNER_TYPE_MAP = {
        "角色祈愿": BannerType.CHARACTER1,
        "武器祈愿": BannerType.WEAPON,
        "常驻祈愿": BannerType.PERMANENT,
        "集录祈愿": BannerType.CHRONICLED,
    }
    SCORE_TYPE_MAP = {
        "五星平均": GachaLogQueryTypeEnum.FIVE_STAR_AVG,
        "UP平均": GachaLogQueryTypeEnum.UP_STAR_AVG,
        "小保底不歪": GachaLogQueryTypeEnum.NO_WARP,
    }

    def __init__(
        self,
        gacha_log_rank_service: GachaLogRankService = None,
    ):
        self.gacha_log_rank_service = gacha_log_rank_service

    @staticmethod
    @abstractmethod
    async def load_json(path):
        """加载json文件"""

    @abstractmethod
    async def get_analysis_data(self, gacha_log: "GachaLogInfo", pool: BannerType, assets: Optional["AssetsService"]):
        """
        获取抽卡记录分析数据
        :param gacha_log: 抽卡记录
        :param pool: 池子类型
        :param assets: 资源服务
        :return: 分析数据
        """

    def parse_analysis_data(self, player_id: int, rank_type: "GachaLogTypeEnum", data: Dict) -> GachaLogRank:
        line = data["line"]
        total = data["allNum"]
        rank = GachaLogRank(player_id=player_id, type=rank_type, score_1=total)
        for l1 in line:
            for l2 in l1:
                label = l2["lable"]
                if label in self.SCORE_TYPE_MAP:
                    gacha_log_type = self.SCORE_TYPE_MAP[label]
                    value = int(float(l2["num"]) * 100)
                    setattr(rank, gacha_log_type.value, value)
        return rank

    async def recount_one_data(self, file_path: Path) -> List[GachaLogRank]:
        """重新计算一个文件的数据"""
        try:
            gacha_log = GachaLogInfo.parse_obj(await self.load_json(file_path))
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

    async def recount_one_from_uid(self, user_id: int, uid: int):
        save_path = self.gacha_log_path / f"{user_id}-{uid}.json"
        await self.recount_one(save_path)

    async def recount_one(self, file_path: Path):
        if not file_path.exists():
            return
        try:
            ranks = await self.recount_one_data(file_path)
            if ranks:
                await self.add_or_update(ranks)
        except GachaLogError:
            logger.warning("更新抽卡排名失败 file[%s]", file_path)

    async def add_or_update(self, ranks: List["GachaLogRank"]):
        """添加或更新用户数据"""
        old_ranks = await self.gacha_log_rank_service.get_rank_by_user_id(ranks[0].player_id)
        old_ranks_map = {r.type: r for r in old_ranks}
        for rank in ranks:
            old_rank = old_ranks_map.get(rank.type)
            if old_rank:
                old_rank.update_by_new(rank)
                await self.gacha_log_rank_service.update(old_rank)
            else:
                await self.gacha_log_rank_service.add(rank)

    async def recount_all_data(self, message: "Message"):
        """重新计算所有数据"""
        for key1 in GachaLogTypeEnum:
            for key2 in GachaLogQueryTypeEnum:
                await self.gacha_log_rank_service.del_all_cache_by_type(key1, key2)  # noqa
        files = [f for f in self.gacha_log_path.glob("*.json") if len(f.stem.split("-")) == 2]
        tasks = []
        for idx, f in enumerate(files):
            tasks.append(self.recount_one(f))
            if len(tasks) >= 10:
                await asyncio.gather(*tasks)
                tasks.clear()
            if idx % 10 == 1:
                with contextlib.suppress(Exception):
                    await message.edit_text(f"已处理 {idx + 1}/{len(files)} 个文件")
        if tasks:
            await asyncio.gather(*tasks)
