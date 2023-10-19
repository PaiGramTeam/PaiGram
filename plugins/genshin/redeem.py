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

    @handler.command(command="redeem", block=False)
    @handler.message(filters=filters.Regex("^兑换码兑换(.*)"), block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.effective_message
        args = self.get_args(context)
        code = args[0] if args else None
        logger.info("用户 %s[%s] 兑换码兑换命令请求 code[%s]", user.full_name, user.id, code)
        if filters.ChatType.GROUPS.filter(message):
            self.add_delete_message_job(message)
        try:
            if not code:
                raise RedemptionInvalid
            async with self.genshin_helper.genshin(user.id) as client:
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
        reply_message = await message.reply_text(msg)
        if filters.ChatType.GROUPS.filter(reply_message):
            self.add_delete_message_job(reply_message)
        self.track_event(update, "redeem")
