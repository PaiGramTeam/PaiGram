import os
from typing import List
import ujson


class Metadata(object):
    def __init__(self):
        project_path = os.path.dirname(__file__)
        characters_file = os.path.join(project_path, 'characters.json')
        with open(characters_file, 'r', encoding='utf-8') as f:
            self.characters = ujson.load(f)
        daily_talents_file = os.path.join(project_path, 'dailytalents.json')
        with open(daily_talents_file, 'r', encoding='utf-8') as f:
            self.daily_talents = ujson.load(f)
        daily_weapons_file = os.path.join(project_path, 'dailyweapons.json')
        with open(daily_weapons_file, 'r', encoding='utf-8') as f:
            self.daily_weapons_file = ujson.load(f)
        weapons_file = os.path.join(project_path, 'weapons.json')
        with open(weapons_file, 'r', encoding='utf-8') as f:
            self.weapons = ujson.load(f)
        gacha_events_file = os.path.join(project_path, 'gachaevents.json')
        with open(gacha_events_file, 'r', encoding='utf-8') as f:
            self.gacha_events = ujson.load(f)

        # 初始化
        self.characters_name_list: List[str] = [characters["Name"] for characters in self.characters]
        self.weapons_name_list: List[str] = [weapons["Name"] for weapons in self.weapons]

    @staticmethod
    def get_info(data: dict, name: str) -> dict:
        for temp in data:
            if temp["Name"] == name:
                return temp
        return {}


metadat = Metadata()
