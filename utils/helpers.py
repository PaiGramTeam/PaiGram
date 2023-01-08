import hashlib
import os
import re
from asyncio import create_subprocess_shell
from inspect import iscoroutinefunction
from pathlib import Path
from typing import Awaitable, Callable, Iterator, Match, Optional, Pattern, Tuple, TypeVar, Union

import aiofiles
import genshin
import httpx
from genshin import Client, types
from httpx import UnsupportedProtocol
from typing_extensions import ParamSpec, TYPE_CHECKING

from core.config import config
from core.dependence.redisdb import RedisDB
from core.error import ServiceNotFoundError
from utils.const import REGION_MAP, REQUEST_HEADERS
from utils.error import UrlResourcesNotFoundError
from utils.log import logger
from utils.models.base import RegionEnum

if TYPE_CHECKING:
    from core.services.cookies import CookiesService, PublicCookiesService
    from core.services.users import UserService

__all__ = [
    "sha1",
    "url_to_file",
    "gen_pkg",
    "async_re_sub",
]

T = TypeVar("T")
P = ParamSpec("P")

current_dir = os.getcwd()
cache_dir = os.path.join(current_dir, "cache")
if not os.path.exists(cache_dir):
    os.mkdir(cache_dir)

cookies_service: Optional["CookiesService"] = None
user_service: Optional["UserService"] = None
public_cookies_service: Optional["PublicCookiesService"] = None
redis_db: Optional["RedisDB"] = None

genshin_cache: Optional[genshin.RedisCache] = None


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
                logger.error("连接不支持 url[%s]", url)
                return ""
        if data.is_error:
            logger.error("请求出现错误 url[%s] status_code[%s]", url, data.status_code)
            raise UrlResourcesNotFoundError(url)
        if data.status_code != 200:
            logger.error("url_to_file 获取url[%s] 错误 status_code[%s]", url, data.status_code)
            raise UrlResourcesNotFoundError(url)
        async with aiofiles.open(file_dir, mode="wb") as f:
            await f.write(data.content)
    logger.debug("url_to_file 获取url[%s] 并下载到 file_dir[%s]", url, file_dir)

    return file_dir if return_path else Path(file_dir).as_uri()


async def get_genshin_client(user_id: int, region: Optional[RegionEnum] = None, need_cookie: bool = True) -> Client:
    from core.services.cookies import CookiesService, PublicCookiesService
    from core.services.users import UserService
    from core.bot import bot

    global cookies_service, user_service, public_cookies_service, redis_db, genshin_cache

    cookies_service = cookies_service or bot.services.get(CookiesService)
    user_service = user_service or bot.services.get(UserService)
    public_cookies_service = public_cookies_service or bot.services.get(PublicCookiesService)
    redis_db = redis_db or bot.services.get(RedisDB)

    if redis_db and config.genshin_ttl:
        genshin_cache = genshin.RedisCache(redis_db.client, ttl=config.genshin_ttl)

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
    from core.services.cookies import PublicCookiesService
    from core.services.users import UserService

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


async def execute(command: Union[str, bytes], pass_error: bool = True) -> str:
    """Executes command and returns output, with the option of enabling stderr."""
    from asyncio import subprocess

    executor = await create_subprocess_shell(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
    )

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
    pattern: Union[str, Pattern],
    repl: Union[str, Callable[[Match], Union[Awaitable[str], str]]],
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


def gen_pkg(path: Path) -> Iterator[str]:
    """生成可以用于 import_module 导入的字符串"""
    from utils.const import PROJECT_ROOT

    for p in path.iterdir():
        if not p.name.startswith("_"):
            if p.is_dir():
                yield from gen_pkg(p)
            elif p.suffix == ".py":
                yield str(p.relative_to(PROJECT_ROOT).with_suffix("")).replace(os.sep, ".")
