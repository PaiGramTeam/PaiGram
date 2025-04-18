import datetime
from enum import Enum
from typing import Any, Dict, List, Union, Optional

from pydantic import field_validator, BaseModel

from simnet.models.base import DateTimeField, add_timezone

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
    time: DateTimeField


class FourStarItem(BaseModel):
    name: str
    icon: str
    count: int
    type: str
    time: DateTimeField


class GachaItem(BaseModel):
    id: str
    name: str
    gacha_type: str
    item_type: str
    rank_type: str
    time: DateTimeField

    @field_validator("name")
    @classmethod
    def name_validator(cls, v):
        if item_id := (roleToId(v) or weaponToId(v)):
            if item_id not in not_real_roles:
                return v
        raise ValueError(f"Invalid name {v}")

    @field_validator("gacha_type")
    @classmethod
    def check_gacha_type(cls, v):
        if v not in {"100", "200", "301", "302", "400", "500"}:
            raise ValueError(f"gacha_type must be 200, 301, 302, 400, 500, invalid value: {v}")
        return v

    @field_validator("item_type")
    @classmethod
    def check_item_type(cls, item):
        if item not in {"角色", "武器"}:
            raise ValueError(f"error item type {item}")
        return item

    @field_validator("rank_type")
    @classmethod
    def check_rank_type(cls, rank):
        if rank not in {"5", "4", "3"}:
            raise ValueError(f"error rank type {rank}")
        return rank


class GachaLogInfo(BaseModel):
    user_id: str
    uid: str
    update_time: DateTimeField
    import_type: str = ""
    item_list: Dict[str, List[GachaItem]] = {
        "角色祈愿": [],
        "武器祈愿": [],
        "常驻祈愿": [],
        "新手祈愿": [],
        "集录祈愿": [],
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
        self.from_time = add_timezone(datetime.datetime.strptime(self.from_, "%Y-%m-%d %H:%M:%S"))
        self.to_time = add_timezone(datetime.datetime.strptime(self.to, "%Y-%m-%d %H:%M:%S"))
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
    CHRONICLED = "500"


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
    gacha_id: Optional[str] = ""


class UIGFInfo(BaseModel):
    export_time: str = ""
    export_timestamp: int = 0
    export_app: str = ""
    export_app_version: str = ""
    version: str = UIGF_VERSION

    def __init__(self, **data: Any):
        super().__init__(**data)
        if not self.export_time:
            self.export_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.export_timestamp = int(datetime.datetime.now().timestamp())


class UIGFListInfo(BaseModel):
    uid: int = 0
    timezone: int = 8
    lang: str = "zh-cn"
    list: List[UIGFItem]


class UIGFModel(BaseModel):
    info: UIGFInfo
    hk4e: List[UIGFListInfo]
    hkrpg: List[UIGFListInfo]
    nap: List[UIGFListInfo]
