import os
import datetime

import genshin
from genshin import GenshinException, DataNotPublic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, ConversationHandler, filters

from logger import Log
from model.base import ServiceEnum
from plugins.base import BasePlugins
from plugins.errorhandler import conversation_error_handler
from service import BaseService
from service.base import UserInfoData


class UidCommandData:
    user_info: UserInfoData = UserInfoData()


class DailyNote(BasePlugins):
    COMMAND_RESULT, = range(10200, 10201)

    def __init__(self, service: BaseService):
        super().__init__(service)
        self.current_dir = os.getcwd()

    async def _start_get_daily_note(self, user_info_data: UserInfoData, service: ServiceEnum) -> bytes:
        if service == ServiceEnum.MIHOYOBBS:
            client = genshin.ChineseClient(cookies=user_info_data.mihoyo_cookie)
            uid = user_info_data.mihoyo_game_uid
        else:
            client = genshin.GenshinClient(cookies=user_info_data.hoyoverse_cookie, lang="zh-cn")
            uid = user_info_data.hoyoverse_game_uid
        try:
            daily_info = await client.get_genshin_notes(uid)
        except GenshinException as error:
            raise error
        day = datetime.datetime.now().strftime("%m-%d %H:%M") + " 星期" + "一二三四五六日"[datetime.datetime.now().weekday()]
        resin_recovery_time = daily_info.resin_recovery_time.strftime("%m-%d %H:%M") if \
            daily_info.max_resin - daily_info.current_resin else None
        realm_recovery_time = (datetime.datetime.now().astimezone() +
                               daily_info.remaining_realm_currency_recovery_time).strftime("%m-%d %H:%M") if \
            daily_info.max_realm_currency - daily_info.current_realm_currency else None
        remained_time = None
        for i in daily_info.expeditions:
            if remained_time:
                if remained_time < i.remaining_time:
                    remained_time = i.remaining_time
            else:
                remained_time = i.remaining_time
        if remained_time:
            remained_time = (datetime.datetime.now().astimezone() + remained_time).strftime("%m-%d %H:%M")
        transformer, transformer_ready, transformer_recovery_time = False, None, None
        if daily_info.remaining_transformer_recovery_time is not None:
            transformer = True
            transformer_ready = daily_info.remaining_transformer_recovery_time.total_seconds() == 0
            transformer_recovery_time = daily_info.transformer_recovery_time.strftime("%m-%d %H:%M")
        daily_data = {
            "uid": uid,
            "day": day,
            "resin_recovery_time": resin_recovery_time,
            "current_resin": daily_info.current_resin,
            "max_resin": daily_info.max_resin,
            "realm_recovery_time": realm_recovery_time,
            "current_realm_currency": daily_info.current_realm_currency,
            "max_realm_currency": daily_info.max_realm_currency,
            "claimed_commission_reward": daily_info.claimed_commission_reward,
            "completed_commissions": daily_info.completed_commissions,
            "max_commissions": daily_info.max_commissions,
            "expeditions": True if daily_info.expeditions else False,
            "remained_time": remained_time,
            "current_expeditions": len(daily_info.expeditions),
            "max_expeditions": daily_info.max_expeditions,
            "remaining_resin_discounts": daily_info.remaining_resin_discounts,
            "max_resin_discounts": daily_info.max_resin_discounts,
            "transformer": transformer,
            "transformer_ready": transformer_ready,
            "transformer_recovery_time": transformer_recovery_time
        }
        png_data = await self.service.template.render('genshin/daily_note', "daily_note.html", daily_data,
                                                      {"width": 600, "height": 548}, full_page=False)
        return png_data

    @conversation_error_handler
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.message
        Log.info(f"用户 {user.full_name}[{user.id}] 查询游戏状态命令请求")
        daily_note_command_data: UidCommandData = context.chat_data.get("daily_note_command_data")
        if daily_note_command_data is None:
            daily_note_command_data = UidCommandData()
            context.chat_data["daily_note_command_data"] = daily_note_command_data
        user_info = await self.service.user_service_db.get_user_info(user.id)
        if user_info.user_id == 0:
            reply_message = await message.reply_text("未查询到账号信息，请先私聊派蒙绑定账号")
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 300)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 300)
            return ConversationHandler.END
        if user_info.service == ServiceEnum.NULL:
            reply_text = "请选择你要查询的类别"
            keyboard = [
                [
                    InlineKeyboardButton("米游社", callback_data="daily_note|米游社"),
                    InlineKeyboardButton("HoYoLab", callback_data="daily_note|HoYoLab")
                ]
            ]
            daily_note_command_data.user_info = user_info
            await update.message.reply_text(reply_text, reply_markup=InlineKeyboardMarkup(keyboard))
            return self.COMMAND_RESULT
        else:
            await update.message.reply_chat_action(ChatAction.TYPING)
            try:
                png_data = await self._start_get_daily_note(user_info, user_info.service)
            except DataNotPublic:
                reply_message = await update.message.reply_text("查询失败惹，可能是便签功能被禁用了？")
                if filters.ChatType.GROUPS.filter(message):
                    self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 300)
                    self._add_delete_message_job(context, message.chat_id, message.message_id, 300)
                return ConversationHandler.END
            await update.message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
            await update.message.reply_photo(png_data, filename=f"{user_info.user_id}.png",
                                             allow_sending_without_reply=True)

        return ConversationHandler.END

    @conversation_error_handler
    async def command_result(self, update: Update, context: CallbackContext) -> int:
        get_user_command_data: UidCommandData = context.chat_data["daily_note_command_data"]
        query = update.callback_query
        await query.answer()
        await query.delete_message()
        if query.data == "daily_note|米游社":
            service = ServiceEnum.MIHOYOBBS
        elif query.data == "daily_note|HoYoLab":
            service = ServiceEnum.HOYOLAB
        else:
            return ConversationHandler.END
        png_data = await self._start_get_daily_note(get_user_command_data.user_info, service)
        await query.message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await query.message.reply_photo(png_data, filename=f"{get_user_command_data.user_info.user_id}.png",
                                        allow_sending_without_reply=True)
        return ConversationHandler.END
