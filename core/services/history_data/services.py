import datetime
from typing import Dict, List

from pytz import timezone
from simnet.models.genshin.chronicle.abyss import SpiralAbyss
from simnet.models.genshin.diary import Diary

from core.services.history_data.models import HistoryData, HistoryDataTypeEnum, HistoryDataAbyss, HistoryDataLedger
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
        return any(d.data == data.data for d in old_data)

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


class HistoryDataLedgerServices(BaseService, HistoryDataBaseServices):
    DATA_TYPE = HistoryDataTypeEnum.LEDGER.value

    @staticmethod
    def create(user_id: int, diary_data: Diary):
        data = HistoryDataLedger(diary_data=diary_data)
        json_data = data.json(by_alias=True, encoder=json_encoder)
        return HistoryData(
            user_id=user_id,
            data_id=diary_data.data_id,
            time_created=datetime.datetime.now(),
            type=HistoryDataLedgerServices.DATA_TYPE,
            data=jsonlib.loads(json_data),
        )
