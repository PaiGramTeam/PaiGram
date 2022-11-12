from typing import Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from core.base.redisdb import RedisDB
from core.baseplugin import BasePlugin
from core.config import config
from core.cookies import CookiesService
from core.plugin import Plugin, handler
from core.user import UserService
from modules.apihelper.hyperion import Verification
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.models.base import RegionEnum


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
    @restricts()
    @error_callable
    async def verify(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        user = await self.user_service.get_user_by_id(user.id)
        if user.region != RegionEnum.HYPERION:
            await message.reply_text("非法用户")
            return
        uid = user.yuanshen_uid
        cookie = await self.cookies_service.get_cookies(user.id, RegionEnum.HYPERION)
        client = Verification(cookie=cookie)
        if context.args and len(context.args) > 0:
            validate = context.args[0]
            _, challenge = await self.system.get_challenge(uid)
            if challenge:
                await client.verify(challenge, validate)
                await message.reply_text("验证成功")
            else:
                await message.reply_text("验证失效")
            return
        data = await client.create()
        challenge = data["challenge"]
        gt = data["gt"]
        validate = await client.ajax(referer="https://webstatic.mihoyo.com/", gt=gt, challenge=challenge)
        if validate:
            await client.verify(challenge, validate)
            await message.reply_text("验证成功")
            return
        await self.system.set_challenge(uid, gt, challenge)
        url = f"{config.pass_challenge_user_web}?username={context.bot.app.bot.username}&command=verify&gt={gt}&challenge={challenge}&uid={uid}"
        button = InlineKeyboardMarkup([[InlineKeyboardButton("验证", url=url)]])
        await message.reply_text("请尽快点击下方手动验证", reply_markup=button)
