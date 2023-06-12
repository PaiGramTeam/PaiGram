from datetime import datetime
from typing import Optional, TYPE_CHECKING

from simnet import GenshinClient
from simnet.errors import (
    InvalidCookies,
    BadRequest as SimnetBadRequest,
    TooManyRequests,
    DataNotPublic,
    AccountNotFound,
)
from simnet.utils.enum_ import Region, Game
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, TelegramObject
from telegram.ext import ConversationHandler, filters
from telegram.helpers import escape_markdown

from core.basemodel import RegionEnum
from core.plugin import Plugin, conversation, handler
from core.services.cookies.error import TooManyRequestPublicCookies
from core.services.cookies.models import CookiesStatusEnum
from core.services.cookies.services import CookiesService, PublicCookiesService
from core.services.players.models import PlayersDataBase as Player, PlayerInfoSQLModel
from core.services.players.services import PlayersService, PlayerInfoService
from utils.log import logger


if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

__all__ = ("BindAccountPlugin",)


class BindAccountPluginData(TelegramObject):
    player: Optional[Player] = None
    region: RegionEnum = RegionEnum.HYPERION
    player_id: Optional[int] = None
    nickname: Optional[str] = None

    def reset(self):
        self.player = None
        self.region = RegionEnum.NULL
        self.player_id = None
        self.nickname = None


CHECK_SERVER, CHECK_METHOD, CHECK_ACCOUNT_ID, CHECK_PLAYER_ID, COMMAND_RESULT = range(10100, 10105)


