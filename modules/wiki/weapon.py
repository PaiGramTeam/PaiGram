import itertools
import re
from typing import List, Optional, Tuple, Union

from bs4 import BeautifulSoup
from httpx import URL

from modules.wiki.base import HONEY_HOST, Model, WikiModel
from modules.wiki.other import AttributeType, WeaponType

__all__ = ["Weapon", "WeaponAffix", "WeaponAttribute"]


class WeaponAttribute(Model):
    """武器词条"""

    type: AttributeType
    value: str


class WeaponAffix(Model):
    """武器技能

    Attributes:
        name: 技能名
        description: 技能描述

    """

    name: str
    description: List[str]


class WeaponState(Model):
    level: str
    ATK: float
    bonus: Optional[str]


class WeaponIcon(Model):
    icon: str
    awakened: str
    gacha: str


class Weapon(WikiModel):
    """武器

    Attributes:
        weapon_type: 武器类型
        attack: 基础攻击力
        attribute:
        affix: 武器技能
        description: 描述
        ascension: 突破材料
        story: 武器故事
    """

    weapon_type: WeaponType
    attack: float
    attribute: Optional[WeaponAttribute]
    affix: Optional[WeaponAffix]
    description: str
    ascension: List[str]
    story: Optional[str]

    stats: List[WeaponState]

    @staticmethod
    def scrape_urls() -> List[URL]:
        return [HONEY_HOST.join(f"fam_{i.lower()}/?lang=CHS") for i in WeaponType.__members__]

    @classmethod
    async def _parse_soup(cls, soup: BeautifulSoup) -> "Weapon":
        """解析武器页"""
        soup = soup.select(".wp-block-post-content")[0]
        tables = soup.find_all("table")
        table_rows = tables[0].find_all("tr")

        def get_table_text(row_num: int) -> str:
            """一个快捷函数，用于返回表格对应行的最后一个单元格中的文本"""
            return table_rows[row_num].find_all("td")[-1].text.replace("\xa0", "")

        def find_table(select: str):
            """一个快捷函数，用于寻找对应表格头的表格"""
            return list(filter(lambda x: select in " ".join(x.attrs["class"]), tables))

        id_ = re.findall(r"/img/(.*?)_gacha", str(table_rows[0]))[0]
        weapon_type = WeaponType[get_table_text(1).split(",")[-1].strip()]
        name = get_table_text(0)
        rarity = len(table_rows[2].find_all("img"))
        attack = float(get_table_text(4))
        ascension = [re.findall(r"/(.*)/", tag.attrs["href"])[0] for tag in table_rows[-1].find_all("a")]
        if rarity > 2:  # 如果是 3 星及其以上的武器
            attribute = WeaponAttribute(
                type=AttributeType.convert(tables[2].find("thead").find("tr").find_all("td")[2].text.split(" ")[1]),
                value=get_table_text(6),
            )
            affix = WeaponAffix(
                name=get_table_text(7), description=[i.find_all("td")[1].text for i in tables[3].find_all("tr")[1:]]
            )
            description = get_table_text(9)
            if story_table := find_table("quotes"):
                story = story_table[0].text.strip()
            else:
                story = None
        else:  # 如果是 2 星及其以下的武器
            attribute = affix = None
            description = get_table_text(5)
            story = tables[-1].text.strip()
        stats = []
        for row in tables[2].find_all("tr")[1:]:
            cells = row.find_all("td")
            if rarity > 2:
                stats.append(WeaponState(level=cells[0].text, ATK=cells[1].text, bonus=cells[2].text))
            else:
                stats.append(WeaponState(level=cells[0].text, ATK=cells[1].text))
        return Weapon(
            id=id_,
            name=name,
            rarity=rarity,
            attack=attack,
            attribute=attribute,
            affix=affix,
            weapon_type=weapon_type,
            story=story,
            stats=stats,
            description=description,
            ascension=ascension,
        )

    @classmethod
    async def get_name_list(cls, *, with_url: bool = False) -> List[Union[str, Tuple[str, URL]]]:
        # 重写此函数的目的是名字去重，例如单手剑页面中有三个 “「一心传」名刀”
        name_list = [i async for i in cls._name_list_generator(with_url=with_url)]
        if with_url:
            return [(i[0], list(i[1])[0][1]) for i in itertools.groupby(name_list, lambda x: x[0])]
        return [i[0] for i in itertools.groupby(name_list, lambda x: x)]

    @property
    def icon(self) -> WeaponIcon:
        return WeaponIcon(
            icon=str(HONEY_HOST.join(f"/img/{self.id}.webp")),
            awakened=str(HONEY_HOST.join(f"/img/{self.id}_awaken_icon.webp")),
            gacha=str(HONEY_HOST.join(f"/img/{self.id}_gacha_icon.webp")),
        )
