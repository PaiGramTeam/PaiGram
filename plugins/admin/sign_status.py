from telegram import Update
from telegram.ext import CallbackContext, CommandHandler

from core.plugin import Plugin, handler
from core.services.task.services import SignServices
from utils.log import logger


class SignStatus(Plugin):
    def __init__(self, sign_service: SignServices):
        self.sign_service = sign_service

    @staticmethod
    async def get_sign_status(sign_service: SignServices) -> str:
        sign_db = await sign_service.get_all()
        names = ["签到成功", "Cookie 无效", "提前签到", "触发验证码", "API异常", "请求超时", "请求失败", "通知失败"]
        values = [0, 0, 0, 0, 0, 0, 0, 0]
        for sign in sign_db:
            values[sign.status.value] += 1
        text = f"<b>自动签到统计信息</b>\n\n总人数：<code>{len(sign_db)}</code>\n"
        return text + "\n".join(f"{name}: <code>{value}</code>" for name, value in zip(names, values))

    @handler(CommandHandler, command="sign_status", block=False, admin=True)
    async def sign_status(self, update: Update, _: CallbackContext):
        user = update.effective_user
        logger.info("用户 %s[%s] sign_status 命令请求", user.full_name, user.id)
        message = update.effective_message
        text = await self.get_sign_status(self.sign_service)
        await message.reply_text(text, parse_mode="html", quote=True)
