from typing import Optional

from pydantic import BaseModel
from telegram import ReplyKeyboardRemove, Update
from telegram.ext import CallbackContext, filters

from core.plugin import Plugin, handler
from plugins.tools.challenge import ChallengeSystem, ChallengeSystemException
from utils.log import logger


class WebAppData(BaseModel):
    path: str
    data: Optional[dict]
    code: int
    message: str


class WebAppDataException(Exception):
    def __init__(self, data):
        self.data = data
        super().__init__()


class WebApp(Plugin):
    def __init__(
        self,
        challenge_system: ChallengeSystem,
    ):
        self.challenge_system = challenge_system

    @staticmethod
    def de_web_app_data(data: str) -> WebAppData:
        try:
            return WebAppData.parse_raw(data)
        except Exception as exc:
            raise WebAppDataException(data) from exc

    @handler.message(filters=filters.StatusUpdate.WEB_APP_DATA, block=False)
    async def app(self, update: Update, _: CallbackContext):
        user = update.effective_user
        message = update.effective_message
        web_app_data = message.web_app_data
        if web_app_data:
            logger.info("用户 %s[%s] 触发 WEB_APP_DATA 请求", user.full_name, user.id)
            result = self.de_web_app_data(web_app_data.data)
            logger.debug(
                "path[%s]\ndata[%s]\ncode[%s]\nmessage[%s]", result.path, result.data, result.code, result.message
            )
            if result.code == 0:
                if result.path == "verify":
                    validate = result.data.get("geetest_validate")
                    if validate is not None:
                        try:
                            status = await self.challenge_system.pass_challenge(user.id, validate=validate)
                        except ChallengeSystemException as exc:
                            await message.reply_text(exc.message, reply_markup=ReplyKeyboardRemove())
                            return
                        if status:
                            await message.reply_text("验证通过", reply_markup=ReplyKeyboardRemove())
                        await message.reply_text("非法请求", reply_markup=ReplyKeyboardRemove())
                        return
            else:
                logger.warning(
                    "用户 %s[%s] WEB_APP_DATA 请求错误 [%s]%s", user.full_name, user.id, result.code, result.message
                )
                if result.path == "verify":
                    await message.reply_text(
                        f"验证过程中出现问题 {result.message}\n如果继续遇到该问题，请打开米游社→我的角色中尝试手动通过验证",
                        reply_markup=ReplyKeyboardRemove(),
                    )
                else:
                    await message.reply_text(f"WebApp返回错误 {result.message}", reply_markup=ReplyKeyboardRemove())
        else:
            logger.warning("用户 %s[%s] WEB_APP_DATA 非法数据", user.full_name, user.id)

    @handler.command("web_cancel", block=False)
    async def web_cancel(self, update: Update, _: CallbackContext) -> None:
        message = update.effective_message
        await message.reply_text("取消操作", reply_markup=ReplyKeyboardRemove())
