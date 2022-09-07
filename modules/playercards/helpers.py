import json
import os
from typing import List, Union, Optional

from modules.playercards._metadata import _de_item_rule
from modules.playercards.models.artifact import ArtifactScoreInfo, ArtifactInfo
from modules.playercards.models.character import CharacterInfo, CharacterValueInfo
from modules.playercards.models.fetter import FetterInfo
from modules.playercards.models.fightprop import FightProp, FightPropScore
from modules.playercards.models.item import GameItem
from modules.playercards.models.skill import Skill
from modules.playercards.models.talent import Talent
from modules.playercards.models.weapon import WeaponInfo

_project_path = os.path.dirname(__file__)
_item_rule_file = os.path.join(_project_path, "metadata", "ItemsRule.json")
_characters_map_file = os.path.join(_project_path, "metadata", "CharactersMap.json")
_name_text_map_hash_file = os.path.join(_project_path, "metadata", "NameTextMapHash.json")
with open(_item_rule_file, "r", encoding="utf-8") as f:
    _item_rule_data: dict = json.load(f)
with open(_characters_map_file, "r", encoding="utf-8") as f:
    _characters_map_json: dict = json.load(f)
with open(_name_text_map_hash_file, "r", encoding="utf-8") as f:
    _name_text_map_hash_json: dict = json.load(f)

item_rule: dict = _de_item_rule(_item_rule_data)


def get_characters_name(item_id: Union[int, str]) -> str:
    if isinstance(item_id, int):
        item_id = str(item_id)
    characters = get_characters(item_id)
    name_text_map_hash = characters.get("NameTextMapHash", "-1")
    return get_text(str(name_text_map_hash))


def get_characters(item_id: Union[int, str]) -> dict:
    if isinstance(item_id, int):
        item_id = str(item_id)
    return _characters_map_json.get(item_id, {})


def get_text(hash_value: Union[int, str]) -> str:
    if isinstance(hash_value, int):
        hash_value = str(hash_value)
    return _name_text_map_hash_json.get(hash_value, "")


