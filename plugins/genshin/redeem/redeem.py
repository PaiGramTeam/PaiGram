import asyncio
import time
from typing import List

from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import filters

from core.plugin import Plugin, handler
from gram_core.services.users.services import UserAdminService
from plugins.genshin.redeem.runner import RedeemRunner, RedeemResult, RedeemQueueFull
from plugins.tools.genshin import GenshinHelper
from utils.log import logger


REDEEM_TEXT = """#### 兑换结果 ####
时间：{} (UTC+8)
UID: {}
兑换码：{}
兑换结果：{}"""


class Redeem(Plugin):
    """兑换码兑换"""

    def __init__(
        self,
        genshin_helper: GenshinHelper,
        user_admin_service: UserAdminService,
    ):
        self.genshin_helper = genshin_helper
        self.user_admin_service = user_admin_service
        self.max_code_in_pri_message = 5
        self.max_code_in_pub_message = 3
        self.redeem_runner = RedeemRunner(genshin_helper)

    async def _callback(self, data: "RedeemResult") -> None:
        code = data.code
        uid = data.uid if data.uid else "未知"
        msg = data.error if data.error else "成功"
        today = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        text = REDEEM_TEXT.format(today, uid, code, msg)
        reply_message = await data.message.edit_text(text)
        if filters.ChatType.GROUPS.filter(reply_message):
            self.add_delete_message_job(reply_message)

    async def redeem_one_code(self, update: Update, user_id: int, code: str):
        if not code:
            return
        message = update.effective_message
        reply_message = await message.reply_text("正在兑换中，请稍等")

        task_data = RedeemResult(user_id=user_id, code=code, message=reply_message)
        priority = 1 if await self.user_admin_service.is_admin(user_id) else 2
        try:
            await self.redeem_runner.run(task_data, self._callback, priority)
        except RedeemQueueFull:
            await reply_message.edit_text("兑换队列已满，请稍后再试")
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(reply_message)

    async def redeem_codes(self, update: Update, user_id: int, codes: List[str]):
        tasks = []
        for code in codes:
            tasks.append(self.redeem_one_code(update, user_id, code))
        await asyncio.gather(*tasks)

    @handler.command(command="redeem", cookie=True, block=False)
    @handler.message(filters=filters.Regex("^兑换码兑换(.*)"), cookie=True, block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user_id = await self.get_real_user_id(update)
        message = update.effective_message
        limit = self.max_code_in_pri_message
        if filters.ChatType.GROUPS.filter(message):
            self.add_delete_message_job(message)
            limit = self.max_code_in_pub_message
        codes = [i for i in self.get_args(context) if i][:limit]
        self.log_user(update, logger.info, "兑换码兑换命令请求 codes[%s]", codes)
        if not codes:
            return
        await self.redeem_codes(update, user_id, codes)

    @handler.command(command="start", filters=filters.Regex(r" redeem_(.*)"), block=False)
    async def start_redeem(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        args = self.get_args(context)
        codes = [i for i in args[0].split("_")[1:] if i][: self.max_code_in_pri_message]
        logger.info("用户 %s[%s] 通过start命令 进入兑换码兑换流程 codes[%s]", user.full_name, user.id, codes)
        await self.redeem_codes(update, user.id, codes)
