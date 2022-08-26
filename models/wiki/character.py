from enum import Enum

from models.wiki.base import Model
from models.wiki.other import Element, WeaponType
from tests.test import WikiModel


class Association(Enum):
    """角色所属"""
    Mainactor = '主角'
    Fatui = '愚人众'
    Sumeru = '须弥'
    Inazuma = '稻妻'
    Liyue = '璃月'
    Mondstadt = '蒙德'


class Birth(Model):
    """生日"""
    day: int
    """天"""
    month: int
    """月"""


class Character(WikiModel):
    """角色"""
    title: str
    """称号"""

    occupation: str
    """所属"""

    association: Association
    """地区"""

    weapon_type: WeaponType
    """武器类型"""

    element: Element
    """元素"""

    birth: Birth
    """生日"""

    constellation: str
    """星座"""

    cn_cv: str
    """中配"""

    jp_cv: str
    """日配"""

    en_cv: str
    """英配"""

    kr_cv: str
    """韩配"""

    description: str
    """角色描述"""