def de_character_info(avatar_data: dict, avatar_id: int) -> CharacterInfo:
    artifact_list = []

    weapon_info: Optional[WeaponInfo] = None

    equip_list = avatar_data["equipList"]  # 圣遗物和武器相关
    fetter_info = avatar_data["fetterInfo"]  # 好感等级
    fight_prop_map = avatar_data["fightPropMap"]  # 属性
    # inherent_proud_skill_list = avatar_data["inherentProudSkillList"]
    prop_map = avatar_data["propMap"]  # 角色等级 其他信息
    # proud_skill_extra_level_map = avatar_data["proudSkillExtraLevelMap"]
    # skill_depot_id = avatar_data["skillDepotId"]  # 不知道
    skill_level_map = avatar_data["skillLevelMap"]  # 技能等级

    # 角色等级
    character_level = prop_map['4001']['val']

    # 角色姓名
    character_name = get_characters_name(avatar_id)
    characters_data = get_characters(avatar_id)

    # 圣遗物和武器
    for equip in equip_list:
        if "reliquary" in equip:  # 圣遗物
            flat = equip["flat"]
            reliquary = equip["reliquary"]
            reliquary_main_stat = flat["reliquaryMainstat"]
            reliquary_sub_stats = flat['reliquarySubstats']
            sub_item = []
            for reliquary_sub in reliquary_sub_stats:
                sub_item.append(GameItem(type=reliquary_sub["appendPropId"], value=reliquary_sub["statValue"]))
            main_item = GameItem(type=reliquary_main_stat["mainPropId"], value=reliquary_main_stat["statValue"])
            name = get_text(flat["nameTextMapHash"])
            artifact_list.append(ArtifactInfo(item_id=equip["itemId"], name=name, star=flat["rankLevel"],
                                              level=reliquary["level"] - 1, main_item=main_item, sub_item=sub_item))
        if "weapon" in equip:  # 武器
            flat = equip["flat"]
            weapon_data = equip["weapon"]
            # 防止未精炼
            if 'promoteLevel' in weapon_data:
                weapon_level = weapon_data['promoteLevel'] - 1
            else:
                weapon_level = 0
            if 'affixMap' in weapon_data:
                affix = list(weapon_data['affixMap'].values())[0] + 1
            else:
                affix = 1
            reliquary_main_stat = flat["weaponStats"][0]
            reliquary_sub_stats = flat['weaponStats'][1]
            sub_item = GameItem(type=reliquary_sub_stats["appendPropId"], value=reliquary_sub_stats["statValue"])
            main_item = GameItem(type=reliquary_main_stat["appendPropId"], value=reliquary_main_stat["statValue"])
            weapon_name = get_text(flat["nameTextMapHash"])
            weapon_info = WeaponInfo(item_id=equip["itemId"], name=weapon_name, star=flat["rankLevel"],
                                     level=weapon_level, main_item=main_item, sub_item=sub_item, affix=affix)

    # 好感度
    fetter = FetterInfo(level=fetter_info["expLevel"])

    # 基础数值处理
    for i in range(40, 47):
        if fight_prop_map[str(i)] > 0:
            dmg_bonus = fight_prop_map[str(i)]
            break
    else:
        dmg_bonus = 0

    base_value = CharacterValueInfo(hp=fight_prop_map["2000"], base_hp=fight_prop_map["1"],
                                    atk=fight_prop_map["2001"], base_atk=fight_prop_map["4"],
                                    def_value=fight_prop_map["2002"], base_def=fight_prop_map["7"],
                                    elemental_mastery=fight_prop_map["28"], crit_rate=fight_prop_map["20"],
                                    crit_dmg=fight_prop_map["22"], energy_recharge=fight_prop_map["23"],
                                    heal_bonus=fight_prop_map["26"], healed_bonus=fight_prop_map["27"],
                                    physical_dmg_sub=fight_prop_map["29"], physical_dmg_bonus=fight_prop_map["30"],
                                    dmg_bonus=dmg_bonus)

    # 技能处理
    skill_list = []
    skills = characters_data["Skills"]
    for skill_id in skill_level_map:
        skill_list.append(Skill(skill_id=skill_id, name=skill_level_map[skill_id], icon=skills[skill_id]))

    # 命座处理
    talent_list = []
    consts = characters_data["Consts"]
    if 'talentIdList' in avatar_data:
        talent_id_list = avatar_data["talentIdList"]
        for index, _ in enumerate(talent_id_list):
            talent_list.append(Talent(talent_id=talent_id_list[index], icon=consts[index]))

    element = characters_data["Element"]
    icon = characters_data["SideIconName"]
    character_info = CharacterInfo(name=character_name, elementl=element, level=character_level, fetter=fetter,
                                   base_value=base_value, weapon=weapon_info, artifact=artifact_list,
                                   skill=skill_list, talent=talent_list, icon=icon)
    return character_info


def artifact_stats_theory(items: List[GameItem], character_name: str = "", main_items: List[FightProp] = None):
    """圣遗物副词条评分"""
    data: List[ArtifactScoreInfo] = []
    # 从数据库获取针对角色的评分规则
    if character_name != "":
        _main_items = item_rule.get(character_name)
        if _main_items is not None:
            main_items = _main_items
    # 如果指定计算词条为空设置默认
    if main_items is None:
        main_items = [FightProp.FIGHT_PROP_CRITICAL, FightProp.FIGHT_PROP_CRITICAL_HURT,
                      FightProp.FIGHT_PROP_ATTACK_PERCENT]
    # 修正要评分的数值词条
    if FightProp.FIGHT_PROP_ATTACK_PERCENT in main_items and FightProp.FIGHT_PROP_ATTACK not in main_items:
        main_items.append(FightProp.FIGHT_PROP_ATTACK)
    if FightProp.FIGHT_PROP_HP_PERCENT in main_items and FightProp.FIGHT_PROP_HP not in main_items:
        main_items.append(FightProp.FIGHT_PROP_HP)
    if FightProp.FIGHT_PROP_DEFENSE_PERCENT in main_items and FightProp.FIGHT_PROP_DEFENSE not in main_items:
        main_items.append(FightProp.FIGHT_PROP_DEFENSE)
    # 鉴定圣遗物为寄.jpg
    for item in items:
        score = 0
        if item.type in main_items:
            score = FightPropScore.__getitem__(item.type.name).value * item.value
        data.append(ArtifactScoreInfo(item=item.type, value=item.value, score=score))
    return data
