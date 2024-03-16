import asyncio
import sys
from abc import ABC, abstractmethod
from collections import Counter
from multiprocessing import RLock
from ssl import SSLZeroReturnError
from typing import Iterable, ParamSpec, TypeVar, final

from httpx import AsyncClient, HTTPError

from core.dependence.assets import AssetsService
from plugins.genshin.farming._const import AREAS, INTERVAL, RETRY_TIMES, WEEK_MAP
from plugins.genshin.farming._model import AreaData, AvatarData, FarmingData, MaterialData, WeaponData
from utils.log import logger

__all__ = ("Spider",)

R = TypeVar("R")
P = ParamSpec("P")


def get_material_serial_name(names: Iterable[str]) -> str:
    counter = None
    for name in names:
        if counter is None:
            counter = Counter(name)
            continue
        counter = counter & Counter(name)
    return "".join(counter.keys()).replace("的", "").replace("之", "")


class Spider(ABC):
    _lock = RLock()
    _client: AsyncClient | None = None

    priority: int = sys.maxsize

    def __init__(self, assets: AssetsService):
        self.assets = assets

    @property
    def client(self) -> AsyncClient:
        with self._lock:
            if self._client is None or self._client.is_closed:
                self._client = AsyncClient()
        return self._client

    @abstractmethod
    async def __call__(self) -> dict[int, FarmingData]:
        pass

    @classmethod
    @final
    async def execute(cls, assets: AssetsService) -> dict[int, FarmingData]:
        result = None
        for spider in sorted(
            map(lambda x: x(assets), cls.__subclasses__()), key=lambda x: (x.priority, x.__class__.__name__)
        ):
            if (result := await spider()) is not None:
                return result
        if result is None:
            logger.error("每日素材刷新失败，请稍后重试")


class Ambr(Spider):
    farming_url = "https://api.ambr.top/v2/chs/dailyDungeon"

    async def _request(self, url: str) -> dict | None:
        response = None
        for attempts in range(RETRY_TIMES):
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                break
            except (HTTPError, SSLZeroReturnError):
                await asyncio.sleep(INTERVAL)
                if attempts + 1 == RETRY_TIMES:
                    return None
                logger.warning("每日素材刷新失败, 正在重试第 %d 次", attempts)
        if response is not None:
            return response.json()["data"]

    async def _parse_item_data(self, material_json_data: dict):
        items = []
        for key in ["avatar", "weapon"]:
            cls = AvatarData if key == "avatar" else WeaponData

            if chunk_data := material_json_data["additions"]["requiredBy"].get(key):
                for data in filter(lambda x: x["rank"] > 3, chunk_data):
                    item_id = data["id"]
                    if isinstance(item_id, str):
                        continue  # 旅行者
                    item_icon = await getattr(self.assets, key)(item_id).icon()
                    items.append(
                        cls(
                            id=item_id,
                            name=data["name"],
                            rarity=data["rank"],
                            icon=item_icon.as_uri(),
                        )
                    )
        return items

    async def _parse_weekday_data(self, weekday_data: dict) -> list[AreaData]:
        area_data_list = []
        for domain in weekday_data.values():
            area_name = AREAS[int(domain["city"]) - 1]

            material_name_list = []
            materials = []
            items = []
            for material_id in domain["reward"][3:]:
                material_json_data = await self._request(f"https://api.ambr.top/v2/CHS/material/{material_id}")
                material_name_list.append(material_json_data["name"])
                material_icon = await self.assets.material(material_id).icon()
                materials.append(MaterialData(icon=material_icon.as_uri(), rarity=material_json_data["rank"]))
                items = await self._parse_item_data(material_json_data)

            area_data_list.append(
                AreaData(
                    name=area_name,
                    material_name=get_material_serial_name(material_name_list),
                    materials=materials,
                    **{"avatars" if isinstance(items[0], AvatarData) else "weapons": items},
                )
            )
        return area_data_list

    async def __call__(self) -> dict[int, FarmingData]:
        week_map = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if (full_farming_json_data := await self._request(self.farming_url)) is None:
            logger.error("从 Ambr 上爬取每日素材失败，请稍后重试")
            return {}

        farming_data_list = []
        for weekday_name, weekday_data in full_farming_json_data.items():
            if (weekday := week_map.index(weekday_name) + 1) == 7:
                continue  # 跳过星期天
            area_data_list = await self._parse_weekday_data(weekday_data)
            farming_data_list.append(FarmingData(weekday=WEEK_MAP[weekday - 1], areas=area_data_list))

        return {k + 1: v for k, v in enumerate(farming_data_list)}
