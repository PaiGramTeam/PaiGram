import asyncio
import os
import re
from datetime import datetime
from typing import Optional, Union, Any, List

from bs4 import BeautifulSoup
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from core.baseplugin import BasePlugin
from core.plugin import Plugin, handler
from core.template import TemplateService
from metadata.genshin import weapon_to_game_id, avatar_to_game_id, WEAPON_DATA, AVATAR_DATA
from modules.apihelper.hyperion import GachaInfo, GachaInfoObject
from modules.gacha.banner import BannerType, GachaBanner
from modules.gacha.player.info import PlayerGachaInfo
from modules.gacha.system import BannerSystem
from utils.bot import get_all_args
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger


class GachaNotFound(Exception):
    """卡池未找到"""

    def __init__(self, gacha_name: str):
        self.gacha_name = gacha_name
        super().__init__(f"{gacha_name} gacha not found")


class GachaHandle:
    def __init__(self, hyperion: Optional[GachaInfo] = None):
        if hyperion is None:
            self.hyperion = GachaInfo()
        else:
            self.hyperion = hyperion

    async def de_banner(self, gacha_id: str, gacha_type: int) -> Optional[GachaBanner]:
        gacha_info = await self.hyperion.get_gacha_info(gacha_id)
        banner = GachaBanner()
        banner.title, banner.html_title = self.de_title(gacha_info["title"])
        for r5_up_items in gacha_info["r5_up_items"]:
            if r5_up_items["item_type"] == "角色":
                banner.rate_up_items5.append(avatar_to_game_id(r5_up_items["item_name"]))
            elif r5_up_items["item_type"] == "武器":
                banner.rate_up_items5.append(weapon_to_game_id(r5_up_items["item_name"]))
        for r5_prob_list in gacha_info["r5_prob_list"]:
            if r5_prob_list["item_type"] == "角色":
                banner.fallback_items5_pool1.append(avatar_to_game_id(r5_prob_list["item_name"]))
            elif r5_prob_list["item_type"] == "武器":
                banner.fallback_items5_pool1.append(weapon_to_game_id(r5_prob_list["item_name"]))
        for r4_up_items in gacha_info["r4_up_items"]:
            if r4_up_items["item_type"] == "角色":
                banner.rate_up_items4.append(avatar_to_game_id(r4_up_items["item_name"]))
            elif r4_up_items["item_type"] == "武器":
                banner.rate_up_items4.append(weapon_to_game_id(r4_up_items["item_name"]))
        for r4_prob_list in gacha_info["r4_prob_list"]:
            if r4_prob_list["item_type"] == "角色":
                banner.fallback_items4_pool1.append(avatar_to_game_id(r4_prob_list["item_name"]))
            elif r4_prob_list["item_type"] == "武器":
                banner.fallback_items4_pool1.append(weapon_to_game_id(r4_prob_list["item_name"]))
        if gacha_type in (310, 400):
            banner.wish_max_progress = 1
            banner.banner_type = BannerType.EVENT
            banner.weight4 = ((1, 510), (8, 510), (10, 10000))
            banner.weight5 = ((1, 60), (73, 60), (90, 10000))
        elif gacha_type == 302:
            banner.wish_max_progress = 3
            banner.banner_type = BannerType.WEAPON
            banner.weight4 = ((1, 600), (7, 600), (10, 10000))
            banner.weight5 = ((1, 70), (62, 70), (90, 10000))
        else:
            banner.banner_type = BannerType.STANDARD
        return banner

    async def gacha_base_info(self, gacha_name: str = "角色活动", default: bool = False) -> GachaInfoObject:
        gacha_list_info = await self.hyperion.get_gacha_list_info()
        now = datetime.now()
        for gacha in gacha_list_info:
            if gacha.gacha_name == gacha_name and gacha.begin_time <= now <= gacha.end_time:
                return gacha
        else:  # pylint: disable=W0120
            if default and len(gacha_list_info) > 0:
                return gacha_list_info[0]
            else:
                raise GachaNotFound(gacha_name)

    @staticmethod
    async def de_item_list(item_list: List[int]) -> List[dict]:
        gacha_item: List[dict] = []
        for item_id in item_list:
            if 10000 <= item_id <= 100000:
                gacha_item.append(WEAPON_DATA.get(str(item_id)))
            if 10000000 <= item_id <= 19999999:
                gacha_item.append(AVATAR_DATA.get(str(item_id)))
        return gacha_item

    @staticmethod
    def de_title(title: str) -> Union[tuple[str, None], tuple[str, Any]]:
        title_html = BeautifulSoup(title, "lxml")
        re_color = re.search(r"<color=#(.*?)>", title, flags=0)
        if re_color is None:
            return title_html.text, None
        color = re_color.group(1)
        title_html.color.name = "span"
        title_html.span["style"] = f"color:#{color};"
        return title_html.text, title_html.p


class Gacha(Plugin, BasePlugin):
    """抽卡模拟器（非首模拟器/减寿模拟器）"""

    def __init__(self, template_service: TemplateService = None):
        self.handle = GachaHandle()
        self.banner_system = BannerSystem()
        self.template_service = template_service
        self.current_dir = os.getcwd()
        self.resources_dir = os.path.join(self.current_dir, "resources")
        self.banner_cache = {}
        self._look = asyncio.Lock()

    @handler(CommandHandler, command="gacha", block=False)
    @handler(MessageHandler, filters=filters.Regex("^非首模拟器(.*)"), block=False)
    @restricts(restricts_time=3, restricts_time_of_groups=20)
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
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
            try:
                gacha_base_info = await self.handle.gacha_base_info(gacha_name)
            except GachaNotFound as exc:
                await message.reply_text(f"没有找到名为 {exc.gacha_name} 的卡池")
                return
        else:
            gacha_base_info = await self.handle.gacha_base_info(default=True)
        logger.info(f"用户 {user.full_name}[{user.id}] 抽卡模拟器命令请求 || 参数 {gacha_name}")
        # 用户数据储存和处理
        await message.reply_chat_action(ChatAction.TYPING)
        await self.handle.hyperion.get_gacha_info(gacha_base_info.gacha_id)
        async with self._look:
            banner = self.banner_cache.get(gacha_base_info.gacha_id)
            if banner is None:
                banner = await self.handle.de_banner(gacha_base_info.gacha_id, gacha_base_info.gacha_type)
                self.banner_cache.setdefault(gacha_base_info.gacha_id, banner)
        player_gacha_info = context.user_data.get("player_gacha_info")
        if player_gacha_info is None:
            player_gacha_info = PlayerGachaInfo()
            context.user_data.setdefault("player_gacha_info", player_gacha_info)
        # 执行抽卡
        item_list = self.banner_system.do_pulls(player_gacha_info, banner, 10)
        data = await self.handle.de_item_list(item_list)
        template_data = {
            "_res_path": f"file://{self.resources_dir}",
            "name": f"{user.full_name}",
            "info": gacha_name,
            "banner_name": banner.html_title,
            "player_gacha_info": player_gacha_info.get_banner_info(banner),
            "items": [],
        }

        def take_rang(elem: dict):
            return elem["rank"]

        data.sort(key=take_rang, reverse=True)
        template_data["items"] = data
        await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
        png_data = await self.template_service.render(
            "genshin/gacha/gacha.html", template_data, {"width": 1157, "height": 603}, False
        )

        reply_message = await message.reply_photo(png_data)
        if filters.ChatType.GROUPS.filter(message):
            self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 300)
            self._add_delete_message_job(context, message.chat_id, message.message_id, 300)
