import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .helpers import get_headers


class Characters:
    CHARACTERS_LIST_URL = "https://genshin.honeyhunterworld.com/db/char/characters/?lang=CHS"
    ROOT_URL = "https://genshin.honeyhunterworld.com"

    def __init__(self):
        self.client = httpx.AsyncClient(headers=get_headers())

    async def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        request = await self.client.get(url)
        return BeautifulSoup(request.text, "lxml")

    async def get_all_characters_url(self):
        url_list = []
        soup = await self._get_soup(self.CHARACTERS_LIST_URL)
        character_list = soup.find_all('div', {'class': 'char_sea_cont'})
        for character in character_list:
            character_link = self.ROOT_URL + character.a['href']
            url_list.append(character_link)
        return url_list

    def get_characters_info_template(self):
        characters_info_dict = {
            "name": "",
            "title": "",
            "rarity": 0,
            "element": {"name": "", "icon": ""},
            "description": "",
            "constellations": {},
            "skills": {
                "normal_attack": self.get_skills_info_template(),
                "skill_e": self.get_skills_info_template(),
                "skill_q": self.get_skills_info_template(),
                "skill_replace": self.get_skills_info_template(),
            },
            "gacha_splash": ""
        }
        return characters_info_dict

    @staticmethod
    def get_skills_info_template():
        skills_info_dict = {
            "icon": "",
            "name": "",
            "description": ""
        }
        return skills_info_dict

    async def get_characters(self, url: str):
        characters_info_dict = self.get_characters_info_template()
        soup = await self._get_soup(url)
        main_content = soup.find("div", {'class': 'wrappercont'})
        char_name = main_content.find('div', {'class': 'custom_title'}).text
        characters_info_dict["name"] = char_name
        # 基础信息
        char_info_table = main_content.find('table', {'class': 'item_main_table'}).find_all('tr')
        for char_info_item in char_info_table:
            content = char_info_item.find_all('td')
            if content[0].text == "Title":
                char_title = content[1].text
                characters_info_dict["title"] = char_title
            if content[0].text == "Allegiance":
                char_allegiance = content[1].text
                characters_info_dict["allegiance"] = char_allegiance
            if content[0].text == "Rarity":
                char_rarity = len(content[1].find_all('div', {'class': 'sea_char_stars_wrap'}))
                characters_info_dict["rarity"] = char_rarity
            if content[0].text == "Element":
                char_element_icon_url = self.ROOT_URL + content[1].find('img')['data-src'].replace("_35", "")
                characters_info_dict["element"]["icon"] = char_element_icon_url
            if content[0].text == "Astrolabe Name":
                char_astrolabe_name = content[1].text
            if content[0].text == "In-game Description":
                char_description = content[1].text
                characters_info_dict["description"] = char_description

        # 角色属性表格 咕咕咕
        skill_dmg_wrapper = main_content.find('div', {'class': 'skilldmgwrapper'}).find_all('tr')

        # 命之座
        constellations_title = main_content.find('span', {'class': 'item_secondary_title'}, string="Constellations")
        constellations_table = constellations_title.findNext('table', {'class': 'item_main_table'}).find_all('tr')
        constellations_list = []
        constellations_list_index = 0
        for index, value in enumerate(constellations_table):
            # 判断第一行
            if index % 2 == 0:
                constellations_dict = {
                    "icon": "",
                    "name": "",
                    "description": ""
                }
                constellations_list.append(constellations_dict)
                icon_url = self.ROOT_URL + value.find_all('img', {'class': 'itempic'})[-1]['data-src']
                constellations_name = value.find_all('a', href=re.compile("/db/skill"))[-1].text
                constellations_list[constellations_list_index]["icon"] = icon_url
                constellations_list[constellations_list_index]["name"] = constellations_name
            if index % 2 == 1:
                constellations_description = value.find('div', {'class': 'skill_desc_layout'}).text
                constellations_list[constellations_list_index]["description"] = constellations_description
                constellations_list_index += 1

        characters_info_dict["constellations"] = constellations_list

        # 技能
        skills_title = main_content.find('span', string='Attack Talents')

        # 普攻
        normal_attack_area = skills_title.find_next_sibling()
        normal_attack_info = normal_attack_area.find_all('tr')
        normal_attack_icon = self.ROOT_URL + normal_attack_info[0].find('img', {'class': 'itempic'})['data-src']
        normal_attack_name = normal_attack_info[0].find('a', href=re.compile('/db/skill/')).text
        normal_attack_desc = normal_attack_info[1].find('div', {'class': 'skill_desc_layout'}).text.replace(" ", "\n")
        normal_attack = characters_info_dict["skills"]["normal_attack"]
        normal_attack["icon"] = normal_attack_icon
        normal_attack["name"] = normal_attack_name
        normal_attack["description"] = normal_attack_desc

        normal_attack_table_area = normal_attack_area.find_next_sibling()
        # normal_attack_table = normal_attack_table_area.find_all('tr')

        skill_e_area = normal_attack_table_area.find_next_sibling()
        skill_e_info = skill_e_area.find_all('tr')
        skill_e_icon = self.ROOT_URL + skill_e_info[0].find('img', {'class': 'itempic'})['data-src']
        skill_e_name = skill_e_info[0].find('a', href=re.compile('/db/skill/')).text
        skill_e_desc = skill_e_info[1].find('div', {'class': 'skill_desc_layout'}).text.replace(" ", "\n")
        skill_e = characters_info_dict["skills"]["skill_e"]
        skill_e["icon"] = skill_e_icon
        skill_e["name"] = skill_e_name
        skill_e["description"] = skill_e_desc

        skill_e_table_area = skill_e_area.find_next_sibling()
        # skillE_table = skillE_table_area.find_all('tr')

        load_another_talent_q: bool = False
        if char_name == "神里绫华" or char_name == "莫娜":
            load_another_talent_q = True

        skill_q_area = skill_e_table_area.find_next_sibling()
        skill_q_info = skill_q_area.find_all('tr')
        skill_q_icon = self.ROOT_URL + skill_q_info[0].find('img', {'class': 'itempic'})['data-src']
        skill_q_name = skill_q_info[0].find('a', href=re.compile('/db/skill/')).text
        skill_q_desc = skill_q_info[1].find('div', {'class': 'skill_desc_layout'}).text.replace(" ", "\n")
        skill_q_table_area = skill_q_area.find_next_sibling()
        # skill_q_table = skill_q_table_area.find_all('tr')

        if load_another_talent_q:
            skill_replace = characters_info_dict["skills"]["skill_replace"]
            skill_replace["icon"] = skill_q_icon
            skill_replace["name"] = skill_q_name
            skill_replace["description"] = skill_q_desc
        else:
            skill_q = characters_info_dict["skills"]["skill_q"]
            skill_q["icon"] = skill_q_icon
            skill_q["name"] = skill_q_name
            skill_q["description"] = skill_q_desc

        if load_another_talent_q:
            skill_q2_area = skill_q_table_area.find_next_sibling()
            skill_q2_info = skill_q2_area.find_all('tr')
            skill_q2_icon = self.ROOT_URL + skill_q2_info[0].find('img', {'class': 'itempic'})['data-src']
            skill_q2_name = skill_q2_info[0].find('a', href=re.compile('/db/skill/')).text
            skill_q2_desc = skill_q2_info[1].find('div', {'class': 'skill_desc_layout'}).text.replace(" ", "\n")
            skill_q2 = characters_info_dict["skills"]["skill_q"]
            skill_q2["icon"] = skill_q2_icon
            skill_q2["name"] = skill_q2_name
            skill_q2["description"] = skill_q2_desc

        # 角色图片
        char_pic_area = main_content.find('span', string='Character Gallery').find_next_sibling()
        all_char_pic = char_pic_area.find("div", {"class": "gallery_cont"})

        gacha_splash_rext = all_char_pic.find("span", {"class": "gallery_cont_span"}, string="Gacha Splash")
        gacha_splash_pic_url = self.ROOT_URL + gacha_splash_rext.previous_element.previous_element["data-src"].replace(
            "_70", "")
        characters_info_dict["gacha_splash"] = gacha_splash_pic_url

        return characters_info_dict
