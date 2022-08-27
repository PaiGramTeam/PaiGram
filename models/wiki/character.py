import re
from enum import Enum
from typing import List, TYPE_CHECKING

from bs4 import BeautifulSoup
from httpx import URL

from models.wiki.base import Model, SCRAPE_HOST
from models.wiki.base import WikiModel
from models.wiki.other import Element, WeaponType

if TYPE_CHECKING:
    from bs4 import Tag


class Association(Enum):
    """角色所属地区"""
    Mainactor = '主角'
    Snezhnaya = '至冬'
    Sumeru = '须弥'
    Inazuma = '稻妻'
    Liyue = '璃月'
    Mondstadt = '蒙德'


class Birth(Model):
    """生日
    Attributes:
        day: 天
        month: 月
    """
    day: int
    month: int


class CharacterAscension(Model):
    level: List[int] = []
    skill: List[int] = []


class Character(WikiModel):
    """角色
    Attributes:
        title: 称号
        occupation: 所属
        association: 地区
        weapon_type: 武器类型
        element: 元素
        birth: 生日
        constellation: 命之座
        cn_cv: 中配
        jp_cv: 日配
        en_cv: 英配
        kr_cv: 韩配
        description: 描述
    """

    id: str
    title: str
    occupation: str
    association: Association
    weapon_type: WeaponType
    element: Element
    birth: Birth
    constellation: str
    cn_cv: str
    jp_cv: str
    en_cv: str
    kr_cv: str
    description: str
    ascension: CharacterAscension

    @classmethod
    def scrape_urls(cls) -> List[URL]:
        return [SCRAPE_HOST.join("fam_chars/?lang=CHS")]

    @classmethod
    async def _parse_soup(cls, soup: BeautifulSoup) -> 'Character':
        soup = soup.select('.wp-block-post-content')[0]
        tables: List['Tag'] = soup.find_all('table')
        table_rows: List['Tag'] = tables[0].find_all('tr')

        def get_table_text(table_num: int) -> str:
            return table_rows[table_num].find_all('td')[-1].text.replace('\xa0', '')

        id_ = re.findall(r'img/(.*?_\d+)_.*', table_rows[0].find('img').attrs['src'])[0]
        name = get_table_text(0)
        title = get_table_text(1)
        occupation = get_table_text(2)
        association = Association[get_table_text(3).lower().title()]
        rarity = len(table_rows[4].find_all('img'))
        weapon_type = WeaponType[get_table_text(5)]
        element = Element[get_table_text(6)]
        birth = Birth(day=int(get_table_text(7)), month=int(get_table_text(8)))
        constellation = get_table_text(10)
        cn_cv = get_table_text(11)
        jp_cv = get_table_text(12)
        en_cv = get_table_text(13)
        kr_cv = get_table_text(14)
        description = get_table_text(-3)
        ascension = CharacterAscension(
            level=[int(re.findall(r'i_(\d+)/', str(i))[0]) for i in table_rows[-2].find_all('a')],
            skill=[int(re.findall(r'i_(\d+)/', str(i))[0]) for i in table_rows[-1].find_all('a')]
        )

        return Character(
            id=id_, name=name, title=title, occupation=occupation, association=association, weapon_type=weapon_type,
            element=element, birth=birth, constellation=constellation, cn_cv=cn_cv, jp_cv=jp_cv, rarity=rarity,
            en_cv=en_cv, kr_cv=kr_cv, description=description, ascension=ascension
        )

    # noinspection PyShadowingBuiltins
    @staticmethod
    async def get_url_by_id(id: str) -> URL:
        return SCRAPE_HOST.join(f'{id}/?lang=CHS')
