from enum import Enum


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
