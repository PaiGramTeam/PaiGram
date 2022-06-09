import os

from pyppeteer import launch
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, ConversationHandler, filters

from logger import Log
from metadata.metadata import metadat
from plugins.base import BasePlugins, RestrictsCalls
from service import BaseService
from service.wish import WishCountInfo, get_one


class Gacha(BasePlugins):
    def __init__(self, service: BaseService):
        super().__init__(service)
        self.browser: launch = None
        self.current_dir = os.getcwd()
        self.resources_dir = os.path.join(self.current_dir, "resources")
        self.character_gacha_card = {}
        for character in metadat.characters:
            name = character["Name"]
            self.character_gacha_card[name] = character["GachaCard"]
        self.user_time = {}

    CHECK_SERVER, COMMAND_RESULT = range(10600, 10602)

    @RestrictsCalls(return_data=ConversationHandler.END, try_delete_message=True)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.message
        user = update.effective_user
        Log.info(f"用户 {user.full_name}[{user.id}] 抽卡模拟器命令请求")
        args = context.args
        gacha_name = "角色活动"
        if len(args) > 1:
            gacha_name = args[1]
            for key, value in {"2": "角色活动-2", "武器": "武器活动", "普通": "常驻"}.items():
                if key == gacha_name:
                    gacha_name = value
                    break
        gacha_info = await self.service.gacha.gacha_info(gacha_name)
        # 用户数据储存和处理
        if gacha_info.get("gacha_id") is None:
            await message.reply_text(f"没有找到名为 {gacha_name} 的卡池")
            return ConversationHandler.END
        gacha_id: str = gacha_info["gacha_id"]
        user_gacha: dict[str, WishCountInfo] = context.user_data.get("gacha")
        if user_gacha is None:
            user_gacha = context.user_data["gacha"] = {}
        user_gacha_count: WishCountInfo = user_gacha.get(gacha_id)
        if user_gacha_count is None:
            user_gacha_count = user_gacha[gacha_id] = WishCountInfo(user_id=user.id)
        # 用户数据储存和处理
        await message.reply_chat_action(ChatAction.TYPING)
        data = {
            "_res_path": f"file://{self.resources_dir}",
            "name": f"{user.full_name}",
            "info": gacha_name,
            "poolName": gacha_info["title"],
            "items": [],
        }
        for a in range(10):
            item = get_one(user_gacha_count, gacha_info)
            # item_name = item["item_name"]
            # item_type = item["item_type"]
            # if item_type == "角色":
            #     gacha_card = self.character_gacha_card.get(item_name)
            #     if gacha_card is None:
            #         await message.reply_text(f"获取角色 {item_name} GachaCard信息失败")
            #         return
            #     item["item_character_img"] = await url_to_file(gacha_card)
            data["items"].append(item)

        def take_rang(elem: dict):
            return elem["rank"]

        data["items"].sort(key=take_rang, reverse=True)
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        png_data = await self.service.template.render('genshin/gacha', "gacha.html", data,
                                                      {"width": 1157, "height": 603}, False)

        reply_message = await message.reply_photo(png_data)
        if filters.ChatType.GROUPS.filter(message):
            self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 300)
            self._add_delete_message_job(context, message.chat_id, message.message_id, 300)
