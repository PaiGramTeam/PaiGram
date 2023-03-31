import datetime
from enum import Enum
from typing import Any, Dict, List, Union

from pydantic import BaseModel, validator

from metadata.shortname import not_real_roles, roleToId, weaponToId
from modules.gacha_log.const import UIGF_VERSION


class ImportType(Enum):
    PaiGram = "PaiGram"
    PAIMONMOE = "PAIMONMOE"
    FXQ = "FXQ"
    UIGF = "UIGF"
    UNKNOWN = "UNKNOWN"


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
    import_type: str = ""
    item_list: Dict[str, List[GachaItem]] = {
        "角色祈愿": [],
        "武器祈愿": [],
        "常驻祈愿": [],
        "新手祈愿": [],
    }

    @property
    def get_import_type(self) -> ImportType:
        try:
            return ImportType(self.import_type)
        except ValueError:
            return ImportType.UNKNOWN


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
                    self.start_init = True
                self.end = i.time

    def to_list(self):
        return list(self.dict.values())


class ItemType(Enum):
    CHARACTER = "角色"
    WEAPON = "武器"


class UIGFGachaType(Enum):
    BEGINNER = "100"
    STANDARD = "200"
    CHARACTER = "301"
    WEAPON = "302"
    CHARACTER2 = "400"


class UIGFItem(BaseModel):
    id: str
    name: str
    count: str = "1"
    gacha_type: UIGFGachaType
    item_id: str = ""
    item_type: ItemType
    rank_type: str
    time: str
    uigf_gacha_type: UIGFGachaType


class UIGFInfo(BaseModel):
    uid: str = "0"
    lang: str = "zh-cn"
    export_time: str = ""
    export_timestamp: int = 0
    export_app: str = ""
    export_app_version: str = ""
    uigf_version: str = UIGF_VERSION

    def __init__(self, **data: Any):
        super().__init__(**data)
        if not self.export_time:
            self.export_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.export_timestamp = int(datetime.datetime.now().timestamp())


class UIGFModel(BaseModel):
    info: UIGFInfo
    list: List[UIGFItem]
