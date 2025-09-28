from datetime import datetime
from typing import Optional, TYPE_CHECKING, List

from simnet import GenshinClient, Region
from simnet.errors import (
    InvalidCookies,
    BadRequest as SimnetBadRequest,
    DataNotPublic,
    AccountNotFound,
    NeedChallenge,
)
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, TelegramObject
from telegram.ext import ConversationHandler, filters
from telegram.helpers import escape_markdown

from core.basemodel import RegionEnum
from core.plugin import Plugin, conversation, handler
from core.services.cookies.error import TooManyRequestPublicCookies, CookiesCachePoolExhausted
from core.services.cookies.services import CookiesService, PublicCookiesService
from core.services.players.models import PlayersDataBase as Player, PlayerInfoSQLModel
from core.services.players.services import PlayersService, PlayerInfoService
from plugins.account.migrate import AccountMigrate
from plugins.tools.genshin import GenshinHelper
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

__all__ = ("BindAccountPlugin",)


class BindAccountPluginData(TelegramObject):
    region: RegionEnum = RegionEnum.HYPERION
    player_id: Optional[int] = None
    nickname: Optional[str] = None

    def reset(self):
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
        helper: GenshinHelper = None,
    ):
        self.public_cookies_service = public_cookies_service
        self.cookies_service = cookies_service
        self.players_service = players_service
        self.player_info_service = player_info_service
        self.helper = helper

    @staticmethod
    async def quit_conversation(update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        context.chat_data.pop("bind_account_plugin_data", None)
        context.chat_data.pop("account_cookies_plugin_data", None)
        await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    @staticmethod
    async def has_another_conversation(update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> Optional[int]:
        if context.chat_data.get("account_cookies_plugin_data") is not None:
            message = update.effective_message
            await message.reply_text("你已经有一个绑定任务在进行中，请先退出后再试")
            return ConversationHandler.END
        return None

    @conversation.fallback
    @handler.command(command="cancel", block=False)
    async def cancel(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        return await self.quit_conversation(update, context)

    @conversation.entry_point
    @handler.command(command="setuid", filters=filters.ChatType.PRIVATE, block=False)
    @handler.command(command="start", filters=filters.ChatType.PRIVATE & filters.Regex("set_uid$"), block=False)
    async def command_start(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 绑定账号命令请求 uid", user.full_name, user.id)
        if await self.has_another_conversation(update, context) is not None:
            return ConversationHandler.END
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
            return await self.quit_conversation(update, context)
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
    async def check_method(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        if message.text == "退出":
            return await self.quit_conversation(update, context)
        if message.text == "通过玩家ID":
            await message.reply_text(
                "请输入你的玩家ID（非通行证ID），此 ID 在 游戏客户端 左/右下角。", reply_markup=ReplyKeyboardRemove()
            )
            return CHECK_PLAYER_ID
        if message.text == "通过账号ID":
            await message.reply_text(
                "请输入你的通行证ID（非玩家ID），此 ID 在 社区APP '我的' 页面。", reply_markup=ReplyKeyboardRemove()
            )
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
            return await self.quit_conversation(update, context)
        try:
            account_id = int(message.text)
        except ValueError:
            await message.reply_text("ID 格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return await self.quit_conversation(update, context)
        try:
            cookies = await self.public_cookies_service.get_cookies(user.id, region)
        except TooManyRequestPublicCookies:
            await message.reply_text("用户查询次数过多，请稍后重试", reply_markup=ReplyKeyboardRemove())
            return await self.quit_conversation(update, context)
        except CookiesCachePoolExhausted:
            await message.reply_text(
                "公共Cookies池已经耗尽，请稍后重试或者绑定 cookie", reply_markup=ReplyKeyboardRemove()
            )
            return await self.quit_conversation(update, context)
        if region == RegionEnum.HYPERION:
            client = GenshinClient(cookies=cookies.data, region=Region.CHINESE)
        elif region == RegionEnum.HOYOLAB:
            client = GenshinClient(cookies=cookies.data, region=Region.OVERSEAS, lang="zh-cn")
        else:
            return await self.quit_conversation(update, context)
        try:
            record_card = await client.get_record_card(account_id)
            if record_card is None:
                await message.reply_text("请在设置展示主界面添加原神", reply_markup=ReplyKeyboardRemove())
                return await self.quit_conversation(update, context)
        except DataNotPublic:
            await message.reply_text("角色未公开", reply_markup=ReplyKeyboardRemove())
            logger.warning("获取账号信息发生错误 %s 账户信息未公开", account_id)
            return await self.quit_conversation(update, context)
        except SimnetBadRequest as exc:
            if exc.ret_code == -10001:
                await message.reply_text("账号所属服务器与选择服务器不符，请检查", reply_markup=ReplyKeyboardRemove())
                return await self.quit_conversation(update, context)
            await message.reply_text("获取账号信息发生错误", reply_markup=ReplyKeyboardRemove())
            logger.error("获取账号信息发生错误")
            logger.exception(exc)
            return await self.quit_conversation(update, context)
        player_info = await self.players_service.get(
            user.id, player_id=record_card.uid, region=bind_account_plugin_data.region
        )
        if player_info:
            await message.reply_text("你已经绑定该账号")
            return await self.quit_conversation(update, context)
        bind_account_plugin_data.account_id = account_id
        reply_keyboard = [["确认", "退出"]]
        await message.reply_text("获取角色基础信息成功，请检查是否正确！")
        logger.info(
            "用户 %s[%s] 获取账号 %s[%s] 信息成功", user.full_name, user.id, record_card.nickname, record_card.uid
        )
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
            return await self.quit_conversation(update, context)
        try:
            player_id = int(message.text)
        except ValueError:
            await message.reply_text("ID 格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return await self.quit_conversation(update, context)
        try:
            async with self.helper.public_genshin(user.id, region=region, uid=player_id) as client:
                player_stats = await client.get_genshin_user(player_id)
        except TooManyRequestPublicCookies:
            await message.reply_text("用户查询次数过多，请稍后重试", reply_markup=ReplyKeyboardRemove())
            return await self.quit_conversation(update, context)
        except AccountNotFound:
            await message.reply_text("找不到用户，uid可能无效", reply_markup=ReplyKeyboardRemove())
            logger.warning("获取账号信息发生错误 %s 找不到用户 uid可能无效", player_id)
            return await self.quit_conversation(update, context)
        except DataNotPublic:
            await message.reply_text("角色未公开", reply_markup=ReplyKeyboardRemove())
            logger.warning("获取账号信息发生错误 %s 账户信息未公开", player_id)
            return await self.quit_conversation(update, context)
        except (InvalidCookies, NeedChallenge):
            await self.public_cookies_service.undo(user.id)
            await message.reply_text("出错了呜呜呜 ~ 请稍后重试或者绑定 cookie")
            return await self.quit_conversation(update, context)
        except SimnetBadRequest as exc:
            if exc.ret_code == -10001:
                await message.reply_text("账号所属服务器与选择服务器不符，请检查", reply_markup=ReplyKeyboardRemove())
                return await self.quit_conversation(update, context)
            await message.reply_text("获取账号信息发生错误", reply_markup=ReplyKeyboardRemove())
            logger.error("获取账号信息发生错误", exc_info=exc)
            return await self.quit_conversation(update, context)
        except ValueError:
            await message.reply_text("ID 格式有误，请检查", reply_markup=ReplyKeyboardRemove())
            return await self.quit_conversation(update, context)
        player_info = await self.players_service.get(
            user.id, player_id=player_id, region=bind_account_plugin_data.region
        )
        if player_info:
            await message.reply_text("你已经绑定该账号")
            return await self.quit_conversation(update, context)
        reply_keyboard = [["确认", "退出"]]
        await message.reply_text("获取角色基础信息成功，请检查是否正确！")
        logger.info(
            "用户 %s[%s] 获取账号 %s[%s] 信息成功", user.full_name, user.id, player_stats.info.nickname, player_id
        )
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

    async def update_player_info(self, player: Player, nickname: str):
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

    @conversation.state(state=COMMAND_RESULT)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def command_result(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        user = update.effective_user
        message = update.effective_message
        bind_account_plugin_data: BindAccountPluginData = context.chat_data.get("bind_account_plugin_data")
        if message.text == "退出":
            return await self.quit_conversation(update, context)
        if message.text == "确认":
            player_id = bind_account_plugin_data.player_id
            nickname = bind_account_plugin_data.nickname
            is_chosen = True
            player_info = await self.players_service.get_player(user.id)  # 寻找主账号
            if player_info is not None and player_info.is_chosen:
                is_chosen = False
            if player_info is not None and player_info.player_id == player_id:
                await message.reply_text("你已经绑定该账号")
                return await self.quit_conversation(update, context)
            player = Player(
                user_id=user.id,
                player_id=player_id,
                region=bind_account_plugin_data.region,
                is_chosen=is_chosen,  # todo 多账号
            )
            await self.players_service.add(player)
            await self.update_player_info(player, nickname)
            logger.success("用户 %s[%s] 绑定UID账号成功", user.full_name, user.id)
            await message.reply_text("保存成功", reply_markup=ReplyKeyboardRemove())
            return await self.quit_conversation(update, context)
        await message.reply_text("回复错误，请重新输入")
        return COMMAND_RESULT

    async def get_migrate_data(
        self, old_user_id: int, new_user_id: int, old_players: List["Player"]
    ) -> Optional[AccountMigrate]:
        return await AccountMigrate.create(
            old_user_id,
            new_user_id,
            old_players,
            self.players_service,
            self.player_info_service,
            self.cookies_service,
        )
