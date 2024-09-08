from __future__ import annotations

import asyncio
import re
from typing import Dict, List, Optional

from aiofiles import open as async_open
from httpx import AsyncClient, HTTPError, Response

from modules.wiki.base import HONEY_HOST
from utils.const import PROJECT_ROOT
from utils.log import logger
from utils.typedefs import StrOrInt

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib

__all__ = [
    "get_avatar_data",
    "get_artifact_data",
    "get_material_data",
    "get_namecard_data",
    "get_weapon_data",
    "update_honey_metadata",
]

DATA_TYPE = Dict[StrOrInt, List[str]]
FULL_DATA_TYPE = Dict[str, DATA_TYPE]

client = AsyncClient()


async def request(url: str, retry: int = 10) -> Optional[Response]:
    for time in range(retry):
        try:
            return await client.get(url)
        except HTTPError as e:
            if time != retry - 1:
                await asyncio.sleep(1)
                continue
            raise e
        except Exception as e:
            raise e


async def get_avatar_data() -> DATA_TYPE:
    result = {}
    url = "https://gensh.honeyhunterworld.com/fam_chars/?lang=CHS"
    response = await request(url)
    chaos_data = re.findall(r"sortable_data\.push\((.*?)\);\s*sortable_cur_page", response.text)[0]
    json_data = jsonlib.loads(chaos_data)  # 转为 json
    for data in json_data:
        cid = int("10000" + re.findall(r"\d+", data[1])[0])
        honey_id = re.findall(r"/(.*?)/", data[1])[0]
        name = re.findall(r">(.*)<", data[1])[0]
        if "测试" in name:
            continue
        rarity = int(re.findall(r">(\d)<", data[2])[0])
        result[cid] = [honey_id, name, rarity]
    return result


async def get_weapon_data() -> DATA_TYPE:
    from modules.wiki.other import WeaponType

    result = {}
    urls = [HONEY_HOST.join(f"fam_{i.lower()}/?lang=CHS") for i in WeaponType.__members__]
    for url in urls:
        response = await request(url)
        chaos_data = re.findall(r"sortable_data\.push\((.*?)\);\s*sortable_cur_page", response.text)[0]
        json_data = jsonlib.loads(chaos_data)  # 转为 json
        for data in json_data:
            name = re.findall(r">(.*)<", data[1])[0]
            if name in ["「一心传」名刀", "石英大剑", "琥珀玥", "黑檀弓"]:  # 跳过特殊的武器
                continue
            wid = int(re.findall(r"\d+", data[1])[0])
            honey_id = re.findall(r"/(.*?)/", data[1])[0]
            rarity = int(re.findall(r">(\d)<", data[2])[0])
            result[wid] = [honey_id, name, rarity]
    return result


async def get_material_data() -> DATA_TYPE:
    result = {}

    weapon = [HONEY_HOST.join(f"fam_wep_{i}/?lang=CHS") for i in ["primary", "secondary", "common"]]
    talent = [HONEY_HOST.join(f"fam_talent_{i}/?lang=CHS") for i in ["book", "boss", "common", "reward"]]
    namecard = [HONEY_HOST.join("fam_nameplate/?lang=CHS")]
    urls = weapon + talent + namecard

    response = await request("https://api.ambr.top/v2/chs/material")
    ambr_data = jsonlib.loads(response.text)["data"]["items"]

    for url in urls:
        response = await request(url)
        chaos_data = re.findall(r"sortable_data\.push\((.*?)\);\s*sortable_cur_page", response.text)[0]
        json_data = jsonlib.loads(chaos_data)  # 转为 json
        for data in json_data:
            honey_id = re.findall(r"/(.*?)/", data[1])[0]
            name = re.findall(r">(.*)<", data[1])[0]
            rarity = int(re.findall(r">(\d)<", data[2])[0])
            mid = None
            for mid, item in ambr_data.items():
                if name == item["name"]:
                    break
            mid = int(mid) or int(re.findall(r"\d+", data[1])[0])
            result[mid] = [honey_id, name, rarity]
    return result


async def get_artifact_data() -> DATA_TYPE:
    async def get_first_id(_link) -> str:
        _response = await request(_link)
        _chaos_data = re.findall(r"sortable_data\.push\((.*?)\);\s*sortable_cur_page", _response.text)[0]
        _json_data = jsonlib.loads(_chaos_data)
        return re.findall(r"/(.*?)/", _json_data[-1][1])[0]

    result = {}
    url = "https://gensh.honeyhunterworld.com/fam_art_set/?lang=CHS"

    response = await request("https://api.ambr.top/v2/chs/reliquary")
    ambr_data = jsonlib.loads(response.text)["data"]["items"]

    response = await request(url)
    chaos_data = re.findall(r"sortable_data\.push\((.*?)\);\s*sortable_cur_page", response.text)[0]
    json_data = jsonlib.loads(chaos_data)  # 转为 json
    for data in json_data:
        honey_id = re.findall(r"/(.*?)/", data[1])[0]
        name = re.findall(r"alt=\"(.*?)\"", data[0])[0]
        link = HONEY_HOST.join(re.findall(r'href="(.*?)"', data[0])[0])
        first_id = await get_first_id(link)
        aid = None
        for aid, item in ambr_data.items():
            if name == item["name"]:
                break
        aid = aid or re.findall(r"\d+", data[1])[0]
        result[aid] = [honey_id, name, first_id]

    return result


async def get_namecard_data() -> DATA_TYPE:
    from metadata.genshin import NAMECARD_DATA

    if not NAMECARD_DATA:
        # noinspection PyProtectedMember
        from metadata.genshin import Data
        from metadata.scripts.metadatas import update_metadata_from_github

        await update_metadata_from_github()
        # noinspection PyPep8Naming
        NAMECARD_DATA = Data("namecard")
    url = HONEY_HOST.join("fam_nameplate/?lang=CHS")
    result = {}

    response = await request(url)
    chaos_data = re.findall(r"sortable_data\.push\((.*?)\);\s*sortable_cur_page", response.text)[0]
    json_data = jsonlib.loads(chaos_data)
    for data in json_data:
        honey_id = re.findall(r"/(.*?)/", data[1])[0]
        name = re.findall(r"alt=\"(.*?)\"", data[0])[0]
        try:
            nid = [key for key, value in NAMECARD_DATA.items() if value["name"] == name][0]
        except IndexError:  # 暂不支持 beta 的名片
            continue
        rarity = int(re.findall(r">(\d)<", data[2])[0])
        result[nid] = [honey_id, name, rarity]

    return result


async def update_honey_metadata(overwrite: bool = True) -> FULL_DATA_TYPE | None:
    path = PROJECT_ROOT.joinpath("metadata/data/honey.json")
    if not overwrite and path.exists():
        return
    avatar_data = await get_avatar_data()
    logger.success("Avatar data is done.")
    weapon_data = await get_weapon_data()
    logger.success("Weapon data is done.")
    material_data = await get_material_data()
    logger.success("Material data is done.")
    artifact_data = await get_artifact_data()
    logger.success("Artifact data is done.")
    namecard_data = await get_namecard_data()
    logger.success("Namecard data is done.")

    result = {
        "avatar": avatar_data,
        "weapon": weapon_data,
        "material": material_data,
        "artifact": artifact_data,
        "namecard": namecard_data,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    async with async_open(path, mode="w", encoding="utf-8") as file:
        await file.write(jsonlib.dumps(result, ensure_ascii=False, indent=4))
    return result
