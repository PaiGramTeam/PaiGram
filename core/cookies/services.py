from typing import List

import genshin
from genshin import GenshinException, InvalidCookies, TooManyRequests, types

from utils.log import logger
from utils.models.base import RegionEnum
from .cache import PublicCookiesCache
from .error import TooManyRequestPublicCookies, CookieServiceError
from .models import CookiesStatusEnum
from .repositories import CookiesNotFoundError, CookiesRepository


class CookiesService:
    def __init__(self, cookies_repository: CookiesRepository) -> None:
        self._repository: CookiesRepository = cookies_repository

    async def update_cookies(self, user_id: int, cookies: dict, region: RegionEnum):
        await self._repository.update_cookies(user_id, cookies, region)

    async def add_cookies(self, user_id: int, cookies: dict, region: RegionEnum):
        await self._repository.add_cookies(user_id, cookies, region)

    async def get_cookies(self, user_id: int, region: RegionEnum):
        return await self._repository.get_cookies(user_id, region)


class PublicCookiesService:
    def __init__(self, cookies_repository: CookiesRepository, public_cookies_cache: PublicCookiesCache):
        self._cache = public_cookies_cache
        self._repository: CookiesRepository = cookies_repository
        self.count: int = 0
        self.user_times_limiter = 3 * 3

    async def refresh(self):
        """刷新公共Cookies 定时任务
        :return:
        """
        user_list: List[int] = []
        cookies_list = await self._repository.get_all_cookies(RegionEnum.HYPERION)  # 从数据库获取2
        for cookies in cookies_list:
            if cookies.status is not None and cookies.status != CookiesStatusEnum.STATUS_SUCCESS:
                continue
            user_list.append(cookies.user_id)
        add, count = await self._cache.add_public_cookies(user_list, RegionEnum.HYPERION)
        logger.info(f"国服公共Cookies池已经添加[{add}]个 当前成员数为[{count}]")
        user_list.clear()
        cookies_list = await self._repository.get_all_cookies(RegionEnum.HOYOLAB)
        for cookies in cookies_list:
            user_list.append(cookies.user_id)
        add, count = await self._cache.add_public_cookies(user_list, RegionEnum.HOYOLAB)
        logger.info(f"国际服公共Cookies池已经添加[{add}]个 当前成员数为[{count}]")

    async def get_cookies(self, user_id: int, region: RegionEnum = RegionEnum.NULL):
        """获取公共Cookies
        :param user_id: 用户ID
        :param region: 注册的服务器
        :return:
        """
        user_times = await self._cache.incr_by_user_times(user_id)
        if int(user_times) > self.user_times_limiter:
            logger.warning(f"用户 [{user_id}] 使用公共Cookie次数已经到达上限")
            raise TooManyRequestPublicCookies(user_id)
        while True:
            public_id, count = await self._cache.get_public_cookies(region)
            try:
                cookies = await self._repository.get_cookies(public_id, region)
            except CookiesNotFoundError:
                await self._cache.delete_public_cookies(public_id, region)
                continue
            if region == RegionEnum.HYPERION:
                client = genshin.Client(cookies=cookies.cookies, game=types.Game.GENSHIN, region=types.Region.CHINESE)
            elif region == RegionEnum.HOYOLAB:
                client = genshin.Client(
                    cookies=cookies.cookies, game=types.Game.GENSHIN, region=types.Region.OVERSEAS, lang="zh-cn"
                )
            else:
                raise CookieServiceError
            try:
                await client.get_record_card()
            except InvalidCookies as exc:
                if "[10001]" in str(exc) or "[-100]" in str(exc):
                    logger.warning(f"用户 [{public_id}] Cookies无效")
                elif "[10103]" in str(exc):
                    logger.warning(f"用户 [{public_id}] Cookie有效，但没有绑定到游戏帐户")
                else:
                    logger.warning("Cookies无效，具体原因未知")
                    logger.exception(exc)
                cookies.status = CookiesStatusEnum.INVALID_COOKIES
                await self._repository.update_cookies_ex(cookies, region)
                await self._cache.delete_public_cookies(cookies.user_id, region)
                continue
            except TooManyRequests:
                logger.warning(f"用户 [{public_id}] 查询次数太多或操作频繁")
                cookies.status = CookiesStatusEnum.TOO_MANY_REQUESTS
                await self._repository.update_cookies_ex(cookies, region)
                await self._cache.delete_public_cookies(cookies.user_id, region)
                continue
            except GenshinException as exc:
                logger.warning(f"用户 [{public_id}] 获取账号信息发生错误，错误信息为")
                logger.exception(exc)
                continue
            logger.info(f"用户 user_id[{user_id}] 请求" f"用户 user_id[{public_id}] 的公共Cookies 该Cookie使用次数为[{count}]次 ")
            return cookies
