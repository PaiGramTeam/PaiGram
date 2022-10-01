import asyncio
import re
from multiprocessing import RLock
from typing import Dict, List, Optional

import ujson as json
from httpx import AsyncClient, HTTPError, Response

from utils.const import PROJECT_ROOT
from utils.typedefs import StrOrInt

__all__ = ['update_honey']

DATA_TYPE = Dict[StrOrInt, List[str]]
FULL_DATA_TYPE = Dict[str, DATA_TYPE]

_lock = RLock()
_client: Optional[AsyncClient] = None


def client() -> AsyncClient:
    global _client
    with _lock:
        if _client is None or _client.is_closed:
            _client = AsyncClient()
    return _client


async def request(url: str, retry: int = 5) -> Optional[Response]:
    for time in range(retry):
        try:
            return await client().get(url)
        except HTTPError:
            if time != retry - 1:
                await asyncio.sleep(1)
                continue
            return None
        except Exception as e:
            raise e


async def _character() -> DATA_TYPE:
    result = {}
    url = "https://genshin.honeyhunterworld.com/fam_chars/?lang=CHS"
    response = await request(url)
    chaos_data = re.findall(r'sortable_data\.push\((.*)\);\s*sortable_cur_page', response.text)[0]
    json_data = json.loads(chaos_data)  # 转为 json
    for data in json_data:
        cid = int("10000" + re.findall(r'\d+', data[1])[0])
        honey_id = re.findall(r"/(.*?)/", data[1])[0]
        name = re.findall(r'>(.*)<', data[1])[0]
        en_name = re.findall(r"(.*?)_\d+", honey_id)[0]
        rarity = int(re.findall(r">(\d)<", data[2])[0])
        result.update({cid: [en_name, name, rarity]})
    return result


async def _weapon() -> DATA_TYPE:
    from modules.wiki.base import SCRAPE_HOST
    from modules.wiki.other import WeaponType

    result = {}
    urls = [SCRAPE_HOST.join(f"fam_{i.lower()}/?lang=CHS") for i in WeaponType.__members__]
    for i, url in enumerate(urls):
        response = await request(url)
        chaos_data = re.findall(r'sortable_data\.push\((.*)\);\s*sortable_cur_page', response.text)[0]
        json_data = json.loads(chaos_data)  # 转为 json
        for data in json_data:
            wid = int(re.findall(r'\d+', data[1])[0])
            name = re.findall(r'>(.*)<', data[1])[0]
            weapon_type = list(WeaponType.__members__)[i]
            rarity = int(re.findall(r">(\d)<", data[2])[0])
            result.update({wid: [name, rarity, weapon_type]})
    return result


async def _material() -> DATA_TYPE:
    from modules.wiki.base import SCRAPE_HOST

    result = {}
    weapon = [SCRAPE_HOST.join(f'fam_wep_{i}/?lang=CHS') for i in ['primary', 'secondary', 'common']]
    talent = [SCRAPE_HOST.join(f'fam_talent_{i}/?lang=CHS') for i in ['book', 'boss', 'common', 'reward']]
    urls = weapon + talent
    for url in urls:
        response = await request(url)
        chaos_data = re.findall(r'sortable_data\.push\((.*)\);\s*sortable_cur_page', response.text)[0]
        json_data = json.loads(chaos_data)  # 转为 json
        for data in json_data:
            mid = int(re.findall(r'\d+', data[1])[0])
            honey_id = re.findall(r'/(.*?)/', data[1])[0]
            name = re.findall(r'>(.*)<', data[1])[0]
            rarity = int(re.findall(r">(\d)<", data[2])[0])
            result.update({mid: [honey_id, name, rarity]})
    return result


async def update_honey() -> FULL_DATA_TYPE:
    character_data = await _character()
    weapon_data = await _weapon()
    material_data = await _material()
    result = {
        'character': character_data,
        'weapon': weapon_data,
        'material': material_data,
    }
    with open(PROJECT_ROOT.joinpath('metadata/data/honey.json'), mode='w', encoding='utf-8') as file:
        file.write(json.dumps(result, ensure_ascii=False))
    return result
#

async def main():
    await update_honey()


if __name__ == '__main__':
    import asyncio
    import sys
    from asyncio import new_event_loop

    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
