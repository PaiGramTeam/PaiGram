from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .helpers import get_headers


class Item:

    def __init__(self):
        self.client = httpx.AsyncClient(headers=get_headers())

    def _get_dict(self):
        materials_dict = {
            "name": "",
            "star": {
                "len": 0,
                "icon": ""
            },
            "city": "",
            "icon": ""
        }
        return materials_dict

    async def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        request = await self.client.get(url)
        return BeautifulSoup(request.text, "lxml")

    async def get_item(self, url: str):
        soup = await self._get_soup(url)
        weapon_content = soup.find("div", {"class": "wrappercont"})
        data = weapon_content.find("div", {"class": "data_cont_wrapper", "style": "display: block"})
