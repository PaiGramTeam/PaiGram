from typing import List

from modules.playercards.models.fightprop import FightProp, FightPropScore
from modules.playercards.models.item import GameItem


def artifact_score(items: List[GameItem], main_items: List[FightProp] = None):
    """圣遗物副词条评分"""
    score: float = 0
    if main_items is None:
        main_items = [FightProp.FIGHT_PROP_CRITICAL, FightProp.FIGHT_PROP_CRITICAL_HURT,
                      FightProp.FIGHT_PROP_ATTACK_PERCENT]
    for item in items:
        for main_type in main_items:
            if item.type == main_type:
                score += FightPropScore.__getitem__(item.type.name).value * item.value
    return round(score, 2)
