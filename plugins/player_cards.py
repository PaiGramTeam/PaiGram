from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CommandHandler, ConversationHandler, CallbackQueryHandler

from model.apihelper.playercards import PlayerCardsAPI
from model.artifact import ArtifactInfo
from model.base import ServiceEnum
from plugins.base import BasePlugins
from plugins.errorhandler import conversation_error_handler
from service import BaseService


class PlayerCards(BasePlugins):

    def __init__(self, service: BaseService):
        self.api = PlayerCardsAPI()
        super().__init__(service)

    @staticmethod
    def create_conversation_handler(service: BaseService):
        player_cards = PlayerCards(service)
        handler = ConversationHandler(
            entry_points=[CommandHandler('player_card', player_cards.command_start, block=True)],
            states={
                1: [CallbackQueryHandler(player_cards.command_result)],
            },
            fallbacks=[CommandHandler('cancel', player_cards.cancel, block=True)]
        )
        return handler

    @conversation_error_handler
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.message
        args = context.args
        if len(args) >= 1:
            try:
                uid = int(args[0])
            except ValueError:
                await message.reply_text("参数错误")
                return
        else:
            user_info = await self.service.user_service_db.get_user_info(user.id)
            if user_info.service == ServiceEnum.HYPERION:
                uid = user_info.mihoyo_game_uid
            else:
                uid = user_info.hoyoverse_game_uid
        context.user_data["player_cards_data"] = None
        user_data_response = await self.api.get_data(uid)
        if user_data_response.status_code != 200:
            await message.reply_text("API 请求错误")
            return
        user_data = user_data_response.json()
        context.user_data["player_cards_data"] = user_data
        player_info = user_data["playerInfo"]
        show_avatar_info_list = player_info["showAvatarInfoList"]
        keyboard = []
        buttons = []
        for index, value in enumerate(show_avatar_info_list):
            avatar_id = value["avatarId"]
            avatar_name = self.api.get_characters_name(str(avatar_id))
            buttons.append(InlineKeyboardButton(f"{avatar_name}", callback_data=f"player_cards|{avatar_id}"))
            if index % 4 == 3:
                keyboard.append(buttons)
                buttons = []
        await message.reply_text("获取旅行者信息成功\n"
                                 "旅行者信息\n"
                                 f"旅行者名称 {player_info['nickname']}\n"
                                 f"旅行者签名 {player_info['signature']}\n"
                                 f"等级 {player_info['level']}\n"
                                 f"世界等级 {player_info['level']}\n"
                                 f"深境螺旋最深抵达 {player_info['towerFloorIndex']}-{player_info['towerLevelIndex']}\n"
                                 f"完成的成就 {player_info['finishAchievementNum']}\n"
                                 "请选择你要查询的角色", reply_markup=InlineKeyboardMarkup(keyboard))
        return 1

    @conversation_error_handler
    async def command_result(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        user_data: dict = context.user_data.get("player_cards_data")
        if user_data is None:
            await query.edit_message_text("数据错误")
            return ConversationHandler.END

        def get_callback_data(callback_query_data: str) -> int:
            _data = callback_query_data.split("|")
            try:
                return int(_data[1])
            except ValueError:
                return -1

        avatar_id = get_callback_data(query.data)
        avatar_info_list = user_data["avatarInfoList"]
        avatar_data: Optional[dict] = None
        for avatar_info in avatar_info_list:
            if avatar_info["avatarId"] == avatar_id:
                avatar_data = avatar_info
                break
        if avatar_data is None:
            await query.edit_message_text("数据错误")
            return ConversationHandler.END
        self.data_handling(avatar_data, avatar_id)
        print(avatar_data)

        return ConversationHandler.END

    def data_handling(self, avatar_data: dict, avatar_id: int):
        avatar_name = self.api.get_characters_name(str(avatar_id))
        equip_list = avatar_data["equipList"]  # 圣遗物和武器相关
        fetterInfo = avatar_data["fetterInfo"]  # 好感等级
        fightPropMap = avatar_data["fightPropMap"]  # 不知道
        inherentProudSkillList = avatar_data["inherentProudSkillList"]  # 不知道
        propMap = avatar_data["propMap"]  # 不知道
        proudSkillExtraLevelMap = avatar_data["proudSkillExtraLevelMap"]  # 不知道
        skillDepotId = avatar_data["skillDepotId"]  # 不知道
        skillLevelMap = avatar_data["skillLevelMap"]  # 技能等级
        talentIdList = avatar_data["talentIdList"]  # 不知道

        for equip in equip_list:
            if "reliquary" in equip:  # 圣遗物
                flat = equip["flat"]
                reliquary = equip["reliquary"]
                name = self.api.get_text(flat["nameTextMapHash"])
                ArtifactInfo(item_id=equip["itemId"], name=name, star=flat["rankLevel"],
                             level=reliquary["level"] - 1, )
            if "weapon" in equip:  # 武器
                pass
