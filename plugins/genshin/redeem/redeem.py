import asyncio
import contextlib
import time
from asyncio import sleep
from typing import List, Tuple

from simnet import Region
from telegram import Update, Message
from telegram.error import BadRequest, Forbidden
from telegram.ext import CallbackContext
from telegram.ext import filters

from core.plugin import Plugin, handler
from gram_core.basemodel import RegionEnum
from gram_core.services.cookies import CookiesService
from gram_core.services.cookies.models import CookiesStatusEnum
from gram_core.services.users.services import UserAdminService
from plugins.genshin.redeem.runner import RedeemRunner, RedeemResult, RedeemQueueFull
from plugins.tools.genshin import GenshinHelper
from utils.log import logger


REDEEM_TEXT = """#### 兑换结果 ####
时间：{} (UTC+8)
UID: {}
兑换码：{}
兑换结果：{}"""
REDEEM_ALL_TEXT = """#### 批量兑换 ####

兑换码：{}
正在兑换中，请稍等
{} / {}"""
REDEEM_ALL_FAIL_TEXT = """#### 批量兑换 ####

兑换码：{}
兑换成功：{}
兑换失败：{}"""


class Redeem(Plugin):
    """兑换码兑换"""

    def __init__(
        self,
        genshin_helper: GenshinHelper,
        user_admin_service: UserAdminService,
        cookies_service: CookiesService,
    ):
        self.genshin_helper = genshin_helper
        self.user_admin_service = user_admin_service
        self.max_code_in_pri_message = 5
        self.max_code_in_pub_message = 3
        self.redeem_runner = RedeemRunner(genshin_helper)
        self.cookies_service = cookies_service

    async def _callback(self, data: "RedeemResult") -> None:
        code = data.code
        uid = data.uid if data.uid else "未知"
        msg = data.error if data.error else "成功"
        today = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        text = REDEEM_TEXT.format(today, uid, code, msg)
        reply_message = None
        try:
            reply_message = await data.message.edit_text(text)
        except BadRequest:
            try:
                reply_message = await data.message.reply_text(text)
            except BadRequest:
                pass
        if reply_message and filters.ChatType.GROUPS.filter(reply_message):
            self.add_delete_message_job(reply_message)

    async def redeem_one_code(self, update: Update, user_id: int, uid: int, code: str, chinese: bool):
        if not code:
            return
        message = update.effective_message
        reply_message = await message.reply_text("正在兑换中，请稍等")

        task_data = RedeemResult(user_id=user_id, code=code, uid=uid, message=reply_message)
        if chinese:
            task_data.error = "此服务器暂不支持进行兑换哦~"
            await self._callback(task_data)
            return
        priority = 1 if await self.user_admin_service.is_admin(user_id) else 2
        try:
            await self.redeem_runner.run(task_data, self._callback, priority)
        except RedeemQueueFull:
            await reply_message.edit_text("兑换队列已满，请稍后再试")
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(reply_message)

    async def redeem_codes(self, update: Update, user_id: int, codes: List[str]):
        uid, offset = self.get_real_uid_or_offset(update)
        async with self.genshin_helper.genshin(user_id, player_id=uid, offset=offset) as client:
            chinese = client.region == Region.CHINESE
            uid = client.player_id
        tasks = []
        for code in codes:
            tasks.append(self.redeem_one_code(update, user_id, uid, code, chinese))
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

    async def _job_callback(self, data: "RedeemResult") -> None:
        if data.error:
            logger.warning("执行自动兑换兑换码时发生错误 user_id[%s] message[%s]", data.user_id, data.error)
            data.count[1] += 1
            return
        data.count[0] += 1
        user_id = data.user_id
        code = data.code
        uid = data.uid if data.uid else "未知"
        msg = "成功"
        today = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        text = REDEEM_TEXT.format(today, uid, code, msg)
        try:
            await self.application.bot.send_message(user_id, text)
        except BadRequest as exc:
            logger.warning("执行自动兑换兑换码时发生错误 user_id[%s] Message[%s]", user_id, exc.message)
        except Forbidden as exc:
            logger.warning("执行自动兑换兑换码时发生错误 user_id[%s] message[%s]", user_id, exc.message)
        except Exception as exc:
            logger.warning("执行自动兑换兑换码时发生错误 user_id[%s]", user_id, exc_info=exc)

    async def job_redeem_one_code(self, user_id: int, code: str, count: List[int]):
        task_data = RedeemResult(user_id=user_id, code=code, count=count)
        priority = 1 if await self.user_admin_service.is_admin(user_id) else 2
        try:
            await self.redeem_runner.run(task_data, self._job_callback, priority, True)
        except RedeemQueueFull:
            await sleep(5)
            await self.job_redeem_one_code(user_id, code, count)

    async def do_redeem_job(self, message: "Message", code: str) -> Tuple[int, int]:
        count = [0, 0]
        task_list = await self.cookies_service.get_all(
            region=RegionEnum.HOYOLAB, status=CookiesStatusEnum.STATUS_SUCCESS
        )
        task_len = len(task_list)
        for idx, task_db in enumerate(task_list):
            user_id = task_db.user_id
            try:
                await self.job_redeem_one_code(user_id, code, count)
            except Exception as exc:
                logger.warning("执行自动兑换兑换码时发生错误 user_id[%s]", user_id, exc_info=exc)
            if idx % 10 == 0:
                text = REDEEM_ALL_TEXT.format(code, idx, task_len)
                with contextlib.suppress(Exception):
                    await message.edit_text(text)
        return count[0], count[1]

    @handler.command(command="redeem_all", admin=True, block=False)
    async def redeem_all_command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        codes = [i for i in self.get_args(context) if i]
        self.log_user(update, logger.info, "兑换码批量兑换命令请求 codes[%s]", codes)
        if not codes:
            await message.reply_text("请输入兑换码")
            return
        code = codes[0]
        reply = await message.reply_text("开始运行批量兑换任务，请等待...")
        success, failed = await self.do_redeem_job(reply, code)
        text = REDEEM_ALL_FAIL_TEXT.format(code, success, failed)
        await message.reply_text(text)
        self.add_delete_message_job(reply, delay=1)
