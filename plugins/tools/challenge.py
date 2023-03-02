from typing import Tuple, Optional

from genshin import Region, GenshinException

from core.dependence.redisdb import RedisDB
from core.plugin import Plugin
from core.services.cookies import CookiesService
from modules.apihelper.client.components.verify import Verify
from modules.apihelper.error import ResponseException, APIHelperException
from plugins.tools.genshin import GenshinHelper, PlayerNotFoundError
from utils.log import logger

__all__ = ("ChallengeSystemException", "ChallengeSystem")


class ChallengeSystemException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__()


class ChallengeSystem(Plugin):
    def __init__(
        self,
        cookies_service: CookiesService,
        redis: RedisDB,
        genshin_helper: GenshinHelper,
    ) -> None:
        self.cookies_service = cookies_service
        self.genshin_helper = genshin_helper
        self.cache = redis.client
        self.qname = "plugin:challenge:"

    async def get_challenge(self, uid: int) -> Tuple[Optional[str], Optional[str]]:
        data = await self.cache.get(f"{self.qname}{uid}")
        if not data:
            return None, None
        data = data.decode("utf-8").split("|")
        return data[0], data[1]

    async def set_challenge(self, uid: int, gt: str, challenge: str):
        await self.cache.set(f"{self.qname}{uid}", f"{gt}|{challenge}")
        await self.cache.expire(f"{self.qname}{uid}", 10 * 60)

    async def create_challenge(
        self, user_id: int, need_verify: bool = True, ajax: bool = False
    ) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        try:
            client = await self.genshin_helper.get_genshin_client(user_id)
        except PlayerNotFoundError:
            raise ChallengeSystemException("用户未找到")
        if client.region != Region.CHINESE:
            raise ChallengeSystemException("非法用户")
        if need_verify:
            try:
                await client.get_genshin_notes()
            except GenshinException as exc:
                if exc.retcode != 1034:
                    raise exc
                raise ChallengeSystemException("账户正常，无需认证")
        verify = Verify(cookies=client.cookie_manager.cookies)
        try:
            data = await verify.create()
            challenge = data["challenge"]
            gt = data["gt"]
        except ResponseException as exc:
            logger.warning("用户 %s 创建验证失效 API返回 [%s]%s", user_id, exc.code, exc.message)
            raise ChallengeSystemException(f"创建验证失败 错误信息为 [{exc.code}]{exc.message} 请稍后重试")
        if ajax:
            try:
                validate = await verify.ajax(referer="https://webstatic.mihoyo.com/", gt=gt, challenge=challenge)
                if validate:
                    await verify.verify(challenge, validate)
                    return client.uid, "ajax", "ajax"
            except APIHelperException as exc:
                logger.warning("用户 %s ajax 验证失效 错误信息为 %s", user_id, str(exc))
        await self.set_challenge(client.uid, gt, challenge)
        return client.uid, gt, challenge

    async def pass_challenge(self, user_id: int, validate: str, challenge: Optional[str] = None) -> bool:
        try:
            client = await self.genshin_helper.get_genshin_client(user_id)
        except PlayerNotFoundError:
            raise ChallengeSystemException("用户未找到")
        if client.region != Region.CHINESE:
            raise ChallengeSystemException("非法用户")
        if challenge is None:
            _, challenge = await self.get_challenge(client.uid)
        if challenge is None:
            raise ChallengeSystemException("验证失效 请求已经过期")
        verify = Verify(cookies=client.cookie_manager.cookies)
        try:
            await verify.verify(challenge=challenge, validate=validate)
        except ResponseException as exc:
            logger.warning("用户 %s 验证失效 API返回 [%s]%s", user_id, exc.code, exc.message)
            if "拼图已过期" in exc.message:
                raise ChallengeSystemException("验证失败，拼图已过期，请稍后重试或更换使用环境进行验证")
            raise ChallengeSystemException(f"验证失败，错误信息为 [{exc.code}]{exc.message}，请稍后重试")
        return True
