from enum import Enum
from typing import Optional

from typing_extensions import Self

from modules.wiki.base import HONEY_HOST

__all__ = [
    "Element",
    "WeaponType",
    "AttributeType",
    "Association",
]


class Element(Enum):
    """元素"""

    Pyro = "火"
    Hydro = "水"
    Electro = "雷"
    Cryo = "冰"
    Dendro = "草"
    Anemo = "风"
    Geo = "岩"
    Multi = "无"  # 主角


_WEAPON_ICON_MAP = {
    "Sword": HONEY_HOST.join("img/s_23101.png"),
    "Claymore": HONEY_HOST.join("img/s_163101.png"),
    "Polearm": HONEY_HOST.join("img/s_233101.png"),
    "Catalyst": HONEY_HOST.join("img/s_43101.png"),
    "Bow": HONEY_HOST.join("img/s_213101.png"),
}


class WeaponType(Enum):
    """武器类型"""

    Sword = "单手剑"
    Claymore = "双手剑"
    Polearm = "长柄武器"
    Catalyst = "法器"
    Bow = "弓"

    def icon_url(self) -> str:
        return str(_WEAPON_ICON_MAP.get(self.name))


_ATTR_TYPE_MAP = {
    # 这个字典用于将 Honey 页面中遇到的 属性的缩写的字符 转为 AttributeType 的字符
    # 例如 Honey 页面上写的 HP% 则对应 HP_p
    "HP": ["Health"],
    "HP_p": ["HP%", "Health %"],
    "ATK": ["Attack"],
    "ATK_p": ["Atk%", "Attack %"],
    "DEF": ["Defense"],
    "DEF_p": ["Def%", "Defense %"],
    "EM": ["Elemental Mastery"],
    "ER": ["ER%", "Energy Recharge %"],
    "CR": ["CrR%", "Critical Rate %", "CritRate%"],
    "CD": ["Crd%", "Critical Damage %", "CritDMG%"],
    "PD": ["Phys%", "Physical Damage %"],
    "HB": [],
    "Pyro": [],
    "Hydro": [],
    "Electro": [],
    "Cryo": [],
    "Dendro": [],
    "Anemo": [],
    "Geo": [],
}


class AttributeType(Enum):
    """属性枚举类。包含了武器和圣遗物的属性。"""

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
    Pyro = "火元素伤害加成"
    Hydro = "水元素伤害加成"
    Electro = "雷元素伤害加成"
    Cryo = "冰元素伤害加成"
    Dendro = "草元素伤害加成"
    Anemo = "风元素伤害加成"
    Geo = "岩元素伤害加成"

    @classmethod
    def convert(cls, string: str) -> Optional[Self]:
        string = string.strip()
        for k, v in _ATTR_TYPE_MAP.items():
            if string == k or string in v or string.upper() == k:
                return cls[k]
        return None


_ASSOCIATION_MAP = {
    "Other": ["Mainactor", "Ranger", "Fatui"],
    "Snezhnaya": [],
    "Sumeru": [],
    "Inazuma": [],
    "Liyue": [],
    "Mondstadt": [],
}


class Association(Enum):
    """角色所属地区"""

    Other = "其它"
    Snezhnaya = "至冬"
    Sumeru = "须弥"
    Inazuma = "稻妻"
    Liyue = "璃月"
    Mondstadt = "蒙德"

    @classmethod
    def convert(cls, string: str) -> Optional[Self]:
        string = string.strip()
        for k, v in _ASSOCIATION_MAP.items():
            if string == k or string in v:
                return cls[k]
            string = string.lower().title()
            if string == k or string in v:
                return cls[k]
        return cls[string]
