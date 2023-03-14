from typing import Tuple, Optional

from async_lru import alru_cache
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.ext import CallbackContext
from telegram.ext import filters
from telegram.helpers import create_deep_linked_url

from core.basemodel import RegionEnum
from core.config import config
from core.handler.callbackqueryhandler import CallbackQueryHandler
from core.plugin import Plugin, handler
from core.services.cookies import CookiesService
from modules.apihelper.client.components.recharge import RechargeClient
from modules.apihelper.models.genshin.recharge import GoodsList, Goods
from plugins.tools.genshin import GenshinHelper, PlayerNotFoundError, CookiesNotFoundError
from utils.log import logger

try:
    import ujson as jsonlib

except ImportError:
    import json as jsonlib

WARNING_TEXT = """该充值接口由米游社提供，此 Bot 不对充值结果负责。
付款后有无法成功到账的可能性。
请在充值前仔细阅读米哈游的充值条款。"""


class RechargePlugin(Plugin):
    """游戏相关"""

    def __init__(
        self,
        cookie_service: CookiesService = None,
        helper: GenshinHelper = None,
    ):
        self.cookie_service = cookie_service
        self.helper = helper
        self.recharge_client = RechargeClient()
        self.temp_photo: Optional[str] = None

    @alru_cache(ttl=60)
    async def get_goods_list(self) -> GoodsList:
        return await self.recharge_client.fetch_goods()

    async def get_goods(self, key: str) -> Goods:
        data: GoodsList = await self.get_goods_list()
        for goods in data.goods_list:
            if goods.goods_id == key:
                return goods
        raise ValueError("商品不存在")

    async def gen_button(self, user_id: int) -> InlineKeyboardMarkup:
        data: GoodsList = await self.get_goods_list()
        buttons = [
            InlineKeyboardButton(
                value.title,
                callback_data=f"recharge|{user_id}|{value.goods_id}",
            )
            for value in data.goods_list
        ]
        all_buttons = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
        return InlineKeyboardMarkup(all_buttons)

    @handler.command("recharge", block=False)
    @handler.message(filters.Regex(r"^原神账号注册时间$"), block=False)
    async def reg_time(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 原神充值命令请求", user.full_name, user.id)
        try:
            await self.helper.get_genshin_client(user.id, region=RegionEnum.HYPERION)
            player_info = await self.helper.players_service.get_player(user.id, region=RegionEnum.HYPERION)
            if not player_info.account_id:
                raise CookiesNotFoundError(user.id)
            if isinstance(self.temp_photo, str):
                photo = self.temp_photo
            else:
                photo = open("resources/img/kitsune.png", "rb")
            await message.reply_photo(
                photo, caption=f"请选择充值商品，{WARNING_TEXT}", reply_markup=await self.gen_button(user.id)
            )
        except (PlayerNotFoundError, CookiesNotFoundError):
            buttons = [[InlineKeyboardButton("点我绑定账号", url=create_deep_linked_url(context.bot.username, "set_cookie"))]]
            reply_msg = await message.reply_text(
                "此功能需要绑定国服<code>cookie</code>后使用，请先私聊派蒙绑定国服账号",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML,
            )
            if filters.ChatType.GROUPS.filter(message):
                self.add_delete_message_job(reply_msg, delay=30)
                self.add_delete_message_job(message, delay=30)

    @handler(CallbackQueryHandler, pattern=r"^recharge\|", block=False)
    async def get_player_cards(self, update: Update, _: CallbackContext) -> None:
        callback_query = update.callback_query
        user = callback_query.from_user
        message = callback_query.message

        async def get_recharge_callback(callback_query_data: str) -> Tuple[int, str]:
            _data = callback_query_data.split("|")
            _user_id = int(_data[1])
            _goods_id = _data[2]
            logger.debug("callback_query_data函数返回 user_id[%s] goods_id[%s]", _user_id, _goods_id)
            return _user_id, _goods_id

        user_id, goods_id = await get_recharge_callback(callback_query.data)
        if user.id != user_id:
            await callback_query.answer(text="这不是你的按钮！\n" + config.notice.user_mismatch, show_alert=True)
            return
        try:
            client = await self.helper.get_genshin_client(user.id, region=RegionEnum.HYPERION)
            player_info = await self.helper.players_service.get_player(user.id, region=RegionEnum.HYPERION)
            goods = await self.get_goods(goods_id)
            order = await self.recharge_client.create_order(client, player_info.account_id, goods)
            data = self.recharge_client.generate_qrcode(order)
            media = InputMediaPhoto(data, caption=f"请在五分钟内完成\n订单号：{order.order_no}", parse_mode=ParseMode.HTML)
            photo = await message.edit_media(media, reply_markup=None)
            result = await self.recharge_client.check_order(client, order)
            if result:
                await photo.reply_text("充值成功", reply_to_message_id=photo.message_id)
            else:
                await photo.reply_text("二维码已过期", reply_to_message_id=photo.message_id)
        except ValueError:
            await callback_query.answer(text="商品不存在", show_alert=True)
        except (PlayerNotFoundError, CookiesNotFoundError):
            await callback_query.answer(text="绑定信息已过期", show_alert=True)
