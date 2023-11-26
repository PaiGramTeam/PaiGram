from typing import NewType, List, Optional, Tuple
from decimal import Decimal
from pydantic import BaseModel

GCSimCharacter = NewType("GCSimCharacter", str)
GCSimWeapon = NewType("GCSimWeapon", str)
GCSimSet = NewType("GCSimSet", str)

class GCSimWeaponInfo(BaseModel):
    weapon: GCSimWeapon
    refinement: int = 1
    level: int = 1
    max_level: int = 90

class GCSimSetInfo(BaseModel):
    set: GCSimSet
    count: int = 2

class GCSimCharacterStats(BaseModel):
    HP: Decimal = Decimal(0)
    HP_PERCENT: Decimal = Decimal(0)
    ATK: Decimal = Decimal(0)
    ATK_PERCENT: Decimal = Decimal(0)
    DEF: Decimal = Decimal(0)
    DEF_PERCENT: Decimal = Decimal(0)
    EM: Decimal = Decimal(0)
    ER: Decimal = Decimal(0)
    CR: Decimal = Decimal(0)
    CD: Decimal = Decimal(0)
    HEAL: Decimal = Decimal(0)
    PYRO_PERCENT: Decimal = Decimal(0)
    HYDRO_PERCENT: Decimal = Decimal(0)
    DENDRO_PERCENT: Decimal = Decimal(0)
    ELECTRO_PERCENT: Decimal = Decimal(0)
    ANEMO_PERCENT: Decimal = Decimal(0)
    CRYO_PERCENT: Decimal = Decimal(0)
    GEO_PERCENT: Decimal = Decimal(0)
    PHYS_PERCENT: Decimal = Decimal(0)

class GCSimCharacterInfo(BaseModel):
    character: GCSimCharacter
    level: int
    max_level: int
    constellation: int
    talent: List[int]
    weapon_info: GCSimWeaponInfo
    set_info: List[GCSimSetInfo]
    stats: GCSimCharacterStats

class GCSimTarget(BaseModel):
    level: int = 100
    resist: float = 0.1
    position: Tuple[float, float] = (0, 0)
    hp: Optional[int] = None

class GCSimEnergySettings(BaseModel):
    intervals: List[int] = [480,720]
    amount: int = 1

class GCSim(BaseModel):
    options: str = "options iteration=1000 duration=90 swap_delay=12;"
    characters: List[GCSimCharacterInfo]
    targets: List[GCSimTarget]
    energy_settings: Optional[GCSimEnergySettings]
    active_character: Optional[GCSimCharacter]
    script: str