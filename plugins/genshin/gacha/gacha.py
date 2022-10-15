import asyncio
import os
import re
from datetime import datetime
from typing import Optional, Union, Any, List

import ujson as json
from bs4 import BeautifulSoup
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from core.base.redisdb import RedisDB
from core.baseplugin import BasePlugin
from core.plugin import Plugin, handler
from core.template import TemplateService
from metadata.genshin import weapon_to_game_id, avatar_to_game_id, WEAPON_DATA, AVATAR_DATA
from metadata.shortname import weaponToName
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


class GachaRedis:
    def __init__(self, redis: RedisDB):
        self.client = redis.client
        self.qname = "plugin:gacha:"

    async def get(self, user_id: int) -> PlayerGachaInfo:
        data = await self.client.get(f"{self.qname}{user_id}")
        if data is None:
            return PlayerGachaInfo()
        return PlayerGachaInfo(**json.loads(data))

    async def set(self, user_id: int, player_gacha_info: PlayerGachaInfo):
        value = player_gacha_info.json()
        await self.client.set(f"{self.qname}{user_id}", value)


class GachaHandle:
    def __init__(self, hyperion: Optional[GachaInfo] = None):
        if hyperion is None:
            self.hyperion = GachaInfo()
        else:
            self.hyperion = hyperion

    async def de_banner(self, gacha_id: str, gacha_type: int) -> Optional[GachaBanner]:
        gacha_info = await self.hyperion.get_gacha_info(gacha_id)
        banner = GachaBanner()
        banner.banner_id = gacha_id
        banner.title, banner.html_title = self.de_title(gacha_info["title"])
        r5_up_items = gacha_info.get("r5_up_items")
        if r5_up_items is not None:
            for r5_up_item in r5_up_items:
                if r5_up_item["item_type"] == "角色":
                    banner.rate_up_items5.append(avatar_to_game_id(r5_up_item["item_name"]))
                elif r5_up_item["item_type"] == "武器":
                    banner.rate_up_items5.append(weapon_to_game_id(r5_up_item["item_name"]))
        r5_prob_list = gacha_info.get("r5_prob_list")
        if r5_prob_list is not None:
            for r5_prob in gacha_info.get("r5_prob_list", []):
                if r5_prob["item_type"] == "角色":
                    banner.fallback_items5_pool1.append(avatar_to_game_id(r5_prob["item_name"]))
                elif r5_prob["item_type"] == "武器":
                    banner.fallback_items5_pool1.append(weapon_to_game_id(r5_prob["item_name"]))
        r4_up_items = gacha_info.get("r4_up_items")
        if r4_up_items is not None:
            for r4_up_item in r4_up_items:
                if r4_up_item["item_type"] == "角色":
                    banner.rate_up_items4.append(avatar_to_game_id(r4_up_item["item_name"]))
                elif r4_up_item["item_type"] == "武器":
                    banner.rate_up_items4.append(weapon_to_game_id(r4_up_item["item_name"]))
        r4_prob_list = gacha_info.get("r4_prob_list")
        if r4_prob_list is not None:
            for r4_prob in r4_prob_list:
                if r4_prob["item_type"] == "角色":
                    banner.fallback_items4_pool1.append(avatar_to_game_id(r4_prob["item_name"]))
                elif r4_prob["item_type"] == "武器":
                    banner.fallback_items4_pool1.append(weapon_to_game_id(r4_prob["item_name"]))
        if gacha_type in (301, 400):
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

    def __init__(self, template_service: TemplateService = None, redis: RedisDB = None):
        self.gacha_db = GachaRedis(redis)
        self.handle = GachaHandle()
        self.banner_system = BannerSystem()
        self.template_service = template_service
        self.current_dir = os.getcwd()
        self.resources_dir = os.path.join(self.current_dir, "resources")
        self.banner_cache = {}
        self._look = asyncio.Lock()

    async def get_banner(self, gacha_base_info: GachaInfoObject):
        async with self._look:
            banner = self.banner_cache.get(gacha_base_info.gacha_id)
            if banner is None:
                banner = await self.handle.de_banner(gacha_base_info.gacha_id, gacha_base_info.gacha_type)
                self.banner_cache.setdefault(gacha_base_info.gacha_id, banner)
            return banner

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
        banner = await self.get_banner(gacha_base_info)
        player_gacha_info = await self.gacha_db.get(user.id)
        # 检查 wish_item_id
        if banner.banner_type == BannerType.WEAPON:
            if player_gacha_info.event_weapon_banner.wish_item_id not in banner.rate_up_items5:
                player_gacha_info.event_weapon_banner.wish_item_id = 0
        # 执行抽卡
        item_list = self.banner_system.do_pulls(player_gacha_info, banner, 10)
        data = await self.handle.de_item_list(item_list)
        player_gacha_banner_info = player_gacha_info.get_banner_info(banner)
        template_data = {
            "_res_path": f"file://{self.resources_dir}",
            "name": f"{user.full_name}",
            "info": gacha_name,
            "banner_name": banner.html_title,
            "banner_type": banner.banner_type.name,
            "player_gacha_banner_info": player_gacha_banner_info,
            "items": [],
            "wish_name": "",
        }
        logger.debug(f"{banner.banner_id}")
        logger.debug(f"{banner.banner_type}")
        logger.debug(f"{banner.rate_up_items5}")
        logger.debug(f"{banner.fallback_items5_pool1}")
        if player_gacha_banner_info.wish_item_id != 0:
            weapon = WEAPON_DATA.get(str(player_gacha_banner_info.wish_item_id))
            if weapon is not None:
                template_data["wish_name"] = weapon["name"]
        await self.gacha_db.set(user.id, player_gacha_info)

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

    @handler(CommandHandler, command="set_wish", block=False)
    @handler(MessageHandler, filters=filters.Regex("^非首模拟器定轨(.*)"), block=False)
    @restricts(restricts_time=3, restricts_time_of_groups=20)
    @error_callable
    async def set_wish(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        args = get_all_args(context)
        gacha_base_info = await self.handle.gacha_base_info("武器活动")
        banner = await self.get_banner(gacha_base_info)
        if len(args) >= 1:
            weapon_name = args[0]
        else:
            reply_message = await message.reply_text("参数错误")
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id, 10)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 10)
            return
        weapon_name = weaponToName(weapon_name)
        player_gacha_info = await self.gacha_db.get(user.id)
        for rate_up_items5 in banner.rate_up_items5:
            weapon = WEAPON_DATA.get(str(rate_up_items5))
            if weapon is None:
                continue
            if weapon["name"] == weapon_name:
                player_gacha_info.event_weapon_banner.wish_item_id = rate_up_items5
                player_gacha_info.event_weapon_banner.failed_chosen_item_pulls = 0
                break
        else:
            reply_message = await message.reply_text(f"没有找到 {weapon_name} 武器或该武器不存在UP卡池中")
            if filters.ChatType.GROUPS.filter(reply_message):
                self._add_delete_message_job(context, message.chat_id, message.message_id, 10)
                self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 10)
            return
        await self.gacha_db.set(user.id, player_gacha_info)
        reply_message = await message.reply_text(f"抽卡模拟器定轨 {weapon_name} 武器成功")
        if filters.ChatType.GROUPS.filter(reply_message):
            self._add_delete_message_job(context, message.chat_id, message.message_id, 10)
            self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id, 10)
        return
