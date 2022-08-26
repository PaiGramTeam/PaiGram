from enum import Enum

from models.wiki.base import Model
from models.wiki.other import Element, WeaponType
from tests.test import WikiModel


class Association(Enum):
    Inazuma = '稻妻'


class Birth(Model):
    """生日"""
    day: int
    month: int


class Character(WikiModel):
    """角色"""
    """称号"""
    title: str

    """所属"""
    occupation: str

    """地区"""
    association: Association

    """武器类型"""
    weapon_type: WeaponType

    """元素"""
    element: Element

    """生日"""
    birth: Birth

    """星座"""
    constellation: str

    """中配"""
    cn_cv: str

    """日配"""
    jp_cv: str

    """英配"""
    en_cv: str

    """韩配"""
    kr_cv: str

    """角色描述"""
    description: str
