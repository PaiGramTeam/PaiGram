import os
import random

import genshin
from genshin import DataNotPublic, GenshinException, TooManyRequests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, ConversationHandler

from logger import Log
from model.base import ServiceEnum
from model.helpers import url_to_file
from plugins.base import BasePlugins
from service import BaseService
from service.base import UserInfoData


class GetUserCommandData:
    user_info: UserInfoData = UserInfoData()


class GetUser(BasePlugins):
    COMMAND_RESULT, = range(10200, 10201)

    def __init__(self, service: BaseService):
        super().__init__(service)
        self.current_dir = os.getcwd()

    async def _start_get_user_info(self, user_info_data: UserInfoData, service: ServiceEnum, uid: int = -1) -> bytes:
        if service == ServiceEnum.MIHOYOBBS:
            client = genshin.ChineseClient(cookies=user_info_data.mihoyo_cookie)
            if uid <= 0:
                _uid = user_info_data.mihoyo_game_uid
            else:
                _uid = uid
        else:
            client = genshin.GenshinClient(cookies=user_info_data.hoyoverse_cookie, lang="zh-cn")
            if uid <= 0:
                _uid = user_info_data.hoyoverse_game_uid
            else:
                _uid = uid
        try:
            user_info = await client.get_user(_uid)
        except TooManyRequests as error:
            raise Exception("查询次数大于30次") from error
        except GenshinException as error:
            raise error
        try:
            # 查询的UID如果是自己的，会返回DataNotPublic，自己查不了自己可还行......
            if uid > 0:
                record_card_info = await client.get_record_card(uid)
            else:
                record_card_info = await client.get_record_card()
        except DataNotPublic as error:
            Log.warning("get_record_card请求失败 查询的用户数据未公开 \n", error)
            nickname = _uid
            user_uid = ""
        except GenshinException as error:
            raise error
        else:
            nickname = record_card_info.nickname
            user_uid = record_card_info.uid
        user_avatar = user_info.characters[0].icon
        user_data = {
            "name": nickname,
            "uid": user_uid,
            "user_avatar": await url_to_file(user_avatar),
            "action_day_number": user_info.stats.days_active,
            "achievement_number": user_info.stats.achievements,
            "avatar_number": user_info.stats.anemoculi,
            "spiral_abyss": user_info.stats.spiral_abyss,
            "way_point_number": user_info.stats.unlocked_waypoints,
            "domain_number": user_info.stats.unlocked_domains,
            "luxurious_number": user_info.stats.luxurious_chests,
            "precious_chest_number": user_info.stats.precious_chests,
            "exquisite_chest_number": user_info.stats.exquisite_chests,
            "common_chest_number": user_info.stats.common_chests,
            "magic_chest_number": user_info.stats.remarkable_chests,
            "anemoculus_number": user_info.stats.anemoculi,
            "geoculus_number": user_info.stats.geoculi,
            "electroculus_number": user_info.stats.electroculi,
            "world_exploration_list": [],
            "teapot_level": user_info.teapot.level,
            "teapot_comfort_num": user_info.teapot.comfort,
            "teapot_item_num": user_info.teapot.items,
            "teapot_visit_num": user_info.teapot.visitors,
            "teapot_list": []
        }
        for exploration in user_info.explorations:
            exploration_data = {
                "name": exploration.name,
                "exploration_percentage": exploration.explored,
                "offerings": [],
                "icon": await url_to_file(exploration.icon)
            }
            for offering in exploration.offerings:
                # 修复上游奇怪的问题
                offering_name = offering.name
                if offering_name == "Reputation":
                    offering_name = "声望等级"
                offering_data = {
                    "data": f"{offering_name}：{offering.level}级"
                }
                exploration_data["offerings"].append(offering_data)
            user_data["world_exploration_list"].append(exploration_data)
        for teapot in user_info.teapot.realms:
            teapot_icon = teapot.icon
            # 修复 国际服绘绮庭 图标 地址请求 为404
            if "UI_HomeworldModule_4_Pic.png" in teapot_icon:
                teapot_icon = "https://upload-bbs.mihoyo.com/game_record/genshin/home/UI_HomeworldModule_4_Pic.png"
            teapot_data = {
                "icon": await url_to_file(teapot_icon),
                "name": teapot.name
            }
            user_data["teapot_list"].append(teapot_data)
        background_image = random.choice(os.listdir(f"{self.current_dir}/resources/background/vertical"))
        user_data["background_image"] = f"file://{self.current_dir}/resources/background/vertical/{background_image}"
        png_data = await self.service.template.render('genshin/info', "info.html", user_data,
                                                      {"width": 1024, "height": 1024})
        return png_data

    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.message
        Log.info(f"用户 {user.full_name}[{user.id}] 查询游戏用户命令请求")
        get_user_command_data: GetUserCommandData = context.chat_data.get("get_user_command_data")
        if get_user_command_data is None:
            get_user_command_data = GetUserCommandData()
            context.chat_data["get_user_command_data"] = get_user_command_data
        user_info = await self.service.user_service_db.get_user_info(user.id)
        if user_info.user_id == 0:
            await message.reply_text("未查询到账号信息")
            return ConversationHandler.END
        uid: int = -1
        try:
            args = message.text.split()
            if len(args) >= 2:
                uid = int(args[1])
        except ValueError as error:
            Log.error("获取 char_id 发生错误！ 错误信息为 \n", error)
            await message.reply_text("输入错误")
            return ConversationHandler.END
        if user_info.service == ServiceEnum.NULL:
            reply_text = "请选择你要查询的类别"
            keyboard = [
                [
                    InlineKeyboardButton("米游社", callback_data="get_user|米游社"),
                    InlineKeyboardButton("HoYoLab", callback_data="get_user|HoYoLab")
                ]
            ]
            get_user_command_data.user_info = user_info
            await update.message.reply_text(reply_text, reply_markup=InlineKeyboardMarkup(keyboard))
            return self.COMMAND_RESULT
        else:
            await update.message.reply_chat_action(ChatAction.FIND_LOCATION)
            png_data = await self._start_get_user_info(user_info, user_info.service, uid)
            await update.message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
            await update.message.reply_photo(png_data, filename=f"{user_info.user_id}.png",
                                             allow_sending_without_reply=True)

        return ConversationHandler.END

    async def command_result(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        get_user_command_data: GetUserCommandData = context.chat_data["get_user_command_data"]
        query = update.callback_query
        await query.answer()
        await query.delete_message()
        if query.data == "get_user|米游社":
            service = ServiceEnum.MIHOYOBBS
        elif query.data == "get_user|HoYoLab":
            service = ServiceEnum.HOYOLAB
        else:
            return ConversationHandler.END
        # Log.info(f"用户 {user.full_name}[{user.id}] 查询角色命令请求 || 参数 UID {uid}")
        png_data = await self._start_get_user_info(get_user_command_data.user_info, service)
        await query.message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await query.message.reply_photo(png_data, filename=f"{get_user_command_data.user_info.user_id}.png",
                                        allow_sending_without_reply=True)
        return ConversationHandler.END
