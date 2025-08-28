import re
import traceback

from datetime import datetime, timedelta
from dateutil.parser import parse
from typing import List

from pydantic import BaseModel

from tools.init import wiki


def get_wiki_page():
    page = wiki.pages["往期祈愿"]
    return page.text()


class WarpData(BaseModel):
    name: List[str]
    start_time: datetime
    end_time: datetime
    five: List[str]
    four: List[str]

    @staticmethod
    def _extract_value(text, key):
        match = re.search(rf"\|{key}=(.+)", text)
        text = match.group(1).strip() if match else None
        if text == "长期":
            return "2099/12/31 23:59"
        return text

    @staticmethod
    def _extract_list(text, key):
        value = WarpData._extract_value(text, key)
        return [x.strip() for x in value.split("、")] if value else []

    @classmethod
    def parse_warp_block(cls, block) -> "WarpData":
        data = {
            "name": [WarpData._extract_value(block, "名称") or ""],
            "start_time": parse(WarpData._extract_value(block, "开始时间")),
            "end_time": parse(WarpData._extract_value(block, "结束时间")),
            "five": WarpData._extract_list(block, "5星角色") or WarpData._extract_list(block, "5星武器"),
            "four": WarpData._extract_list(block, "4星角色") or WarpData._extract_list(block, "4星武器"),
        }
        value = cls(**data)
        if value.start_time.hour < 12:
            value.start_time = value.start_time.replace(hour=6, minute=0, second=0, microsecond=0)
        if value.end_time.minute == 59:
            value.end_time = value.end_time.replace(second=59, microsecond=0)
        elif value.end_time.minute == 0:
            value.end_time = value.end_time - timedelta(seconds=1)
        return value

    def print_pool_format(self):
        from_time = self.start_time.strftime("%Y-%m-%d %H:%M:%S")
        to_time = self.end_time.strftime("%Y-%m-%d %H:%M:%S")
        name = "|".join([i for i in set(self.name) if i])
        self.four.reverse()
        print("{")
        print(f'    "five": {self.five},')
        print(f'    "four": {self.four},')
        print(f'    "name": "{name}",')
        print(f'    "from": "{from_time}",')
        print(f'    "to": "{to_time}",')
        print("}")


def parse_text(text):
    # 分割不同版本
    version_sections = re.split(r"===(.+?)===", text)[3:]

    for i in range(0, len(version_sections), 2):
        version = version_sections[i].strip()
        content = version_sections[i + 1]

        avatar_pool, weapon_pool = None, None
        warp_blocks = re.findall(r"\{\{(.+?)}}", content, re.DOTALL)
        for block in warp_blocks:
            try:
                warp_data = WarpData.parse_warp_block(block)
            except Exception as e:
                traceback.print_exc()
                continue
            if "角色" in block:
                if avatar_pool:
                    avatar_pool.name.extend(warp_data.name)
                    avatar_pool.five.extend(warp_data.five)
                else:
                    avatar_pool = warp_data
            elif "武器" in block:
                if weapon_pool:
                    weapon_pool.name.extend(warp_data.name)
                    weapon_pool.five.extend(warp_data.five)
                else:
                    weapon_pool = warp_data
        print(version)
        if avatar_pool:
            avatar_pool.print_pool_format()
        if weapon_pool:
            weapon_pool.print_pool_format()


def main():
    text = get_wiki_page()
    parse_text(text)


if __name__ == "__main__":
    main()
