import enum
from typing import Dict

from pydantic import BaseModel
from simnet.models.genshin.chronicle.abyss import SpiralAbyss
from simnet.models.genshin.chronicle.img_theater import ImgTheaterData
from simnet.models.genshin.diary import Diary

from gram_core.services.history_data.models import HistoryData

__all__ = (
    "HistoryData",
    "HistoryDataTypeEnum",
    "HistoryDataAbyss",
    "HistoryDataLedger",
    "HistoryDataImgTheater",
)


class HistoryDataTypeEnum(int, enum.Enum):
    ABYSS = 0  # 深境螺旋
    LEDGER = 2  # 开拓月历
    ROLE_COMBAT = 3  # 幻想真境剧诗


class HistoryDataAbyss(BaseModel):
    abyss_data: SpiralAbyss
    character_data: Dict[int, int]

    @classmethod
    def from_data(cls, data: HistoryData) -> "HistoryDataAbyss":
        return cls.parse_obj(data.data)


class HistoryDataLedger(BaseModel):
    diary_data: Diary

    @classmethod
    def from_data(cls, data: HistoryData) -> "HistoryDataLedger":
        return cls.parse_obj(data.data)


class HistoryDataImgTheater(BaseModel):
    abyss_data: ImgTheaterData
    character_data: Dict[int, int]

    @classmethod
    def from_data(cls, data: HistoryData) -> "HistoryDataImgTheater":
        return cls.parse_obj(data.data)
