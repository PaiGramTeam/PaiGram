from typing import TYPE_CHECKING, Optional, List

from simnet import GenshinClient, Region
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler
from telegram.helpers import create_deep_linked_url

from core.basemodel import RegionEnum
from core.plugin import Plugin, handler, conversation
from core.services.cookies import CookiesService
from core.services.players.services import PlayersService
from core.services.template.services import TemplateService
from modules.gacha_log.helpers import from_url_get_authkey
from modules.pay_log.error import PayLogNotFound, PayLogAccountNotFound, PayLogInvalidAuthkey, PayLogAuthkeyTimeout
from modules.pay_log.log import PayLog
from modules.pay_log.migrate import PayLogMigrate
from plugins.tools.genshin import PlayerNotFoundError, CookiesNotFoundError
from plugins.tools.player_info import PlayerInfoSystem
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update, User
    from telegram.ext import ContextTypes
    from gram_core.services.players.models import Player


INPUT_URL, CONFIRM_DELETE = range(10100, 10102)


class PayLogPlugin(Plugin.Conversation):
    """充值记录导入/导出/分析"""

    def __init__(
        self,
        template_service: TemplateService,
        players_service: PlayersService,
        cookie_service: CookiesService,
        player_info: PlayerInfoSystem,
    ):
        self.template_service = template_service
        self.players_service = players_service
        self.cookie_service = cookie_service
        self.pay_log = PayLog()
        self.player_info = player_info

    async def get_player_id(self, uid: int) -> int:
        """获取绑定的游戏ID"""
        logger.debug("尝试获取已绑定的原神账号")
        player = await self.players_service.get_player(uid)
        if player is None:
            raise PlayerNotFoundError(uid)
        return player.player_id

    async def _refresh_user_data(self, user: "User", authkey: str = None) -> str:
        """刷新用户数据
        :param user: 用户
        :param authkey: 认证密钥
        :return: 返回信息
        """
        try:
            player_id = await self.get_player_id(user.id)
            new_num = await self.pay_log.get_log_data(user.id, player_id, authkey)
            return "更新完成，本次没有新增数据" if new_num == 0 else f"更新完成，本次共新增{new_num}条充值记录"
        except PayLogNotFound:
            return "派蒙没有找到你的充值记录，快去充值吧~"
        except PayLogAccountNotFound:
            return "导入失败，可能文件包含的祈愿记录所属 uid 与你当前绑定的 uid 不同"
        except PayLogInvalidAuthkey:
            return "更新数据失败，authkey 无效"
        except PayLogAuthkeyTimeout:
            return "更新数据失败，authkey 已经过期"
        except PlayerNotFoundError:
            logger.info("未查询到用户 %s[%s] 所绑定的账号信息", user.full_name, user.id)
            return "派蒙没有找到您所绑定的账号信息，请先私聊派蒙绑定账号"

    @conversation.entry_point
    @handler.command(command="pay_log_import", filters=filters.ChatType.PRIVATE, block=False)
    @handler.message(filters=filters.Regex("^导入充值记录$") & filters.ChatType.PRIVATE, block=False)
    @handler.command(command="start", filters=filters.Regex("pay_log_import$"), block=False)
    async def command_start(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 导入充值记录命令请求", user.full_name, user.id)
        player_info = await self.players_service.get_player(user.id, region=RegionEnum.HYPERION)
        if player_info is not None:
            cookies = await self.cookie_service.get(user.id, account_id=player_info.account_id)
            if cookies is not None:
                if "stoken" in cookies.data:
                    if stuid := next(
                        (value for key, value in cookies.data.items() if key in ["ltuid", "login_uid"]), None
                    ):
                        cookies.data["stuid"] = stuid
                        async with GenshinClient(
                            cookies=cookies.data, region=Region.CHINESE, lang="zh-cn", player_id=player_info.player_id
                        ) as client:
                            authkey = await client.get_authkey_by_stoken("csc")
                else:
                    await message.reply_text("该功能需要绑定 stoken 才能使用")
                    return ConversationHandler.END
            else:
                raise CookiesNotFoundError(user.id)
        else:
            raise CookiesNotFoundError(user.id)
        text = "小派蒙正在从服务器获取数据，请稍后"
        reply = await message.reply_text(text)
        await message.reply_chat_action(ChatAction.TYPING)
        data = await self._refresh_user_data(user, authkey=authkey)
        await reply.edit_text(data)
        return ConversationHandler.END

    @conversation.state(state=INPUT_URL)
    @handler.message(filters=~filters.COMMAND, block=False)
    async def import_data_from_message(self, update: "Update", _: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        user = update.effective_user
        if message.document:
            await message.reply_text("呜呜呜~本次导入不支持文件导入，请尝试获取连接")
            return INPUT_URL
        if not message.text:
            await message.reply_text("呜呜呜~输入错误，请尝试重新获取连接")
            return INPUT_URL
        authkey = from_url_get_authkey(message.text)
        reply = await message.reply_text("小派蒙正在从服务器获取数据，请稍后")
        await message.reply_chat_action(ChatAction.TYPING)
        text = await self._refresh_user_data(user, authkey=authkey)
        await reply.edit_text(text)
        return ConversationHandler.END

    @conversation.entry_point
    @handler(CommandHandler, command="pay_log_delete", filters=filters.ChatType.PRIVATE, block=False)
    @handler(MessageHandler, filters=filters.Regex("^删除充值记录$") & filters.ChatType.PRIVATE, block=False)
    async def command_start_delete(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 删除充值记录命令请求", user.full_name, user.id)
        player_info = await self.players_service.get_player(user.id)
        if player_info is None:
            logger.info("未查询到用户 %s[%s] 所绑定的账号信息", user.full_name, user.id)
            await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号")
            return ConversationHandler.END
        _, status = await self.pay_log.load_history_info(str(user.id), str(player_info.player_id), only_status=True)
        if not status:
            await message.reply_text("你还没有导入充值记录哦~")
            return ConversationHandler.END
        context.chat_data["uid"] = player_info.player_id
        await message.reply_text(
            "你确定要删除充值记录吗？（此项操作无法恢复），如果确定请发送 ”确定“，发送其他内容取消"
        )
        return CONFIRM_DELETE

    @conversation.state(state=CONFIRM_DELETE)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def command_confirm_delete(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> int:
        message = update.effective_message
        user = update.effective_user
        if message.text == "确定":
            status = await self.pay_log.remove_history_info(str(user.id), str(context.chat_data["uid"]))
            await message.reply_text("充值记录已删除" if status else "充值记录删除失败")
            return ConversationHandler.END
        await message.reply_text("已取消")
        return ConversationHandler.END

    @handler(CommandHandler, command="pay_log_force_delete", block=False, admin=True)
    async def command_pay_log_force_delete(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        message = update.effective_message
        args = self.get_args(context)
        if not args:
            await message.reply_text("请指定用户ID")
            return
        try:
            cid = int(args[0])
            if cid < 0:
                raise ValueError("Invalid cid")
            player_info = await self.players_service.get_player(cid)
            if player_info is None:
                await message.reply_text("该用户暂未绑定账号")
                return
            _, status = await self.pay_log.load_history_info(str(cid), str(player_info.player_id), only_status=True)
            if not status:
                await message.reply_text("该用户还没有导入充值记录")
                return
            status = await self.pay_log.remove_history_info(str(cid), str(player_info.player_id))
            await message.reply_text("充值记录已强制删除" if status else "充值记录删除失败")
        except PayLogNotFound:
            await message.reply_text("该用户还没有导入充值记录")
        except (ValueError, IndexError):
            await message.reply_text("用户ID 不合法")

    @handler(CommandHandler, command="pay_log_export", filters=filters.ChatType.PRIVATE, block=False)
    @handler(MessageHandler, filters=filters.Regex("^导出充值记录$") & filters.ChatType.PRIVATE, block=False)
    async def command_start_export(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        message = update.effective_message
        user = update.effective_user
        logger.info("用户 %s[%s] 导出充值记录命令请求", user.full_name, user.id)
        try:
            await message.reply_chat_action(ChatAction.TYPING)
            player_id = await self.get_player_id(user.id)
            path = self.pay_log.get_file_path(str(user.id), str(player_id))
            if not path.exists():
                raise PayLogNotFound
            await message.reply_chat_action(ChatAction.UPLOAD_DOCUMENT)
            await message.reply_document(document=open(path, "rb+"), caption="充值记录导出文件")
        except PayLogNotFound:
            buttons = [
                [InlineKeyboardButton("点我导入", url=create_deep_linked_url(context.bot.username, "pay_log_import"))]
            ]
            await message.reply_text(
                "派蒙没有找到你的充值记录，快来私聊派蒙导入吧~", reply_markup=InlineKeyboardMarkup(buttons)
            )
        except PayLogAccountNotFound:
            await message.reply_text("导出失败，可能文件包含的祈愿记录所属 uid 与你当前绑定的 uid 不同")
        except PlayerNotFoundError:
            logger.info("未查询到用户 %s[%s] 所绑定的账号信息", user.full_name, user.id)
            await message.reply_text("未查询到您所绑定的账号信息，请先绑定账号")

    @handler.command(command="pay_log", player=True, block=False)
    @handler.message(filters=filters.Regex("^充值记录$"), player=True, block=False)
    async def command_start_analysis(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        user_id = await self.get_real_user_id(update)
        message = update.effective_message
        self.log_user(update, logger.info, "充值记录统计命令请求")
        try:
            await message.reply_chat_action(ChatAction.TYPING)
            player_id = await self.get_player_id(user_id)
            data = await self.pay_log.get_analysis(user_id, player_id)
            await message.reply_chat_action(ChatAction.UPLOAD_PHOTO)
            name_card = await self.player_info.get_name_card(player_id, user_id)
            data["name_card"] = name_card
            png_data = await self.template_service.render(
                "genshin/pay_log/pay_log.jinja2", data, full_page=True, query_selector=".container"
            )
            await png_data.reply_photo(message)
        except PayLogNotFound:
            buttons = [
                [InlineKeyboardButton("点我导入", url=create_deep_linked_url(context.bot.username, "pay_log_import"))]
            ]
            await message.reply_text(
                "派蒙没有找到你的充值记录，快来点击按钮私聊派蒙导入吧~", reply_markup=InlineKeyboardMarkup(buttons)
            )

    @staticmethod
    async def get_migrate_data(
        old_user_id: int, new_user_id: int, old_players: List["Player"]
    ) -> Optional[PayLogMigrate]:
        return await PayLogMigrate.create(old_user_id, new_user_id, old_players)
