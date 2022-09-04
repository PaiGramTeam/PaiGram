import re
from typing import List

from bs4 import BeautifulSoup
from httpx import URL
from typing_extensions import Self

from models.wiki.base import SCRAPE_HOST, WikiModel

__all__ = ['Material']


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

        id_ = re.findall(r'/img/(.*?)\.webp', str(table_rows[0]))[0]
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

    @property
    def icon(self) -> str:
        return str(SCRAPE_HOST.join(f'/img/{self.id}.webp'))
