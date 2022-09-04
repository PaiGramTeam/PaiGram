import re
from typing import List, Optional

from bs4 import BeautifulSoup
from httpx import URL

from modules.wiki.base import Model, SCRAPE_HOST
from modules.wiki.base import WikiModel
from modules.wiki.other import Association, Element, WeaponType


class Birth(Model):
    """生日
    Attributes:
        day: 天
        month: 月
    """
    day: int
    month: int


class CharacterAscension(Model):
    """角色的突破材料

    Attributes:
        level: 等级突破材料
        skill: 技能/天赋培养材料
    """
    level: List[str] = []
    skill: List[str] = []


class CharacterState(Model):
    """角色属性值

    Attributes:
        level: 等级
        HP: 生命
        ATK: 攻击力
        DEF: 防御力
        CR: 暴击率
        CD: 暴击伤害
        bonus: 突破属性
    """
    level: str
    HP: int
    ATK: float
    DEF: float
    CR: str
    CD: str
    bonus: str


class CharacterIcon(Model):
    icon: str
    side: str
    gacha: str
    splash: Optional[str]


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
    birth: Optional[Birth]
    constellation: str
    cn_cv: str
    jp_cv: str
    en_cv: str
    kr_cv: str
    description: str
    ascension: CharacterAscension

    stats: List[CharacterState]

    @classmethod
    def scrape_urls(cls) -> List[URL]:
        return [SCRAPE_HOST.join("fam_chars/?lang=CHS")]

    @classmethod
    async def _parse_soup(cls, soup: BeautifulSoup) -> 'Character':
        """解析角色页"""
        soup = soup.select('.wp-block-post-content')[0]
        tables = soup.find_all('table')
        table_rows = tables[0].find_all('tr')

        def get_table_text(row_num: int) -> str:
            """一个快捷函数，用于返回表格对应行的最后一个单元格中的文本"""
            return table_rows[row_num].find_all('td')[-1].text.replace('\xa0', '')

        id_ = re.findall(r'img/(.*?_\d+)_.*', table_rows[0].find('img').attrs['src'])[0]
        name = get_table_text(0)
        if name != '旅行者':  # 如果角色名不是 旅行者
            title = get_table_text(1)
            occupation = get_table_text(2)
            association = Association.convert(get_table_text(3).lower().title())
            rarity = len(table_rows[4].find_all('img'))
            weapon_type = WeaponType[get_table_text(5)]
            element = Element[get_table_text(6)]
            birth = Birth(day=int(get_table_text(7)), month=int(get_table_text(8)))
            constellation = get_table_text(10)
            cn_cv = get_table_text(11)
            jp_cv = get_table_text(12)
            en_cv = get_table_text(13)
            kr_cv = get_table_text(14)
        else:
            name = '空' if id_.endswith('5') else '荧'
            title = get_table_text(0)
            occupation = get_table_text(1)
            association = Association.convert(get_table_text(2).lower().title())
            rarity = len(table_rows[3].find_all('img'))
            weapon_type = WeaponType[get_table_text(4)]
            element = Element[get_table_text(5)]
            birth = None
            constellation = get_table_text(7)
            cn_cv = get_table_text(8)
            jp_cv = get_table_text(9)
            en_cv = get_table_text(10)
            kr_cv = get_table_text(11)
        description = get_table_text(-3)
        ascension = CharacterAscension(
            level=[
                target[0] for i in table_rows[-2].find_all('a')
                if (target := re.findall(r'/(.*)/', i.attrs['href']))  # 过滤掉错误的材料(honey网页的bug)
            ],
            skill=[re.findall(r'/(.*)/', i.attrs['href'])[0] for i in table_rows[-1].find_all('a')]
        )
        stats = []
        for row in tables[2].find_all('tr')[1:]:
            cells = row.find_all('td')
            stats.append(
                CharacterState(
                    level=cells[0].text, HP=cells[1].text, ATK=cells[2].text, DEF=cells[3].text,
                    CR=cells[4].text, CD=cells[5].text, bonus=cells[6].text
                )
            )
        return Character(
            id=id_, name=name, title=title, occupation=occupation, association=association, weapon_type=weapon_type,
            element=element, birth=birth, constellation=constellation, cn_cv=cn_cv, jp_cv=jp_cv, rarity=rarity,
            en_cv=en_cv, kr_cv=kr_cv, description=description, ascension=ascension, stats=stats
        )

    @classmethod
    async def get_url_by_name(cls, name: str) -> Optional[URL]:
        # 重写此函数的目的是处理主角名字的 ID
        _map = {'荧': "playergirl_007", '空': "playerboy_005"}
        if (id_ := _map.get(name, None)) is not None:
            return await cls.get_url_by_id(id_)
        return await super(Character, cls).get_url_by_name(name)

    @property
    def icon(self) -> CharacterIcon:
        return CharacterIcon(
            icon=str(SCRAPE_HOST.join(f'/img/{self.id}_icon.webp')),
            side=str(SCRAPE_HOST.join(f'/img/{self.id}_side_icon.webp')),
            gacha=str(SCRAPE_HOST.join(f'/img/{self.id}_gacha_card.webp')),
            splash=str(SCRAPE_HOST.join(f'/img/{self.id}_gacha_splash.webp'))
        )
