import re
from enum import Enum
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .helpers import get_headers


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

    # 地址
    ROOT_URL = "https://genshin.honeyhunterworld.com"

    # 正则表达式
    # /db/weapon/w_3203/?lang=CHS
    _GET_WEAPON_ID_BY_URL_RGX = re.compile(r"/db/weapon/w_(?P<weapon_id>\d+)")

    TEXT_MAPPING = {
        "Type": "类型",
        "Rarity": "Rarity",
        "Base Attack": "基础攻击力"
    }

    def __init__(self):
        self.client = httpx.AsyncClient(headers=get_headers())

    def _get_weapon_id_by_url(self, url: str) -> int:
        matches = self._GET_WEAPON_ID_BY_URL_RGX.search(url)
        if matches is None:
            return -1
        entries = matches.groupdict()
        if entries is None:
            return -1
        try:
            art_id = int(entries.get('weapon_id'))
        except (IndexError, ValueError, TypeError):
            return -1
        return art_id

    async def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        request = await self.client.get(url)
        return BeautifulSoup(request.text, "lxml")

    async def get_weapon_url_list(self, weapon_type: WeaponType):
        weapon_url_list = []
        url = self.ROOT_URL + f"/db/weapon/{weapon_type.value}/?lang=CHS"
        soup = await self._get_soup(url)
        weapon_table = soup.find("span", {"class": "item_secondary_title"},
                                 string="Released (Codex) Weapons").find_next_sibling()
        row = weapon_table.find_all("tr")
        for i in range(len(row)):
            content = row[i].find_all("td")[2]
            weapon_url = self.ROOT_URL + content.find("a")["href"]
            weapon_id = self._get_weapon_id_by_url(weapon_url)
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
        weapon_info_dict = {}
        weapon_info_dict["name"] = ""
        weapon_info_dict["description"] = ""
        weapon_info_dict["atk"] = {
            "min": 0,
            "max": 999999,
            "name": "基础攻击力"
        }
        weapon_info_dict["secondary"] = {
            "min": 0,
            "max": 999999,
            "name": ""
        }
        weapon_info_dict["star"] = {
            "len": -1,
            "icon": ""
        }
        weapon_info_dict["type"] = {
            "name": "",
            "icon": ""
        }
        weapon_info_dict["passive_ability"] = {
            "name": "",
            "description": ""
        }
        materials_dict = {
            "name": "",
            "star": {
                "len": 0,
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
                weapon_info_dict["source_img"] = content[0].find("img", {"class": "itempic lazy"})["data-src"]
                weapon_info_dict["type"]["name"] = content[2].text
            elif len(content) == 2:
                if content[0].text == "Rarity":
                    weapon_info_dict["star"]["len"] = len(content[1].find_all("div", {"class": "sea_char_stars_wrap"}))
                elif content[0].text == "Special (passive) Ability":
                    weapon_info_dict["passive_ability"]["name"] = content[1].text
                elif content[0].text == "Special (passive) Ability Description":
                    weapon_info_dict["passive_ability"]["weapon_info_dict"] = content[1].text
                elif content[0].text == "In-game Description":
                    weapon_info_dict["description"] = content[1].text

        stat_table = data.find("span", {"class": "item_secondary_title"},
                               string=" Stat Progression ").find_next_sibling()
        stat_table_row = stat_table.find_all("tr")
        for content in stat_table_row:
            # 通过等级判断
            if content[0].text == "1":
                weapon_info_dict["atk"]["min"] = content[2].text
                weapon_info_dict["secondary"]["min"] = content[3].text
            elif content[0].text == "90":
                weapon_info_dict["atk"]["max"] = content[2].text
                weapon_info_dict["secondary"]["max"] = content[3].text

        return weapon_info_dict
