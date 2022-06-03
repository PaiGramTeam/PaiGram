import httpx
from bs4 import BeautifulSoup

from .helpers import get_headers


class Characters:
    CHARACTERS_LIST_URL = "https://genshin.honeyhunterworld.com/db/char/characters/?lang=CHS"

    def __init__(self):
        self.client = httpx.AsyncClient(headers=get_headers())

    async def get_characters(self):
        request = await self.client.get(self.CHARACTERS_LIST_URL)
        soup = BeautifulSoup(request.text, 'lxml')
        character_list = soup.find_all('div', {'class': 'char_sea_cont'})

        for character in character_list:
            character_name = character.find("span", {"class": "sea_charname"}).text
