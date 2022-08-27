import re
from typing import List, Optional, Union, TYPE_CHECKING

from bs4 import BeautifulSoup
from httpx import URL

from models.wiki.base import Model, WikiModel, SCRAPE_HOST
from models.wiki.other import WeaponType, AttributeType

if TYPE_CHECKING:
    from bs4 import Tag

__all__ = ['Weapon', 'WeaponAffix', 'WeaponAttribute']


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


class Weapon(WikiModel):
    """武器

    Attributes:
        type: 武器类型
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
    ascension: List[int]
    story: Optional[str]

    @staticmethod
    def scrape_urls() -> List[URL]:
        return [SCRAPE_HOST.join(f"fam_{i.lower()}/?lang=CHS") for i in WeaponType.__members__]

    # noinspection PyShadowingBuiltins
    @classmethod
    async def _parse_soup(cls, soup: BeautifulSoup) -> 'Weapon':
        soup = soup.select('.wp-block-post-content')[0]
        tables: List['Tag'] = soup.find_all('table')
        table_rows: List['Tag'] = tables[0].find_all('tr')

        def get_table_text(table_num: int) -> str:
            return table_rows[table_num].find_all('td')[-1].text.replace('\xa0', '')

        def find_table(select: str) -> List['Tag']:
            return list(filter(lambda x: select in ' '.join(x.attrs['class']), tables))

        id_ = int(re.findall(r'/img/.*?(\d+).*', str(table_rows[0]))[0])
        weapon_type = WeaponType[get_table_text(1).split(',')[-1].strip()]
        name = get_table_text(0)
        rarity = len(table_rows[2].find_all('img'))
        attack = float(get_table_text(4))
        ascension = [re.findall(r'\d+', tag.attrs['href'])[0] for tag in table_rows[-1].find_all('a')]
        if rarity > 2:  # 如果是 3 星及其以上的武器
            attribute = WeaponAttribute(
                type=AttributeType.convert_str(
                    tables[2].find('thead').find('tr').find_all('td')[2].text.split(' ')[1]
                ),
                value=get_table_text(6)
            )
            affix = WeaponAffix(name=get_table_text(7), description=[
                i.find_all('td')[1].text for i in tables[3].find_all('tr')[1:]
            ])
            if len(tables) < 11:
                description = get_table_text(-1)
            else:
                description = get_table_text(9)
            story = find_table('quotes')[0].text.strip()
        else:  # 如果是 2 星及其以下的武器
            attribute = affix = None
            description = get_table_text(5)
            story = tables[-1].text.strip()
        return Weapon(
            id=id_, name=name, rarity=rarity, attack=attack, attribute=attribute, affix=affix, weapon_type=weapon_type,
            story=story,
            description=description, ascension=ascension
        )

    # noinspection PyShadowingBuiltins
    @staticmethod
    async def get_url_by_id(id: Union[int, str]) -> URL:
        return SCRAPE_HOST.join(f'i_n{int(id)}/?lang=CHS')
