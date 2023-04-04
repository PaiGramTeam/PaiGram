from typing import List, Optional

import genshin
from genshin import GenshinException, InvalidCookies, TooManyRequests, types, Game

from core.base_service import BaseService
from core.basemodel import RegionEnum
from core.services.cookies.cache import PublicCookiesCache
from core.services.cookies.error import CookieServiceError, TooManyRequestPublicCookies
from core.services.cookies.models import CookiesDataBase as Cookies, CookiesStatusEnum
from core.services.cookies.repositories import CookiesRepository
from utils.log import logger

__all__ = ("CookiesService", "PublicCookiesService")


class CookiesService(BaseService):
    def __init__(self, cookies_repository: CookiesRepository) -> None:
        self._repository: CookiesRepository = cookies_repository

    async def update(self, cookies: Cookies):
        await self._repository.update(cookies)

    async def add(self, cookies: Cookies):
        await self._repository.add(cookies)

    async def get(
        self,
        user_id: int,
        account_id: Optional[int] = None,
        region: Optional[RegionEnum] = None,
    ) -> Optional[Cookies]:
        return await self._repository.get(user_id, account_id, region)

    async def delete(self, cookies: Cookies) -> None:
        return await self._repository.delete(cookies)


class PublicCookiesService(BaseService):
    def __init__(self, cookies_repository: CookiesRepository, public_cookies_cache: PublicCookiesCache):
        self._cache = public_cookies_cache
        self._repository: CookiesRepository = cookies_repository
        self.count: int = 0
        self.user_times_limiter = 3 * 3

    async def initialize(self) -> None:
        logger.info("正在初始化公共Cookies池")
        await self.refresh()
        logger.success("刷新公共Cookies池成功")

    async def refresh(self):
        """刷新公共Cookies 定时任务
        :return:
        """
        user_list: List[int] = []
        cookies_list = await self._repository.get_all_by_region(RegionEnum.HYPERION)  # 从数据库获取2
        for cookies in cookies_list:
            if cookies.status is None or cookies.status == CookiesStatusEnum.STATUS_SUCCESS:
                user_list.append(cookies.user_id)
        if len(user_list) > 0:
            add, count = await self._cache.add_public_cookies(user_list, RegionEnum.HYPERION)
            logger.info("国服公共Cookies池已经添加[%s]个 当前成员数为[%s]", add, count)
        user_list.clear()
        cookies_list = await self._repository.get_all_by_region(RegionEnum.HOYOLAB)
        for cookies in cookies_list:
            if cookies.status is None or cookies.status == CookiesStatusEnum.STATUS_SUCCESS:
                user_list.append(cookies.user_id)
        if len(user_list) > 0:
            add, count = await self._cache.add_public_cookies(user_list, RegionEnum.HOYOLAB)
            logger.info("国际服公共Cookies池已经添加[%s]个 当前成员数为[%s]", add, count)

    async def get_cookies(self, user_id: int, region: RegionEnum = RegionEnum.NULL):
        """获取公共Cookies
        :param user_id: 用户ID
        :param region: 注册的服务器
        :return:
        """
        user_times = await self._cache.incr_by_user_times(user_id)
        if int(user_times) > self.user_times_limiter:
            logger.warning("用户 %s 使用公共Cookies次数已经到达上限", user_id)
            raise TooManyRequestPublicCookies(user_id)
        while True:
            public_id, count = await self._cache.get_public_cookies(region)
            cookies = await self._repository.get(public_id, region=region)
            if cookies is None:
                await self._cache.delete_public_cookies(public_id, region)
                continue
            if region == RegionEnum.HYPERION:
                client = genshin.Client(cookies=cookies.data, game=types.Game.GENSHIN, region=types.Region.CHINESE)
            elif region == RegionEnum.HOYOLAB:
                client = genshin.Client(
                    cookies=cookies.data, game=types.Game.GENSHIN, region=types.Region.OVERSEAS, lang="zh-cn"
                )
            else:
                raise CookieServiceError
            try:
                if client.cookie_manager.user_id is None:
                    raise RuntimeError("account_id not found")
                record_cards = await client.get_record_cards()
                for record_card in record_cards:
                    if record_card.game == Game.GENSHIN:
                        await client.get_partial_genshin_user(record_card.uid)
                        break
                else:
                    accounts = await client.get_game_accounts()
                    for account in accounts:
                        if account.game == Game.GENSHIN:
                            await client.get_partial_genshin_user(account.uid)
                            break
            except InvalidCookies as exc:
                if exc.retcode in (10001, -100):
                    logger.warning("用户 [%s] Cookies无效", public_id)
                elif exc.retcode == 10103:
                    logger.warning("用户 [%s] Cookies有效，但没有绑定到游戏帐户", public_id)
                else:
                    logger.warning("Cookies无效 ")
                    logger.exception(exc)
                cookies.status = CookiesStatusEnum.INVALID_COOKIES
                await self._repository.update(cookies)
                await self._cache.delete_public_cookies(cookies.user_id, region)
                continue
            except TooManyRequests:
                logger.warning("用户 [%s] 查询次数太多或操作频繁", public_id)
                cookies.status = CookiesStatusEnum.TOO_MANY_REQUESTS
                await self._repository.update(cookies)
                await self._cache.delete_public_cookies(cookies.user_id, region)
                continue
            except GenshinException as exc:
                if "invalid content type" in exc.msg:
                    raise exc
                if exc.retcode == 1034:
                    logger.warning("用户 [%s] 触发验证", public_id)
                else:
                    logger.warning("用户 [%s] 获取账号信息发生错误，错误信息为", public_id)
                    logger.exception(exc)
                await self._cache.delete_public_cookies(cookies.user_id, region)
                continue
            except RuntimeError as exc:
                if "account_id not found" in str(exc):
                    cookies.status = CookiesStatusEnum.INVALID_COOKIES
                    await self._repository.update(cookies)
                    await self._cache.delete_public_cookies(cookies.user_id, region)
                    continue
                raise exc
            except Exception as exc:
                await self._cache.delete_public_cookies(cookies.user_id, region)
                raise exc
            logger.info("用户 user_id[%s] 请求用户 user_id[%s] 的公共Cookies 该Cookies使用次数为%s次 ", user_id, public_id, count)
            return cookies

    async def undo(self, user_id: int, cookies: Optional[Cookies] = None, status: Optional[CookiesStatusEnum] = None):
        await self._cache.incr_by_user_times(user_id, -1)
        if cookies is not None and status is not None:
            cookies.status = status
            await self._repository.update(cookies)
            await self._cache.delete_public_cookies(cookies.user_id, cookies.region)
            logger.info("用户 user_id[%s] 反馈用户 user_id[%s] 的Cookies状态为 %s", user_id, cookies.user_id, status.name)
        else:
            logger.info("用户 user_id[%s] 撤销一次公共Cookies计数", user_id)
