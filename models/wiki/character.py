from enum import Enum

from models.wiki.base import Model
from models.wiki.other import Element, WeaponType
from models.wiki.base import WikiModel


class Association(Enum):
    """角色所属地区"""
    Mainactor = '主角'
    Snezhnaya = '至冬'
    Sumeru = '须弥'
    Inazuma = '稻妻'
    Liyue = '璃月'
    Mondstadt = '蒙德'


class Birth(Model):
    """生日
    Attributes:
        day: 天
        month: 月
    """
    day: int
    month: int


class Character(WikiModel):
    """角色
    Attributes:
        title: 称号
        occupation: 所属
        association: 地区
        weapon_type: 武器类型
        element: 元素
        birth: 生日
        constellation: 命之座
        cn_cv: 中配
        jp_cv: 日配
        en_cv: 英配
        kr_cv: 韩配
        description: 描述
    """
    id: str
    title: str
    occupation: str
    association: Association
    weapon_type: WeaponType
    element: Element
    birth: Birth
    constellation: str
    cn_cv: str
    jp_cv: str
    en_cv: str
    kr_cv: str
    description: str
