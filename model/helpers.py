import hashlib
import os
from typing import List
import httpx
from telegram import Bot
from service.cache import RedisCache
import aiofiles

USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                  "Chrome/90.0.4430.72 Safari/537.36"
headers: dict = {'User-Agent': USER_AGENT}
current_dir = os.getcwd()
cache_dir = os.path.join(current_dir, "cache")
if not os.path.exists(cache_dir):
    os.mkdir(cache_dir)


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
            data = await client.get(url)
        if data.is_error:
            return ""
        async with aiofiles.open(file_dir, mode='wb') as f:
            await f.write(data.content)
    return prefix + file_dir

