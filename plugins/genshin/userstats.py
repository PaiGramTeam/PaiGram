import os
import random
from typing import Optional

from genshin import DataNotPublic, GenshinException, Client
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, ConversationHandler, filters

from core.baseplugin import BasePlugin
from core.cookies.error import CookiesNotFoundError
from core.plugin import Plugin, handler
from core.template.services import TemplateService
from core.user.error import UserNotFoundError
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.helpers import url_to_file, get_genshin_client, get_public_genshin_client
from utils.log import logger


class TeapotUnlocked(Exception):
    """尘歌壶未解锁"""


class UserStatsPlugins(Plugin, BasePlugin):
    """玩家统计查询"""

    def __init__(self, template_service: TemplateService = None):
        self.template_service = template_service
        self.current_dir = os.getcwd()

    async def _start_get_user_info(self, client: Client, uid: int = -1) -> bytes:
        if uid == -1:
            _uid = client.uid
        else:
            _uid = uid
        try:
            user_info = await client.get_genshin_user(_uid)
        except GenshinException as exc:
            raise exc
        if user_info.teapot is None:
            raise TeapotUnlocked
        try:
            # 查询的UID如果是自己的，会返回DataNotPublic，自己查不了自己可还行......
            if uid > 0:
                record_card_info = await client.get_record_card(uid)
            else:
                record_card_info = await client.get_record_card()
        except DataNotPublic:
            logger.warning("get_record_card请求失败 查询的用户数据未公开")
            nickname = _uid
            user_uid = ""
        except GenshinException as exc:
            raise exc
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
            "avatar_number": user_info.stats.characters,
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
            "dendroculi_number": user_info.stats.dendroculi,
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
        user_data[
            "background_image"] = f"file://{self.current_dir}/resources/background/vertical/{background_image}"
        png_data = await self.template_service.render('genshin/info', "info.html", user_data,
                                                      {"width": 1024, "height": 1024})
        return png_data

    @handler(CommandHandler, command="stats", block=False)
    @handler(MessageHandler, filters=filters.Regex("^玩家统计查询(.*)"), block=False)
    @restricts(return_data=ConversationHandler.END)
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> Optional[int]:
        user = update.effective_user
        message = update.effective_message
        logger.info(f"用户 {user.full_name}[{user.id}] 查询游戏用户命令请求")
        uid: int = -1
        try:
            args = context.args
            if args is not None and len(args) >= 1:
                uid = int(args[0])
        except ValueError as exc:
            logger.error("获取 uid 发生错误！ 错误信息为")
            logger.exception(exc)
            await message.reply_text("输入错误")
            return ConversationHandler.END
        try:
            try:
                client = await get_genshin_client(user.id)
            except CookiesNotFoundError:
                client, _uid = await get_public_genshin_client(user.id)
                if uid == -1:
                    uid = _uid
            png_data = await self._start_get_user_info(client, uid)
        except UserNotFoundError:
            reply_message = await message.reply_text("未查询到账号信息，请先私聊派蒙绑定账号")
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 30)

                self._add_delete_message_job(context, message.chat_id, message.message_id, 30)
            return
        except TeapotUnlocked:
            await message.reply_text("角色尘歌壶未解锁 如果想要查看具体数据 嗯...... 咕咕咕~")
            return ConversationHandler.END
        except AttributeError as exc:
            logger.warning("角色数据有误", exc)
            await message.reply_text("角色数据有误 估计是派蒙晕了")
            return ConversationHandler.END
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        await message.reply_photo(png_data, filename=f"{client.uid}.png", allow_sending_without_reply=True)
