from typing import Optional, List

from pydantic import BaseModel

from modules.playercards.models.artifact import ArtifactInfo
from modules.playercards.models.fetter import FetterInfo
from modules.playercards.models.skill import Skill
from modules.playercards.models.talent import Talent
from modules.playercards.models.weapon import WeaponInfo


class CharacterValueInfo(BaseModel):
    """角色数值信息"""
    hp: float = 0  # 生命值
    base_hp: float = 0  # 基础生命值
    atk: float = 0  # 攻击力
    base_atk: float = 0  # 基础攻击力
    def_value: float = 0  # 防御力
    base_def: float = 0  # 基础防御力
    elemental_mastery: float = 0  # 元素精通
    crit_rate: float = 0  # 暴击率
    crit_dmg: float = 0  # 暴击伤害
    energy_recharge: float = 0  # 充能效率
    heal_bonus: float = 0  # 治疗
    healed_bonus: float = 0  # 受治疗
    physical_dmg_sub: float = 0  # 物理伤害加成
    physical_dmg_bonus: float = 0  # 物理伤害抗性
    dmg_bonus: float = 0  # 物理伤害抗性

    @property
    def add_hp(self) -> float:
        return self.hp - self.base_hp

    @property
    def add_atk(self) -> float:
        return self.atk - self.base_atk

    @property
    def add_def(self) -> float:
        return self.def_value - self.base_def


class CharacterInfo(BaseModel):
    """角色信息"""
    name: str = ""  # 角色名字
    elementl: str = 0  # 角色等级
    level: int = 0  # 属性
    fetter: Optional[FetterInfo] = None  # 好感度
    base_value: Optional[CharacterValueInfo] = None  # 基础数值
    weapon: Optional[WeaponInfo] = None  # 武器
    artifact: List[ArtifactInfo] = []  # 圣遗物
    skill: List[Skill] = []  # 技能
    talent: List[Talent] = []  # 命座
    icon: str = ""  # 角色图片
