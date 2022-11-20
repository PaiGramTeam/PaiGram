from genshin import Region, GenshinException
from pydantic import BaseModel
from telegram import ReplyKeyboardRemove, Update, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import CallbackContext, filters

from core.base.redisdb import RedisDB
from core.config import config
from core.cookies import CookiesService
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler
from core.user import UserService
from core.user.error import UserNotFoundError
from modules.apihelper.error import ResponseException
from modules.apihelper.hyperion import Verification
from plugins.genshin.verification import VerificationSystem
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client
from utils.log import logger


class WebAppData(BaseModel):
    path: str
    data: dict
    code: int
    message: str


class WebAppDataException(Exception):
    def __init__(self, data):
        self.data = data
        super().__init__()


class WebApp(Plugin):
    def __init__(self, user_service: UserService = None, cookies_service: CookiesService = None, redis: RedisDB = None):
        self.cookies_service = cookies_service
        self.user_service = user_service
        self.verification_system = VerificationSystem(redis)

    @staticmethod
    def de_web_app_data(data: str) -> WebAppData:
        try:
            return WebAppData.parse_raw(data)
        except Exception as exc:
            raise WebAppDataException(data) from exc

    @handler.message(filters=filters.StatusUpdate.WEB_APP_DATA, block=False)
    @restricts()
    async def app(self, update: Update, context: CallbackContext):
        user = update.effective_user
        message = update.effective_message
        web_app_data = message.web_app_data
        if web_app_data:
            logger.info("用户 %s[%s] 触发 WEB_APP_DATA 请求", user.full_name, user.id)
            result = self.de_web_app_data(web_app_data.data)
            logger.debug("path:%s\ndata:%s\ncode:%s\nmessage:%s", result.path, result.data, result.code, result.message)
            if result.code == 0:
                if result.path == "verify":
                    validate = result.data.get("geetest_validate")
                    try:
                        client = await get_genshin_client(user.id)
                        if client.region != Region.CHINESE:
                            await message.reply_text("非法用户", reply_markup=ReplyKeyboardRemove())
                            return
                    except UserNotFoundError:
                        await message.reply_text("用户未找到", reply_markup=ReplyKeyboardRemove())
                        return
                    except CookiesNotFoundError:
                        await message.reply_text("检测到用户为UID绑定，无需认证", reply_markup=ReplyKeyboardRemove())
                        return
                    verification = Verification(cookies=client.cookie_manager.cookies)
                    if validate:
                        _, challenge = await self.verification_system.get_challenge(client.uid)
                        if challenge:
                            logger.info(
                                "用户 %s[%s] 请求通过认证\nchallenge:%s\nvalidate:%s",
                                user.full_name,
                                user.id,
                                challenge,
                                validate,
                            )
                            try:
                                await verification.verify(challenge=challenge, validate=validate)
                                logger.success("用户 %s[%s] 验证成功", user.full_name, user.id)
                                await message.reply_text("验证成功", reply_markup=ReplyKeyboardRemove())
                            except ResponseException as exc:
                                logger.warning(
                                    "用户 %s[%s] 验证失效 API返回 [%s]%s", user.full_name, user.id, exc.code, exc.message
                                )
                                if "拼图已过期" in exc.message:
                                    await message.reply_text(
                                        "验证失败，拼图已过期，请稍后重试或更换使用环境进行验证", reply_markup=ReplyKeyboardRemove()
                                    )
                                else:
                                    await message.reply_text(
                                        f"验证失败，错误信息为 [{exc.code}]{exc.message}，请稍后重试",
                                        reply_markup=ReplyKeyboardRemove(),
                                    )
                        else:
                            logger.warning("用户 %s[%s] 验证失效 请求已经过期", user.full_name, user.id)
                            await message.reply_text("验证失效 请求已经过期 请稍后重试", reply_markup=ReplyKeyboardRemove())
                        return
                    try:
                        await client.get_genshin_notes()
                    except GenshinException as exc:
                        if exc.retcode != 1034:
                            raise exc
                    else:
                        await message.reply_text("账户正常，无需认证")
                        return
                    try:
                        data = await verification.create(is_high=True)
                        challenge = data["challenge"]
                        gt = data["gt"]
                        logger.success("用户 %s[%s] 创建验证成功\ngt:%s\nchallenge%s", user.full_name, user.id, gt, challenge)
                    except ResponseException as exc:
                        logger.warning("用户 %s[%s] 创建验证失效 API返回 [%s]%s", user.full_name, user.id, exc.code, exc.message)
                        await message.reply_text(
                            f"创建验证失败 错误信息为 [{exc.code}]{exc.message} 请稍后重试", reply_markup=ReplyKeyboardRemove()
                        )
                        return
                    await self.verification_system.set_challenge(client.uid, gt, challenge)
                    url = f"{config.pass_challenge_user_web}/webapp?username={context.bot.username}&command=verify&gt={gt}&challenge={challenge}&uid={client.uid}"
                    await message.reply_text(
                        "请尽快点击下方手动验证 或发送 /web_cancel 取消操作",
                        reply_markup=ReplyKeyboardMarkup.from_button(
                            KeyboardButton(
                                text="点我手动验证",
                                web_app=WebAppInfo(url=url),
                            )
                        ),
                    )
            else:
                logger.warning(
                    "用户 %s[%s] WEB_APP_DATA 请求错误 [%s]%s", user.full_name, user.id, result.code, result.message
                )
                await message.reply_text(result.message, reply_markup=ReplyKeyboardRemove())
        else:
            logger.warning("用户 %s[%s] WEB_APP_DATA 非法数据", user.full_name, user.id)

    @handler.command("web_cancel", block=False)
    @restricts()
    async def web_cancel(self, update: Update, _: CallbackContext) -> None:
        message = update.effective_message
        await message.reply_text("取消操作", reply_markup=ReplyKeyboardRemove())
