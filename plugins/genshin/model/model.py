from enum import Enum
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, validator


class WeaponType(Enum):
    BOW = "bow"
    CLAYMORE = "claymore"
    CATALYST = "catalyst"
    POLEARM = "polearm"
    SWORD = "sword"

class ArtifactPosition(Enum):
    FLOWER = "flower"
    PLUME = "plume"
    SANDS = "sands"
    GOBLET = "goblet"
    CIRCLET = "circlet"

class ArtifactAttributeType(Enum):
    HP = "hp"
    ATK = "atk"
    DEF = "def"
    HP_PERCENT = "hp_percent"
    ATK_PERCENT = "atk_percent"
    DEF_PERCENT = "def_percent"
    ELEMENTAL_MASTERY = "elemental_mastery"
    ENERGY_RECHARGE = "energy_recharge"
    CRIT_RATE = "crit_rate"
    CRIT_DMG = "crit_dmg"
    HEALING_BONUS = "healing_bonus"
    PYRO_DMG_BONUS = "pyro_dmg_bonus"
    HYDRO_DMG_BONUS = "hydro_dmg_bonus"
    DENDRO_DMG_BONUS = "dendro_dmg_bonus"
    ELECTRO_DMG_BONUS = "electro_dmg_bonus"
    ANEMO_DMG_BONUS = "anemo_dmg_bonus"
    CRYO_DMG_BONUS = "cryo_dmg_bonus"
    GEO_DMG_BONUS = "geo_dmg_bonus"
    PHYSICAL_DMG_BONUS = "physical_dmg_bonus"

class ArtifactAttribute(BaseModel):
    type: ArtifactAttributeType
    value: Decimal

class Weapon(BaseModel):
    id: int = 0
    name: str = ""
    type: WeaponType
    level: int = 0
    max_level: int = 0
    refinement: int = 0
    ascension: int = 0

    @validator('max_level')
    def validate_max_level(cls, v, values):
        if v < values['level']:
            raise ValueError('max_level must be greater than or equal to level')
        return v
    @validator('refinement')
    def validate_refinement(cls, v, values):
        if v < 0 or v > 5:
            raise ValueError('refinement must be between 1 and 5')
        return v

class Artifact(BaseModel):
    id: int = 0
    name: str = ""
    position: ArtifactPosition
    level: int = 0
    rarity: int = 0
    main_attribute: ArtifactAttribute
    sub_attributes: List[ArtifactAttribute] = []

    @validator('level')
    def validate_level(cls, v):
        if v < 0 or v > 20:
            raise ValueError('level must be between 0 and 20')
        return v

    @validator('rarity')
    def validate_rarity(cls, v):
        if v < 0 or v > 5:
            raise ValueError('rarity must be between 0 and 5')
        return v

    @validator('sub_attributes')
    def validate_sub_attributes(cls, v):
        if len(v) > 4:
            raise ValueError('sub_attributes must not be greater than 4')
        return v

