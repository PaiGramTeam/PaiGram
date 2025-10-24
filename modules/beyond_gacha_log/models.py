from typing import Dict, List, TYPE_CHECKING

from pydantic import BaseModel

from simnet.models.base import DateTimeField
from simnet.models.genshin.wish import GenshinBeyondBannerType

from modules.gacha_log.models import ImportType, UIGFInfo

if TYPE_CHECKING:
    from simnet.models.genshin.wish import GenshinBeyondWish


class BeyondGachaItem(BaseModel):
    """BeyondGachaItem"""

    schedule_id: int
    uid: int
    region: str

    id: int
    item_type: str
    item_id: int
    item_name: str
    rank_type: int
    time: DateTimeField

    banner_type: GenshinBeyondBannerType
    op_gacha_type: int

    is_up: str

    @staticmethod
    def from_simnet(data: "GenshinBeyondWish") -> "BeyondGachaItem":
        return BeyondGachaItem(
            schedule_id=data.schedule_id,
            uid=data.uid,
            region=data.region,
            id=data.id,
            item_type=data.type,
            item_id=data.item_id,
            item_name=data.name,
            rank_type=data.rarity,
            time=data.time,
            banner_type=data.banner_type,
            op_gacha_type=data.op_gacha_type,
            is_up=data.is_up,
        )


class BeyondGachaLogInfo(BaseModel):
    user_id: str
    uid: str
    update_time: DateTimeField
    import_type: str = ""
    item_list: Dict[str, List[BeyondGachaItem]] = {
        "常驻颂愿": [],
        "活动颂愿": [],
    }

    @property
    def get_import_type(self) -> ImportType:
        try:
            return ImportType(self.import_type)
        except ValueError:
            return ImportType.UNKNOWN


class UIGFListInfo(BaseModel):
    uid: int = 0
    timezone: int = 8
    lang: str = "zh-cn"
    list: List[BeyondGachaItem]


class UIGFModel(BaseModel):
    info: UIGFInfo
    hk4e_beyond: List[UIGFListInfo]
