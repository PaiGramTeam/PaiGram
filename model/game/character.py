from typing import Optional, List

from model.baseobject import BaseObject
from model.game.artifact import ArtifactInfo
from model.game.fetter import FetterInfo
from model.game.skill import Skill
from model.game.talent import Talent
from model.game.weapon import WeaponInfo
from model.types import JSONDict


class CharacterValueInfo(BaseObject):
    """角色数值信息
    """

    def __init__(self, hp: float = 0, base_hp: float = 0, atk: float = 0, base_atk: float = 0,
                 def_value: float = 0, base_def: float = 0, elemental_mastery: float = 0, crit_rate: float = 0,
                 crit_dmg: float = 0, energy_recharge: float = 0, heal_bonus: float = 0, healed_bonus: float = 0,
                 physical_dmg_sub: float = 0, physical_dmg_bonus: float = 0, dmg_bonus: float = 0):
        """
        :param hp: 生命值
        :param base_hp: 基础生命值
        :param atk: 攻击力
        :param base_atk: 基础攻击力
        :param def_value: 防御力
        :param base_def: 基础防御力
        :param elemental_mastery: 元素精通
        :param crit_rate: 暴击率
        :param crit_dmg: 暴击伤害
        :param energy_recharge: 充能效率
        :param heal_bonus: 治疗
        :param healed_bonus: 受治疗
        :param physical_dmg_sub: 物理伤害加成
        :param physical_dmg_bonus: 物理伤害抗性
        :param dmg_bonus: 伤害加成
        """
        self.dmg_bonus = dmg_bonus
        self.physical_dmg_bonus = physical_dmg_bonus
        self.physical_dmg_sub = physical_dmg_sub
        self.healed_bonus = healed_bonus
        self.heal_bonus = heal_bonus
        self.energy_recharge = energy_recharge
        self.crit_dmg = crit_dmg
        self.crit_rate = crit_rate
        self.elemental_mastery = elemental_mastery
        self.base_def = base_def
        self.def_value = def_value
        self.base_atk = base_atk
        self.atk = atk
        self.base_hp = base_hp
        self.hp = hp

    @property
    def add_hp(self) -> float:
        return self.hp - self.base_hp

    @property
    def add_atk(self) -> float:
        return self.atk - self.base_atk

    @property
    def add_def(self) -> float:
        return self.def_value - self.base_def

    __slots__ = (
        "hp", "base_hp", "atk", "base_atk", "def_value", "base_def", "elemental_mastery", "crit_rate", "crit_dmg",
        "energy_recharge", "dmg_bonus", "physical_dmg_bonus", "physical_dmg_sub", "healed_bonus",
        "heal_bonus")


class CharacterInfo(BaseObject):
    """角色信息
    """

    def __init__(self, name: str = "", elementl: str = 0, level: int = 0, fetter: Optional[FetterInfo] = None,
                 base_value: Optional[CharacterValueInfo] = None, weapon: Optional[WeaponInfo] = None,
                 artifact: Optional[List[ArtifactInfo]] = None, skill: Optional[List[Skill]] = None,
                 talent: Optional[List[Talent]] = None, icon: str = ""):
        """
        :param name: 角色名字
        :param level: 角色等级
        :param elementl: 属性
        :param fetter: 好感度
        :param base_value: 基础数值
        :param weapon: 武器
        :param artifact: 圣遗物
        :param skill: 技能
        :param talent: 命座
        :param icon: 角色图片
        """
        self.icon = icon
        self.elementl = elementl
        self.talent = talent
        self.skill = skill
        self.artifact = artifact
        self.weapon = weapon
        self.base_value = base_value
        self.fetter = fetter
        self.level = level
        self.name = name

    def to_dict(self) -> JSONDict:
        data = super().to_dict()
        if self.artifact:
            data["artifact"] = [e.to_dict() for e in self.artifact]
        if self.artifact:
            data["skill"] = [e.to_dict() for e in self.skill]
        if self.artifact:
            data["talent"] = [e.to_dict() for e in self.talent]
        return data

    @classmethod
    def de_json(cls, data: Optional[JSONDict]) -> Optional["CharacterInfo"]:
        data = cls._parse_data(data)
        if not data:
            return None
        data["artifact"] = ArtifactInfo.de_list(data.get("sub_item"))
        data["skill"] = Skill.de_list(data.get("sub_item"))
        data["talent"] = Talent.de_list(data.get("sub_item"))
        return cls(**data)

    __slots__ = (
        "name", "level", "level", "fetter", "base_value", "weapon", "artifact", "skill", "talent", "elementl", "icon")
