import os

from pyppeteer import launch
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import filters, CommandHandler, MessageHandler, CallbackContext

from app.template import TemplateService
from logger import Log
from model.apihelper.gacha import GachaInfo
from plugins.base import BasePlugins
from plugins.gacha.wish import WishCountInfo, get_one
from utils.app.inject import inject
from utils.bot import get_all_args
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.plugins.manager import listener_plugins_class


@listener_plugins_class()
class Gacha(BasePlugins):
    """抽卡模拟器（非首模拟器/减寿模拟器）"""

    CHECK_SERVER, COMMAND_RESULT = range(10600, 10602)

    @classmethod
    def create_handlers(cls) -> list:
        gacha = cls()
        return [
            CommandHandler("gacha", gacha.command_start, block=False),
            MessageHandler(filters.Regex("^抽卡模拟器(.*)"), gacha.command_start, block=False),
            MessageHandler(filters.Regex("^非首模拟器(.*)"), gacha.command_start, block=False),
        ]

    @inject
    def __init__(self, template_service: TemplateService = None):
        self.gacha = GachaInfo()
        self.template_service = template_service
        self.browser: launch = None
        self.current_dir = os.getcwd()
        self.resources_dir = os.path.join(self.current_dir, "resources")
        self.character_gacha_card = {}
        self.user_time = {}

    async def gacha_info(self, gacha_name: str = "角色活动", default: bool = False):
        gacha_list_info = await self.gacha.get_gacha_list_info()
        gacha_id = ""
        for gacha in gacha_list_info.data["list"]:
            if gacha["gacha_name"] == gacha_name:
                gacha_id = gacha["gacha_id"]
        if gacha_id == "":
            if default and len(gacha_list_info.data["list"]) > 0:
                gacha_id = gacha_list_info.data["list"][0]["gacha_id"]
            else:
                return {}
        gacha_info = await self.gacha.get_gacha_info(gacha_id)
        gacha_info["gacha_id"] = gacha_id
        return gacha_info

    @restricts(filters.ChatType.GROUPS, restricts_time=20, try_delete_message=True)
    @restricts(filters.ChatType.PRIVATE)
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.message
        user = update.effective_user
        args = get_all_args(context)
        gacha_name = "角色活动"
        if len(args) >= 1:
            gacha_name = args[0]
            if gacha_name not in ("角色活动-2", "武器活动", "常驻", "角色活动"):
                for key, value in {"2": "角色活动-2", "武器": "武器活动", "普通": "常驻"}.items():
                    if key == gacha_name:
                        gacha_name = value
                        break
            gacha_info = await self.gacha_info(gacha_name)
            if gacha_info.get("gacha_id") is None:
                await message.reply_text(f"没有找到名为 {gacha_name} 的卡池")
                return
        else:
            gacha_info = await self.gacha_info(default=True)
        Log.info(f"用户 {user.full_name}[{user.id}] 抽卡模拟器命令请求 || 参数 {gacha_name}")
        # 用户数据储存和处理
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
        for _ in range(10):
            item = get_one(user_gacha_count, gacha_info)
            # 下面为忽略的代码，因为metadata未完善，具体武器和角色类型无法显示
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
        # 因为 gacha_info["title"] 返回的是 HTML 标签 尝试关闭自动转义
        png_data = await self.template_service.render('genshin/gacha', "gacha.html", data,
                                                      {"width": 1157, "height": 603}, False, False)

        reply_message = await message.reply_photo(png_data)
        if filters.ChatType.GROUPS.filter(message):
            self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 300)
            self._add_delete_message_job(context, message.chat_id, message.message_id, 300)
