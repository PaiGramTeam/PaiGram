import re
from typing import Iterator, List, Optional, Union

from bs4 import BeautifulSoup
from httpx import URL
from typing_extensions import Self

from models.wiki.base import Model, SCRAPE_HOST, WikiModel

__all__ = ['Material', 'MaterialSeries']


class Material(WikiModel):
    """材料

    Attributes:
        type: 类型
        source: 获取方式
        description: 描述
        serise: 材料系列
    """

    type: str
    source: List[str]
    description: str

    @staticmethod
    def scrape_urls() -> List[URL]:
        return [SCRAPE_HOST.join(f'fam_wep_{i}/?lang=CHS') for i in ['primary', 'secondary', 'common']]

    @classmethod
    async def _parse_soup(cls, soup: BeautifulSoup) -> Self:
        """解析材料页"""
        soup = soup.select('.wp-block-post-content')[0]
        tables = soup.find_all('table')
        table_rows = tables[0].find_all('tr')

        def get_table_text(row_num: int) -> str:
            """一个快捷函数，用于返回表格对应行的最后一个单元格中的文本"""
            return table_rows[row_num].find_all('td')[-1].text.replace('\xa0', '')

        id_ = int(re.findall(r'/img/.*?(\d+).*', str(table_rows[0]))[0])
        name = get_table_text(0)
        rarity = len(table_rows[3].find_all('img'))
        type_ = get_table_text(1)
        source = list(
            filter(
                lambda x: x,  # filter 在这里的作用是过滤掉为空的数据
                table_rows[-2].find_all('td')[-1].encode_contents().decode().split('<br/>')
            )
        )
        description = get_table_text(-1)
        return Material(id=id_, name=name, rarity=rarity, type=type_, source=source, description=description)

    @staticmethod
    async def get_url_by_id(id_: Union[int, str]) -> URL:
        return SCRAPE_HOST.join(f'i_{int(id_)}/?lang=CHS')


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
        """该系列是否包含这个材料

        Args:
            material: 目标的材料 或 目标材料的ID
        Returns:
            一个布尔类型
        """
        if isinstance(material, Material):
            material = material.id
        return bool(list(filter(lambda x: x == material, self.__iter__())))
