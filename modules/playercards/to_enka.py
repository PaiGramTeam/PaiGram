from typing import TYPE_CHECKING, Dict, List, Any, Optional

from enkanetwork import Assets, CharacterStats

from utils.log import logger

if TYPE_CHECKING:
    from simnet.models.genshin.chronicle.character_detail import (
        GenshinDetailCharacters,
        GenshinDetailCharacter,
        PropertyValue,
        DetailArtifact,
        ArtifactProperty,
        DetailCharacterWeapon,
    )


class HashMapRev:
    HASH_MAP_REV: Dict[str, Dict[str, str]] = {}

    @classmethod
    def get_hash_map(cls, name: str) -> Optional[str]:
        cls.reload_assets()
        for key in cls.HASH_MAP_REV:
            if name in cls.HASH_MAP_REV[key]:
                return cls.HASH_MAP_REV[key][name]
        return ""

    @classmethod
    def get_artifacts_data(cls, artifact_id: int) -> Dict:
        cls.reload_assets()
        return Assets.DATA["artifacts"][str(artifact_id)]

    @classmethod
    def get_weapon_data(cls, weapon_id: int) -> Dict:
        cls.reload_assets()
        return Assets.DATA["weapons"][str(weapon_id)]

    @classmethod
    def reload_assets(cls) -> None:
        # Load assets
        if not Assets.HASH_MAP:
            Assets.reload_assets()
        if not cls.HASH_MAP_REV:
            cls.HASH_MAP_REV = {key: {v["CHS"]: k for k, v in value.items()} for key, value in Assets.HASH_MAP.items()}


def get_prop_name_from_id(prop_id: int) -> str:
    for k, v in CharacterStats.__fields__.items():
        if v.default.id == prop_id:
            return k
    return ""


def get_equip_list_single_artifact_stats(data: "DetailArtifact") -> Dict:
    main_stat = data.main_property
    sub_stats = data.sub_property_list

    def _get_stat(v: "ArtifactProperty", key: str) -> Dict:
        return {
            key: get_prop_name_from_id(v.property_type),
            "statValue": float(v.value.replace("%", "")),
        }

    return {
        "reliquaryMainstat": _get_stat(main_stat, "mainPropId"),
        "reliquarySubstats": [_get_stat(v, "appendPropId") for v in sub_stats],
    }


def get_equip_list_single_weapon_stats(data: "DetailCharacterWeapon") -> List[Dict]:
    stats = [data.main_property]
    if data.sub_property:
        stats.append(data.sub_property)

    def _get_stat(v: "PropertyValue") -> Dict:
        return {
            "appendPropId": get_prop_name_from_id(v.property_type),
            "statValue": float(v.final.replace("%", "")),
        }

    return [_get_stat(v) for v in stats]


def get_equip_list_single_artifact(data: "DetailArtifact") -> Dict:
    item_id = data.id
    item_data = HashMapRev.get_artifacts_data(item_id)
    reliquary = {
        "appendPropIdList": [],
        "level": data.level + 1,
    }
    flat = {
        "equipType": item_data["equipType"],
        "icon": item_data["icon"],
        "itemType": item_data["itemType"],
        "nameTextMapHash": str(item_data["nameTextMapHash"]),
        "rankLevel": item_data["rankLevel"],
        "setNameTextMapHash": HashMapRev.get_hash_map(data.set.name),
        **get_equip_list_single_artifact_stats(data),
    }
    return {
        "flat": flat,
        "itemId": item_id,
        "reliquary": reliquary,
    }


def get_equip_list_single_weapon(data: "DetailCharacterWeapon") -> Dict:
    item_id = data.id
    item_data = HashMapRev.get_weapon_data(item_id)
    weapon = {
        "affixMap": {"0": data.refinement - 1},
        "level": data.level,
        "promoteLevel": data.ascension,
    }
    flat = {
        "icon": item_data["icon"],
        "itemType": "ITEM_WEAPON",
        "nameTextMapHash": str(item_data["nameTextMapHash"]),
        "rankLevel": item_data["rankLevel"],
        "weaponStats": get_equip_list_single_weapon_stats(data),
    }
    return {
        "flat": flat,
        "itemId": item_id,
        "weapon": weapon,
    }


def get_equip_list_single(index: int, data: "GenshinDetailCharacter") -> Dict:
    if index >= len(data.artifacts):
        return get_equip_list_single_weapon(data.weapon)
    return get_equip_list_single_artifact(data.artifacts[index])


def get_equip_list_loop(data: "GenshinDetailCharacter") -> List[Dict]:
    return [get_equip_list_single(index, data) for index in range(len(data.artifacts) + 1)]


def get_fetter_info(data: "GenshinDetailCharacter") -> Dict[str, int]:
    return {"expLevel": data.base.friendship}


