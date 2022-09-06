import enum


class FightProp(enum.Enum):
    FIGHT_PROP_BASE_ATTACK = "基础攻击力"  # 基础攻击力
    FIGHT_PROP_BASE_DEFENSE = "基础防御力"  # 基础防御力
    FIGHT_PROP_BASE_HP = "基础血量"
    FIGHT_PROP_ATTACK = "攻击力"  # 数值攻击力
    FIGHT_PROP_ATTACK_PERCENT = "百分比攻击力"
    FIGHT_PROP_HP = "血量"  # 数值防御力
    FIGHT_PROP_HP_PERCENT = "百分比血量"
    FIGHT_PROP_DEFENSE = "防御力"  # 数值防御力
    FIGHT_PROP_DEFENSE_PERCENT = "百分比防御力"
    FIGHT_PROP_ELEMENT_MASTERY = "元素精通"
    FIGHT_PROP_CRITICAL = "暴击率"
    FIGHT_PROP_CRITICAL_HURT = "暴击伤害"
    FIGHT_PROP_CHARGE_EFFICIENCY = "元素充能效率"
    FIGHT_PROP_FIRE_SUB_HURT = "火元素抗性"
    FIGHT_PROP_ELEC_SUB_HURT = "雷元素抗性"
    FIGHT_PROP_ICE_SUB_HURT = "冰元素抗性"
    FIGHT_PROP_WATER_SUB_HURT = "水元素抗性"
    FIGHT_PROP_WIND_SUB_HURT = "风元素抗性"
    FIGHT_PROP_ROCK_SUB_HURT = "岩元素抗性"
    FIGHT_PROP_GRASS_SUB_HURT = "草元素抗性"
    FIGHT_PROP_FIRE_ADD_HURT = "火元素伤害加成"
    FIGHT_PROP_ELEC_ADD_HURT = "雷元素伤害加成"
    FIGHT_PROP_ICE_ADD_HURT = "冰元素伤害加成"
    FIGHT_PROP_WATER_ADD_HURT = "水元素伤害加成"
    FIGHT_PROP_WIND_ADD_HURT = "风元素伤害加成"
    FIGHT_PROP_ROCK_ADD_HURT = "岩元素伤害加成"
    FIGHT_PROP_GRASS_ADD_HURT = "草元素伤害加成"
    FIGHT_PROP_PHYSICAL_ADD_HURT = "物理伤害加成"
    FIGHT_PROP_HEAL_ADD = "治疗加成"


class FightPropScore(enum.Enum):
    FIGHT_PROP_BASE_ATTACK = 1
    FIGHT_PROP_BASE_DEFENSE = 1
    FIGHT_PROP_BASE_HP = 1
    FIGHT_PROP_ATTACK = 0
    FIGHT_PROP_ATTACK_PERCENT = 4 / 3
    FIGHT_PROP_HP = 0
    FIGHT_PROP_HP_PERCENT = 4 / 3
    FIGHT_PROP_DEFENSE = 0
    FIGHT_PROP_DEFENSE_PERCENT = 4 / 3
    FIGHT_PROP_ELEMENT_MASTERY = 1 / 3
    FIGHT_PROP_CRITICAL = 2
    FIGHT_PROP_CRITICAL_HURT = 1
    FIGHT_PROP_CHARGE_EFFICIENCY = 4 / 3
    FIGHT_PROP_FIRE_SUB_HURT = 1
    FIGHT_PROP_ELEC_SUB_HURT = 1
    FIGHT_PROP_ICE_SUB_HURT = 1
    FIGHT_PROP_WATER_SUB_HURT = 1
    FIGHT_PROP_WIND_SUB_HURT = 1
    FIGHT_PROP_ROCK_SUB_HURT = 1
    FIGHT_PROP_GRASS_SUB_HURT = 1
    FIGHT_PROP_FIRE_ADD_HURT = 1
    FIGHT_PROP_ELEC_ADD_HURT = 1
    FIGHT_PROP_ICE_ADD_HURT = 1
    FIGHT_PROP_WATER_ADD_HURT = 1
    FIGHT_PROP_WIND_ADD_HURT = 1
    FIGHT_PROP_ROCK_ADD_HURT = 1
    FIGHT_PROP_GRASS_ADD_HURT = 1
    FIGHT_PROP_PHYSICAL_ADD_HURT = 1
    FIGHT_PROP_HEAL_ADD = 1
