import datetime
import time

from genshin import Game, GenshinException, AlreadyClaimed, Client
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ConversationHandler, filters, CallbackContext

from app.user.repositories import UserNotFoundError
from logger import Log
from plugins.base import BasePlugins
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import get_genshin_client
from utils.plugins.manager import listener_plugins_class


@listener_plugins_class()
class Sign(BasePlugins):
    """每日签到"""

    CHECK_SERVER, COMMAND_RESULT = range(10400, 10402)

    @classmethod
    def create_handlers(cls):
        sign = cls()
        return [CommandHandler('sign', sign.command_start, block=True),
                MessageHandler(filters.Regex(r"^每日签到(.*)"), sign.command_start, block=True)]

    @staticmethod
    async def _start_sign(client: Client) -> str:
        try:
            rewards = await client.get_monthly_rewards(game=Game.GENSHIN, lang="zh-cn")
        except GenshinException as error:
            Log.error(f"UID {client.uid} 获取签到信息失败，API返回信息为 {str(error)}")
            return f"获取签到信息失败，API返回信息为 {str(error)}"
        try:
            daily_reward_info = await client.get_reward_info(game=Game.GENSHIN, lang="zh-cn")  # 获取签到信息失败
        except GenshinException as error:
            Log.error(f"UID {client.uid} 获取签到状态失败，API返回信息为 {str(error)}")
            return f"获取签到状态失败，API返回信息为 {str(error)}"
        if not daily_reward_info.signed_in:
            try:
                request_daily_reward = await client.request_daily_reward("sign", method="POST",
                                                                         game=Game.GENSHIN, lang="zh-cn")
                Log.info(f"UID {client.uid} 签到请求 {request_daily_reward}")
            except AlreadyClaimed:
                result = "今天旅行者已经签到过了~"
            except GenshinException as error:
                Log.error(f"UID {client.uid} 签到失败，API返回信息为 {str(error)}")
                return f"获取签到状态失败，API返回信息为 {str(error)}"
            else:
                result = "OK"
        else:
            result = "今天旅行者已经签到过了~"
        Log.info(f"UID {client.uid} 签到结果 {result}")
        reward = rewards[daily_reward_info.claimed_rewards - (1 if daily_reward_info.signed_in else 0)]
        today = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        cn_timezone = datetime.timezone(datetime.timedelta(hours=8))
        now = datetime.datetime.now(cn_timezone)
        missed_days = now.day - daily_reward_info.claimed_rewards
        if not daily_reward_info.signed_in:
            missed_days -= 1
        message = f"#### {today} (UTC+8) ####\n" \
                  f"UID: {client.uid}\n" \
                  f"今日奖励: {reward.name} × {reward.amount}\n" \
                  f"本月漏签次数：{missed_days}\n" \
                  f"签到结果: {result}"
        return message

    @error_callable
    @restricts(return_data=ConversationHandler.END)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        user = update.effective_user
        message = update.message
        Log.info(f"用户 {user.full_name}[{user.id}] 每日签到命令请求")
        if filters.ChatType.GROUPS.filter(message):
            self._add_delete_message_job(context, message.chat_id, message.message_id)
        try:
            client = await get_genshin_client(user.id, self.user_service, self.cookies_service)
            sign_text = await self._start_sign(client)
            reply_message = await message.reply_text(sign_text, allow_sending_without_reply=True)
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
        except UserNotFoundError:
            reply_message = await message.reply_text("未查询到账号信息，请先私聊派蒙绑定账号")
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            return
