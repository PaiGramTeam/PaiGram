from enum import Enum
from typing import List

from models.wiki.base import Model, WikiModel
from models.wiki.material import Material
from models.wiki.other import WeaponType


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


class WeaponAttribute(Model):
    """武器词条"""
    type: WeaponAttributeType
    value: float


class WeaponAffix(Model):
    """武器技能"""
    """技能名"""
    name: str

    """技能描述"""
    description: List[str]


class Weapon(WikiModel):
    """武器"""
    """武器类型"""
    type: WeaponType

    """攻击力"""
    attack: float

    """武器词条"""
    attribute: WeaponAttribute

    """武器技能"""
    affix: WeaponAffix

    """描述"""
    description: str

    """突破材料"""
    ascension: List[Material]

    """故事"""
    story: str
