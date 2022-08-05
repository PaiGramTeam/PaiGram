import hashlib
import os
from typing import Union

import aiofiles
import genshin
import httpx
from genshin import Client, types
from httpx import UnsupportedProtocol

from apps.cookies.services import CookiesService
from apps.user.services import UserService
from logger import Log
from models.base import RegionEnum

USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                  "Chrome/90.0.4430.72 Safari/537.36"
REQUEST_HEADERS: dict = {'User-Agent': USER_AGENT}
current_dir = os.getcwd()
cache_dir = os.path.join(current_dir, "cache")
if not os.path.exists(cache_dir):
    os.mkdir(cache_dir)

REGION_MAP = {
    "1": RegionEnum.HYPERION,
    "2": RegionEnum.HYPERION,
    "5": RegionEnum.HYPERION,
    "6": RegionEnum.HOYOLAB,
    "7": RegionEnum.HOYOLAB,
    "8": RegionEnum.HOYOLAB,
    "9": RegionEnum.HOYOLAB,
}


def sha1(text: str) -> str:
    _sha1 = hashlib.sha1()
    _sha1.update(text.encode())
    return _sha1.hexdigest()


async def url_to_file(url: str, prefix: str = "file://") -> str:
    url_sha1 = sha1(url)
    url_file_name = os.path.basename(url)
    _, extension = os.path.splitext(url_file_name)
    temp_file_name = url_sha1 + extension
    file_dir = os.path.join(cache_dir, temp_file_name)
    if not os.path.exists(file_dir):
        async with httpx.AsyncClient(headers=REQUEST_HEADERS) as client:
            try:
                data = await client.get(url)
            except UnsupportedProtocol as error:
                Log.error(f"连接不支持 url[{url}]")
                Log.error("错误信息为", error)
                return ""
        if data.is_error:
            Log.error(f"请求出现错误 url[{url}] status_code[{data.status_code}]")
            return ""
        async with aiofiles.open(file_dir, mode='wb') as f:
            await f.write(data.content)
    return prefix + file_dir


async def get_genshin_client(user_id: int, user_service: UserService, cookies_service: CookiesService,
                             region: RegionEnum = RegionEnum.NULL) -> Client:
    user = await user_service.get_user_by_id(user_id)
    cookies = await cookies_service.get_cookies(user_id, region)
    if region is None:
        region = user.region
    if region == RegionEnum.HYPERION:
        uid = user.yuanshen_uid
        client = genshin.Client(cookies=cookies, game=types.Game.GENSHIN, region=types.Region.CHINESE, uid=uid)
    elif region == RegionEnum.HOYOLAB:
        uid = user.genshin_uid
        client = genshin.Client(cookies=cookies,
                                game=types.Game.GENSHIN, region=types.Region.OVERSEAS, lang="zh-cn", uid=uid)
    else:
        raise TypeError(f"region is not RegionEnum.NULL")
    return client


def region_server(uid: Union[int, str]) -> RegionEnum:
    if isinstance(uid, int):
        region = REGION_MAP.get(str(uid)[0])
    elif isinstance(uid, str):
        region = REGION_MAP.get(str(uid)[0])
    else:
        raise TypeError(f"UID variable type error")
    if region:
        return region
    else:
        raise TypeError(f"UID {uid} isn't associated with any region")
