import re
from typing import List, Optional, Iterator, Union, TYPE_CHECKING

from bs4 import BeautifulSoup
from httpx import URL
from typing_extensions import Self

from models.wiki.base import WikiModel, Model, SCRAPE_HOST

if TYPE_CHECKING:
    from bs4 import Tag

__all__ = ['Material', 'MaterialSeries']


class Material(WikiModel):
    """材料

    Attributes:
        type: 类型
        source: 获取方式
        description: 描述
        serise: 材料系列
    """

    @staticmethod
    def scrape_urls() -> List[URL]:
        return [SCRAPE_HOST.join(f'fam_wep_{i}/?lang=CHS') for i in ['primary', 'secondary', 'common']]

    @classmethod
    async def _parse_soup(cls, soup: BeautifulSoup) -> Self:
        soup = soup.select('.wp-block-post-content')[0]
        tables: List['Tag'] = soup.find_all('table')
        table_rows: List['Tag'] = tables[0].find_all('tr')

        def get_table_text(table_num: int) -> str:
            return table_rows[table_num].find_all('td')[-1].text.replace('\xa0', '')

        id_ = int(re.findall(r'/img/.*?(\d+).*', str(table_rows[0]))[0])
        name = get_table_text(0)
        rarity = len(table_rows[3].find_all('img'))
        type_ = get_table_text(1)
        source = list(
            filter(lambda x: x, table_rows[-2].find_all('td')[-1].encode_contents().decode().split('<br/>')))
        description = get_table_text(-1)
        return Material(id=id_, name=name, rarity=rarity, type=type_, source=source, description=description)

    @staticmethod
    async def get_url_by_id(id_: Union[int, str]) -> URL:
        return SCRAPE_HOST.join(f'i_{int(id_)}/?lang=CHS')

    type: str
    source: List[str]
    description: str


class MaterialSeries(Model):
    """系列材料

    例如 史莱姆凝液、史莱姆清 和 史莱姆原浆 是属于一个系列的
    根据材料的等级来存放：例如 史莱姆原浆 是 3 星材料，那么它将存放在 `level_3` 中

    """
    level_1: Optional[int] = None
    level_2: Optional[int] = None
    level_3: Optional[int] = None
    level_4: Optional[int] = None
    level_5: Optional[int] = None

    def __iter__(self) -> Iterator[int]:
        """生成这个系列的所有材料的迭代器"""
        return iter(filter(
            lambda x: x is not None, [self.level_1, self.level_2, self.level_3, self.level_4, self.level_5]
        ))

    def __getitem__(self, index: int) -> Optional[int]:
        """获取这个系列的第某个材料

        不会包含空值，例如该系列只有等级为 2-5 的材料，则当 `index` 为 1 的时候，会返回 `level_2`

        Args:
            index (:obj:int): 材料的索引
        """
        return list(self.__iter__())[index + 1]

    def __contains__(self, material: Union[int, Material]) -> bool:
        if isinstance(material, Material):
            material = material.id
        return bool(list(filter(lambda x: x == material, self.__iter__())))
