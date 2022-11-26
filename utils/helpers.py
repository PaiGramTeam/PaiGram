from __future__ import annotations

import hashlib
import os
import re
from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE
from inspect import iscoroutinefunction
from pathlib import Path
from typing import Awaitable, Callable, Match, Optional, Pattern, Tuple, TypeVar, Union, cast

import aiofiles
import genshin
import httpx
from genshin import Client, types
from httpx import UnsupportedProtocol
from typing_extensions import ParamSpec

from core.base.redisdb import RedisDB
from core.bot import bot
from core.config import config
from core.cookies.services import CookiesService, PublicCookiesService
from core.error import ServiceNotFoundError
from core.user.services import UserService
from utils.error import UrlResourcesNotFoundError
from utils.log import logger
from utils.models.base import RegionEnum

T = TypeVar("T")
P = ParamSpec("P")

USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/90.0.4430.72 Safari/537.36"
)
REQUEST_HEADERS: dict = {"User-Agent": USER_AGENT}
current_dir = os.getcwd()
cache_dir = os.path.join(current_dir, "cache")
if not os.path.exists(cache_dir):
    os.mkdir(cache_dir)

cookies_service = bot.services.get(CookiesService)
cookies_service = cast(CookiesService, cookies_service)
user_service = bot.services.get(UserService)
user_service = cast(UserService, user_service)
public_cookies_service = bot.services.get(PublicCookiesService)
public_cookies_service = cast(PublicCookiesService, public_cookies_service)
redis_db = bot.services.get(RedisDB)
redis_db = cast(RedisDB, redis_db)
genshin_cache: Optional[genshin.RedisCache] = None
if redis_db and config.genshin_ttl:
    genshin_cache = genshin.RedisCache(redis_db.client, ttl=config.genshin_ttl)

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


async def url_to_file(url: str, return_path: bool = False) -> str:
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
        async with aiofiles.open(file_dir, mode="wb") as f:
            await f.write(data.content)
    logger.debug(f"url_to_file 获取url[{url}] 并下载到 file_dir[{file_dir}]")

    return file_dir if return_path else Path(file_dir).as_uri()


async def get_genshin_client(user_id: int, region: Optional[RegionEnum] = None, need_cookie: bool = True) -> Client:
    if user_service is None:
        raise ServiceNotFoundError(UserService)
    if cookies_service is None:
        raise ServiceNotFoundError(CookiesService)
    user = await user_service.get_user_by_id(user_id)
    if region is None:
        region = user.region
    cookies = None
    if need_cookie:
        cookies = await cookies_service.get_cookies(user_id, region)
        cookies = cookies.cookies
    if region == RegionEnum.HYPERION:
        uid = user.yuanshen_uid
        client = genshin.Client(cookies=cookies, game=types.Game.GENSHIN, region=types.Region.CHINESE, uid=uid)
    elif region == RegionEnum.HOYOLAB:
        uid = user.genshin_uid
        client = genshin.Client(
            cookies=cookies, game=types.Game.GENSHIN, region=types.Region.OVERSEAS, lang="zh-cn", uid=uid
        )
    else:
        raise TypeError("region is not RegionEnum.NULL")
    if genshin_cache:
        client.cache = genshin_cache
    return client


async def get_public_genshin_client(user_id: int) -> Tuple[Client, Optional[int]]:
    if user_service is None:
        raise ServiceNotFoundError(UserService)
    if public_cookies_service is None:
        raise ServiceNotFoundError(PublicCookiesService)
    user = await user_service.get_user_by_id(user_id)
    region = user.region
    cookies = await public_cookies_service.get_cookies(user_id, region)
    if region == RegionEnum.HYPERION:
        uid = user.yuanshen_uid
        client = genshin.Client(cookies=cookies.cookies, game=types.Game.GENSHIN, region=types.Region.CHINESE)
    elif region == RegionEnum.HOYOLAB:
        uid = user.genshin_uid
        client = genshin.Client(
            cookies=cookies.cookies, game=types.Game.GENSHIN, region=types.Region.OVERSEAS, lang="zh-cn"
        )
    else:
        raise TypeError("region is not RegionEnum.NULL")
    if genshin_cache:
        client.cache = genshin_cache
    return client, uid


def region_server(uid: Union[int, str]) -> RegionEnum:
    if isinstance(uid, (int, str)):
        region = REGION_MAP.get(str(uid)[0])
    else:
        raise TypeError("UID variable type error")
    if region:
        return region
    else:
        raise TypeError(f"UID {uid} isn't associated with any region")


async def execute(command, pass_error=True):
    """Executes command and returns output, with the option of enabling stderr."""
    executor = await create_subprocess_shell(command, stdout=PIPE, stderr=PIPE, stdin=PIPE)

    stdout, stderr = await executor.communicate()
    if pass_error:
        try:
            result = str(stdout.decode().strip()) + str(stderr.decode().strip())
        except UnicodeDecodeError:
            result = str(stdout.decode("gbk").strip()) + str(stderr.decode("gbk").strip())
    else:
        try:
            result = str(stdout.decode().strip())
        except UnicodeDecodeError:
            result = str(stdout.decode("gbk").strip())
    return result


async def async_re_sub(
    pattern: str | Pattern,
    repl: str | Callable[[Match], str] | Callable[[Match], Awaitable[str]],
    string: str,
    count: int = 0,
    flags: int = 0,
) -> str:
    """
    一个支持 repl 参数为 async 函数的 re.sub
    Args:
        pattern (str | Pattern): 正则对象
        repl (str | Callable[[Match], str] | Callable[[Match], Awaitable[str]]): 替换后的文本或函数
        string (str): 目标文本
        count (int): 要替换的最大次数
        flags (int): 标志常量

    Returns:
        返回经替换后的字符串
    """
    result = ""
    temp = string
    if count != 0:
        for _ in range(count):
            match = re.search(pattern, temp, flags=flags)
            replaced = None
            if iscoroutinefunction(repl):
                # noinspection PyUnresolvedReferences,PyCallingNonCallable
                replaced = await repl(match)
            elif callable(repl):
                # noinspection PyCallingNonCallable
                replaced = repl(match)
            result += temp[: match.span(1)[0]] + (replaced or repl)
            temp = temp[match.span(1)[1] :]
    else:
        while match := re.search(pattern, temp, flags=flags):
            replaced = None
            if iscoroutinefunction(repl):
                # noinspection PyUnresolvedReferences,PyCallingNonCallable
                replaced = await repl(match)
            elif callable(repl):
                # noinspection PyCallingNonCallable
                replaced = repl(match)
            result += temp[: match.span(1)[0]] + (replaced or repl)
            temp = temp[match.span(1)[1] :]
    return result + temp
