import hashlib
import os
from typing import Union, Optional

import aiofiles
import genshin
import httpx
from genshin import Client, types
from httpx import UnsupportedProtocol

from core.bot import bot
from core.cookies.services import CookiesService
from core.error import ServiceNotFoundError
from core.user.services import UserService
from models.base import RegionEnum
from utils.error import UrlResourcesNotFoundError
from utils.log import logger

USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                  "Chrome/90.0.4430.72 Safari/537.36"
REQUEST_HEADERS: dict = {'User-Agent': USER_AGENT}
current_dir = os.getcwd()
cache_dir = os.path.join(current_dir, "cache")
if not os.path.exists(cache_dir):
    os.mkdir(cache_dir)

cookies_service = bot.services.get(CookiesService)
user_service = bot.services.get(UserService)

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
            except UnsupportedProtocol:
                logger.error(f"连接不支持 url[{url}]")
                return ""
        if data.is_error:
            logger.error(f"请求出现错误 url[{url}] status_code[{data.status_code}]")
            raise UrlResourcesNotFoundError(url)
        if data.status_code != 200:
            logger.error(f"url_to_file 获取url[{url}] 错误 status_code[f{data.status_code}]")
            raise UrlResourcesNotFoundError(url)
        async with aiofiles.open(file_dir, mode='wb') as f:
            await f.write(data.content)
    logger.debug(f"url_to_file 获取url[{url}] 并下载到 file_dir[{file_dir}]")
    return prefix + file_dir


async def get_genshin_client(user_id: int, region: Optional[RegionEnum] = None) -> Client:
    if user_service is None:
        raise ServiceNotFoundError(UserService)
    if cookies_service is None:
        raise ServiceNotFoundError(CookiesService)
    user = await user_service.get_user_by_id(user_id)
    if region is None:
        region = user.region
    cookies = await cookies_service.get_cookies(user_id, region)
    if region == RegionEnum.HYPERION:
        uid = user.yuanshen_uid
        client = genshin.Client(cookies=cookies.cookies, game=types.Game.GENSHIN, region=types.Region.CHINESE, uid=uid)
    elif region == RegionEnum.HOYOLAB:
        uid = user.genshin_uid
        client = genshin.Client(cookies=cookies.cookies,
                                game=types.Game.GENSHIN, region=types.Region.OVERSEAS, lang="zh-cn", uid=uid)
    else:
        raise TypeError("region is not RegionEnum.NULL")
    return client


def region_server(uid: Union[int, str]) -> RegionEnum:
    if isinstance(uid, int):
        region = REGION_MAP.get(str(uid)[0])
    elif isinstance(uid, str):
        region = REGION_MAP.get(str(uid)[0])
    else:
        raise TypeError("UID variable type error")
    if region:
        return region
    else:
        raise TypeError(f"UID {uid} isn't associated with any region")
