from enum import Enum
from typing import List

from pydantic import BaseModel


class Date(BaseModel):
    """日历日期"""

    month: int
    date: List[int]  # skipcq: PTC-W0052
    week: List[str]
    is_today: List[bool]


class ActEnum(str, Enum):
    """活动类型"""

    character = "character"
    weapon = "weapon"
    activity = "activity"
    normal = "normal"
    no_display = "pass"
    abyss = "abyss"

    def __str__(self) -> str:
        return self.value


class FinalAct(BaseModel):
    """最终活动数据"""

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
    duration: int = 0


class ActDetail(BaseModel):
    """活动详情"""

    ann_id: int = 0
    banner: str = ""
    tag_icon: str = ""
    title: str
    start_time: str
    end_time: str
    ...


class ActTime(BaseModel):
    """活动时间"""

    title: str = ""
    start: str = ""
    end: str = ""
    display: bool = True


class BirthChar(BaseModel):
    """生日角色"""

    name: str
    star: int
    icon: str
