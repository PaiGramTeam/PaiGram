from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, MessageHandler, filters

from logger import Log
from manager import listener_plugins_class
from model.helpers import get_genshin_client, url_to_file
from plugins.base import BasePlugins
from service.base import UserInfoData
from utils.base import PaimonContext


@listener_plugins_class()
class Abyss(BasePlugins):

    @classmethod
    def create_handlers(cls) -> list:
        abyss = cls()
        return [
            CommandHandler("abyss", abyss.command_start, block=False),
            MessageHandler(filters.Regex(r"^深渊数据查询(.*)"), abyss.command_start, block=True)
        ]

    @staticmethod
    def _get_role_star_bg(value: int):
        if value == 4:
            return "./background/roleStarBg4.png"
        elif value == 5:
            return "./background/roleStarBg5.png"
        else:
            raise ValueError("错误的数据")

    async def _get_abyss_data(self, user_info_data: UserInfoData) -> dict:
        client, uid = await get_genshin_client(user_info_data)
        spiral_abyss_info = await client.get_spiral_abyss(uid)
        if not spiral_abyss_info.unlocked:
            raise ValueError("unlocked is false")
        ranks = spiral_abyss_info.ranks
        if len(spiral_abyss_info.ranks.most_kills) == 0:
            raise ValueError("本次深渊旅行者还没挑战呢")
        abyss_data = {
            "uid": uid,
            "max_floor": spiral_abyss_info.max_floor,
            "total_battles": spiral_abyss_info.total_battles,
            "total_stars": spiral_abyss_info.total_stars,
            "most_played_list": [],
            "most_kills": {
                "icon": await url_to_file(ranks.most_kills[0].icon),
                "value": ranks.most_kills[0].value,
            },
            "strongest_strike": {
                "icon": await url_to_file(ranks.strongest_strike[0].icon),
                "value": ranks.strongest_strike[0].value
            },
            "most_damage_taken": {
                "icon": await url_to_file(ranks.most_damage_taken[0].icon),
                "value": ranks.most_damage_taken[0].value
            },
            "most_bursts_used": {
                "icon": await url_to_file(ranks.most_bursts_used[0].icon),
                "value": ranks.most_bursts_used[0].value
            },
            "most_skills_used": {
                "icon": await url_to_file(ranks.most_skills_used[0].icon),
                "value": ranks.most_skills_used[0].value
            }
        }
        # most_kills
        most_played_list = ranks.most_played
        for most_played in most_played_list:
            temp = {
                "icon": await url_to_file(most_played.icon),
                "value": most_played.value,
                "background": self._get_role_star_bg(most_played.rarity)
            }
            abyss_data["most_played_list"].append(temp)
        return abyss_data

    async def command_start(self, update: Update, context: PaimonContext) -> None:
        user = update.effective_user
        message = update.message
        service = context.service
        Log.info(f"用户 {user.full_name}[{user.id}] 查深渊挑战命令请求")
        await message.reply_chat_action(ChatAction.TYPING)
        user_info = await service.user_service_db.get_user_info(user.id)
        if user_info.user_id == 0:
            reply_message = await message.reply_text("未查询到账号信息，请先私聊派蒙绑定账号")
            if filters.ChatType.GROUPS.filter(message):
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 300)
                self._add_delete_message_job(context, message.chat_id, message.message_id, 300)
            return
        try:
            abyss_data = await self._get_abyss_data(user_info)
        except ValueError as exc:
            if "unlocked is false" in str(exc):
                await message.reply_text("本次深渊旅行者还没挑战呢，咕咕咕~~~")
                return
            if "本次深渊旅行者还没挑战呢" in str(exc):
                await message.reply_text("本次深渊旅行者还没挑战呢，咕咕咕~~~")
                return
            raise exc
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        png_data = await service.template.render('genshin/abyss', "abyss.html", abyss_data,
                                                 {"width": 690, "height": 504}, full_page=False)
        await message.reply_photo(png_data, filename=f"abyss_{user.id}.png",
                                  allow_sending_without_reply=True)
        return
