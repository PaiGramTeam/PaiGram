import datetime
import time

import genshin
from genshin import Game, GenshinException, AlreadyClaimed
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, ConversationHandler, filters, \
    CallbackQueryHandler

from logger import Log
from model.base import ServiceEnum
from plugins.base import BasePlugins, RestrictsCalls
from plugins.errorhandler import conversation_error_handler
from service import BaseService
from service.base import UserInfoData


class SignCommandData:
    user_info: UserInfoData = UserInfoData()
    chat_id: int = 0
    reply_to_message_id: int = 0


class Sign(BasePlugins):
    """
    每日签到
    """

    CHECK_SERVER, COMMAND_RESULT = range(10400, 10402)

    @staticmethod
    def create_conversation_handler(service: BaseService):
        sign = Sign(service)
        sign_handler = ConversationHandler(
            entry_points=[CommandHandler('sign', sign.command_start, block=True),
                          MessageHandler(filters.Regex(r"^每日签到(.*)"), sign.command_start, block=True)],
            states={
                sign.COMMAND_RESULT: [CallbackQueryHandler(sign.command_result, block=True)]
            },
            fallbacks=[CommandHandler('cancel', sign.cancel, block=True)]
        )
        return sign_handler

    @staticmethod
    async def _start_sign(user_info: UserInfoData, service: ServiceEnum) -> str:
        if service == ServiceEnum.HYPERION:
            client = genshin.ChineseClient(cookies=user_info.mihoyo_cookie)
            uid = user_info.mihoyo_game_uid
        else:
            client = genshin.GenshinClient(cookies=user_info.hoyoverse_cookie, lang="zh-cn")
            uid = user_info.hoyoverse_game_uid
        try:
            rewards = await client.get_monthly_rewards(game=Game.GENSHIN, lang="zh-cn")
        except GenshinException as error:
            Log.error(f"UID {uid} 获取签到信息失败，API返回信息为 {str(error)}")
            return f"获取签到信息失败，API返回信息为 {str(error)}"
        try:
            daily_reward_info = await client.get_reward_info(game=Game.GENSHIN, lang="zh-cn")  # 获取签到信息失败
        except GenshinException as error:
            Log.error(f"UID {uid} 获取签到状态失败，API返回信息为 {str(error)}")
            return f"获取签到状态失败，API返回信息为 {str(error)}"
        if not daily_reward_info.signed_in:
            try:
                request_daily_reward = await client.request_daily_reward("sign", method="POST",
                                                                         game=Game.GENSHIN, lang="zh-cn")
                Log.info(f"UID {uid} 签到请求 {request_daily_reward}")
            except AlreadyClaimed:
                result = "今天旅行者已经签到过了~"
            except GenshinException as error:
                Log.error(f"UID {uid} 签到失败，API返回信息为 {str(error)}")
                return f"获取签到状态失败，API返回信息为 {str(error)}"
            else:
                result = "OK"
        else:
            result = "今天旅行者已经签到过了~"
        Log.info(f"UID {uid} 签到结果 {result}")
        reward = rewards[daily_reward_info.claimed_rewards - (1 if daily_reward_info.signed_in else 0)]
        today = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        cn_timezone = datetime.timezone(datetime.timedelta(hours=8))
        now = datetime.datetime.now(cn_timezone)
        missed_days = now.day - daily_reward_info.claimed_rewards
        if not daily_reward_info.signed_in:
            missed_days -= 1
        message = f"#### {today} (UTC+8) ####\n" \
                  f"UID: {uid}\n" \
                  f"今日奖励: {reward.name} × {reward.amount}\n" \
                  f"本月漏签次数：{missed_days}\n" \
                  f"签到结果: {result}"
        return message

    @conversation_error_handler
    @RestrictsCalls(filters_chat=filters.ALL, return_data=ConversationHandler.END, try_delete_message=True)
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.message
        Log.info(f"用户 {user.full_name}[{user.id}] 每日签到命令请求")
        if filters.ChatType.GROUPS.filter(message):
            self._add_delete_message_job(context, message.chat_id, message.message_id)
        sign_command_data: SignCommandData = context.chat_data.get("sign_command_data")
        if sign_command_data is None:
            sign_command_data = SignCommandData()
            context.chat_data["sign_command_data"] = sign_command_data
        user_info = await self.service.user_service_db.get_user_info(user.id)
        if user_info.user_id == 0:
            await update.message.reply_text("未查询到账号信息，请先私聊派蒙绑定账号")
            return ConversationHandler.END
        if user_info.service == ServiceEnum.NULL:
            keyboard = [
                [
                    InlineKeyboardButton("米游社", callback_data="sign|米游社"),
                    InlineKeyboardButton("HoYoLab", callback_data="sign|HoYoLab")
                ]
            ]
            sign_command_data.user_info = user_info
            await update.message.reply_text("请选择你要签到的服务器", reply_markup=InlineKeyboardMarkup(keyboard))
            sign_command_data.chat_id = update.message.chat_id
            sign_command_data.reply_to_message_id = update.message.message_id
            return self.COMMAND_RESULT
        else:
            await message.reply_chat_action(ChatAction.TYPING)
            sign = await self._start_sign(user_info, user_info.service)
            reply_message = await message.reply_text(sign, allow_sending_without_reply=True)
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
        return ConversationHandler.END

    @conversation_error_handler
    async def command_result(self, update: Update, context: CallbackContext) -> int:
        sign_command_data: SignCommandData = context.chat_data["sign_command_data"]
        user_info = sign_command_data.user_info
        query = update.callback_query
        await query.answer()
        message = "签到失败"
        await query.message.reply_chat_action(ChatAction.TYPING)
        if query.data == "sign|米游社":
            message = await self._start_sign(user_info, ServiceEnum.HYPERION)
        if query.data == "sign|HoYoLab":
            message = await self._start_sign(user_info, ServiceEnum.HOYOLAB)
        await query.edit_message_text(message)
        if query_message := query.message:
            if filters.ChatType.GROUPS.filter(query_message):
                self._add_delete_message_job(context, query_message.chat_id, query_message.message_id)
        return ConversationHandler.END
