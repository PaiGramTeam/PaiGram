from typing import Dict

from enkanetwork import EquipmentsStats

from modules.playercards.fight_prop import FightProp, FightPropScore


class ArtifactStatsTheory:
    def __init__(self, character_name: str, fight_prop_rule_data: Dict[str, Dict[str, float]]):
        self.character_name = character_name
        self.fight_prop_rules = fight_prop_rule_data.get(self.character_name, {})
        fight_prop_rule_list = list(self.fight_prop_rules.keys())
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
        main_prop = {x.name: x for x in self.main_prop}
        if prop := main_prop.get(sub_stats.prop_id):
            weight = self.fight_prop_rules.get(prop.value, 0.0)
            if weight == 0.0:
                weight = float(FightPropScore[sub_stats.prop_id].value)
            score = weight * sub_stats.value
        return round(score, 1)
