from datetime import timedelta
from enum import Enum
from typing import List

from pydantic import BaseModel


class Date(BaseModel):
    month: int
    date: List[int]
    week: List[str]
    is_today: List[bool]


class ActEnum(str, Enum):
    character = "character"
    weapon = "weapon"
    activity = "activity"
    normal = "normal"
    no_display = "pass"
    abyss = "abyss"

    def __str__(self) -> str:
        return self.value


class FinalAct(BaseModel):
    id: int
    type: ActEnum
    title: str
    banner: str
    mergeStatus: int = 0
    face: str = ""
    icon: str = ""
    left: float = 0.0
    width: float = 0.0
    label: str = ""
    sort: int = 0
    idx: int = 0
    start: str = ""
    end: str = ""
    duration: timedelta = timedelta(0)


class ActDetail(BaseModel):
    ann_id: int = 0
    banner: str = ""
    tag_icon: str = ""
    title: str
    start_time: str
    end_time: str
    ...


class ActTime(BaseModel):
    title: str = ""
    start: str = ""
    end: str = ""
    display: bool = True


class BirthChar(BaseModel):
    name: str
    star: int
    icon: str
