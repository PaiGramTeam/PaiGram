from typing import TYPE_CHECKING, Union, Optional

from pydantic import ValidationError
from simnet import Region
from simnet.errors import DataNotPublic, BadRequest as SimnetBadRequest
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, KeyboardButton, WebAppInfo
from telegram.ext import CallbackContext, ConversationHandler, filters
from telegram.helpers import escape_markdown

from core.config import config
from core.plugin import Plugin, conversation, handler
from core.services.cookies.services import CookiesService
from core.services.players.services import PlayersService, PlayerInfoService
from plugins.app.webapp import WebApp
from plugins.tools.daily_note import DailyNoteSystem, WebAppData
from plugins.tools.genshin import GenshinHelper
from utils.log import logger

if TYPE_CHECKING:
    from simnet import GenshinClient

__all__ = ("DailyNoteTasksPlugin",)

SET_BY_WEB = 10100


class DailyNoteTasksPlugin(Plugin.Conversation):
    """自动便签提醒任务"""

    def __init__(
        self,
        players_service: PlayersService,
        cookies_service: CookiesService,
        player_info_service: PlayerInfoService,
        helper: GenshinHelper,
        note_system: DailyNoteSystem,
    ):
        self.cookies_service = cookies_service
        self.players_service = players_service
        self.player_info_service = player_info_service
        self.helper = helper
        self.note_system = note_system

    @conversation.entry_point
    @handler.command(command="dailynote_tasks", filters=filters.ChatType.PRIVATE, block=False)
    @handler.command(command="daily_note_tasks", filters=filters.ChatType.PRIVATE, block=False)
    @handler.command(command="start", filters=filters.Regex(r"daily_note_tasks$"), block=False)
    async def command_start(self, update: Update, _: CallbackContext) -> int:
        user_id = await self.get_real_user_id(update)
        uid, offset = self.get_real_uid_or_offset(update)
        message = update.effective_message
        self.log_user(update, logger.info, "设置自动便签提醒命令请求")
        text = await self.check_genshin_user(user_id, uid, offset, False)
        if isinstance(text, str):
            await message.reply_text(text, reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        note_user = await self.note_system.get_single_task_user(user_id, text)
        url = f"{config.pass_challenge_user_web}/tasks1?command=tasks&bot_data={note_user.web_config}"
        text = escape_markdown("请点击下方按钮，开始设置，或者回复退出取消操作")
        await message.reply_markdown_v2(
            text,
            reply_markup=ReplyKeyboardMarkup(
                [
                    [
                        KeyboardButton(
                            text="点我开始设置",
                            web_app=WebAppInfo(url=url),
                        )
                    ],
                    [
                        "退出",
                    ],
                ]
            ),
        )
        return SET_BY_WEB

    async def check_genshin_user(
        self, user_id: int, uid: int, offset: Optional[int], request_note: bool
    ) -> Union[str, int]:
        try:
            async with self.helper.genshin(user_id, player_id=uid, offset=offset) as client:
                client: "GenshinClient"
                if request_note:
                    if client.region == Region.CHINESE:
                        await client.get_genshin_notes_by_stoken()
                    else:
                        await client.get_genshin_notes()
                return client.player_id
        except ValueError:
            return "Cookies 缺少 stoken ，请尝试重新绑定账号。"
        except DataNotPublic:
            return "查询失败惹，可能是便签功能被禁用了？请尝试通过米游社或者 hoyolab 获取一次便签信息后重试。"
        except SimnetBadRequest as e:
            return f"获取便签失败，可能遇到验证码风控，请尝试重新绑定账号。{e}"

    @conversation.state(state=SET_BY_WEB)
    @handler.message(filters=filters.TEXT & ~filters.COMMAND, block=False)
    async def set_by_web_text(self, update: Update, _: CallbackContext) -> int:
        message = update.effective_message
        if message.text == "退出":
            await message.reply_text("退出任务", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        await message.reply_text("输入错误，请重新输入")
        return SET_BY_WEB

    @conversation.state(state=SET_BY_WEB)
    @handler.message(filters=filters.StatusUpdate.WEB_APP_DATA, block=False)
    async def set_by_web(self, update: Update, _: CallbackContext) -> int:
        user = update.effective_user
        message = update.effective_message
        web_app_data = message.web_app_data
        if web_app_data:
            result = WebApp.de_web_app_data(web_app_data.data)
            if result.code == 0:
                if result.path == "tasks":
                    try:
                        validate = WebAppData(**result.data)
                        if validate.user_id != user.id:
                            raise ValidationError(None, None)
                    except ValidationError:
                        await message.reply_text(
                            "数据错误\n树脂提醒数值必须在 60 ~ 200 之间\n洞天宝钱提醒数值必须在 100 ~ 2400 之间\n每日任务提醒时间必须在 0 ~ 23 之间",
                            reply_markup=ReplyKeyboardRemove(),
                        )
                        return ConversationHandler.END
                    need_note = await self.check_genshin_user(validate.user_id, validate.player_id, None, True)
                    if isinstance(need_note, str):
                        await message.reply_text(need_note, reply_markup=ReplyKeyboardRemove())
                        return ConversationHandler.END
                    await self.note_system.import_web_config(validate)
                    await message.reply_text("修改设置成功", reply_markup=ReplyKeyboardRemove())
            else:
                logger.warning(
                    "用户 %s[%s] WEB_APP_DATA 请求错误 [%s]%s", user.full_name, user.id, result.code, result.message
                )
                await message.reply_text(f"WebApp返回错误 {result.message}", reply_markup=ReplyKeyboardRemove())
        else:
            logger.warning("用户 %s[%s] WEB_APP_DATA 非法数据", user.full_name, user.id)
        return ConversationHandler.END