class BindAccountPlugin(Plugin.Conversation):
    """UID用户绑定"""

    def __init__(
        self,
        players_service: PlayersService = None,
        cookies_service: CookiesService = None,
        player_info_service: PlayerInfoService = None,
        public_cookies_service: PublicCookiesService = None,
    ):
        self.public_cookies_service = public_cookies_service
        self.cookies_service = cookies_service
        self.players_service = players_service
        self.player_info_service = player_info_service

    @conversation.entry_point
    @handler.command(command="setuid", filters=filters.ChatType.PRIVATE, block=False)
    async def command_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
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
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def check_server(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        bind_account_plugin_data: BindAccountPluginData = context.chat_data.get("bind_account_plugin_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if message.text == "米游社":
            bind_account_plugin_data.region = RegionEnum.HYPERION
        elif message.text == "HoYoLab":
            bind_account_plugin_data.region = RegionEnum.HOYOLAB
        else:
            await message.reply_text("选择错误，请重新选择")
            return CHECK_SERVER
        reply_keyboard = [["通过玩家ID", "通过账号ID"], ["退出"]]
        await message.reply_markdown_v2(
            "请选择你要绑定的方式", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
        return CHECK_METHOD

    @conversation.state(state=CHECK_METHOD)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def check_method(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if message.text == "通过玩家ID":
            await message.reply_text("请输入你的玩家ID（非通行证ID）", reply_markup=ReplyKeyboardRemove())
            return CHECK_PLAYER_ID
        if message.text == "通过账号ID":
            await message.reply_text("请输入你的通行证ID（非玩家ID）", reply_markup=ReplyKeyboardRemove())
            return CHECK_ACCOUNT_ID
        await message.reply_text("选择错误，请重新选择")
        return CHECK_METHOD

    @conversation.state(state=CHECK_ACCOUNT_ID)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def check_account(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
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
            client = GenshinClient(cookies=cookies.data, region=Region.CHINESE)
        elif region == RegionEnum.HOYOLAB:
            client = GenshinClient(cookies=cookies.data, region=Region.OVERSEAS, lang="zh-cn")
        else:
            return ConversationHandler.END
        try:
            record_card = await client.get_record_card(account_id)
            if record_card is None:
                await message.reply_text("请在设置展示主界面添加原神", reply_markup=ReplyKeyboardRemove())
                return ConversationHandler.END
        except DataNotPublic:
            await message.reply_text("角色未公开", reply_markup=ReplyKeyboardRemove())
            logger.warning("获取账号信息发生错误 %s 账户信息未公开", account_id)
            return ConversationHandler.END
        except SimnetBadRequest as exc:
            await message.reply_text("获取账号信息发生错误", reply_markup=ReplyKeyboardRemove())
            logger.error("获取账号信息发生错误")
            logger.exception(exc)
            return ConversationHandler.END
        player_info = await self.players_service.get(
            user.id, player_id=record_card.uid, region=bind_account_plugin_data.region
        )
        if player_info:
            await message.reply_text("你已经绑定该账号")
            return ConversationHandler.END
        bind_account_plugin_data.account_id = account_id
        reply_keyboard = [["确认", "退出"]]
        await message.reply_text("获取角色基础信息成功，请检查是否正确！")
        logger.info("用户 %s[%s] 获取账号 %s[%s] 信息成功", user.full_name, user.id, record_card.nickname, record_card.uid)
        text = (
            f"*角色信息*\n"
            f"角色名称：{escape_markdown(record_card.nickname, version=2)}\n"
            f"角色等级：{record_card.level}\n"
            f"UID：`{record_card.uid}`\n"
            f"服务器名称：`{record_card.server_name}`\n"
        )
        bind_account_plugin_data.player_id = record_card.uid
        bind_account_plugin_data.nickname = record_card.nickname
        await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return COMMAND_RESULT

    @conversation.state(state=CHECK_PLAYER_ID)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def check_player(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        user = update.effective_user
        message = update.effective_message
        bind_account_plugin_data: BindAccountPluginData = context.chat_data.get("bind_account_plugin_data")
        region = bind_account_plugin_data.region
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            player_id = int(message.text)
        except ValueError:
            await message.reply_text("ID 格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        try:
            cookies = await self.public_cookies_service.get_cookies(user.id, region)
        except TooManyRequestPublicCookies:
            await message.reply_text("用户查询次数过多，请稍后重试", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if region == RegionEnum.HYPERION:
            client = GenshinClient(cookies=cookies.data, region=Region.CHINESE)
        elif region == RegionEnum.HOYOLAB:
            client = GenshinClient(cookies=cookies.data, region=Region.OVERSEAS, lang="zh-cn")
        else:
            return ConversationHandler.END
        try:
            player_stats = await client.get_genshin_user(player_id)
        except AccountNotFound:
            await message.reply_text("找不到用户，uid可能无效", reply_markup=ReplyKeyboardRemove())
            logger.warning("获取账号信息发生错误 %s 找不到用户 uid可能无效", player_id)
            return ConversationHandler.END
        except DataNotPublic:
            await message.reply_text("角色未公开", reply_markup=ReplyKeyboardRemove())
            logger.warning("获取账号信息发生错误 %s 账户信息未公开", player_id)
            return ConversationHandler.END
        except InvalidCookies:
            await self.public_cookies_service.undo(user.id, cookies, CookiesStatusEnum.INVALID_COOKIES)
            await message.reply_text("出错了呜呜呜 ~ 请稍后重试")
            return ConversationHandler.END
        except SimnetBadRequest as exc:
            if exc.ret_code == 1034:
                await self.public_cookies_service.undo(user.id)
                await message.reply_text("出错了呜呜呜 ~ 请稍后重试")
                return ConversationHandler.END
            await message.reply_text("获取账号信息发生错误", reply_markup=ReplyKeyboardRemove())
            logger.error("获取账号信息发生错误")
            logger.exception(exc)
            return ConversationHandler.END
        except ValueError:
            await message.reply_text("ID 格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        finally:
            await client.shutdown()
        player_info = await self.players_service.get(
            user.id, player_id=player_id, region=bind_account_plugin_data.region
        )
        if player_info:
            await message.reply_text("你已经绑定该账号")
            return ConversationHandler.END
        reply_keyboard = [["确认", "退出"]]
        await message.reply_text("获取角色基础信息成功，请检查是否正确！")
        logger.info("用户 %s[%s] 获取账号 %s[%s] 信息成功", user.full_name, user.id, player_stats.info.nickname, player_id)
        text = (
            f"*角色信息*\n"
            f"角色名称：{escape_markdown(player_stats.info.nickname, version=2)}\n"
            f"角色等级：{player_stats.info.level}\n"
            f"UID：`{player_id}`\n"
        )
        bind_account_plugin_data.player_id = player_id
        bind_account_plugin_data.nickname = player_stats.info.nickname
        await message.reply_markdown_v2(text, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return COMMAND_RESULT

    @conversation.state(state=COMMAND_RESULT)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def command_result(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        user = update.effective_user
        message = update.effective_message
        bind_account_plugin_data: BindAccountPluginData = context.chat_data.get("bind_account_plugin_data")
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        if message.text == "确认":
            player_id = bind_account_plugin_data.player_id
            nickname = bind_account_plugin_data.nickname
            is_chosen = True
            player_info = await self.players_service.get_player(user.id)  # 寻找主账号
            if player_info is not None and player_info.is_chosen:
                is_chosen = False
            player = Player(
                user_id=user.id,
                player_id=player_id,
                region=bind_account_plugin_data.region,
                is_chosen=is_chosen,  # todo 多账号
            )
            await self.players_service.add(player)
            player_info = await self.player_info_service.get(player)
            if player_info is None:
                player_info = PlayerInfoSQLModel(
                    user_id=player.user_id,
                    player_id=player.player_id,
                    nickname=nickname,
                    create_time=datetime.now(),
                    is_update=True,
                )  # 不添加更新时间
                await self.player_info_service.add(player_info)
            logger.success("用户 %s[%s] 绑定UID账号成功", user.full_name, user.id)
            await message.reply_text("保存成功", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await message.reply_text("回复错误，请重新输入")
        return COMMAND_RESULT
