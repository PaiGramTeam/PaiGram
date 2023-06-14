import asyncio
import re
from datetime import datetime
from typing import Any, List, Optional, Tuple, Union

from bs4 import BeautifulSoup
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters

from core.dependence.assets import AssetsService
from core.dependence.redisdb import RedisDB
from core.plugin import Plugin, handler
from core.services.template.services import TemplateService
from metadata.genshin import AVATAR_DATA, WEAPON_DATA, avatar_to_game_id, weapon_to_game_id
from metadata.shortname import weaponToName
from modules.apihelper.client.components.gacha import Gacha as GachaClient
from modules.apihelper.models.genshin.gacha import GachaInfo
from modules.gacha.banner import GenshinBannerType, GachaBanner
from modules.gacha.player.info import PlayerGachaInfo
from modules.gacha.system import BannerSystem
from utils.log import logger

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib


class GachaNotFound(Exception):
    """卡池未找到"""

    def __init__(self, gacha_name: str):
        self.gacha_name = gacha_name
        super().__init__(f"{gacha_name} gacha not found")


class GachaDataFound(Exception):
    """卡池数据未找到"""

    def __init__(self, item_id: int):
        self.item_id = item_id
        super().__init__(f"item_id[{item_id}] data not found")


class GachaRedis:
    def __init__(self, redis: RedisDB):
        self.client = redis.client
        self.qname = "plugin:gacha:"

    async def get(self, user_id: int) -> PlayerGachaInfo:
        data = await self.client.get(f"{self.qname}{user_id}")
        if data is None:
            return PlayerGachaInfo()
        return PlayerGachaInfo(**jsonlib.loads(data))

    async def set(self, user_id: int, player_gacha_info: PlayerGachaInfo):
        value = player_gacha_info.json()
        await self.client.set(f"{self.qname}{user_id}", value)


class WishSimulatorHandle:
    def __init__(self):
        self.hyperion = GachaClient()

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
        if gacha_type in {301, 400}:
            banner.wish_max_progress = 1
            banner.banner_type = GenshinBannerType.EVENT
            banner.weight4 = ((1, 510), (8, 510), (10, 10000))
            banner.weight5 = ((1, 60), (73, 60), (90, 10000))
        elif gacha_type == 302:
            banner.wish_max_progress = 2
            banner.banner_type = GenshinBannerType.WEAPON
            banner.weight4 = ((1, 600), (7, 600), (10, 10000))
            banner.weight5 = ((1, 70), (62, 70), (90, 10000))
        else:
            banner.banner_type = GenshinBannerType.STANDARD
        return banner

    async def gacha_base_info(self, gacha_name: str = "角色活动", default: bool = False) -> GachaInfo:
        gacha_list_info = await self.hyperion.get_gacha_list_info()
        now = datetime.now()
        for gacha in gacha_list_info:
            if gacha.gacha_name == gacha_name and gacha.begin_time <= now <= gacha.end_time:
                return gacha
        else:  # pylint: disable=W0120
            if default and len(gacha_list_info) > 0:
                return gacha_list_info[0]
            raise GachaNotFound(gacha_name)

    @staticmethod
    def de_title(title: str) -> Union[Tuple[str, None], Tuple[str, Any]]:
        title_html = BeautifulSoup(title, "lxml")
        re_color = re.search(r"<color=#(.*?)>", title, flags=0)
        if re_color is None:
            return title_html.text, None
        color = re_color[1]
        title_html.color.name = "span"
        title_html.span["style"] = f"color:#{color};"
        return title_html.text, title_html.p


