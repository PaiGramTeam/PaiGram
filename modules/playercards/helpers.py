import os

import ujson as json
from enkanetwork import EquipmentsStats

from modules.playercards.fight_prop import FightProp, FightPropScore

_project_path = os.path.dirname(__file__)
_fight_prop_rule_file = os.path.join(_project_path, "metadata", "FightPropRule.json")
with open(_fight_prop_rule_file, "r", encoding="utf-8") as f:
    fight_prop_rule_data: dict = json.load(f)


class ArtifactStatsTheory:
    def __init__(self, character_name: str):
        self.character_name = character_name
        fight_prop_rule_list = fight_prop_rule_data.get(self.character_name, [])
        self.main_prop = [FightProp(fight_prop_rule) for fight_prop_rule in fight_prop_rule_list]
        if not self.main_prop:
            self.main_prop = [
                FightProp.FIGHT_PROP_CRITICAL,
                FightProp.FIGHT_PROP_CRITICAL_HURT,
                FightProp.FIGHT_PROP_ATTACK_PERCENT,
            ]
        # 修正要评分的数值词条
        if FightProp.FIGHT_PROP_ATTACK_PERCENT in self.main_prop and FightProp.FIGHT_PROP_ATTACK not in self.main_prop:
            self.main_prop.append(FightProp.FIGHT_PROP_ATTACK)
        if FightProp.FIGHT_PROP_HP_PERCENT in self.main_prop and FightProp.FIGHT_PROP_HP not in self.main_prop:
            self.main_prop.append(FightProp.FIGHT_PROP_HP)
        if (
            FightProp.FIGHT_PROP_DEFENSE_PERCENT in self.main_prop
            and FightProp.FIGHT_PROP_DEFENSE not in self.main_prop
        ):
            self.main_prop.append(FightProp.FIGHT_PROP_DEFENSE)

    def theory(self, sub_stats: EquipmentsStats) -> float:
        """圣遗物副词条评分
        Args:
            sub_stats: 圣遗物对象
        Returns:
            返回得分
        """
        score: float = 0
        if sub_stats.prop_id in map(lambda x: x.name, self.main_prop):
            score = float(FightPropScore[sub_stats.prop_id].value) * sub_stats.value
        return round(score, 1)
