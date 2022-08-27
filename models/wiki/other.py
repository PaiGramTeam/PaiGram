from enum import Enum

from typing import Optional

from typing_extensions import Self

__all__ = [
    'Element',
    'WeaponType',
    'AttributeType'
]

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


class Element(Enum):
    Pyro = '火'
    Hydro = '水'
    Electro = '雷'
    Cryo = '冰'
    Dendro = '草'
    Anemo = '风'
    Geo = '岩'
    Multi = '多种'  # 主角


class WeaponType(Enum):
    Sword = '单手剑'
    Claymore = '双手剑'
    Polearm = '长柄武器'
    Catalyst = '法器'
    Bow = '弓'


class AttributeType(Enum):
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

    @classmethod
    def convert_str(cls, string: str) -> Optional[Self]:
        string = string.strip()
        for k, v in _WEAPON_ATTR_TYPE_MAP.items():
            if string == k or string in v or string.upper() == k:
                return cls[k]
