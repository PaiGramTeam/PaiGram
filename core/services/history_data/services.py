import datetime
from typing import Dict, List

from pytz import timezone
from simnet.models.genshin.chronicle.abyss import SpiralAbyss

from core.services.history_data.models import HistoryData, HistoryDataTypeEnum, HistoryDataAbyss
from gram_core.base_service import BaseService
from gram_core.services.history_data.services import HistoryDataBaseServices

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib


__all__ = (
    "HistoryDataBaseServices",
    "HistoryDataAbyssServices",
)

TZ = timezone("Asia/Shanghai")


def json_encoder(value):
    if isinstance(value, datetime.datetime):
        return value.astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S")
    return value


class HistoryDataAbyssServices(BaseService, HistoryDataBaseServices):
    DATA_TYPE = HistoryDataTypeEnum.ABYSS.value

    @staticmethod
    def exists_data(data: HistoryData, old_data: List[HistoryData]) -> bool:
        for d in old_data:
            if d.data == data.data:
                return True
        return False

    @staticmethod
    def create(user_id: int, abyss_data: SpiralAbyss, character_data: Dict[int, int]):
        data = HistoryDataAbyss(abyss_data=abyss_data, character_data=character_data)
        json_data = data.json(by_alias=True, encoder=json_encoder)
        return HistoryData(
            user_id=user_id,
            data_id=abyss_data.season,
            time_created=datetime.datetime.now(),
            type=HistoryDataAbyssServices.DATA_TYPE,
            data=jsonlib.loads(json_data),
        )
