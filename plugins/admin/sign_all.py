from telegram import Update
from telegram.ext import CallbackContext

from core.plugin import Plugin, handler
from plugins.tools.sign import SignSystem, SignJobType
from utils.log import logger


class SignAll(Plugin):
    def __init__(self, sign_system: SignSystem):
        self.sign_system = sign_system

    @handler.command(command="sign_all", block=False, admin=True)
    async def sign_all(self, update: Update, context: CallbackContext):
        user = update.effective_user
        logger.info("用户 %s[%s] sign_all 命令请求", user.full_name, user.id)
        message = update.effective_message
        reply = await message.reply_text("正在全部重新签到，请稍后...")
        await self.sign_system.do_sign_job(context, job_type=SignJobType.START)
        await reply.edit_text("全部账号重新签到完成")
