import os
from typing import List
import ujson


class Metadata:
    def __init__(self):
        project_path = os.path.dirname(__file__)
        characters_file = os.path.join(project_path, 'characters.json')
        with open(characters_file, 'r', encoding='utf-8') as f:
            self.characters = ujson.load(f)

        # 初始化
        self.characters_name_list: List[str] = [characters["Name"] for characters in self.characters]

    @staticmethod
    def get_info(data: dict, name: str) -> dict:
        for temp in data:
            if temp["Name"] == name:
                return temp
        return {}


metadat = Metadata()