class CharacterStats(BaseModel):
    BASE_HP: Decimal = Decimal(0)
    HP: Decimal = Field(Decimal(0), alias="FIGHT_PROP_HP")
    HP_PERCENT: Decimal = Field(Decimal(0), alias="FIGHT_PROP_HP_PERCENT")
    BASE_ATTACK: Decimal = Field(Decimal(0), alias="FIGHT_PROP_BASE_ATTACK")
    ATTACK: Decimal = Field(Decimal(0), alias="FIGHT_PROP_ATTACK")
    ATTACK_PERCENT: Decimal = Field(Decimal(0), alias="FIGHT_PROP_ATTACK_PERCENT")
    BASE_DEFENSE: Decimal = Field(Decimal(0), alias="FIGHT_PROP_BASE_DEFENSE")
    DEFENSE: Decimal = Field(Decimal(0), alias="FIGHT_PROP_DEFENSE")
    DEFENSE_PERCENT: Decimal = Field(Decimal(0), alias="FIGHT_PROP_DEFENSE_PERCENT")
    ELEMENTAL_MASTERY: Decimal = Field(Decimal(0), alias="FIGHT_PROP_ELEMENT_MASTERY")

    CRIT_RATE: Decimal = Field(Decimal(0), alias="FIGHT_PROP_CRITICAL")
    CRIT_DMG: Decimal = Field(Decimal(0), alias="FIGHT_PROP_CRITICAL_HURT")
    HEALING_BONUS: Decimal = Field(Decimal(0), alias="FIGHT_PROP_HEAL_ADD")
    INCOMING_HEALING_BONUS: Decimal = Field(Decimal(0), alias="FIGHT_PROP_HEALED_ADD")
    ENERGY_RECHARGE: Decimal = Field(Decimal(0), alias="FIGHT_PROP_CHARGE_EFFICIENCY")
    CD_REDUCTION: Decimal = Field(Decimal(0), alias="FIGHT_PROP_SKILL_CD_MINUS_RATIO")
    SHIELD_STRENGTH: Decimal = Field(Decimal(0), alias="FIGHT_PROP_SHIELD_COST_MINUS_RATIO")

    PYRO_DMG_BONUS: Decimal = Field(Decimal(0), alias="FIGHT_PROP_FIRE_ADD_HURT")
    PTRO_RES: Decimal = Field(Decimal(0), alias="FIGHT_PROP_FIRE_SUB_HURT")
    HYDRO_DMG_BONUS: Decimal = Field(Decimal(0), alias="FIGHT_PROP_WATER_ADD_HURT")
    HYDRO_RES: Decimal = Field(Decimal(0), alias="FIGHT_PROP_WATER_SUB_HURT")
    DENDRO_DMG_BONUS: Decimal = Field(Decimal(0), alias="FIGHT_PROP_GRASS_ADD_HURT")
    DENDRO_RES: Decimal = Field(Decimal(0), alias="FIGHT_PROP_GRASS_SUB_HURT")
    ELECTRO_DMG_BONUS: Decimal = Field(Decimal(0), alias="FIGHT_PROP_ELEC_ADD_HURT")
    ELECTRO_RES: Decimal = Field(Decimal(0), alias="FIGHT_PROP_ELEC_SUB_HURT")
    ANEMO_DMG_BONUS: Decimal = Field(Decimal(0), alias="FIGHT_PROP_WIND_ADD_HURT")
    ANEMO_RES: Decimal = Field(Decimal(0), alias="FIGHT_PROP_WIND_SUB_HURT")
    CRYO_DMG_BONUS: Decimal = Field(Decimal(0), alias="FIGHT_PROP_ICE_ADD_HURT")
    CRYO_RES: Decimal = Field(Decimal(0), alias="FIGHT_PROP_ICE_SUB_HURT")
    GEO_DMG_BONUS: Decimal = Field(Decimal(0), alias="FIGHT_PROP_ROCK_ADD_HURT")
    GEO_RES: Decimal = Field(Decimal(0), alias="FIGHT_PROP_ROCK_SUB_HURT")
    PHYSICAL_DMG_BONUS: Decimal = Field(Decimal(0), alias="FIGHT_PROP_PHYSICAL_SUB_HURT")
    PHYSICAL_RES: Decimal = Field(Decimal(0), alias="FIGHT_PROP_PHYSICAL_ADD_HURT")

    CURRENT_HP: Decimal = Field(Decimal(0), alias="FIGHT_PROP_CUR_HP")
    MAX_HP: Decimal = Field(Decimal(0), alias="FIGHT_PROP_MAX_HP")
    CURRENT_ATTACK: Decimal = Field(Decimal(0), alias="FIGHT_PROP_CUR_ATTACK")
    CURRENT_DEFENSE: Decimal = Field(Decimal(0), alias="FIGHT_PROP_CUR_DEFENSE")


class Character(BaseModel):
    id: int = 0
    name: str = ""
    weapon: Optional[Weapon] = None
    artifacts: List[Artifact] = []
    level: int = 0
    max_level: int = 0
    constellation: int = 0
    ascension: int = 0
    skills: List[int] = []
    rarity: int = 0
    stats: CharacterStats = CharacterStats()

    @validator('max_level')
    def validate_max_level(cls, v, values):
        if v < values['level']:
            raise ValueError('max_level must be greater than or equal to level')
        return v
    
    @validator('skills')
    def validate_skills(cls, v):
        # if len(v) == 0:
        #     raise ValueError('skills must not be empty')
        if len(v) > 3:
            raise ValueError('skills must not be greater than 3')
        return v

