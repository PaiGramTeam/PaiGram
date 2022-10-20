import datetime
from enum import Enum
from typing import List, Dict, Union

from pydantic import BaseModel, validator

from metadata.shortname import roleToId, weaponToId, not_real_roles
from modules.gacha_log.const import UIGF_VERSION, PM2UIGF_VERSION, PM2UIGF_NAME


class FiveStarItem(BaseModel):
    name: str
    icon: str
    count: int
    type: str
    isUp: bool
    isBig: bool
    time: datetime.datetime


class FourStarItem(BaseModel):
    name: str
    icon: str
    count: int
    type: str
    time: datetime.datetime


class GachaItem(BaseModel):
    id: str
    name: str
    gacha_type: str
    item_type: str
    rank_type: str
    time: datetime.datetime

    @validator("name")
    def name_validator(cls, v):
        if item_id := (roleToId(v) or weaponToId(v)):
            if item_id not in not_real_roles:
                return v
        raise ValueError("Invalid name")

    @validator("gacha_type")
    def check_gacha_type(cls, v):
        if v not in {"100", "200", "301", "302", "400"}:
            raise ValueError("gacha_type must be 200, 301, 302 or 400")
        return v

    @validator("item_type")
    def check_item_type(cls, item):
        if item not in {"角色", "武器"}:
            raise ValueError("error item type")
        return item

    @validator("rank_type")
    def check_rank_type(cls, rank):
        if rank not in {"5", "4", "3"}:
            raise ValueError("error rank type")
        return rank


class GachaLogInfo(BaseModel):
    user_id: str
    uid: str
    update_time: datetime.datetime
    item_list: Dict[str, List[GachaItem]] = {
        "角色祈愿": [],
        "武器祈愿": [],
        "常驻祈愿": [],
        "新手祈愿": [],
    }


class Pool:
    def __init__(self, five: List[str], four: List[str], name: str, to: str, **kwargs):
        self.five = five
        self.real_name = name
        self.name = "、".join(self.five)
        self.four = four
        self.from_ = kwargs.get("from")
        self.to = to
        self.from_time = datetime.datetime.strptime(self.from_, "%Y-%m-%d %H:%M:%S")
        self.to_time = datetime.datetime.strptime(self.to, "%Y-%m-%d %H:%M:%S")
        self.start = self.from_time
        self.start_init = False
        self.end = self.to_time
        self.dict = {}
        self.count = 0

    def parse(self, item: Union[FiveStarItem, FourStarItem]):
        if self.from_time <= item.time <= self.to_time:
            if self.dict.get(item.name):
                self.dict[item.name]["count"] += 1
            else:
                self.dict[item.name] = {
                    "name": item.name,
                    "icon": item.icon,
                    "count": 1,
                    "rank_type": 5 if isinstance(item, FiveStarItem) else 4,
                }

    def count_item(self, item: List[GachaItem]):
        for i in item:
            if self.from_time <= i.time <= self.to_time:
                self.count += 1
                if not self.start_init:
                    self.start = i.time
                self.end = i.time

    def to_list(self):
        return list(self.dict.values())


class XlsxType(Enum):
    PAIMONMOE = 1
    FXQ = 2
    UIGF = 3


class ItemType(Enum):
    CHARACTER = "角色"
    WEAPON = "武器"


class UIGFGachaType(Enum):
    BEGINNER = 100
    STANDARD = 200
    CHARACTER = 301
    WEAPON = 302


class XlsxLine:
    def __init__(
            self, uigf_gacha_type: UIGFGachaType, item_type: ItemType, name: str, time: str, rank_type: int, _id: int
    ) -> None:
        self.uigf_gacha_type = uigf_gacha_type
        self.item_type = item_type
        self.name = name
        self.time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
        self.rank_type = rank_type
        self.id = _id

    def json(self):
        return {
            "gacha_type": str(self.uigf_gacha_type.value),  # 注意！
            "item_id": "",
            "count": "1",
            "time": self.time.strftime("%Y-%m-%d %H:%M:%S"),
            "name": self.name,
            "item_type": self.item_type.value,
            "rank_type": str(self.rank_type),
            "id": str(self.id),
            "uigf_gacha_type": str(self.uigf_gacha_type.value),
        }


class XlsxImporter:
    lines: List[XlsxLine]
    uid: int
    export_time: datetime
    export_app: str = PM2UIGF_NAME
    export_app_version: str = PM2UIGF_VERSION
    uigf_version = UIGF_VERSION
    lang = "zh-cn"

    def __init__(self, lines: List[XlsxLine], uid: int, export_time: datetime.datetime) -> None:
        self.uid = uid
        self.lines = lines
        self.lines.sort(key=lambda x: x.time)
        if self.lines[0].id == "0":  # 如果是从 paimon.moe 导入的，那么就给id赋值
            for index, _ in enumerate(self.lines):
                self.lines[index].id = str(index + 1)
        self.export_time = export_time
        export_time.strftime()

    def json(self) -> dict:
        json_d = {
            "info": {
                "uid": str(self.uid),
                "lang": self.lang,
                "export_time": self.export_time.strftime("%Y-%m-%d %H:%M:%S"),
                "export_timestamp": self.export_time.timestamp(),
                "export_app": self.export_app,
                "export_app_version": self.export_app_version,
                "uigf_version": self.uigf_version,
            },
            "list": [],
        }
        for line in self.lines:
            json_d["list"].append(line.json())
        return json_d


class UIGFItem(BaseModel):
    id: str
    name: str
    count: int = 1
    gacha_type: str
    item_id: str = ""
    item_type: ItemType
    rank_type: str
    time: datetime.datetime
    uigf_gacha_type: UIGFGachaType

    @validator("name")
    def name_validator(cls, v):
        if item_id := (roleToId(v) or weaponToId(v)):
            if item_id not in not_real_roles:
                return v
        raise ValueError("Invalid name")

    @validator("gacha_type")
    def check_gacha_type(cls, v):
        if v not in {"100", "200", "301", "302", "400"}:
            raise ValueError("gacha_type must be 200, 301, 302 or 400")
        return v

    @validator("item_type")
    def check_item_type(cls, item):
        if isinstance(item, str):
            if item not in {"角色", "武器"}:
                raise ValueError("error item type")
            else:
                return ItemType(item)
        elif isinstance(item, ItemType):
            return item
        raise ValueError("error item type")

    @validator("rank_type")
    def check_rank_type(cls, rank):
        if rank not in {"5", "4", "3"}:
            raise ValueError("error rank type")
        return rank

    @validator("time")
    def check_time(cls, t):
        if isinstance(t, str):
            return datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
        elif isinstance(t, datetime.datetime):
            return t
        raise ValueError("error time type")

    class Config:
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S")
        }
