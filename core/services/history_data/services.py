import datetime
from typing import Dict, List

from simnet.models.genshin.chronicle.abyss import SpiralAbyss
from simnet.models.genshin.chronicle.hard_challenge import HardChallengeData
from simnet.models.genshin.chronicle.img_theater import ImgTheaterData
from simnet.models.genshin.diary import Diary

from core.services.history_data.models import (
    HistoryData,
    HistoryDataTypeEnum,
    HistoryDataAbyss,
    HistoryDataLedger,
    HistoryDataImgTheater,
    HistoryDataHardChallenge,
)
from gram_core.base_service import BaseService
from gram_core.services.history_data.services import HistoryDataBaseServices

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib


__all__ = (
    "HistoryDataBaseServices",
    "HistoryDataAbyssServices",
    "HistoryDataLedgerServices",
    "HistoryDataImgTheaterServices",
    "HistoryDataHardChallengeServices",
)


class HistoryDataAbyssServices(BaseService, HistoryDataBaseServices):
    DATA_TYPE = HistoryDataTypeEnum.ABYSS.value

    @staticmethod
    def exists_data(data: HistoryData, old_data: List[HistoryData]) -> bool:
        def _get_data(_d: dict):
            return _d.get("abyss_data", {}).get("floors")

        floor = _get_data(data.data)
        return any(_get_data(d.data) == floor for d in old_data)

    @staticmethod
    def create(user_id: int, abyss_data: SpiralAbyss, character_data: Dict[int, int]):
        data = HistoryDataAbyss(abyss_data=abyss_data, character_data=character_data)
        json_data = data.model_dump_json(by_alias=True)
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
        json_data = data.model_dump_json(by_alias=True)
        return HistoryData(
            user_id=user_id,
            data_id=diary_data.data_id,
            time_created=datetime.datetime.now(),
            type=HistoryDataLedgerServices.DATA_TYPE,
            data=jsonlib.loads(json_data),
        )


class HistoryDataImgTheaterServices(BaseService, HistoryDataBaseServices):
    DATA_TYPE = HistoryDataTypeEnum.ROLE_COMBAT.value

    @staticmethod
    def exists_data(data: HistoryData, old_data: List[HistoryData]) -> bool:
        def _get_data(_d: dict):
            return _d.get("abyss_data", {}).get("detail", {}).get("rounds_data")

        floor = _get_data(data.data)
        return any(_get_data(d.data) == floor for d in old_data)

    @staticmethod
    def create(user_id: int, abyss_data: ImgTheaterData, character_data: Dict[int, int]):
        data = HistoryDataImgTheater(abyss_data=abyss_data, character_data=character_data)
        json_data = data.model_dump_json(by_alias=True)
        return HistoryData(
            user_id=user_id,
            data_id=abyss_data.schedule.id,
            time_created=datetime.datetime.now(),
            type=HistoryDataImgTheaterServices.DATA_TYPE,
            data=jsonlib.loads(json_data),
        )


class HistoryDataHardChallengeServices(BaseService, HistoryDataBaseServices):
    DATA_TYPE = HistoryDataTypeEnum.HARD_CHALLENGE.value

    @staticmethod
    def exists_data(data: HistoryData, old_data: List[HistoryData]) -> bool:
        def _get_data(_d: dict):
            return _d.get("abyss_data", {}).get("single", {}).get("challenge", [{}])[0].get("teams", [])

        abyss_data = _get_data(data.data)
        return any(_get_data(d.data) == abyss_data for d in old_data)

    @staticmethod
    def create(user_id: int, abyss_data: HardChallengeData):
        data = HistoryDataHardChallenge(abyss_data=abyss_data)
        json_data = data.model_dump_json(by_alias=True)
        return HistoryData(
            user_id=user_id,
            data_id=abyss_data.schedule.id,
            time_created=datetime.datetime.now(),
            type=HistoryDataHardChallengeServices.DATA_TYPE,
            data=jsonlib.loads(json_data),
        )
