from enum import Enum
from typing import List, Optional

from typing_extensions import Self

from models.wiki.base import Model, WikiModel
from models.wiki.material import Material
from models.wiki.other import WeaponType

__all__ = ['WeaponAttributeType', 'Weapon', 'WeaponAffix', 'WeaponAttribute']

_WEAPON_ATTR_TYPE_MAP = {
    "HP": ['Health'],
    "HP_p": ['HP%', 'Health %'],
    "ATK": ['Attack'],
    "ATK_p": ['Atk%', 'Attack %'],
    "DEF": ['Defense'],
    "DEF_p": ['Def%', 'Defense %'],
    "EM": ['Elemental Mastery'],
    "ER": ['ER%', 'Energy Recharge %'],
    "CR": ['CrR%', 'Critical Rate %'],
    "CD": ['Crd%', 'Critical Damage %'],
    "PD": ['Phys%', 'Physical Damage %'],
    "HB": [],
    "Pyro": [],
    "Hydro": [],
    "Electro": [],
    "Cryo": [],
    "Dendro": [],
    "Anemo": [],
    "Geo": [],
}


class WeaponAttributeType(Enum):
    HP = "生命"
    HP_p = "生命%"
    ATK = "攻击力"
    ATK_p = "攻击力%"
    DEF = "防御力"
    DEF_p = "防御力%"
    EM = "元素精通"
    ER = "元素充能效率"
    CR = "暴击率"
    CD = "暴击伤害"
    PD = "物理伤害加成"
    HB = "治疗加成"
    Pyro = '火元素伤害加成'
    Hydro = '水元素伤害加成'
    Electro = '雷元素伤害加成'
    Cryo = '冰元素伤害加成'
    Dendro = '草元素伤害加成'
    Anemo = '风元素伤害加成'
    Geo = '岩元素伤害加成'

    # noinspection PyShadowingBuiltins
    @classmethod
    def convert_str(cls, type: str) -> Optional[Self]:
        type = type.strip()
        for k, v in _WEAPON_ATTR_TYPE_MAP.items():
            if type == k or type in v or type.upper() == k:
                return cls[k]


class WeaponAttribute(Model):
    """武器词条"""
    type: WeaponAttributeType
    value: str


class WeaponAffix(Model):
    """武器技能

    Attributes:
        name: 技能名
        description: 技能描述

    """
    name: str
    description: List[str]


class Weapon(WikiModel):
    """武器

    Attributes:
        type: 武器类型
        attack: 基础攻击力
        attribute:
        affix: 武器技能
        description: 描述
        ascension: 突破材料
        story: 武器故事
    """
    type: WeaponType
    attack: float
    attribute: Optional[WeaponAttribute]
    affix: Optional[WeaponAffix]
    description: str
    ascension: List[int]
    story: Optional[str]
