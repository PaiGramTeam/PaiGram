import hashlib
import os
from typing import List

import aiofiles
import httpx
from httpx import UnsupportedProtocol
from telegram import Bot

from logger import Log
from model.base import ServiceEnum
from service.cache import RedisCache

USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                  "Chrome/90.0.4430.72 Safari/537.36"
headers: dict = {'User-Agent': USER_AGENT}
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


async def get_admin_list(bot: Bot, cache: RedisCache, chat_id: int, extra_user: List[int]) -> List[int]:
    admin_id_list = await cache.get_chat_admin(chat_id)
    if len(admin_id_list) == 0:
        admin_list = await bot.get_chat_administrators(chat_id)
        admin_id_list = [admin.user.id for admin in admin_list]
        await cache.set_chat_admin(chat_id, admin_id_list)
    admin_id_list += extra_user
    return admin_id_list


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
        async with httpx.AsyncClient(headers=headers) as client:
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


def get_server(uid: int) -> ServiceEnum:
    server = SERVICE_MAP.get(str(uid)[0])
    if server:
        return server
    else:
        raise TypeError(f"UID {uid} isn't associated with any server")