class WishSimulatorPlugin(Plugin):
    """抽卡模拟器（非首模拟器/减寿模拟器）"""

    def __init__(self, assets: AssetsService, template_service: TemplateService, redis: RedisDB):
        self.gacha_db = GachaRedis(redis)
        self.handle = WishSimulatorHandle()
        self.banner_system = BannerSystem()
        self.template_service = template_service
        self.banner_cache = {}
        self._look = asyncio.Lock()
        self.assets_service = assets

    async def get_banner(self, gacha_base_info: GachaInfo):
        async with self._look:
            banner = self.banner_cache.get(gacha_base_info.gacha_id)
            if banner is None:
                banner = await self.handle.de_banner(gacha_base_info.gacha_id, gacha_base_info.gacha_type)
                self.banner_cache.setdefault(gacha_base_info.gacha_id, banner)
            return banner

    async def de_item_list(self, item_list: List[int]) -> List[dict]:
        gacha_item: List[dict] = []
        for item_id in item_list:
            if item_id is None:
                continue
            if 10000 <= item_id <= 100000:
                data = WEAPON_DATA.get(str(item_id))
                avatar = self.assets_service.weapon(item_id)
                gacha = await avatar.gacha()
                if gacha is None:
                    raise GachaDataFound(item_id)
                data.setdefault("url", gacha.as_uri())
                gacha_item.append(data)
            elif 10000000 <= item_id <= 19999999:
                data = AVATAR_DATA.get(str(item_id))
                avatar = self.assets_service.avatar(item_id)
                gacha = await avatar.gacha_card()
                if gacha is None:
                    raise GachaDataFound(item_id)
                data.setdefault("url", gacha.as_uri())
                gacha_item.append(data)
        return gacha_item

    async def shutdown(self) -> None:
        pass
        # todo 目前清理消息无法执行 因为先停止Job导致无法获取全部信息
        # logger.info("正在清理消息")
        # job_queue = self.application.telegram.job_queue
        # jobs = job_queue.jobs()
        # for job in jobs:
        #    if "wish_simulator" in job.name and not job.removed:
        #        logger.info("当前Job name %s", job.name)
        #        try:
        #            await job.run(job_queue.application)
        #        except CancelledError:
        #            continue
        #        except Exception as exc:
        #            logger.warning("执行失败 %", str(exc))
        # else:
        #    logger.info("Jobs为空")
        # logger.success("清理卡池消息成功")

    @handler(CommandHandler, command="wish", block=False)
    @handler(MessageHandler, filters=filters.Regex("^抽卡模拟器(.*)"), block=False)
    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        args = self.get_args(context)
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
                await message.reply_text(f"没有找到名为 {exc.gacha_name} 的卡池，可能是卡池不存在或者卡池已经结束，请检查后重试。如果你想抽取默认卡池，请不要输入参数。")
                return
        else:
            try:
                gacha_base_info = await self.handle.gacha_base_info(default=True)
            except GachaNotFound:
                await message.reply_text("当前卡池正在替换中，请稍后重试。")
                return
        logger.info("用户 %s[%s] 抽卡模拟器命令请求 || 参数 %s", user.full_name, user.id, gacha_name)
        # 用户数据储存和处理
        await message.reply_chat_action(ChatAction.TYPING)
        banner = await self.get_banner(gacha_base_info)
        player_gacha_info = await self.gacha_db.get(user.id)
        # 检查 wish_item_id
        if (
            banner.banner_type == GenshinBannerType.WEAPON
            and player_gacha_info.event_weapon_banner.wish_item_id not in banner.rate_up_items5
        ):
            player_gacha_info.event_weapon_banner.wish_item_id = 0
        # 执行抽卡
        item_list = self.banner_system.do_pulls(player_gacha_info, banner, 10)
        try:
            data = await self.de_item_list(item_list)
        except GachaDataFound as exc:
            logger.warning("角色 item_id[%s] 抽卡立绘未找到", exc.item_id)
            reply_message = await message.reply_text("出错了呜呜呜 ~ 卡池部分数据未找到！")
            if filters.ChatType.GROUPS.filter(message):
                self.add_delete_message_job(reply_message, name="wish_simulator")
                self.add_delete_message_job(message, name="wish_simulator")
            return
        player_gacha_banner_info = player_gacha_info.get_banner_info(banner)
        template_data = {
            "name": f"{user.full_name}",
            "info": gacha_name,
            "banner_name": banner.html_title if banner.html_title else banner.title,
            "banner_type": banner.banner_type.name,
            "player_gacha_banner_info": player_gacha_banner_info,
            "items": [],
            "wish_name": "",
        }
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
            "genshin/wish/wish.jinja2", template_data, {"width": 1157, "height": 603}, False
        )

        reply_message = await message.reply_photo(png_data.photo)
        if filters.ChatType.GROUPS.filter(message):
            self.add_delete_message_job(reply_message, name="wish_simulator")
            self.add_delete_message_job(message, name="wish_simulator")

    @handler(CommandHandler, command="set_wish", block=False)
    @handler(MessageHandler, filters=filters.Regex("^非首模拟器定轨(.*)"), block=False)
    async def set_wish(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        args = self.get_args(context)
        try:
            gacha_base_info = await self.handle.gacha_base_info("武器活动")
        except GachaNotFound:
            reply_message = await message.reply_text("当前还没有武器正在 UP，可能是卡池不存在或者卡池已经结束。")
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message, delay=30)
                self.add_delete_message_job(reply_message, delay=30)
            return
        banner = await self.get_banner(gacha_base_info)
        up_weapons = {}
        for rate_up_items5 in banner.rate_up_items5:
            weapon = WEAPON_DATA.get(str(rate_up_items5))
            if weapon is None:
                continue
            up_weapons[weapon["name"]] = rate_up_items5
        up_weapons_text = "当前 UP 武器有：" + "、".join(up_weapons.keys())
        if len(args) >= 1:
            weapon_name = args[0]
        else:
            reply_message = await message.reply_text(f"输入的参数不正确，请输入需要定轨的武器名称。\n{up_weapons_text}")
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message, delay=30)
                self.add_delete_message_job(reply_message, delay=30)
            return
        weapon_name = weaponToName(weapon_name)
        player_gacha_info = await self.gacha_db.get(user.id)
        if weapon_name in up_weapons:
            player_gacha_info.event_weapon_banner.wish_item_id = up_weapons[weapon_name]
            player_gacha_info.event_weapon_banner.failed_chosen_item_pulls = 0
        else:
            reply_message = await message.reply_text(
                f"输入的参数不正确，可能是没有名为 {weapon_name} 的武器或该武器不存在当前 UP 卡池中\n{up_weapons_text}"
            )
            if filters.ChatType.GROUPS.filter(reply_message):
                self.add_delete_message_job(message, delay=30)
                self.add_delete_message_job(reply_message, delay=30)
            return
        await self.gacha_db.set(user.id, player_gacha_info)
        reply_message = await message.reply_text(f"抽卡模拟器定轨 {weapon_name} 武器成功")
        if filters.ChatType.GROUPS.filter(reply_message):
            self.add_delete_message_job(message, delay=30)
            self.add_delete_message_job(reply_message, delay=30)
