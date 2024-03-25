from typing import TYPE_CHECKING

from simnet.errors import RedemptionInvalid, RedemptionClaimed, RegionNotSupported, RedemptionCooldown
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import filters

from core.plugin import Plugin, handler
from plugins.tools.genshin import GenshinHelper
from utils.log import logger

if TYPE_CHECKING:
    from simnet import GenshinClient


class Redeem(Plugin):
    """兑换码兑换"""

    def __init__(
        self,
        genshin_helper: GenshinHelper,
    ):
        self.genshin_helper = genshin_helper

    async def redeem_code(self, uid: int, code: str) -> str:
        try:
            if not code:
                raise RedemptionInvalid
            async with self.genshin_helper.genshin(uid) as client:
                client: "GenshinClient"
                await client.redeem_code_by_hoyolab(code)
            msg = "兑换码兑换成功。"
        except RegionNotSupported:
            msg = "此服务器暂不支持进行兑换哦~"
        except RedemptionInvalid:
            msg = "兑换码格式不正确，请确认。"
        except RedemptionClaimed:
            msg = "此兑换码已经兑换过了。"
        except RedemptionCooldown as e:
            msg = e.message
        return msg

    @handler.command(command="redeem", cookie=True, block=False)
    @handler.message(filters=filters.Regex("^兑换码兑换(.*)"), cookie=True, block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user_id = await self.get_real_user_id(update)
        message = update.effective_message
        args = self.get_args(context)
        code = args[0] if args else None
        self.log_user(update, logger.info, "兑换码兑换命令请求 code[%s]", code)
        if filters.ChatType.GROUPS.filter(message):
            self.add_delete_message_job(message)
        msg = await self.redeem_code(user_id, code)
        reply_message = await message.reply_text(msg)
        if filters.ChatType.GROUPS.filter(reply_message):
            self.add_delete_message_job(reply_message)

    @handler.command(command="start", filters=filters.Regex(r" redeem_(.*)"), block=False)
    async def start_redeem(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        args = self.get_args(context)
        code = args[0].split("_")[1]
        logger.info("用户 %s[%s] 通过start命令 进入兑换码兑换流程 code[%s]", user.full_name, user.id, code)
        msg = await self.redeem_code(user.id, code)
        await message.reply_text(msg)
