from telegram import KeyboardButton, ReplyKeyboardMarkup, Update, WebAppInfo
from telegram.ext import CallbackContext, filters

from core.config import config
from core.plugin import Plugin, handler
from plugins.tools.challenge import ChallengeSystem, ChallengeSystemException
from utils.log import logger


class VerificationPlugins(Plugin):
    def __init__(
        self,
        challenge_system: ChallengeSystem,
    ):
        self.challenge_system = challenge_system

    @handler.command("verify", filters=filters.ChatType.PRIVATE, block=False)
    async def verify(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 发出verify命令", user.full_name, user.id)
        try:
            uid, gt, challenge = await self.challenge_system.create_challenge(
                user.id, context.args is not None and not len(context.args) >= 1
            )
        except ChallengeSystemException as exc:
            await message.reply_text(exc.message)
            return
        url = (
            f"{config.pass_challenge_user_web}/webapp?"
            f"gt={gt}&username={context.bot.username}&command=verify&challenge={challenge}&uid={uid}"
        )
        await message.reply_text(
            "请尽快在10秒内完成手动验证\n或发送 /web_cancel 取消操作",
            reply_markup=ReplyKeyboardMarkup.from_button(
                KeyboardButton(
                    text="点我手动验证",
                    web_app=WebAppInfo(url=url),
                )
            ),
        )
        self.track_event(update, "verify")
