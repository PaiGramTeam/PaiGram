from enum import Enum
from typing import Optional

import httpx
import os

import ujson
from bs4 import BeautifulSoup

from .helpers import get_headers, get_id_form_url


class WeaponType(Enum):
    Sword = "sword"  # 单手剑
    Claymore = "claymore"  # 双手剑
    PoleArm = "polearm"  # 长柄武器
    Bow = "bow"  # 弓
    Catalyst = "catalyst"  # 法器


class Weapons:
    IGNORE_WEAPONS_ID = [
        "1001", "1101", "1406",
        "2001", "2101", "2204", "2406", "2407",
        "3001", "3101", "3204", "3404",
        "4001", "4101", "4201", "4403", "4405", "4406",
        "5001", "5101", "5201", "5404", "5404", "5405",
    ]  # 忽略的武器包括一星、二星武器，beta表格内无名武器，未上架到正服的武器

    # 根地址
    ROOT_URL = "https://genshin.honeyhunterworld.com"

    TEXT_MAPPING = {
        "Type": "类型",
        "Rarity": "Rarity",
        "Base Attack": "基础攻击力"
    }

    WEAPON_TYPE_MAPPING = {
        "Sword": "https://genshin.honeyhunterworld.com/img/skills/s_33101.png",  # 单手剑
        "Claymore": "https://genshin.honeyhunterworld.com/img/skills/s_163101.png",  # 双手剑
        "Polearm": "https://genshin.honeyhunterworld.com/img/skills/s_233101.png",  # 长枪
        "Bow": "https://genshin.honeyhunterworld.com/img/skills/s_213101.png",  # 弓箭
        "Catalyst": "https://genshin.honeyhunterworld.com/img/skills/s_43101.png",  # 法器
    }

    def __init__(self):
        self.client = httpx.AsyncClient(headers=get_headers())
        project_path = os.path.dirname(__file__)
        characters_file = os.path.join(project_path, "metadata", "ascension.json")
        monster_file = os.path.join(project_path, "metadata", "monster.json")
        elite_file = os.path.join(project_path, "metadata", "elite.json")
        with open(characters_file, "r", encoding="utf-8") as f:
            self._ascension_json: dict = ujson.load(f)
        with open(monster_file, "r", encoding="utf-8") as f:
            self._monster_json: dict = ujson.load(f)
        with open(elite_file, "r", encoding="utf-8") as f:
            self._elite_json: dict = ujson.load(f)

    async def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        request = await self.client.get(url)
        return BeautifulSoup(request.text, "lxml")

    async def get_weapon_url_list(self, weapon_type: WeaponType):
        weapon_url_list = []
        url = self.ROOT_URL + f"/db/weapon/{weapon_type.value}/?lang=CHS"
        soup = await self._get_soup(url)
        weapon_table = soup.find("span", {"class": "item_secondary_title"},
                                 string="Released (Codex) Weapons").find_next_sibling()
        weapon_table_rows = weapon_table.find_all("tr")
        for weapon_table_row in weapon_table_rows:
            content = weapon_table_row.find_all("td")[2]
            if content.find("a") is not None:
                weapon_url = self.ROOT_URL + content.find("a")["href"]
                weapon_id = str(get_id_form_url(weapon_url))
                if weapon_id not in self.IGNORE_WEAPONS_ID:
                    weapon_url_list.append(weapon_url)
        return weapon_url_list

    async def get_all_weapon_url(self):
        all_weapon_url = []
        temp_data = await self.get_weapon_url_list(WeaponType.Bow)
        all_weapon_url.extend(temp_data)
        temp_data = await self.get_weapon_url_list(WeaponType.Sword)
        all_weapon_url.extend(temp_data)
        temp_data = await self.get_weapon_url_list(WeaponType.PoleArm)
        all_weapon_url.extend(temp_data)
        temp_data = await self.get_weapon_url_list(WeaponType.Catalyst)
        all_weapon_url.extend(temp_data)
        temp_data = await self.get_weapon_url_list(WeaponType.Claymore)
        all_weapon_url.extend(temp_data)
        return all_weapon_url

    @staticmethod
    def get_weapon_info_template():
        weapon_info_dict = {
            "name": "",
            "description": "",
            "source_img": "",
            "atk":
                {
                    "min": 0,
                    "max": 999999,
                    "name": "基础攻击力"
                },
            "secondary":
                {
                    "min": 0.1,
                    "max": 999999.9,
                    "name": ""
                },
            "star":
                {
                    "value": -1,
                    "icon": ""
                },
            "type":
                {
                    "name": "",
                    "icon": ""
                },
            "passive_ability":
                {
                    "name": "",
                    "description": ""
                }
        }
        materials_dict = {
            "name": "",
            "star": {
                "value": 0,
                "icon": ""
            },
            "city": "",
            "icon": ""
        }
        weapon_info_dict["materials"] = {
            "ascension": materials_dict,
            "elite": materials_dict,
            "monster": materials_dict,
        }
        return weapon_info_dict

    async def get_weapon_info(self, url: str):
        weapon_info_dict = self.get_weapon_info_template()
        soup = await self._get_soup(url)
        weapon_content = soup.find("div", {"class": "wrappercont"})
        data = weapon_content.find("div", {"class": "data_cont_wrapper", "style": "display: block"})
        weapon_info = data.find("table", {"class": "item_main_table"})
        weapon_name = weapon_content.find("div", {"class": "custom_title"}).text.replace("-", "").replace(" ", "")
        weapon_info_dict["name"] = weapon_name
        weapon_info_row = weapon_info.find_all("tr")
        for weapon_info_ in weapon_info_row:
            content = weapon_info_.find_all("td")
            if len(content) == 3:  # 第一行会有三个td，其中一个td是武器图片
                weapon_info_dict["source_img"] = self.ROOT_URL + content[0].find("img",
                                                                                 {"class": "itempic lazy"})["data-src"]
                weapon_info_dict["type"]["name"] = content[2].text
                weapon_info_dict["type"]["icon"] = self.get_weapon_type(content[2].text)
            elif len(content) == 2:
                if content[0].text == "Rarity":
                    weapon_info_dict["star"]["value"] = len(
                        content[1].find_all("div", {"class": "sea_char_stars_wrap"}))
                elif content[0].text == "Special (passive) Ability":
                    weapon_info_dict["passive_ability"]["name"] = content[1].text
                elif content[0].text == "Special (passive) Ability Description":
                    weapon_info_dict["passive_ability"]["description"] = content[1].text
                elif content[0].text == "In-game Description":
                    weapon_info_dict["description"] = content[1].text
                elif content[0].text == "Secondary Stat":
                    weapon_info_dict["secondary"]["name"] = content[1].text

        stat_table = data.find("span", {"class": "item_secondary_title"},
                               string=" Stat Progression ").find_next_sibling()
        stat_table_row = stat_table.find_all("tr")
        for stat_table_ in stat_table_row:
            content = stat_table_.find_all("td")
            # 通过等级判断
            if content[0].text == "1":
                weapon_info_dict["atk"]["min"] = int(content[1].text)
                weapon_info_dict["secondary"]["min"] = float(content[2].text)
            elif content[0].text == "80+":
                item_hrefs = content[3].find_all("a")
                for item_href in item_hrefs:
                    item_id = get_id_form_url(item_href["href"])
                    ascension = self.get_ascension(str(item_id))
                    if ascension.get("name") is not None:
                        weapon_info_dict["materials"]["ascension"] = ascension
                    monster = self.get_monster(str(item_id))
                    if monster.get("name") is not None:
                        weapon_info_dict["materials"]["monster"] = monster
                    elite = self.get_elite(str(item_id))
                    if elite.get("name") is not None:
                        weapon_info_dict["materials"]["elite"] = elite
            elif content[0].text == "90":
                weapon_info_dict["atk"]["max"] = int(content[1].text)
                weapon_info_dict["secondary"]["max"] = float(content[2].text)

        return weapon_info_dict

    def get_ascension(self, item_id: str):
        return self._ascension_json.get(item_id, {})

    def get_monster(self, item_id: str):
        return self._monster_json.get(item_id, {})

    def get_elite(self, item_id: str):
        return self._elite_json.get(item_id, {})

    def get_weapon_type(self, weapon_type: str):
        return self.WEAPON_TYPE_MAPPING.get(weapon_type, "")
