from typing import Optional

import genshin
from genshin import DataNotPublic, GenshinException, types
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, TelegramObject, Update
from telegram.ext import CallbackContext, ConversationHandler, filters
from telegram.helpers import escape_markdown

from core.plugin import Plugin, conversation, handler
from core.services.cookies.error import TooManyRequestPublicCookies
from core.services.cookies.services import CookiesService, PublicCookiesService
from core.services.players.services import PlayersService
from core.services.players.models import PlayersDataBase as Player, RegionEnum
from utils.decorators.error import error_callable
from utils.decorators.restricts import restricts
from utils.log import logger

__all__ = ("BindAccountPlugin",)


class BindAccountPluginData(TelegramObject):
    player: Optional[Player] = None
    region: RegionEnum = RegionEnum.HYPERION
    account_id: int = 0
    player_id: int = 0

    def reset(self):
        self.player = None
        self.region = RegionEnum.NULL
        self.player_id = 0
        self.account_id = 0


CHECK_SERVER, CHECK_UID, COMMAND_RESULT = range(10100, 10103)


class BindAccountPlugin(Plugin.Conversation):
    """UID用户绑定"""

    def __init__(
        self,
        players_service: PlayersService = None,
        cookies_service: CookiesService = None,
        public_cookies_service: PublicCookiesService = None,
    ):
        self.public_cookies_service = public_cookies_service
        self.cookies_service = cookies_service
        self.players_service = players_service

    @conversation.entry_point
    @handler.command(command="setuid", filters=filters.ChatType.PRIVATE, block=True)
    @restricts()
    @error_callable
    async def command_start(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 绑定账号命令请求", user.full_name, user.id)
        bind_account_plugin_data: BindAccountPluginData = context.chat_data.get("bind_account_plugin_data")
        if bind_account_plugin_data is None:
            bind_account_plugin_data = BindAccountPluginData()
            context.chat_data["bind_account_plugin_data"] = bind_account_plugin_data
        else:
            bind_account_plugin_data.reset()
        text = (
            f"你好 {user.mention_markdown_v2()} "
            f'{escape_markdown("！请输入通行证ID（非游戏玩家ID），BOT将会通过通行证UID查找游戏UID。请选择要绑定的服务器！或回复退出取消操作")}'
        )
        reply_keyboard = [["米游社", "HoYoLab"], ["退出"]]
        await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return CHECK_SERVER

    @conversation.state(state=CHECK_SERVER)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def check_server(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        bind_account_plugin_data: BindAccountPluginData = context.chat_data.get("bind_account_plugin_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif message.text == "米游社":
            bind_account_plugin_data.region = RegionEnum.HYPERION
        elif message.text == "HoYoLab":
            bind_account_plugin_data.region = RegionEnum.HOYOLAB
        else:
            await message.reply_text("选择错误，请重新选择")
            return CHECK_SERVER
        await message.reply_text("请输入你的通行证ID（非玩家ID）", reply_markup=ReplyKeyboardRemove())
        return CHECK_UID

    @conversation.state(state=CHECK_UID)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def check_cookies(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        bind_account_plugin_data: BindAccountPluginData = context.chat_data.get("bind_account_plugin_data")
        region = bind_account_plugin_data.region
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            account_id = int(message.text)
        except ValueError:
            await message.reply_text("ID 格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            cookies = await self.public_cookies_service.get_cookies(user.id, region)
        except TooManyRequestPublicCookies:
            await message.reply_text("用户查询次数过多，请稍后重试", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if region == RegionEnum.HYPERION:
            client = genshin.Client(cookies=cookies.cookies, game=types.Game.GENSHIN, region=types.Region.CHINESE)
        elif region == RegionEnum.HOYOLAB:
            client = genshin.Client(
                cookies=cookies.cookies, game=types.Game.GENSHIN, region=types.Region.OVERSEAS, lang="zh-cn"
            )
        else:
            return ConversationHandler.END
        try:
            user_info = await client.get_record_card(account_id)
        except DataNotPublic:
            await message.reply_text("角色未公开", reply_markup=ReplyKeyboardRemove())
            logger.warning("获取账号信息发生错误 %s 账户信息未公开", account_id)
            return ConversationHandler.END
        except GenshinException as exc:
            await message.reply_text("获取账号信息发生错误", reply_markup=ReplyKeyboardRemove())
            logger.error("获取账号信息发生错误")
            logger.exception(exc)
            return ConversationHandler.END
        if user_info.game != types.Game.GENSHIN:
            await message.reply_text("角色信息查询返回非原神游戏信息，" "请设置展示主界面为原神", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        player_info = await self.players_service.get(user.id, user_info.uid, bind_account_plugin_data.region)
        if player_info:
            await message.reply_text("你已经绑定该账号")
            return ConversationHandler.END
        bind_account_plugin_data.player = player_info
        reply_keyboard = [["确认", "退出"]]
        await message.reply_text("获取角色基础信息成功，请检查是否正确！")
        logger.info("用户 %s[%s] 获取账号 %s[%s] 信息成功", user.full_name, user.id, user_info.nickname, user_info.uid)
        text = (
            f"*角色信息*\n"
            f"角色名称：{escape_markdown(user_info.nickname, version=2)}\n"
            f"角色等级：{user_info.level}\n"
            f"UID：`{user_info.uid}`\n"
            f"服务器名称：`{user_info.server_name}`\n"
        )
        bind_account_plugin_data.player_id = user_info.uid
        await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return COMMAND_RESULT

    @conversation.state(state=COMMAND_RESULT)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=True)
    @error_callable
    async def command_result(self, update: Update, context: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        bind_account_plugin_data: BindAccountPluginData = context.chat_data.get("bind_account_plugin_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        elif message.text == "确认":
            if bind_account_plugin_data.player:
                is_chosen = True
                player_info = await self.players_service.get_player(user.id)  # 寻找主账号
                if player_info.is_chosen:
                    is_chosen = False
                player = Player(
                    user_id=user.id,
                    account_id=bind_account_plugin_data.account_id,
                    player_id=bind_account_plugin_data.player_id,
                    region=bind_account_plugin_data.region,
                    is_chosen=is_chosen,  # todo 多账号
                )
                await self.players_service.add(player)
                logger.success("用户 %s[%s] 绑定UID账号成功", user.full_name, user.id)
            else:
                await message.reply_text("数据错误")
                return ConversationHandler.END
            await message.reply_text("保存成功", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        else:
            await message.reply_text("回复错误，请重新输入")
            return COMMAND_RESULT
