import enum
from typing import Dict

from pydantic import BaseModel
from simnet.models.genshin.chronicle.abyss import SpiralAbyss

from gram_core.services.history_data.models import HistoryData

__all__ = (
    "HistoryData",
    "HistoryDataTypeEnum",
    "HistoryDataAbyss",
)


class HistoryDataTypeEnum(int, enum.Enum):
    ABYSS = 0  # 深境螺旋


class HistoryDataAbyss(BaseModel):
    abyss_data: SpiralAbyss
    character_data: Dict[int, int]

    @classmethod
    def from_data(cls, data: HistoryData):
        return cls.parse_obj(data.data)
