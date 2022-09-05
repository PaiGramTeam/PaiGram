import os
from typing import Union, Optional

import httpx
import ujson

from modules.apihelper.helpers import get_headers
from modules.playercards.models.artifact import ArtifactInfo
from modules.playercards.models.character import CharacterInfo, CharacterValueInfo
from modules.playercards.models.fetter import FetterInfo
from modules.playercards.models.skill import Skill
from modules.playercards.models.talent import Talent
from modules.playercards.models.weapon import WeaponInfo
from utils.models.base import GameItem


class PlayerCardsAPI:
    UI_URL = "https://enka.shinshin.moe/ui/"

    def __init__(self):
        self.client = httpx.AsyncClient(headers=get_headers())
        project_path = os.path.dirname(__file__)
        characters_map_file = os.path.join(project_path, "metadata", "CharactersMap.json")
        name_text_map_hash_file = os.path.join(project_path, "metadata", "NameTextMapHash.json")
        reliquary_name_map_file = os.path.join(project_path, "metadata", "ReliquaryNameMap.json")
        with open(characters_map_file, "r", encoding="utf-8") as f:
            self._characters_map_json: dict = ujson.load(f)
        with open(name_text_map_hash_file, "r", encoding="utf-8") as f:
            self._name_text_map_hash_json: dict = ujson.load(f)
        with open(reliquary_name_map_file, "r", encoding="utf-8") as f:
            self._reliquary_name_map_json: dict = ujson.load(f)

    def get_characters_name(self, item_id: Union[int, str]) -> str:
        if isinstance(item_id, int):
            item_id = str(item_id)
        characters = self.get_characters(item_id)
        name_text_map_hash = characters.get("NameTextMapHash", "-1")
        return self.get_text(str(name_text_map_hash))

    def get_characters(self, item_id: Union[int, str]) -> dict:
        if isinstance(item_id, int):
            item_id = str(item_id)
        return self._characters_map_json.get(item_id, {})

    def get_text(self, hash_value: Union[int, str]) -> str:
        if isinstance(hash_value, int):
            hash_value = str(hash_value)
        return self._name_text_map_hash_json.get(hash_value, "")

    def get_reliquary_name(self, reliquary: str) -> str:
        return self._reliquary_name_map_json[reliquary]

    async def get_data(self, uid: Union[str, int]):
        url = f"https://enka.shinshin.moe/u/{uid}/__data.json"
        response = await self.client.get(url)
        return response

    def data_handler(self, avatar_data: dict, avatar_id: int) -> CharacterInfo:
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
        character_name = self.get_characters_name(avatar_id)
        characters_data = self.get_characters(avatar_id)

        # 圣遗物和武器
        for equip in equip_list:
            if "reliquary" in equip:  # 圣遗物
                flat = equip["flat"]
                reliquary = equip["reliquary"]
                reliquary_main_stat = flat["reliquaryMainstat"]
                reliquary_sub_stats = flat['reliquarySubstats']
                sub_item = []
                for reliquary_sub in reliquary_sub_stats:
                    sub_item.append(GameItem(name=self.get_reliquary_name(reliquary_sub["appendPropId"]),
                                             item_type=reliquary_sub["appendPropId"], value=reliquary_sub["statValue"]))
                main_item = GameItem(name=self.get_reliquary_name(reliquary_main_stat["mainPropId"]),
                                     item_type=reliquary_main_stat["mainPropId"],
                                     value=reliquary_main_stat["statValue"])
                name = self.get_text(flat["nameTextMapHash"])
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
                sub_item = GameItem(name=self.get_reliquary_name(reliquary_main_stat["appendPropId"]),
                                    item_type=reliquary_sub_stats["appendPropId"],
                                    value=reliquary_sub_stats["statValue"])
                main_item = GameItem(name=self.get_reliquary_name(reliquary_main_stat["appendPropId"]),
                                     item_type=reliquary_main_stat["appendPropId"],
                                     value=reliquary_main_stat["statValue"])
                weapon_name = self.get_text(flat["nameTextMapHash"])
                weapon_info = WeaponInfo(item_id=equip["itemId"], name=weapon_name, star=flat["rankLevel"],
                                         level=weapon_level, main_item=main_item, sub_item=sub_item, affix=affix)

        # 好感度
        fetter = FetterInfo(fetter_info["expLevel"])

        # 基础数值处理
        for i in range(40, 47):
            if fight_prop_map[str(i)] > 0:
                dmg_bonus = fight_prop_map[str(i)]
                break
        else:
            dmg_bonus = 0

        base_value = CharacterValueInfo(fight_prop_map["2000"], fight_prop_map["1"], fight_prop_map["2001"],
                                        fight_prop_map["4"], fight_prop_map["2002"], fight_prop_map["7"],
                                        fight_prop_map["28"], fight_prop_map["20"], fight_prop_map["22"],
                                        fight_prop_map["23"], fight_prop_map["26"], fight_prop_map["27"],
                                        fight_prop_map["29"], fight_prop_map["30"], dmg_bonus)

        # 技能处理
        skill_list = []
        skills = characters_data["Skills"]
        for skill_id in skill_level_map:
            skill_list.append(Skill(skill_id, name=skill_level_map[skill_id], icon=skills[skill_id]))

        # 命座处理
        talent_list = []
        consts = characters_data["Consts"]
        if 'talentIdList' in avatar_data:
            talent_id_list = avatar_data["talentIdList"]
            for index, _ in enumerate(talent_id_list):
                talent_list.append(Talent(talent_id_list[index], icon=consts[index]))

        element = characters_data["Element"]
        icon = characters_data["SideIconName"]
        character_info = CharacterInfo(character_name, element, character_level, fetter, base_value, weapon_info,
                                       artifact_list, skill_list, talent_list, icon)
        return character_info
