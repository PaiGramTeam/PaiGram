from typing import Tuple, Optional

from genshin import Region, GenshinException
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from core.base.redisdb import RedisDB
from core.baseplugin import BasePlugin
from core.config import config
from core.cookies import CookiesService
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler
from core.user import UserService
from core.user.error import UserNotFoundError
from modules.apihelper.error import ResponseException, APIHelperException
from modules.apihelper.hyperion import Verification
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client
from utils.log import logger


class VerificationSystem:
    def __init__(self, redis: RedisDB = None):
        self.cache = redis.client
        self.qname = "plugin:verification:"

    async def get_challenge(self, uid: int) -> Tuple[Optional[str], Optional[str]]:
        data = await self.cache.get(f"{self.qname}{uid}")
        if not data:
            return None, None
        data = data.decode("utf-8").split("|")
        return data[0], data[1]

    async def set_challenge(self, uid: int, gt: str, challenge: str):
        await self.cache.set(f"{self.qname}{uid}", f"{gt}|{challenge}")
        await self.cache.expire(f"{self.qname}{uid}", 10 * 60)


class VerificationPlugins(Plugin, BasePlugin):
    def __init__(self, user_service: UserService = None, cookies_service: CookiesService = None, redis: RedisDB = None):
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.system = VerificationSystem(redis)

    @handler.command("verify", block=False)
    @restricts(restricts_time=60)
    @error_callable
    async def verify(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 发出verify命令", user.full_name, user.id)
        try:
            client = await get_genshin_client(user.id)
            if client.region != Region.CHINESE:
                await message.reply_text("非法用户")
                return
        except UserNotFoundError:
            await message.reply_text("用户未找到")
            return
        except CookiesNotFoundError:
            await message.reply_text("检测到用户为UID绑定，无需认证")
            return
        verification = Verification(cookies=client.cookie_manager.cookies)
        if context.args and len(context.args) > 0:
            validate = context.args[0]
            _, challenge = await self.system.get_challenge(client.uid)
            if challenge:
                try:
                    await verification.verify(challenge, validate)
                    logger.success(f"用户 %s[%s] 验证成功", user.full_name, user.id)
                    await message.reply_text("验证成功")
                except ResponseException as exc:
                    logger.warning(f"用户 %s[%s] 验证失效 API返回 [%s]%s", user.full_name, user.id, exc.code, exc.message)
                    await message.reply_text(f"验证失败 错误信息为 [{exc.code}]{exc.message} 请稍后重试")
            else:
                logger.warning(f"用户 %s[%s] 验证失效 请求已经过期", user.full_name, user.id)
                await message.reply_text("验证失效 请求已经过期 请稍后重试")
            return
        try:
            await client.get_genshin_notes()
        except GenshinException as exc:
            if exc.retcode != 1034:
                raise exc
            logger.info("检测到用户 %s[%s] 玩家 %s 触发 1034 异常", user.full_name, user.id, client.uid)
        else:
            await message.reply_text("账户正常，无需认证")
            return
        try:
            data = await verification.create()
            logger.success("用户 %s[%s] 创建验证成功", user.full_name, user.id)
        except ResponseException as exc:
            logger.warning("用户 %s[%s] 创建验证失效 API返回 [%s]%s", user.full_name, user.id, exc.code, exc.message)
            await message.reply_text(f"创建验证失败 错误信息为 [{exc.code}]{exc.message} 请稍后重试")
            return
        challenge = data["challenge"]
        gt = data["gt"]
        try:
            validate = await verification.ajax(referer="https://webstatic.mihoyo.com/", gt=gt, challenge=challenge)
            if validate:
                await verification.verify(challenge, validate)
                logger.success("用户 %s[%s] 通过 ajax 验证", user.full_name, user.id)
                await message.reply_text("验证成功")
                return
        except APIHelperException as exc:
            logger.warning("用户 %s[%s] ajax 验证失效 错误信息为 %s", user.full_name, user.id, repr(exc))
        await self.system.set_challenge(client.uid, gt, challenge)
        url = f"{config.pass_challenge_user_web}?username={context.bot.username}&command=verify&gt={gt}&challenge={challenge}&uid={client.uid}"
        button = InlineKeyboardMarkup([[InlineKeyboardButton("验证", url=url)]])
        await message.reply_text("请尽快点击下方手动验证", reply_markup=button)
