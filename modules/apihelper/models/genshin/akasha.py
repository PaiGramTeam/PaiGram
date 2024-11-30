from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional

from pydantic import Field
from simnet.models.base import APIModel as BaseModel


class AkashaSubStat(str, Enum):
    CRR = "双暴"
    ATK = "百分比攻击力"
    HP = "百分比生命值"
    DEF = "百分比防御力"
    ATKF = "固定攻击力"
    HPF = "固定生命值"
    DEFF = "固定防御力"
    EM = "元素精通"
    ER = "元素充能效率"
    CR = "暴击率"
    CD = "暴击伤害"


class AkashaRankCalFit(BaseModel):
    calculationId: str
    short: str
    name: str
    details: str
    result: float
    ranking: str
    outOf: int
    priority: int
    type: str


class AkashaRankCal(BaseModel):
    fit: AkashaRankCalFit


class AkashaRank(BaseModel):
    _id: str
    characterId: int
    uid: int
    constellation: int
    icon: str


class AkashaLeaderboardCategoryWeapon(BaseModel):
    name: str
    icon: str
    substat: str
    type: str
    rarity: str
    refinement: int
    calculationId: str
    details: str


class AkashaLeaderboardCategory(BaseModel):
    _id: str
    name: str
    addDate: datetime
    c6: str
    characterId: int
    characterName: str
    count: int
    details: str
    element: str
    new: int
    rarity: int
    short: str
    weapons: List[AkashaLeaderboardCategoryWeapon]
    weaponsCount: int
    characterIcon: str
    index: int


class AkashaLeaderboardCalculation(BaseModel):
    id: str
    result: float

    @property
    def int(self) -> int:
        return int(self.result)


class AkashaLeaderboardArtifactSet(BaseModel):
    icon: str
    count: int


class AkashaLeaderboardOwner(BaseModel):
    nickname: str
    adventureRank: float
    profilePicture: Any = None
    nameCard: str
    patreon: Dict[str, Any]
    region: str


class AkashaLeaderboardStatsValue(BaseModel):
    value: float

    @property
    def int(self) -> int:
        return int(self.value)

    @property
    def percent(self) -> str:
        return f"{self.value * 100:.1f}"

    @property
    def web_value(self) -> str:
        return f"{self.value:.2f}"


class AkashaLeaderboardStats(BaseModel):
    maxHp: AkashaLeaderboardStatsValue
    atk: AkashaLeaderboardStatsValue
    def_: AkashaLeaderboardStatsValue = Field(..., alias="def")
    elementalMastery: AkashaLeaderboardStatsValue
    energyRecharge: AkashaLeaderboardStatsValue
    healingBonus: AkashaLeaderboardStatsValue
    critRate: AkashaLeaderboardStatsValue
    critDamage: AkashaLeaderboardStatsValue
    electroDamageBonus: Optional[AkashaLeaderboardStatsValue] = None


class AkashaLeaderboardWeaponInfo(BaseModel):
    level: int
    promoteLevel: int
    refinementLevel: AkashaLeaderboardStatsValue


class AkashaLeaderboardWeapon(BaseModel):
    weaponInfo: AkashaLeaderboardWeaponInfo
    flat: Dict[str, Any]
    name: str
    icon: str


class AkashaLeaderboardCharacterMetadata(BaseModel):
    element: str


class AkashaLeaderboard(BaseModel):
    _id: str
    calculation: AkashaLeaderboardCalculation
    characterId: int
    type: str
    uid: str
    artifactObjects: Dict[str, Any]
    artifactSets: Dict[str, AkashaLeaderboardArtifactSet]
    constellation: int
    costumeId: str
    critValue: float
    md5: str
    name: str
    owner: AkashaLeaderboardOwner
    propMap: Dict[str, Any]
    proudSkillExtraLevelMap: Dict[str, Any]
    stats: AkashaLeaderboardStats
    talentsLevelMap: Dict[str, Any]
    weapon: AkashaLeaderboardWeapon
    icon: str
    index: str
    nameCardLink: str
    profilePictureLink: str
    characterMetadata: AkashaLeaderboardCharacterMetadata


class AkashaArtifactType(str, Enum):
    BRACER = "EQUIP_BRACER"
    """生之花"""
    NECKLACE = "EQUIP_NECKLACE"
    """死之羽"""
    SHOES = "EQUIP_SHOES"
    """时之沙"""
    RING = "EQUIP_RING"
    """空之杯"""
    DRESS = "EQUIP_DRESS"
    """理之冠"""

    @property
    def real_name(self):
        name_map = {
            "EQUIP_BRACER": "生之花",
            "EQUIP_NECKLACE": "死之羽",
            "EQUIP_SHOES": "时之沙",
            "EQUIP_RING": "空之杯",
            "EQUIP_DRESS": "理之冠",
        }
        return name_map[self.value]


class AkashaArtifact(BaseModel):
    _id: str
    uid: int
    critValue: float
    equipType: AkashaArtifactType
    icon: str
    level: int
    mainStatKey: str
    mainStatValue: float
    name: str
    owner: AkashaLeaderboardOwner
    setName: str
    stars: int
    substats: Dict[str, float]
    substatsIdList: List[int]
    index: int
    nameCardLink: str
    profilePictureLink: str
