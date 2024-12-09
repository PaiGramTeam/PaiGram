import time
from typing import TYPE_CHECKING

from simnet import Region
from telegram.constants import ChatAction
from telegram.ext import filters

from core.config import config
from core.plugin import Plugin, handler
from core.services.task.models import Task as SignUser, TaskStatusEnum
from core.services.users.services import UserAdminService
from gram_core.services.task.services import TaskCardServices
from plugins.tools.cloud_game import CloudGameHelper
from plugins.tools.genshin import PlayerNotFoundError, CookiesNotFoundError
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes


class CloudGameSign(Plugin):
    """云游戏每日签到"""

    CHECK_SERVER, COMMAND_RESULT = range(10400, 10402)

    def __init__(
        self,
        cloud_game_helper: CloudGameHelper,
        sign_service: TaskCardServices,
        user_admin_service: UserAdminService,
    ):
        self.user_admin_service = user_admin_service
        self.sign_service = sign_service
        self.cloud_game_helper = cloud_game_helper

    async def _process_auto_sign(self, user_id: int, player_id: int, offset: int, chat_id: int, method: str) -> str:
        try:
            async with self.cloud_game_helper.client(user_id, player_id=player_id, offset=offset) as c:
                if c.region is Region.OVERSEAS:
                    return "云游戏相关功能仅支持国服"
                await c.get_cloud_game_notifications()
                player_id = c.player_id
        except (PlayerNotFoundError, CookiesNotFoundError):
            return config.notice.user_not_found
        user: SignUser = await self.sign_service.get_by_user_id(user_id, player_id)
        if user:
            if method == "关闭":
                await self.sign_service.remove(user)
                return f"UID {player_id} 关闭云游戏自动签到成功"
            if method == "开启":
                if user.chat_id == chat_id:
                    return f"UID {player_id} 云游戏自动签到已经开启过了"
                user.chat_id = chat_id
                user.status = TaskStatusEnum.STATUS_SUCCESS
                await self.sign_service.update(user)
                return f"UID {player_id} 修改云游戏自动签到通知对话成功"
        elif method == "关闭":
            return f"UID {player_id} 您还没有开启云游戏自动签到"
        elif method == "开启":
            user = self.sign_service.create(user_id, player_id, chat_id, TaskStatusEnum.STATUS_SUCCESS)
            await self.sign_service.add(user)
            return f"UID {player_id} 开启云游戏自动签到成功"

    @handler.command(command="cloud_game_sign", cookie=True, block=False)
    @handler.message(filters=filters.Regex("^云游戏每日签到(.*)"), cookie=True, block=False)
    @handler.command(command="start", filters=filters.Regex("cloud_game_sign$"), block=False)
    async def command_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        args = self.get_args(context)
        if len(args) >= 1:
            msg = None
            if args[0] == "开启自动签到":
                if await self.user_admin_service.is_admin(user_id):
                    msg = await self._process_auto_sign(user_id, uid, offset, message.chat_id, "开启")
                else:
                    msg = await self._process_auto_sign(user_id, uid, offset, user_id, "开启")
            elif args[0] == "关闭自动签到":
                msg = await self._process_auto_sign(user_id, uid, offset, message.chat_id, "关闭")
            if msg:
                self.log_user(update, logger.info, "云游戏自动签到命令请求 || 参数 %s", args[0])
                reply_message = await message.reply_text(msg)
                if filters.ChatType.GROUPS.filter(message):
                    self.add_delete_message_job(reply_message, delay=30)
                    self.add_delete_message_job(message, delay=30)
                return
        self.log_user(update, logger.info, "云游戏每日签到命令请求")
        if filters.ChatType.GROUPS.filter(message):
            self.add_delete_message_job(message)
        async with self.cloud_game_helper.client(user_id, player_id=uid, offset=offset) as client:
            if client.region is Region.OVERSEAS:
                reply_message = await message.reply_text("云游戏相关功能仅支持国服")
                if filters.ChatType.GROUPS.filter(reply_message):
                    self.add_delete_message_job(message)
                    self.add_delete_message_job(reply_message)
                return
            await message.reply_chat_action(ChatAction.TYPING)
            sign_text = await self.cloud_game_helper.start_sign(client)
        reply_message = await message.reply_text(sign_text)
        if filters.ChatType.GROUPS.filter(reply_message):
            self.add_delete_message_job(reply_message)

    @handler.command(command="cloud_game_wallet", cookie=True, block=False)
    async def command_start_wallet(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> None:
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        self.log_user(update, logger.info, "云游戏查询钱包命令请求")
        async with self.cloud_game_helper.client(user_id, player_id=uid, offset=offset) as client:
            if client.region is Region.OVERSEAS:
                reply_message = await message.reply_text("云游戏相关功能仅支持国服")
                if filters.ChatType.GROUPS.filter(reply_message):
                    self.add_delete_message_job(message)
                    self.add_delete_message_job(reply_message)
                return
            await message.reply_chat_action(ChatAction.TYPING)
            wallet = await self.cloud_game_helper.get_wallet(client)
        today = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        free_time = wallet.free_time.free_time
        pay_time = int(wallet.coin.coin_num / wallet.coin.exchange)
        total_time = wallet.total_time
        card = wallet.play_card.msg
        text = (
            "#### 云游戏钱包 ####\n"
            f"时间：{today} (UTC+8)\n"
            f"免费时长：{free_time} 分钟\n"
            f"付费时长：{pay_time} 分钟\n"
            f"畅玩卡：{card}\n"
            f"总时长：{total_time} 分钟"
        )
        await message.reply_text(text)
