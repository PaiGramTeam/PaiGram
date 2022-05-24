import time

import genshin
from genshin import Game, GenshinException, AlreadyClaimed
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler, filters

from logger import Log
from model.base import ServiceEnum
from model.genshinhelper import YuanShen, Genshin
from plugins.base import BasePlugins
from service import BaseService
from service.base import UserInfoData


class SignCommandData:
    user_info: UserInfoData = UserInfoData()
    chat_id: int = 0
    reply_to_message_id: int = 0


class Sign(BasePlugins):
    def __init__(self, service: BaseService):
        super().__init__(service)
        self._sign_yuanshen = YuanShen()
        self._sing_genshin = Genshin()

    CHECK_SERVER, COMMAND_RESULT = range(10400, 10402)

    @staticmethod
    async def _start_sign_ex(user_info: UserInfoData, service: ServiceEnum) -> str:
        if service == ServiceEnum.MIHOYOBBS:
            client = genshin.ChineseClient(cookies=user_info.mihoyo_cookie)
            uid = user_info.mihoyo_game_uid
        else:
            client = genshin.GenshinClient(cookies=user_info.mihoyo_cookie, lang="zh-cn")
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
        reward = rewards[daily_reward_info.claimed_rewards - 1]
        today = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        message = f"###### {today} (UTC+8) ######\n" \
                  f"UID: {uid}\n" \
                  f"今日奖励: {reward.name} × {reward.amount}\n" \
                  f"签到结果: {result}"
        return message

    async def _start_sign(self, user_info: UserInfoData, service: ServiceEnum) -> str:
        if service == ServiceEnum.MIHOYOBBS:
            sign_api = self._sign_yuanshen
            uid = user_info.mihoyo_game_uid
            cookies = user_info.mihoyo_cookie
        else:
            sign_api = self._sing_genshin
            uid = user_info.hoyoverse_game_uid
            cookies = user_info.hoyoverse_cookie
        sign_give = await sign_api.get_sign_give(cookies=cookies)
        if sign_give.error:
            Log.error(f"UID {uid} 获取签到信息失败，API返回信息为 {sign_give.message}")
            return f"获取签到信息失败，API返回信息为 {sign_give.message}"
        is_sign = await sign_api.is_sign(uid, cookies=cookies)
        if is_sign.error:
            Log.error(f"UID {uid} 获取签到信息失败，API返回信息为 {is_sign.message}")
            return f"获取签到状态失败，API返回信息为 {is_sign.message}"
        total_sign_day = is_sign.data["total_sign_day"]
        award_name = sign_give.data["awards"][total_sign_day - 1]["name"]
        award_cnt = sign_give.data["awards"][total_sign_day - 1]["cnt"]
        today = is_sign.data["today"]
        if not is_sign.data["is_sign"]:
            sign = await sign_api.sign(uid, cookies=cookies)
            if sign.code == 0:
                result = "OK"
            elif sign.code == -5003:
                result = "今天旅行者已经签到过了~"
            else:
                Log.error(f"UID {uid} 签到失败 返回 错误代码 {sign.code} 错误信息 {sign.message}")
                result = f"签到失败 返回 错误代码 {sign.code} 错误信息 {sign.message}"
        else:
            result = "今天旅行者已经签到过了~"
        Log.info(f"UID {uid} 签到结果 {result}")
        message = f"###### {today} ######\n" \
                  f"UID: {uid}\n" \
                  f"今日奖励: {award_name} × {award_cnt}\n" \
                  f"签到结果: {result}"
        return message

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
            await update.message.reply_text("未查询到账号信息")
            return ConversationHandler.END
        if user_info.service == ServiceEnum.NULL:
            message = "请选择你要签到的服务器"
            keyboard = [
                [
                    InlineKeyboardButton("米游社", callback_data="sign|米游社"),
                    InlineKeyboardButton("HoYoLab", callback_data="sign|HoYoLab")
                ]
            ]
            sign_command_data.user_info = user_info
            await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
            sign_command_data.chat_id = update.message.chat_id
            sign_command_data.reply_to_message_id = update.message.message_id
            return self.COMMAND_RESULT
        else:
            sign = await self._start_sign_ex(user_info, user_info.service)
            reply_message = await message.reply_text(sign)
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
        return ConversationHandler.END

    async def command_result(self, update: Update, context: CallbackContext) -> int:
        sign_command_data: SignCommandData = context.chat_data["sign_command_data"]
        user_info = sign_command_data.user_info
        query = update.callback_query
        await query.answer()
        message = "签到失败"
        if query.data == "sign|米游社":
            message = await self._start_sign_ex(user_info, ServiceEnum.MIHOYOBBS)
        if query.data == "sign|HoYoLab":
            message = await self._start_sign_ex(user_info, ServiceEnum.HOYOLAB)
        await query.edit_message_text(message)
        if query_message := query.message:
            if filters.ChatType.GROUPS.filter(query_message):
                self._add_delete_message_job(context, query_message.chat_id, query_message.message_id)
        return ConversationHandler.END
