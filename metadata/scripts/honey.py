import asyncio
import re
from multiprocessing import RLock
from typing import Dict, List, Optional

import ujson as json
from aiofiles import open as async_open
from httpx import AsyncClient, HTTPError, Response

from modules.wiki.base import HONEY_HOST
from utils.const import PROJECT_ROOT
from utils.log import logger
from utils.typedefs import StrOrInt

__all__ = ['update_honey_metadata']

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


async def _avatar() -> DATA_TYPE:
    result = {}
    url = "https://genshin.honeyhunterworld.com/fam_chars/?lang=CHS"
    response = await request(url)
    chaos_data = re.findall(r'sortable_data\.push\((.*)\);\s*sortable_cur_page', response.text)[0]
    json_data = json.loads(chaos_data)  # 转为 json
    for data in json_data:
        cid = int("10000" + re.findall(r'\d+', data[1])[0])
        honey_id = re.findall(r"/(.*?)/", data[1])[0]
        name = re.findall(r'>(.*)<', data[1])[0]
        rarity = int(re.findall(r">(\d)<", data[2])[0])
        result.update({cid: [honey_id, name, rarity]})
    return result


async def _weapon() -> DATA_TYPE:
    from modules.wiki.other import WeaponType

    result = {}
    urls = [HONEY_HOST.join(f"fam_{i.lower()}/?lang=CHS") for i in WeaponType.__members__]
    for i, url in enumerate(urls):
        response = await request(url)
        chaos_data = re.findall(r'sortable_data\.push\((.*)\);\s*sortable_cur_page', response.text)[0]
        json_data = json.loads(chaos_data)  # 转为 json
        for data in json_data:
            wid = int(re.findall(r'\d+', data[1])[0])
            honey_id = re.findall(r"/(.*?)/", data[1])[0]
            name = re.findall(r'>(.*)<', data[1])[0]
            rarity = int(re.findall(r">(\d)<", data[2])[0])
            result.update({wid: [honey_id, name, rarity]})
    return result


async def _material() -> DATA_TYPE:
    result = {}

    weapon = [HONEY_HOST.join(f'fam_wep_{i}/?lang=CHS') for i in ['primary', 'secondary', 'common']]
    talent = [HONEY_HOST.join(f'fam_talent_{i}/?lang=CHS') for i in ['book', 'boss', 'common', 'reward']]
    namecard = [HONEY_HOST.join("fam_nameplate/?lang=CHS")]
    urls = weapon + talent + namecard

    response = await request("https://api.ambr.top/v2/chs/material")
    ambr_data = json.loads(response.text)['data']['items']

    for url in urls:
        response = await request(url)
        chaos_data = re.findall(r'sortable_data\.push\((.*)\);\s*sortable_cur_page', response.text)[0]
        json_data = json.loads(chaos_data)  # 转为 json
        for data in json_data:
            honey_id = re.findall(r'/(.*?)/', data[1])[0]
            name = re.findall(r'>(.*)<', data[1])[0]
            rarity = int(re.findall(r">(\d)<", data[2])[0])
            mid = None
            for mid, item in ambr_data.items():
                if name == item['name']:
                    break
            mid = int(mid) or int(re.findall(r'\d+', data[1])[0])
            result.update({mid: [honey_id, name, rarity]})
    return result


async def _artifact() -> DATA_TYPE:
    result = {}
    url = "https://genshin.honeyhunterworld.com/fam_art_set/?lang=CHS"

    response = await request("https://api.ambr.top/v2/chs/reliquary")
    ambr_data = json.loads(response.text)['data']['items']

    response = await request(url)
    chaos_data = re.findall(r'sortable_data\.push\((.*)\);\s*sortable_cur_page', response.text)[0]
    json_data = json.loads(chaos_data)  # 转为 json
    for data in json_data:
        honey_id = re.findall(r'/(.*?)/', data[1])[0]
        name = re.findall(r'>(.*)<', data[1])[0]
        mid = None
        for mid, item in ambr_data.items():
            if name == item['name']:
                break
        mid = int(mid) or int(re.findall(r'\d+', data[1])[0])
        result.update({mid: [honey_id, name]})

    return result


async def update_honey_metadata() -> FULL_DATA_TYPE:
    avatar_data = await _avatar()
    logger.success("Avatar data is done.")
    weapon_data = await _weapon()
    logger.success("Weapon data is done.")
    material_data = await _material()
    logger.success("Material data is done.")
    artifact_data = await _artifact()
    logger.success("Artifact data is done.")
    result = {
        'avatar': avatar_data,
        'weapon': weapon_data,
        'material': material_data,
        'reliquary': artifact_data,
    }
    path = PROJECT_ROOT.joinpath('metadata/data/honey.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    async with async_open(path, mode='w', encoding='utf-8') as file:
        await file.write(json.dumps(result, ensure_ascii=False))
    return result


async def main():
    await update_honey_metadata()


def __main__():
    import asyncio
    import sys

    if sys.version_info >= (3, 8) and sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())


if __name__ == '__main__':
    __main__()