def get_fight_prop_map(data: "GenshinDetailCharacter") -> Dict[str, float]:
    f = []
    f.extend(data.base_properties)
    f.extend(data.extra_properties)
    f.extend(data.element_properties)
    f.sort(key=lambda k: k.property_type)

    def _prop_to_value(v: "PropertyValue") -> float:
        if "%" not in v.final:
            return float(v.final)
        return float(v.final.replace("%", "")) / 100

    return {str(prop.property_type): _prop_to_value(prop) for prop in f}


def get_inherent_proud_skill_list(data: "GenshinDetailCharacter") -> List[int]:
    return [(skill.id * 100 + 1) for skill in data.skills if skill.skill_type == 2]


def get_prop_map(data: "GenshinDetailCharacter") -> Dict[str, Dict[str, Any]]:
    level = str(data.base.level)
    return {
        "1001": {"ival": "0", "type": 1001},  # XP
        "1002": {"ival": "6", "type": 1002, "val": "6"},  # Ascension
        "4001": {"ival": level, "type": 4001, "val": level},  # Level
    }


def get_skill_depot_id(data: "GenshinDetailCharacter") -> int:
    skill = data.skills[0]
    if data.base.id in [10000117, 10000118]:
        for i in data.skills:
            if i.id > 100000:
                skill = i
                break
    skill_id = skill.id % 10
    if data.base.id in [10000005, 10000007, 10000117, 10000118]:
        skill_id += 1
    skill_id_pre = (data.base.id - 10000000) * 100
    return skill_id_pre + skill_id


def get_skill_level_map(data: "GenshinDetailCharacter", proud_skill_extra_level_map: Dict[str, int]) -> Dict:
    _data = {}
    for skill in data.skills:
        if skill.skill_type != 1:
            continue

        _skill = Assets.skills(skill.id)
        if not _skill:
            continue

        level = skill.level
        if proud_skill_extra_level_map:
            boost_level = proud_skill_extra_level_map.get(str(_skill.pround_map), None)
            if boost_level is not None:
                level -= boost_level
        _data[str(skill.id)] = level
    return _data


def get_talent_id_list(data: "GenshinDetailCharacter") -> List[int]:
    return [constellation.id for constellation in data.constellations if constellation.activated]


def get_proud_skill_extra_level_map(data: "GenshinDetailCharacter") -> Dict[str, int]:
    skill_names_map = {skill.name: skill.id for skill in data.skills if skill.skill_type == 1}
    constellations_index = (2, 4)
    need_level_up_skills_id = []
    for index in constellations_index:
        if index >= len(data.constellations):
            continue
        constellation = data.constellations[index]
        if not constellation.activated:
            continue
        for skill_name, skill_id in skill_names_map.items():
            if skill_name not in constellation.effect:
                continue
            need_level_up_skills_id.append(skill_id)

    data = {}
    for skill_id in need_level_up_skills_id:
        _skill = Assets.skills(skill_id)
        if not _skill:
            continue
        data[str(_skill.pround_map)] = 3

    return data


def from_simnet_to_enka_single(index: int, data: "GenshinDetailCharacters") -> Dict:
    character = data.characters[index]
    avatar_id = character.base.id
    equip_list = get_equip_list_loop(character)
    fetter_info = get_fetter_info(character)
    fight_prop_map = get_fight_prop_map(character)
    inherent_proud_skill_list = get_inherent_proud_skill_list(character)
    prop_map = get_prop_map(character)
    skill_depot_id = get_skill_depot_id(character)
    talent_id_list = get_talent_id_list(character)
    proud_skill_extra_level_map = get_proud_skill_extra_level_map(character)
    skill_level_map = get_skill_level_map(character, proud_skill_extra_level_map)
    if not skill_level_map:
        logger.warning("解析技能等级数据失败 ch_id[%s]", avatar_id)
        return {}
    return {
        "avatarId": avatar_id,
        "equipList": equip_list,
        "fetterInfo": fetter_info,
        "propMap": prop_map,
        "talentIdList": talent_id_list,
        "skillDepotId": skill_depot_id,
        "inherentProudSkillList": inherent_proud_skill_list,
        "fightPropMap": fight_prop_map,
        "skillLevelMap": skill_level_map,
        "proudSkillExtraLevelMap": proud_skill_extra_level_map,
    }


def from_simnet_to_enka_loop(data: "GenshinDetailCharacters") -> List[Dict]:
    d = []
    for index, ch in enumerate(data.characters):
        try:
            if parsed_data := from_simnet_to_enka_single(index, data):
                d.append(parsed_data)
        except Exception as e:
            cid = ch.base.id
            logger.error("从 simnet 模型转换为 enka 模型时出现错误 cid[%s]", cid, exc_info=e)
    logger.success("成功转换 %s 个角色", len(d))
    return d


def from_simnet_to_enka(data: "GenshinDetailCharacters") -> Dict:
    return {
        "avatarInfoList": from_simnet_to_enka_loop(data),
    }
