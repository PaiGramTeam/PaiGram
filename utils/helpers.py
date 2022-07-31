import hashlib
import os
from typing import Optional

import aiofiles
import genshin
import httpx
from genshin import Client, types
from httpx import UnsupportedProtocol

from app.cookies.service import CookiesService
from app.user import UserService
from logger import Log
from model.base import ServiceEnum

USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                  "Chrome/90.0.4430.72 Safari/537.36"
REQUEST_HEADERS: dict = {'User-Agent': USER_AGENT}
current_dir = os.getcwd()
cache_dir = os.path.join(current_dir, "cache")
if not os.path.exists(cache_dir):
    os.mkdir(cache_dir)

SERVICE_MAP = {
    "1": ServiceEnum.HYPERION,
    "2": ServiceEnum.HYPERION,
    "5": ServiceEnum.HYPERION,
    "6": ServiceEnum.HOYOLAB,
    "7": ServiceEnum.HOYOLAB,
    "8": ServiceEnum.HOYOLAB,
    "9": ServiceEnum.HOYOLAB,
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
                             game_service: Optional[ServiceEnum] = None) -> Client:
    user = await user_service.get_user_by_id(user_id)
    cookies = await cookies_service.read_cookies(user_id, game_service)
    if game_service is None:
        game_service = user.default_service
    if game_service == ServiceEnum.HYPERION:
        uid = user.yuanshen_game_uid
        client = genshin.Client(cookies=cookies, game=types.Game.GENSHIN, region=types.Region.CHINESE, uid=uid)
    else:
        uid = user.genshin_game_uid
        client = genshin.Client(cookies=cookies,
                                game=types.Game.GENSHIN, region=types.Region.OVERSEAS, lang="zh-cn", uid=uid)
    return client


def get_server(uid: int) -> ServiceEnum:
    server = SERVICE_MAP.get(str(uid)[0])
    if server:
        return server
    else:
        raise TypeError(f"UID {uid} isn't associated with any server")
